import os
import sys
import shutil
import asyncio
import logging
from pathlib import Path

# Ensure root and backend directories are in sys.path
_CURRENT_DIR = Path(__file__).resolve().parent
_ROOT_DIR = _CURRENT_DIR.parent
if str(_ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(_ROOT_DIR))
if str(_CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(_CURRENT_DIR))

from typing import List, Optional, Dict, Any
from fastapi import FastAPI, Depends, HTTPException, Query, UploadFile, File, Form, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import or_, desc, func

try:
    import fitz  # PyMuPDF
except (ImportError, Exception):
    fitz = None

try:
    from backend.config import (
        BASE_DIR, FRONTEND_DIR, STATIC_DIR, AUDIO_DIR, PDFS_DIR,
        GEMINI_API_KEY, GEMINI_MODEL, ZOTERO_LIBRARY_ID, ZOTERO_API_KEY,
        ZOTERO_LIBRARY_TYPE, DEFAULT_TTS_VOICE, AVAILABLE_VOICES, IS_SERVERLESS
    )
    from backend.database import init_db, get_db, Paper
    from backend.zotero_sync import ZoteroSyncService
    from backend.processor import (
        PDFProcessor, GeminiSummarizer, AudioSynthesizer,
        parse_briefing_sections, extract_document_chapters
    )
    from backend.conference_scout import ConferenceScoutService
    from backend.academic_engines import (
        ResearchGapService, ReviewerSimulatorService,
        FundingScoutService, IndustryLabService
    )
    from backend.twin_agent import TwinAgentService, PortfolioSyncService
except ImportError:
    from config import (
        BASE_DIR, FRONTEND_DIR, STATIC_DIR, AUDIO_DIR, PDFS_DIR,
        GEMINI_API_KEY, GEMINI_MODEL, ZOTERO_LIBRARY_ID, ZOTERO_API_KEY,
        ZOTERO_LIBRARY_TYPE, DEFAULT_TTS_VOICE, AVAILABLE_VOICES, IS_SERVERLESS
    )
    from database import init_db, get_db, Paper
    from zotero_sync import ZoteroSyncService
    from processor import (
        PDFProcessor, GeminiSummarizer, AudioSynthesizer,
        parse_briefing_sections, extract_document_chapters
    )
    from conference_scout import ConferenceScoutService
    from academic_engines import (
        ResearchGapService, ReviewerSimulatorService,
        FundingScoutService, IndustryLabService
    )
    from twin_agent import TwinAgentService, PortfolioSyncService

logger = logging.getLogger("api")

# Active processing tasks tracking: paper_id -> {"current": int, "total": int, "percent": int, "status": str}
ACTIVE_SYNTHESIS_PROGRESS = {}
ACTIVE_SYNTHESIS_LOCK = set()
logging.basicConfig(level=logging.INFO)

# Initialize database schema safely without crashing serverless cold starts
try:
    init_db()
except Exception as e:
    logger.warning(f"Database initialization warning: {e}")

app = FastAPI(
    title="Zotero Audio Mentor API",
    description="Transforms Zotero reference library research papers into conversational audio briefings.",
    version="1.0.0"
)

# Enable CORS for frontend integrations
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Pydantic Request Schemas
class SyncRequest(BaseModel):
    library_id: Optional[str] = None
    library_type: Optional[str] = "user"
    api_key: Optional[str] = None
    limit: Optional[int] = 25


class ProcessRequest(BaseModel):
    mode: Optional[str] = "summary"  # "summary" or "full_paper"
    voice: Optional[str] = None
    gemini_api_key: Optional[str] = None
    gemini_model: Optional[str] = None
    scope: Optional[str] = "article"  # "article" (complete paper up to References) or "all"


class SwitchModeRequest(BaseModel):
    mode: str  # "summary" or "full_paper"


class SettingsUpdateRequest(BaseModel):
    gemini_api_key: Optional[str] = None
    gemini_model: Optional[str] = None
    zotero_library_id: Optional[str] = None
    zotero_api_key: Optional[str] = None
    zotero_library_type: Optional[str] = None
    default_voice: Optional[str] = None


class ConferenceSearchRequest(BaseModel):
    query: Optional[str] = ""
    year: Optional[int] = None
    doctoral_only: Optional[bool] = False
    grants_only: Optional[bool] = False
    region: Optional[str] = None
    upcoming_only: Optional[bool] = True


class RadarAnalysisRequest(BaseModel):
    topic: str
    idea_proposal: Optional[str] = ""
    target_domain: Optional[str] = "Computer Science"


class ReviewerRequest(BaseModel):
    title: str
    abstract: str
    methodology: Optional[str] = ""
    target_venue: Optional[str] = "NeurIPS / IEEE"


class FundingSearchRequest(BaseModel):
    query: Optional[str] = ""
    research_work: Optional[str] = ""
    destination: Optional[str] = "All"
    category: Optional[str] = "All"


class LabSearchRequest(BaseModel):
    query: Optional[str] = ""
    research_work: Optional[str] = ""
    location: Optional[str] = "All"
    item_type: Optional[str] = "All"


class TwinSyncRequest(BaseModel):
    url: Optional[str] = "https://febmac.vercel.app"


class TwinUpdateRequest(BaseModel):
    custom_notes: Optional[str] = None
    active_focus: Optional[str] = None


class TwinApplyGrantRequest(BaseModel):
    grant_title: str
    grant_details: Optional[Dict[str, Any]] = {}


class TwinApplyLabRequest(BaseModel):
    lab_title: str
    lab_details: Optional[Dict[str, Any]] = {}


class TwinChatRequest(BaseModel):
    message: str
    history: Optional[List[Dict[str, str]]] = []


# Core Pipeline Execution Helper
async def execute_processing_pipeline(
    paper_id: int,
    mode: str = "summary",
    voice: Optional[str] = None,
    gemini_key: Optional[str] = None,
    gemini_model: Optional[str] = None,
    scope: Optional[str] = "article",
    db: Session = None
):
    if paper_id in ACTIVE_SYNTHESIS_LOCK:
        logger.info(f"Paper {paper_id} is already actively synthesizing. Skipping duplicate call.")
        return

    ACTIVE_SYNTHESIS_LOCK.add(paper_id)
    ACTIVE_SYNTHESIS_PROGRESS[paper_id] = {
        "current": 0,
        "total": 1,
        "percent": 0,
        "status": "Starting synthesis...",
        "mode": mode
    }
    """
    Executes either:
    - mode="summary": extraction -> Gemini AI 4-part mentor script -> Edge-TTS synthesis
    - mode="full_paper": extraction -> speech sanitization of full text -> Edge-TTS long synthesis
    """
    close_db_at_end = False
    if db is None:
        try:
            from backend.database import SessionLocal
        except ImportError:
            from database import SessionLocal
        db = SessionLocal()
        close_db_at_end = True

    try:
        paper = db.query(Paper).filter(Paper.id == paper_id).first()
        if not paper:
            logger.error(f"Paper ID {paper_id} not found for processing.")
            return

        paper.status = "Processing"
        paper.error_message = None
        db.commit()

        selected_voice = voice or paper.voice_used or DEFAULT_TTS_VOICE

        if mode == "full_paper":
            # --- 100% VERBATIM FULL PAPER READING PIPELINE ---
            logger.info(f"Processing Paper ID {paper.id} in 100% VERBATIM FULL PAPER mode (no words omitted or replaced)...")
            
            # Extract complete verbatim text with PyMuPDF
            if paper.pdf_path and os.path.exists(paper.pdf_path):
                verbatim_text, total_p = PDFProcessor.extract_verbatim_text(paper.pdf_path, scope=scope or "article")
            else:
                verbatim_text = paper.abstract or paper.title

            cleaned_speech = AudioSynthesizer.prepare_verbatim_for_speech(verbatim_text)
            paper.full_text = verbatim_text
            db.commit()

            def on_progress(current, total):
                pct = int((current / max(1, total)) * 100)
                ACTIVE_SYNTHESIS_PROGRESS[paper_id] = {
                    "current": current,
                    "total": total,
                    "percent": pct,
                    "status": f"Synthesizing audio: Chunk {current}/{total} ({pct}%)",
                    "mode": mode
                }

            audio_filename = f"paper_{paper.id}_full_{paper.zotero_item_key or 'direct'}.mp3"
            audio_path, duration = await AudioSynthesizer.synthesize_long_text_async(
                text=cleaned_speech,
                output_filename=audio_filename,
                voice=selected_voice,
                concurrency=5,
                progress_callback=on_progress
            )

            paper.full_audio_path = f"/api/audio/{audio_filename}"
            paper.full_audio_duration = duration
            paper.audio_path = paper.full_audio_path
            paper.audio_duration = duration
            paper.audio_mode = "full_paper"
            paper.voice_used = selected_voice
            paper.status = "Ready"
            paper.error_message = None
            db.commit()
            logger.info(f"Full verbatim paper audio ready for '{paper.title}' (Duration: {duration}s)")

        else:
            # --- SUMMARY BRIEFING PIPELINE ---
            logger.info(f"Processing Paper ID {paper.id} in SUMMARY BRIEFING mode...")
            # Step 1: Text Extraction for summary
            extracted_text = ""
            if paper.pdf_path and os.path.exists(paper.pdf_path):
                try:
                    extracted_text, _ = PDFProcessor.extract_text(paper.pdf_path, max_pages=25)
                except Exception as e:
                    logger.warning(f"Failed to extract text from PDF {paper.pdf_path}: {e}")
                    extracted_text = paper.abstract or paper.title
            else:
                extracted_text = paper.abstract or paper.title

            summarizer = GeminiSummarizer(
                api_key=gemini_key or os.getenv("GEMINI_API_KEY", GEMINI_API_KEY),
                model=gemini_model or os.getenv("GEMINI_MODEL", GEMINI_MODEL)
            )
            briefing_script = summarizer.generate_briefing(
                title=paper.title,
                text=extracted_text,
                authors=paper.authors,
                abstract=paper.abstract
            )

            # Parse 4 structured sections
            sections = parse_briefing_sections(briefing_script)

            audio_filename = f"paper_{paper.id}_{paper.zotero_item_key or 'direct'}.mp3"
            audio_path, duration = await AudioSynthesizer.synthesize_audio_async(
                text=briefing_script,
                output_filename=audio_filename,
                voice=selected_voice
            )

            paper.summary_text = briefing_script
            paper.summary_problem = sections.get("problem", "")
            paper.summary_methodology = sections.get("methodology", "")
            paper.summary_results = sections.get("results", "")
            paper.summary_limitations = sections.get("limitations", "")
            paper.summary_audio_path = f"/api/audio/{audio_filename}"
            paper.summary_audio_duration = duration
            paper.audio_path = paper.summary_audio_path
            paper.audio_duration = duration
            paper.audio_mode = "summary"
            paper.voice_used = selected_voice
            paper.status = "Ready"
            paper.error_message = None
            db.commit()
            logger.info(f"Summary audio briefing ready for '{paper.title}' (Duration: {duration}s)")

    except Exception as e:
        logger.error(f"Error processing paper {paper_id}: {e}", exc_info=True)
        try:
            db.rollback()
            fresh_paper = db.query(Paper).filter(Paper.id == paper_id).first()
            if fresh_paper:
                fresh_paper.status = "Failed"
                fresh_paper.error_message = str(e)
                db.commit()
        except Exception:
            pass
    finally:
        ACTIVE_SYNTHESIS_LOCK.discard(paper_id)
        ACTIVE_SYNTHESIS_PROGRESS.pop(paper_id, None)
        if close_db_at_end:
            db.close()


# API Endpoints
@app.get("/api/health")
def health_check():
    return {
        "status": "online",
        "service": "Zotero Audio Mentor",
        "version": "1.0.0"
    }


@app.get("/api/voices")
def get_available_voices():
    """Returns supported natural Microsoft Edge neural TTS voices."""
    return {
        "default": DEFAULT_TTS_VOICE,
        "voices": AVAILABLE_VOICES
    }


@app.get("/api/settings")
def get_settings():
    """Returns current environment / API configurations (keys masked)."""
    gemini_key = os.getenv("GEMINI_API_KEY", GEMINI_API_KEY)
    zotero_key = os.getenv("ZOTERO_API_KEY", ZOTERO_API_KEY)
    zotero_lib = os.getenv("ZOTERO_LIBRARY_ID", ZOTERO_LIBRARY_ID)
    zotero_type = os.getenv("ZOTERO_LIBRARY_TYPE", ZOTERO_LIBRARY_TYPE)

    return {
        "has_gemini_key": bool(gemini_key),
        "gemini_key_preview": f"{gemini_key[:4]}...{gemini_key[-4:]}" if len(gemini_key) > 8 else ("Configured" if gemini_key else "Not Set"),
        "gemini_model": os.getenv("GEMINI_MODEL", GEMINI_MODEL),
        "has_zotero_key": bool(zotero_key),
        "zotero_library_id": zotero_lib or "",
        "zotero_library_type": zotero_type or "user",
        "default_voice": DEFAULT_TTS_VOICE,
    }


@app.post("/api/settings/test-zotero")
def test_zotero_connection(req: SyncRequest):
    """Test Zotero credentials without performing a full sync."""
    service = ZoteroSyncService(
        library_id=req.library_id,
        library_type=req.library_type,
        api_key=req.api_key
    )
    result = service.test_connection()
    return result


@app.post("/api/settings/test-gemini")
def test_gemini_connection(payload: Dict[str, str]):
    """Test Gemini API key with a fast ping."""
    key = payload.get("gemini_api_key") or os.getenv("GEMINI_API_KEY", GEMINI_API_KEY)
    if not key:
        return {"success": False, "message": "Gemini API key is not provided."}

    try:
        from google import genai
        client = genai.Client(api_key=key)
        response = client.models.generate_content(
            model=os.getenv("GEMINI_MODEL", GEMINI_MODEL),
            contents="Say 'OK' if you can read this.",
        )
        return {"success": True, "message": f"Connected to Gemini API successfully! Model response: {response.text.strip()}"}
    except Exception as e:
        return {"success": False, "message": f"Gemini API connection error: {str(e)}"}


@app.post("/api/sync")
def sync_zotero(
    req: SyncRequest = SyncRequest(),
    db: Session = Depends(get_db)
):
    """Triggers a sync with Zotero using credentials from request or environment."""
    service = ZoteroSyncService(
        library_id=req.library_id,
        library_type=req.library_type,
        api_key=req.api_key
    )

    if not service.client:
        raise HTTPException(
            status_code=400,
            detail="Zotero credentials missing. Please configure Library ID and API Key in Settings or .env."
        )

    result = service.sync_library(db=db, limit=req.limit or 25)
    return result


@app.get("/api/papers")
def list_papers(
    status: Optional[str] = Query(None, description="Filter by status: Pending, Processing, Ready, Failed"),
    search: Optional[str] = Query(None, description="Search term for title or author"),
    has_pdf: Optional[bool] = Query(None, description="Filter papers having PDF"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """Returns list of ingested papers with summaries, audio paths, and metadata."""
    query = db.query(Paper)

    if status:
        query = query.filter(Paper.status == status)

    if has_pdf is not None:
        query = query.filter(Paper.has_pdf == has_pdf)

    if search:
        search_filter = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Paper.title.ilike(search_filter),
                Paper.authors.ilike(search_filter),
                Paper.abstract.ilike(search_filter),
            )
        )

    total_count = query.count()
    papers = query.order_by(desc(Paper.created_at)).offset(offset).limit(limit).all()

    # Fast SQL aggregate metrics (sub-millisecond)
    ready_count = db.query(Paper).filter(Paper.status == "Ready").count()
    total_audio_seconds = db.query(func.coalesce(func.sum(Paper.audio_duration), 0.0)).filter(Paper.status == "Ready").scalar() or 0.0

    paper_list = []
    for p in papers:
        # include_full_text=False for ultra-fast, lightweight listing payloads (<3KB vs 300KB)
        p_dict = p.to_dict(include_full_text=False)
        if p.id in ACTIVE_SYNTHESIS_PROGRESS:
            p_dict["synthesis_progress"] = ACTIVE_SYNTHESIS_PROGRESS[p.id]
        paper_list.append(p_dict)

    return {
        "total": total_count,
        "ready_count": ready_count,
        "total_audio_minutes": round(total_audio_seconds / 60.0, 1),
        "papers": paper_list
    }


@app.get("/api/papers/{paper_id}")
def get_paper(paper_id: int, db: Session = Depends(get_db)):
    """Retrieve detailed record for a specific paper."""
    paper = db.query(Paper).filter(Paper.id == paper_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    # Auto-extract full verbatim text on-demand in milliseconds if not yet cached
    if (not paper.full_text or not paper.full_text.strip()):
        if paper.pdf_path and os.path.exists(paper.pdf_path):
            try:
                verbatim_text, _ = PDFProcessor.extract_verbatim_text(paper.pdf_path)
                paper.full_text = verbatim_text
                db.commit()
                db.refresh(paper)
            except Exception as e:
                logger.warning(f"Error auto-extracting text on get_paper: {e}")
        elif paper.abstract:
            paper.full_text = paper.abstract
            db.commit()
            db.refresh(paper)

    d = paper.to_dict()
    d["chapters"] = extract_document_chapters(paper)
    if paper.id in ACTIVE_SYNTHESIS_PROGRESS:
        d["synthesis_progress"] = ACTIVE_SYNTHESIS_PROGRESS[paper.id]
    return d


@app.get("/api/papers/{paper_id}/chapters")
def get_paper_chapters(paper_id: int, db: Session = Depends(get_db)):
    """Extracts navigation chapters and timestamps for seeking specific parts of the audio."""
    paper = db.query(Paper).filter(Paper.id == paper_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")
    return extract_document_chapters(paper)


@app.post("/api/papers/{paper_id}/extract-text")
def extract_paper_text(paper_id: int, db: Session = Depends(get_db)):
    """Instantly extracts full verbatim text from paper's PDF in milliseconds without audio synthesis."""
    paper = db.query(Paper).filter(Paper.id == paper_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    if paper.pdf_path and os.path.exists(paper.pdf_path):
        verbatim_text, total_pages = PDFProcessor.extract_verbatim_text(paper.pdf_path)
        paper.full_text = verbatim_text
        db.commit()
        db.refresh(paper)
        return {
            "success": True,
            "message": f"Extracted {len(verbatim_text)} characters across {total_pages} pages.",
            "full_text": verbatim_text,
            "total_pages": total_pages,
            "words": len(verbatim_text.split())
        }
    elif paper.abstract:
        paper.full_text = paper.abstract
        db.commit()
        db.refresh(paper)
        return {
            "success": True,
            "message": "Used abstract as full text (no attached PDF).",
            "full_text": paper.abstract,
            "total_pages": 1,
            "words": len(paper.abstract.split())
        }
    else:
        raise HTTPException(status_code=400, detail="No PDF file or abstract available for text extraction.")


@app.post("/api/process/{item_key_or_id}")
async def process_paper(
    item_key_or_id: str,
    req: ProcessRequest = ProcessRequest(),
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db)
):
    """
    Triggers pipeline for a paper:
    - mode="summary": Extract -> Gemini 4-part mentor briefing -> Edge-TTS Audio -> Update DB
    - mode="full_paper": Extract -> Clean full paper text -> Edge-TTS Full Audio -> Update DB
    Accepts either database paper id or Zotero item key.
    """
    paper = None
    if item_key_or_id.isdigit():
        paper = db.query(Paper).filter(Paper.id == int(item_key_or_id)).first()

    if not paper:
        paper = db.query(Paper).filter(Paper.zotero_item_key == item_key_or_id).first()

    if not paper:
        raise HTTPException(status_code=404, detail=f"Paper '{item_key_or_id}' not found.")

    target_mode = req.mode or "summary"
    paper.status = "Processing"
    paper.error_message = None
    db.commit()

    # Launch processing in background task to avoid client timeouts on long full papers
    async def run_pipeline():
        try:
            from backend.database import SessionLocal
        except ImportError:
            from database import SessionLocal
        bg_db = SessionLocal()
        try:
            await execute_processing_pipeline(
                paper_id=paper.id,
                mode=target_mode,
                voice=req.voice,
                gemini_key=req.gemini_api_key,
                gemini_model=req.gemini_model,
                scope=req.scope or "article",
                db=bg_db
            )
        except Exception as err:
            logger.error(f"Background pipeline failed for paper {paper.id}: {err}", exc_info=True)
        finally:
            bg_db.close()

    asyncio.create_task(run_pipeline())

    return {
        "success": True,
        "message": f"Processing ({target_mode}) started in background.",
        "paper": paper.to_dict()
    }


@app.post("/api/process-batch")
async def process_batch_papers(
    req: ProcessRequest = ProcessRequest(),
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db)
):
    """Processes all pending papers sequentially in the background."""
    pending_papers = db.query(Paper).filter(Paper.status == "Pending").all()
    if not pending_papers:
        return {"success": True, "message": "No pending papers to process.", "count": 0}

    target_mode = req.mode or "summary"
    # Queue background execution
    for paper in pending_papers:
        await execute_processing_pipeline(
            paper_id=paper.id,
            mode=target_mode,
            voice=req.voice,
            gemini_key=req.gemini_api_key,
            gemini_model=req.gemini_model,
            db=db
        )

    return {
        "success": True,
        "message": f"Triggered processing for {len(pending_papers)} pending papers in '{target_mode}' mode.",
        "count": len(pending_papers)
    }


@app.post("/api/papers/{paper_id}/switch-mode")
def switch_paper_mode(paper_id: int, req: SwitchModeRequest, db: Session = Depends(get_db)):
    """Switches the active audio track for a paper between 'summary' and 'full_paper'."""
    paper = db.query(Paper).filter(Paper.id == paper_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    target_mode = (req.mode or "summary").lower()
    if target_mode not in ["summary", "full_paper"]:
        raise HTTPException(status_code=400, detail="Invalid mode. Must be 'summary' or 'full_paper'.")

    if target_mode == "summary":
        has_summary = bool(paper.summary_audio_path or (paper.audio_path and paper.audio_mode == "summary"))
        if not has_summary:
            return {
                "success": False,
                "needs_generation": True,
                "message": "Summary audio briefing has not been generated yet for this paper."
            }
        paper.audio_mode = "summary"
        if paper.summary_audio_path:
            paper.audio_path = paper.summary_audio_path
            paper.audio_duration = paper.summary_audio_duration or 0.0
        db.commit()
        return {"success": True, "paper": paper.to_dict()}

    elif target_mode == "full_paper":
        has_full = bool(paper.full_audio_path or (paper.audio_path and paper.audio_mode == "full_paper"))
        if not has_full:
            return {
                "success": False,
                "needs_generation": True,
                "message": "Full paper audio reading has not been generated yet for this paper."
            }
        paper.audio_mode = "full_paper"
        if paper.full_audio_path:
            paper.audio_path = paper.full_audio_path
            paper.audio_duration = paper.full_audio_duration or 0.0
        db.commit()
        return {"success": True, "paper": paper.to_dict()}


@app.post("/api/upload")
async def upload_pdf(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    authors: Optional[str] = Form(None),
    auto_process: bool = Form(False),
    mode: Optional[str] = Form("summary"),
    voice: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """Directly upload a research PDF file without requiring Zotero setup."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    import uuid
    file_id = f"upload_{uuid.uuid4().hex[:8]}"
    saved_filename = f"{file_id}_{file.filename}"
    target_path = PDFS_DIR / saved_filename

    with open(target_path, "wb") as buffer:
        while chunk := await file.read(1024 * 1024):
            buffer.write(chunk)

    # Inspect PDF metadata or first page to infer title if not provided
    doc_title = title
    doc_authors = authors or "Uploaded Researcher"
    abstract_preview = ""

    try:
        doc = fitz.open(target_path)
        meta = doc.metadata or {}
        if not doc_title:
            doc_title = meta.get("title") or file.filename.replace(".pdf", "").replace("_", " ").title()
        if not authors and meta.get("author"):
            doc_authors = meta.get("author")

        # Grab first 800 chars for preview
        if len(doc) > 0:
            first_page_text = doc[0].get_text("text")
            abstract_preview = first_page_text[:1200].strip()
        doc.close()
    except Exception as e:
        logger.warning(f"Could not read PDF metadata: {e}")
        if not doc_title:
            doc_title = file.filename.replace(".pdf", "").replace("_", " ").title()

    # Extract complete verbatim text immediately upon upload (takes ~0.1-0.2s)
    full_verbatim_text = ""
    try:
        full_verbatim_text, _ = PDFProcessor.extract_verbatim_text(target_path)
    except Exception as e:
        logger.warning(f"Could not extract verbatim text upon upload: {e}")

    initial_status = "Processing" if auto_process else "Pending"
    paper = Paper(
        zotero_item_key=file_id,
        title=doc_title,
        authors=doc_authors,
        abstract=abstract_preview,
        full_text=full_verbatim_text or abstract_preview,
        pdf_path=str(target_path),
        has_pdf=True,
        status=initial_status,
        publication_year=str(import_year := 2026)
    )
    db.add(paper)
    db.commit()
    db.refresh(paper)

    # Launch processing asynchronously in background to ensure upload responds in milliseconds
    if auto_process:
        asyncio.create_task(
            execute_processing_pipeline(
                paper_id=paper.id,
                mode=mode or "summary",
                voice=voice or DEFAULT_TTS_VOICE
            )
        )

    return {
        "success": True,
        "message": f"Successfully uploaded '{doc_title}'.",
        "paper": paper.to_dict()
    }


@app.post("/api/sample-papers")
async def load_sample_papers(db: Session = Depends(get_db)):
    """Populates the database with benchmark AI research papers for immediate out-of-the-box demoing."""
    samples = [
        {
            "zotero_item_key": "ATTN_2017",
            "title": "Attention Is All You Need",
            "authors": "Ashish Vaswani, Noam Shazeer, Niki Parmar, Jakob Uszkoreit, Llion Jones, Aidan N. Gomez, Łukasz Kaiser, Illia Polosukhin",
            "publication_year": "2017",
            "journal": "Advances in Neural Information Processing Systems (NeurIPS)",
            "abstract": "The dominant sequence transduction models are based on complex recurrent or convolutional neural networks that include an encoder and a decoder. The best performing models also connect the encoder and decoder through an attention mechanism. We propose a new simple network architecture, the Transformer, based solely on attention mechanisms, dispensing with recurrence and convolutions entirely. Experiments on two machine translation tasks show these models to be superior in quality while being more parallelizable and requiring significantly less time to train."
        },
        {
            "zotero_item_key": "LORA_2021",
            "title": "LoRA: Low-Rank Adaptation of Large Language Models",
            "authors": "Edward J. Hu, Yelong Shen, Phillip Wallis, Zeyuan Allen-Zhu, Yuanzhi Li, Shean Wang, Lu Wang, Weizhu Chen",
            "publication_year": "2021",
            "journal": "International Conference on Learning Representations (ICLR)",
            "abstract": "An important paradigm of natural language processing consists of large-scale pre-training on general domain data and adaptation to specific tasks. As we pre-train larger models, full fine-tuning becomes increasingly infeasible. We propose Low-Rank Adaptation (LoRA), which freezes the pre-trained model weights and injects trainable rank decomposition matrices into each layer of the Transformer architecture, greatly reducing the number of trainable parameters for downstream tasks. Compared to fine-tuning of GPT-3 175B with Adam, LoRA can reduce the number of trainable parameters by 10,000 times and the GPU memory requirement by 3 times."
        },
        {
            "zotero_item_key": "RAG_2020",
            "title": "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks",
            "authors": "Patrick Lewis, Ethan Perez, Aleksandra Piktus, Fabio Petroni, Vladimir Karpukhin, Naman Goyal, Heinrich Küttler, Mike Lewis, Wen-tau Yih, Tim Rocktäschel, Sebastian Riedel, Douwe Kiela",
            "publication_year": "2020",
            "journal": "Advances in Neural Information Processing Systems (NeurIPS)",
            "abstract": "Large pre-trained language models have been shown to store factual knowledge in their parameters, and achieve state-of-the-art results when fine-tuned on downstream NLP tasks. However, their ability to precisely access and manipulate knowledge is still limited. We explore a general-purpose fine-tuning recipe for retrieval-augmented generation (RAG)—models which combine pre-trained parametric and non-parametric memory for language generation. We introduce RAG models where the parametric memory is a pre-trained seq2seq model and the non-parametric memory is a dense vector index of Wikipedia, accessed with a pre-trained neural retriever."
        },
        {
            "zotero_item_key": "DPO_2023",
            "title": "Direct Preference Optimization: Your Language Model is Secretly a Reward Model",
            "authors": "Rafael Rafailov, Archit Sharma, Eric Mitchell, Stefano Ermon, Christopher D. Manning, Chelsea Finn",
            "publication_year": "2023",
            "journal": "Advances in Neural Information Processing Systems (NeurIPS)",
            "abstract": "While large-scale language models can learn broad general knowledge, controlling their behavior via human feedback is crucial. Existing techniques use Reinforcement Learning from Human Feedback (RLHF), which fits a reward model to a dataset of human preferences and then optimizes a policy via RL algorithms like PPO. However, RLHF is complex and unstable. We propose Direct Preference Optimization (DPO), a mathematically principled algorithm that optimizes policy directly from preference data without training a separate reward model or sampling from the LM during fine-tuning."
        }
    ]

    added = 0
    for s in samples:
        existing = db.query(Paper).filter(Paper.zotero_item_key == s["zotero_item_key"]).first()
        if not existing:
            p = Paper(
                zotero_item_key=s["zotero_item_key"],
                title=s["title"],
                authors=s["authors"],
                publication_year=s["publication_year"],
                journal=s["journal"],
                abstract=s["abstract"],
                status="Pending",
                has_pdf=False
            )
            db.add(p)
            added += 1

    db.commit()
    return {
        "success": True,
        "message": f"Loaded {added} benchmark research papers into your library.",
        "total_samples": len(samples)
    }


@app.delete("/api/papers/{paper_id}")
def delete_paper(paper_id: int, db: Session = Depends(get_db)):
    """Delete a paper record and its associated audio/PDF files."""
    paper = db.query(Paper).filter(Paper.id == paper_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    # Delete audio files if exist
    audio_paths_to_remove = set(filter(None, [paper.audio_path, paper.summary_audio_path, paper.full_audio_path]))
    for a_path in audio_paths_to_remove:
        filename = a_path.split("/")[-1]
        audio_file = AUDIO_DIR / filename
        if audio_file.exists():
            try:
                audio_file.unlink()
            except Exception as e:
                logger.warning(f"Could not remove audio file {audio_file}: {e}")

    # Delete PDF file if it was a local download/upload
    if paper.pdf_path and os.path.exists(paper.pdf_path):
        try:
            Path(paper.pdf_path).unlink()
        except Exception as e:
            logger.warning(f"Could not remove PDF file {paper.pdf_path}: {e}")

    db.delete(paper)
    db.commit()
    return {"success": True, "message": f"Paper '{paper.title}' deleted."}


@app.get("/api/audio/{filename}")
def stream_audio(filename: str):
    """Streams generated MP3 audio files with support for HTTP Range requests."""
    audio_path = AUDIO_DIR / filename
    if not audio_path.exists():
        raise HTTPException(status_code=404, detail=f"Audio file '{filename}' not found.")

    return FileResponse(
        path=str(audio_path),
        media_type="audio/mpeg",
        filename=filename,
        headers={"Accept-Ranges": "bytes"}
    )


@app.get("/api/papers/{paper_id}/figures")
def get_paper_figures(paper_id: int, db: Session = Depends(get_db)):
    """Extracts and returns list of diagrams, figures, and charts from the paper's PDF."""
    paper = db.query(Paper).filter(Paper.id == paper_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    if not paper.pdf_path or not os.path.exists(paper.pdf_path):
        return {"figures": [], "count": 0, "has_pdf": False}

    figures = PDFProcessor.extract_figures(paper.pdf_path, paper.id)
    return {
        "figures": figures,
        "count": len(figures),
        "has_pdf": True
    }


@app.get("/api/papers/{paper_id}/pdf")
def stream_paper_pdf(paper_id: int, db: Session = Depends(get_db)):
    """Streams paper PDF by paper ID with inline disposition."""
    paper = db.query(Paper).filter(Paper.id == paper_id).first()
    if not paper or not paper.pdf_path or not os.path.exists(paper.pdf_path):
        raise HTTPException(status_code=404, detail="Paper PDF not found")
    filename = os.path.basename(paper.pdf_path)
    return FileResponse(
        path=paper.pdf_path,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"inline; filename=\"{filename}\"",
            "Accept-Ranges": "bytes"
        }
    )


@app.get("/api/pdf/{filename}")
def stream_pdf(filename: str):
    """Streams PDF files with inline disposition for seamless iframe and tab viewing."""
    pdf_path = PDFS_DIR / filename
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail=f"PDF file '{filename}' not found.")

    return FileResponse(
        path=str(pdf_path),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"inline; filename=\"{filename}\"",
            "Accept-Ranges": "bytes"
        }
    )


@app.post("/api/conferences/search")
def search_conferences(payload: ConferenceSearchRequest):
    """Intelligent conference and academic event scout for PhD researchers."""
    scout = ConferenceScoutService(api_key=GEMINI_API_KEY, model=GEMINI_MODEL)
    return scout.search(
        query=payload.query or "",
        year=payload.year,
        doctoral_only=bool(payload.doctoral_only),
        grants_only=bool(payload.grants_only),
        region=payload.region,
        upcoming_only=payload.upcoming_only if payload.upcoming_only is not None else True
    )


@app.get("/api/conferences/featured")
def get_featured_conferences():
    """Returns top curated academic conferences with active doctoral consortiums."""
    scout = ConferenceScoutService(api_key=GEMINI_API_KEY, model=GEMINI_MODEL)
    return scout.search(query="", upcoming_only=True)


# =====================================================================
# ENGINE 3: RESEARCH GAP & NOVELTY RADAR ENDPOINTS
# =====================================================================
@app.post("/api/radar/analyze")
def analyze_research_gap(payload: RadarAnalysisRequest):
    """Audits literature, calculates novelty index, and surfaces unsolved research gaps."""
    service = ResearchGapService(api_key=GEMINI_API_KEY, model=GEMINI_MODEL)
    return service.analyze_gap(
        topic=payload.topic,
        idea_proposal=payload.idea_proposal or "",
        target_domain=payload.target_domain or "Computer Science"
    )


@app.post("/api/radar/upload-pdf")
async def upload_pdf_for_radar(
    file: UploadFile = File(...),
    target_domain: Optional[str] = Form("Computer Science")
):
    """Extracts topic and proposed methodology from an uploaded proposal or paper PDF and runs novelty gap radar."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")
    
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    full_text = ""
    total_pages = 0
    extracted_title = ""
    
    try:
        if fitz is not None:
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            total_pages = len(doc)
            meta = doc.metadata or {}
            extracted_title = meta.get("title") or ""
            text_parts = []
            for page in doc:
                text_parts.append(page.get_text("text"))
            full_text = "\n\n".join(text_parts).strip()
            doc.close()
    except Exception as e:
        logger.warning(f"Error extracting PDF text for radar: {e}")

    if not full_text:
        import uuid
        temp_path = PDFS_DIR / f"radar_{uuid.uuid4().hex[:8]}_{file.filename}"
        try:
            with open(temp_path, "wb") as f:
                f.write(file_bytes)
            full_text, total_pages = PDFProcessor.extract_verbatim_text(temp_path)
        except Exception as e:
            logger.warning(f"Fallback extraction failed: {e}")
        finally:
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except Exception:
                    pass

    if not full_text:
        raise HTTPException(status_code=400, detail="Could not extract readable text from the uploaded PDF.")

    service = ResearchGapService(api_key=GEMINI_API_KEY, model=GEMINI_MODEL)
    result = service.analyze_from_pdf_text(pdf_text=full_text, filename=file.filename, domain=target_domain or "Computer Science")
    return {
        "success": True,
        "filename": file.filename,
        "total_pages": total_pages,
        "word_count": len(full_text.split()),
        "radar": result
    }


# =====================================================================
# ENGINE 4: AI "REVIEWER #2" SIMULATOR ENDPOINTS
# =====================================================================
@app.post("/api/reviewer/simulate")
def simulate_reviewer_two(payload: ReviewerRequest):
    """Simulates a ruthless Tier-1 peer reviewer critique on draft papers."""
    service = ReviewerSimulatorService(api_key=GEMINI_API_KEY, model=GEMINI_MODEL)
    return service.review_paper(
        title=payload.title,
        abstract=payload.abstract,
        methodology=payload.methodology or "",
        target_venue=payload.target_venue or "NeurIPS / IEEE"
    )


@app.post("/api/reviewer/upload-pdf")
async def upload_pdf_for_reviewer(
    file: UploadFile = File(...),
    target_venue: Optional[str] = Form("NeurIPS / IEEE")
):
    """Audits an uploaded PDF manuscript draft, extracting sections, evaluating methodology, and generating publication improvements."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")
    
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    full_text = ""
    total_pages = 0
    extracted_title = ""
    
    try:
        if fitz is not None:
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            total_pages = len(doc)
            meta = doc.metadata or {}
            extracted_title = meta.get("title") or ""
            text_parts = []
            for page in doc:
                text_parts.append(page.get_text("text"))
            full_text = "\n\n".join(text_parts).strip()
            doc.close()
    except Exception as e:
        logger.warning(f"Error extracting PDF text for reviewer: {e}")

    if not full_text:
        import uuid
        temp_path = PDFS_DIR / f"rev_{uuid.uuid4().hex[:8]}_{file.filename}"
        try:
            with open(temp_path, "wb") as f:
                f.write(file_bytes)
            full_text, total_pages = PDFProcessor.extract_verbatim_text(temp_path)
        except Exception as e:
            logger.warning(f"Fallback extraction failed: {e}")
        finally:
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except Exception:
                    pass

    if not full_text:
        raise HTTPException(status_code=400, detail="Could not extract readable text from the uploaded PDF.")

    if not extracted_title:
        extracted_title = file.filename.replace(".pdf", "").replace("_", " ").title()

    service = ReviewerSimulatorService(api_key=GEMINI_API_KEY, model=GEMINI_MODEL)
    result = service.review_full_manuscript(full_text=full_text, title=extracted_title, target_venue=target_venue or "NeurIPS / IEEE")
    return {
        "success": True,
        "filename": file.filename,
        "total_pages": total_pages,
        "word_count": len(full_text.split()),
        "review": result
    }


# =====================================================================
# ENGINE 5: FELLOWSHIP, TRAVEL GRANT & FUNDING RADAR ENDPOINTS
# =====================================================================
@app.get("/api/grants/search")
def get_grants(
    query: Optional[str] = "",
    research_work: Optional[str] = "",
    destination: Optional[str] = "All",
    category: Optional[str] = "All"
):
    """Returns doctoral fellowships and student conference travel grants matched by topic and destination."""
    service = FundingScoutService(api_key=GEMINI_API_KEY, model=GEMINI_MODEL)
    return service.search_funding(
        query=query or "",
        research_work=research_work or "",
        destination=destination or "All",
        category=category or "All"
    )


@app.post("/api/grants/search")
def post_grants(payload: FundingSearchRequest):
    """Searches doctoral fellowships and travel grants with live AI expansion."""
    service = FundingScoutService(api_key=GEMINI_API_KEY, model=GEMINI_MODEL)
    return service.search_funding(
        query=payload.query or "",
        research_work=payload.research_work or "",
        destination=payload.destination or "All",
        category=payload.category or "All"
    )


# =====================================================================
# ENGINE 6: TECH SUMMIT & INDUSTRY LAB CONNECTOR ENDPOINTS
# =====================================================================
@app.get("/api/labs/search")
def get_labs(
    query: Optional[str] = "",
    research_work: Optional[str] = "",
    location: Optional[str] = "All",
    item_type: Optional[str] = "All"
):
    """Returns research scientist internships and global tech expos matched by field and preferred location."""
    service = IndustryLabService(api_key=GEMINI_API_KEY, model=GEMINI_MODEL)
    return service.search_labs(
        query=query or "",
        research_work=research_work or "",
        location=location or "All",
        item_type=item_type or "All"
    )


@app.post("/api/labs/search")
def post_labs(payload: LabSearchRequest):
    """Searches research scientist internships and tech summits with live AI expansion."""
    service = IndustryLabService(api_key=GEMINI_API_KEY, model=GEMINI_MODEL)
    return service.search_labs(
        query=payload.query or "",
        research_work=payload.research_work or "",
        location=payload.location or "All",
        item_type=payload.item_type or "All"
    )


# =====================================================================
# ENGINE 7: AUTONOMOUS PHD DIGITAL TWIN & EXECUTIVE CO-PILOT ENDPOINTS
# =====================================================================
@app.get("/api/twin/profile")
def get_twin_profile():
    """Returns Mark Febiri's digital twin knowledge base, synced with febmac.vercel.app."""
    service = TwinAgentService(api_key=GEMINI_API_KEY, model=GEMINI_MODEL)
    return service.get_profile()


@app.post("/api/twin/sync")
def sync_twin_portfolio(payload: TwinSyncRequest = TwinSyncRequest()):
    """Live re-crawls Mark Febiri's portfolio website to refresh profile knowledge."""
    return PortfolioSyncService.live_sync(base_url=payload.url or "https://febmac.vercel.app")


@app.post("/api/twin/update-profile")
def update_twin_profile(payload: TwinUpdateRequest):
    """Updates custom research notes or active focus for the Digital Twin."""
    service = TwinAgentService(api_key=GEMINI_API_KEY, model=GEMINI_MODEL)
    return service.update_profile(custom_notes=payload.custom_notes, active_focus=payload.active_focus)


@app.post("/api/twin/apply-grant")
def twin_apply_grant(payload: TwinApplyGrantRequest):
    """Autonomous drafter: creates complete grant/fellowship dossier on Mark's behalf."""
    service = TwinAgentService(api_key=GEMINI_API_KEY, model=GEMINI_MODEL)
    return service.apply_for_grant(grant_title=payload.grant_title, grant_details=payload.grant_details or {})


@app.post("/api/twin/apply-lab")
def twin_apply_lab(payload: TwinApplyLabRequest):
    """Autonomous drafter: creates complete research lab internship pitch & cold email on Mark's behalf."""
    service = TwinAgentService(api_key=GEMINI_API_KEY, model=GEMINI_MODEL)
    return service.apply_for_lab(lab_title=payload.lab_title, lab_details=payload.lab_details or {})


@app.get("/api/twin/suggestions")
def get_twin_suggestions():
    """Proactive strategic advisor: returns prioritized actions Mark should take over the next 14-60 days."""
    service = TwinAgentService(api_key=GEMINI_API_KEY, model=GEMINI_MODEL)
    return service.get_strategic_suggestions()


@app.post("/api/twin/chat")
def chat_with_twin(payload: TwinChatRequest):
    """Interactive chat with Mark Febiri's perfectionist digital twin."""
    service = TwinAgentService(api_key=GEMINI_API_KEY, model=GEMINI_MODEL)
    response_text = service.chat_with_twin(user_message=payload.message, chat_history=payload.history or [])
    return {"reply": response_text}


@app.get("/api/health")
def api_health():
    """Health check endpoint to test runtime status."""
    return {
        "status": "healthy",
        "service": "febPhD",
        "serverless": IS_SERVERLESS,
        "database": "connected"
    }


# Safely mount static directory if it exists, without crashing if directory is missing
try:
    if not STATIC_DIR.exists():
        STATIC_DIR.mkdir(parents=True, exist_ok=True)
    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
except Exception as e:
    logger.warning(f"Static directory could not be mounted: {e}")


def _load_html(filename: str) -> Optional[str]:
    """Search multiple paths for frontend templates and load string content."""
    candidates = [
        FRONTEND_DIR / filename,
        BASE_DIR / "frontend" / filename,
        Path.cwd() / "frontend" / filename,
        Path(__file__).resolve().parent.parent / "frontend" / filename,
    ]
    for p in candidates:
        if p.exists():
            try:
                return p.read_text(encoding="utf-8")
            except Exception:
                pass
    return None


@app.get("/favicon.ico", include_in_schema=False)
def get_favicon():
    favicon_path = STATIC_DIR / "favicon.ico"
    if favicon_path.exists():
        return FileResponse(str(favicon_path), media_type="image/x-icon")
    raise HTTPException(status_code=404, detail="Favicon not found")


# Serve modern white Home page
@app.get("/")
def serve_home():
    content = _load_html("home.html")
    if content:
        return HTMLResponse(content=content)
    return serve_app()


# Serve Intelligent Academic Conference & Event Scout standalone page
@app.get("/conferences")
@app.get("/conferences/")
@app.get("/scout")
@app.get("/events")
def serve_conferences():
    content = _load_html("conferences.html")
    if content:
        return HTMLResponse(content=content)
    return serve_home()


# Serve Zotero Audio Mentor workspace
@app.get("/app")
@app.get("/app/")
@app.get("/library")
@app.get("/reader")
def serve_app():
    content = _load_html("index.html")
    if content:
        return HTMLResponse(content=content)
    return JSONResponse(
        status_code=404,
        content={"message": "Frontend index.html not found. Ensure frontend directory is populated."}
    )


# Serve Engine 03: Research Gap & Novelty Radar
@app.get("/radar")
@app.get("/radar/")
@app.get("/novelty")
def serve_radar():
    content = _load_html("radar.html")
    if content:
        return HTMLResponse(content=content)
    return serve_home()


# Serve Engine 04: AI "Reviewer #2" Harsh Peer-Review Simulator
@app.get("/reviewer")
@app.get("/reviewer/")
@app.get("/peer-review")
def serve_reviewer():
    content = _load_html("reviewer.html")
    if content:
        return HTMLResponse(content=content)
    return serve_home()


# Serve Engine 05: Fellowship, Travel Grant & Funding Radar
@app.get("/grants")
@app.get("/grants/")
@app.get("/funding")
@app.get("/fellowships")
def serve_grants():
    content = _load_html("grants.html")
    if content:
        return HTMLResponse(content=content)
    return serve_home()


# Serve Engine 06: Tech Summit & Industry Research Lab Connector
@app.get("/lab-connector")
@app.get("/lab-connector/")
@app.get("/labs")
@app.get("/labs/")
@app.get("/careers")
@app.get("/summits")
def serve_lab_connector():
    content = _load_html("lab_connector.html")
    if content:
        return HTMLResponse(content=content)
    return serve_home()


# Serve Engine 07: Autonomous PhD Digital Twin & Executive Co-Pilot Studio
@app.get("/agent")
@app.get("/agent/")
@app.get("/twin")
@app.get("/copilot")
def serve_agent():
    content = _load_html("agent.html")
    if content:
        return HTMLResponse(content=content)
    return serve_home()
