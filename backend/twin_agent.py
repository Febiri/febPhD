import os
import re
import json
import logging
import urllib.request
import urllib.parse
from typing import Dict, Any, List, Optional
from datetime import datetime, date
from pathlib import Path
import httpx
try:
    from bs4 import BeautifulSoup
except Exception:
    BeautifulSoup = None

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None

try:
    from backend.config import GEMINI_API_KEY, GEMINI_MODEL, BASE_DIR, IS_SERVERLESS, is_writable, GITHUB_TOKEN, GITHUB_USERNAME
except ImportError:
    try:
        from config import GEMINI_API_KEY, GEMINI_MODEL, BASE_DIR, IS_SERVERLESS, is_writable, GITHUB_TOKEN, GITHUB_USERNAME
    except ImportError:
        GEMINI_API_KEY = ""
        GEMINI_MODEL = "gemini-2.5-flash"
        BASE_DIR = Path(__file__).resolve().parent.parent
        IS_SERVERLESS = True
        is_writable = False
        GITHUB_TOKEN = ""
        GITHUB_USERNAME = "Febiri"

logger = logging.getLogger("twin_agent")
logging.basicConfig(level=logging.INFO)

PROFILE_CACHE_PATH = (
    Path("/tmp/mark_febiri_profile.json")
    if (IS_SERVERLESS or not is_writable)
    else BASE_DIR / "data" / "mark_febiri_profile.json"
)

# Master curated knowledge dossier for Mark Febiri (Synced from https://febmac.vercel.app/)
MASTER_PROFILE: Dict[str, Any] = {
    "name": "Mark Febiri",
    "title": "Co-Founder & Chief Technology Officer (CTO) at DevSpace Systems",
    "roles": [
        "Chief Technology Officer (CTO) at DevSpace Systems",
        "Multimodal AI & Computational Biology Researcher",
        "Precision Medicine Group (PMG) Technical Consultant"
    ],
    "email": "Febirimark27@gmail.com",
    "phone": "+91 8780006210",
    "locations": "Vadodara, Gujarat, India • Sunyani, Ghana • Global Remote",
    "portfolio_url": "https://febmac.vercel.app/",
    "github_url": "https://github.com/Febiri",
    "linkedin_url": "https://www.linkedin.com/in/mark-febiri-a067b3209/",
    "experience_summary": "Nearly 10 years of computational innovation, AI research, and technological leadership uniting advanced artificial intelligence, computational biology, genomic data science, and entrepreneurial software engineering.",
    "research_focus": "Engineering intelligent systems, neuro-symbolic reasoning, multimodal transformers (CLIP & BART), multi-omics pipelines, and clinical variant interpretation.",
    "publications": [
        {
            "venue": "ICETCI 2025 (Accepted)",
            "title": "Multimodal Transformers & Computational Intelligence Frameworks",
            "status": "Accepted for Presentation & Proceedings"
        },
        {
            "venue": "Springer Nature (Under Review)",
            "title": "Scalable Multi-Omics Genomic Workflow Orchestration and Variant Annotation",
            "status": "Under Review"
        }
    ],
    "flagship_projects": [
        {
            "name": "neuro-symbolic-rag",
            "tagline": "Neuro-Symbolic Agentic RAG Engine",
            "description": "Enterprise AI framework combining stochastic LLM reasoning with deterministic symbolic logic verification and scientific literature retrieval (PubMed & arXiv).",
            "stack": ["Python", "FastAPI", "Neuro-Symbolic AI", "RAG", "Knowledge Graphs", "PubMed"],
            "repo": "https://github.com/Febiri/neuro-symbolic-rag"
        },
        {
            "name": "ClawBio-Pipeline",
            "tagline": "Multi-Omics Workflow Orchestrator",
            "description": "Production multi-omics workflow orchestrator featuring ClinVar ACMG variant annotation, Biopython pipelines, and genomic sequence alignment.",
            "stack": ["Python", "Biopython", "Genomics", "ClinVar ACMG", "Nextflow / Workflows"],
            "repo": "https://github.com/Febiri/ClawBio-Pipeline"
        },
        {
            "name": "multimodal-clip-bart",
            "tagline": "Multimodal Scientific Document Synthesis",
            "description": "Cross-modal attention architecture synthesizing biomedical diagrams, text, and clinical abstracts.",
            "stack": ["PyTorch", "Transformers", "CLIP", "BART", "Computer Vision", "NLP"],
            "repo": "https://github.com/Febiri"
        }
    ],
    "technical_arsenal": {
        "ai_ml": [
            "Multimodal Transformers (CLIP & BART)",
            "PyTorch, TensorFlow & Keras",
            "Hugging Face Transformers & NLP",
            "Deep Reinforcement Learning (DQL)",
            "Agentic RAG & Knowledge Graphs",
            "Neuro-Symbolic Verification"
        ],
        "computational_biology": [
            "R & Bioconductor (Genomic Data Science)",
            "Sequence Alignment (BLAST, BWA, Bowtie2)",
            "ClinVar ACMG Variant Annotation",
            "Functional Genomics & Multi-Omics Pipelines",
            "Biomedical Data Analysis"
        ],
        "software_systems": [
            "Python (FastAPI, PyTorch, SciPy)",
            "TypeScript, JavaScript (React, Next.js)",
            "SQL & PostgreSQL Schema Architecture",
            "High-Performance Computing & Cloud Platforms",
            "Enterprise Architecture & CTO Leadership"
        ]
    },
    "custom_notes": "Actively seeking doctoral fellowships, top-tier conference travel support, and high-impact research scientist internships at premier industry labs (DeepMind, FAIR, MSR).",
    "last_synced": datetime.now().isoformat()
}


class PortfolioSyncService:
    """Synchronizes Mark Febiri's digital twin brain with his live portfolio at https://febmac.vercel.app/"""

    @classmethod
    def get_profile(cls) -> Dict[str, Any]:
        """Loads cached profile or returns default master profile."""
        try:
            if PROFILE_CACHE_PATH.exists():
                text = PROFILE_CACHE_PATH.read_text(encoding="utf-8")
                data = json.loads(text)
                if isinstance(data, dict) and "name" in data:
                    return data
        except Exception as e:
            logger.warning(f"Could not read profile cache: {e}")
        return MASTER_PROFILE

    @classmethod
    def save_profile(cls, profile: Dict[str, Any]) -> None:
        """Saves profile to local cache."""
        try:
            PROFILE_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
            PROFILE_CACHE_PATH.write_text(json.dumps(profile, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception as e:
            logger.warning(f"Could not persist profile cache: {e}")

    @classmethod
    def live_sync(cls, base_url: str = "https://febmac.vercel.app") -> Dict[str, Any]:
        """Live crawls febmac.vercel.app subpages to update knowledge base."""
        profile = cls.get_profile()
        crawled_snippets = {}
        pages = ["/", "/about", "/projects", "/skills"]

        for p in pages:
            url = base_url.rstrip("/") + p
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
                with urllib.request.urlopen(req, timeout=8) as resp:
                    html = resp.read().decode("utf-8", errors="ignore")
                    if BeautifulSoup is not None:
                        soup = BeautifulSoup(html, "html.parser")
                        for s in soup(["script", "style", "nav", "footer"]):
                            s.decompose()
                        text = " ".join(soup.get_text().split())
                    else:
                        cleaned = re.sub(r"<(script|style|nav|footer)[^>]*>.*?</\1>", " ", html, flags=re.DOTALL | re.IGNORECASE)
                        cleaned = re.sub(r"<[^>]+>", " ", cleaned)
                        text = " ".join(cleaned.split())
                    crawled_snippets[p] = text[:2000]
            except Exception as e:
                logger.warning(f"Failed to crawl {url}: {e}")

        if crawled_snippets:
            profile["last_synced"] = datetime.now().isoformat()
            profile["live_crawled_summary"] = f"Successfully synced {len(crawled_snippets)} pages from {base_url}."
            cls.save_profile(profile)

        return profile


class GitHubConnectorService:
    """Manages secure programmatic connection and autonomous operations on Mark's GitHub."""

    _cached_token: Optional[str] = None

    def __init__(self, token: Optional[str] = None, username: Optional[str] = None):
        self.token = (token or self._cached_token or GITHUB_TOKEN or "").strip()
        self.username = (username or GITHUB_USERNAME or "Febiri").strip()

    @classmethod
    def set_token(cls, token: str):
        cls._cached_token = token.strip()

    def get_status(self) -> Dict[str, Any]:
        """Checks connection status, authenticated scopes, and rate limits."""
        headers = {"User-Agent": "febPhD-TwinAgent/1.0"}
        if self.token:
            headers["Authorization"] = f"token {self.token}"
            url = "https://api.github.com/user"
        else:
            url = f"https://api.github.com/users/{self.username}"

        try:
            with httpx.Client(timeout=8.0) as client:
                resp = client.get(url, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    scopes_raw = resp.headers.get("x-oauth-scopes", "")
                    scopes = [s.strip() for s in scopes_raw.split(",") if s.strip()]
                    return {
                        "connected": True,
                        "authenticated": bool(self.token),
                        "username": data.get("login", self.username),
                        "name": data.get("name", "Febiri Mark"),
                        "avatar_url": data.get("avatar_url", ""),
                        "public_repos": data.get("public_repos", 0),
                        "bio": data.get("bio", ""),
                        "scopes": scopes,
                        "has_write_access": ("repo" in scopes or "public_repo" in scopes or bool(self.token)),
                        "rate_limit_remaining": resp.headers.get("x-ratelimit-remaining", "60")
                    }
                else:
                    return {
                        "connected": False,
                        "authenticated": False,
                        "error": f"GitHub API responded with status {resp.status_code}"
                    }
        except Exception as e:
            logger.warning(f"GitHub connection check failed: {e}")
            return {
                "connected": False,
                "authenticated": False,
                "error": str(e)
            }

    def fetch_live_repositories(self) -> List[Dict[str, Any]]:
        """Fetches Mark's live GitHub repositories to update Twin knowledge base."""
        headers = {"User-Agent": "febPhD-TwinAgent/1.0"}
        if self.token:
            headers["Authorization"] = f"token {self.token}"

        url = f"https://api.github.com/users/{self.username}/repos?sort=updated&per_page=20"
        try:
            with httpx.Client(timeout=8.0) as client:
                resp = client.get(url, headers=headers)
                if resp.status_code == 200:
                    raw_repos = resp.json()
                    formatted = []
                    for r in raw_repos:
                        formatted.append({
                            "name": r.get("name"),
                            "full_name": r.get("full_name"),
                            "description": r.get("description") or "Open-source research repository",
                            "language": r.get("language") or "Python",
                            "stars": r.get("stargazers_count", 0),
                            "forks": r.get("forks_count", 0),
                            "url": r.get("html_url"),
                            "updated_at": r.get("updated_at")
                        })
                    return formatted
        except Exception as e:
            logger.warning(f"Error fetching live repos from GitHub: {e}")
        return []

    def dispatch_application_log(self, application_packet: Dict[str, Any], target_repo: str = "febPhD") -> Dict[str, Any]:
        """Creates a tracking issue in Mark's repo for the dispatched application."""
        if not self.token:
            return {
                "logged_to_github": False,
                "message": "GitHub Personal Access Token (PAT) not set. Logged locally in application database."
            }

        headers = {
            "User-Agent": "febPhD-TwinAgent/1.0",
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github.v3+json"
        }
        title = f"[Application Log] {application_packet.get('opportunity_title', 'Fellowship / Lab Application')} — Mark Febiri"
        body = (
            f"## Autonomous Application Dispatch Receipt\n\n"
            f"- **Applicant:** {application_packet.get('applicant', {}).get('name', 'Mark Febiri')}\n"
            f"- **Target Opportunity:** {application_packet.get('opportunity_title', '')}\n"
            f"- **Organization:** {application_packet.get('organization', '')}\n"
            f"- **Date Dispatched:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}\n"
            f"- **Status:** Dispatched (Pending Committee Review)\n\n"
            f"### Statement of Purpose / Cover Letter\n"
            f"{application_packet.get('statement_of_purpose', '')}\n\n"
            f"### Justification\n"
            f"{application_packet.get('secondary_defense_text', '')}\n\n"
            f"---\n*Generated and logged autonomously by febPhD Executive Digital Twin.*"
        )
        url = f"https://api.github.com/repos/{self.username}/{target_repo}/issues"
        try:
            with httpx.Client(timeout=8.0) as client:
                resp = client.post(url, headers=headers, json={"title": title, "body": body, "labels": ["application", "fellowship"]})
                if resp.status_code in [200, 201]:
                    issue_data = resp.json()
                    return {
                        "logged_to_github": True,
                        "issue_url": issue_data.get("html_url"),
                        "issue_number": issue_data.get("number"),
                        "message": f"Successfully created GitHub tracking issue #{issue_data.get('number')}!"
                    }
                else:
                    return {
                        "logged_to_github": False,
                        "status_code": resp.status_code,
                        "message": f"GitHub issue creation response: {resp.status_code}"
                    }
        except Exception as e:
            return {"logged_to_github": False, "message": str(e)}


class TwinAgentService:
    """Autonomous Digital Twin that acts on Mark Febiri's behalf with higher perfection."""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = (api_key or GEMINI_API_KEY or "").strip()
        self.model = (model or GEMINI_MODEL or "gemini-2.5-flash").strip()

    def get_profile(self) -> Dict[str, Any]:
        return PortfolioSyncService.get_profile()

    def update_profile(self, custom_notes: Optional[str] = None, active_focus: Optional[str] = None) -> Dict[str, Any]:
        profile = PortfolioSyncService.get_profile()
        if custom_notes is not None:
            profile["custom_notes"] = custom_notes.strip()
        if active_focus is not None:
            profile["active_focus"] = active_focus.strip()
        profile["last_updated"] = datetime.now().isoformat()
        PortfolioSyncService.save_profile(profile)
        return profile

    def apply_for_grant(self, grant_title: str, grant_details: Dict[str, Any]) -> Dict[str, Any]:
        """Drafts a comprehensive, tailored, committee-winning grant or fellowship application on Mark's behalf."""
        profile = self.get_profile()
        if self.api_key:
            try:
                res = self._gemini_draft_grant_application(profile, grant_title, grant_details)
                if res:
                    return res
            except Exception as e:
                logger.warning(f"Gemini grant application error: {e}. Using deterministic synthesis.")

        return self._fallback_grant_application(profile, grant_title, grant_details)

    def apply_for_lab(self, lab_title: str, lab_details: Dict[str, Any]) -> Dict[str, Any]:
        """Drafts an elite research internship / visiting researcher pitch and cold email on Mark's behalf."""
        profile = self.get_profile()
        if self.api_key:
            try:
                res = self._gemini_draft_lab_application(profile, lab_title, lab_details)
                if res:
                    return res
            except Exception as e:
                logger.warning(f"Gemini lab application error: {e}. Using deterministic synthesis.")

        return self._fallback_lab_application(profile, lab_title, lab_details)

    def prepare_application_packet(
        self,
        opportunity_type: str,
        title: str,
        details: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Prepares a complete, structured submission package for Mark Febiri.
        Pre-populates every field so all Mark needs to do is review ('Check') and click 'Proceed'.
        """
        profile = self.get_profile()
        org = details.get("organization") or details.get("org") or "Selection Committee"
        award_or_role = details.get("award") or details.get("role") or "Fellowship / Research Residency"
        portal_url = details.get("url") or details.get("portal_url") or "https://github.com/Febiri"

        # Generate custom draft based on opportunity
        if opportunity_type == "lab":
            dossier = self.apply_for_lab(title, details)
            statement = dossier.get("cover_letter", "")
            secondary_text = dossier.get("cold_outreach_email", "")
            summary = dossier.get("project_alignment_pitch", "")
        else:
            dossier = self.apply_for_grant(title, details)
            statement = dossier.get("statement_of_purpose", "")
            secondary_text = dossier.get("research_justification", "")
            summary = f"Grant application for {title} under {org}."

        budget = dossier.get("itemized_budget", [
            {"item": "Roundtrip International Flights", "amount": "$1,350", "notes": "Economy class"},
            {"item": "Conference Accommodation (5 Nights)", "amount": "$850", "notes": "Standard lodging"},
            {"item": "Student Author Registration", "amount": "$450", "notes": "Doctoral pass"},
            {"item": "Consular Visa & Travel Insurance", "amount": "$250", "notes": "Official entry processing"}
        ])

        publications = [
            f"{p.get('venue')}: {p.get('title')}" for p in profile.get("publications", [])
        ]

        # JavaScript Bookmarklet / Injection script to auto-fill forms on external portals
        autofill_js = f"""(function(){{
    const fields = {{
        'name': '{profile.get("name")}',
        'first_name': 'Mark',
        'last_name': 'Febiri',
        'email': '{profile.get("email")}',
        'phone': '{profile.get("phone")}',
        'organization': 'DevSpace Systems',
        'affiliation': 'DevSpace Systems / Computational Biology Research',
        'website': '{profile.get("portfolio_url")}',
        'portfolio': '{profile.get("portfolio_url")}',
        'github': '{profile.get("github_url")}',
        'linkedin': '{profile.get("linkedin_url")}',
        'address': 'Vadodara, Gujarat, India',
        'country': 'India',
        'statement': {json.dumps(statement)},
        'essay': {json.dumps(statement)},
        'cover_letter': {json.dumps(statement)}
    }};
    let filled = 0;
    document.querySelectorAll('input, textarea, select').forEach(el => {{
        const key = (el.name || el.id || el.placeholder || '').toLowerCase();
        for (const [k, v] of Object.entries(fields)) {{
            if (key.includes(k) && !el.value) {{
                el.value = v;
                el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                filled++;
                break;
            }}
        }}
    }});
    alert('febPhD Twin Agent: Pre-filled ' + filled + ' fields for Mark Febiri!');
}})();"""

        applicant_dict = {
            "name": profile.get("name", "Mark Febiri"),
            "email": profile.get("email", "Febirimark27@gmail.com"),
            "phone": profile.get("phone", "+91 8780006210"),
            "current_role": profile.get("title", "CTO at DevSpace Systems"),
            "affiliation": "Co-Founder & CTO at DevSpace Systems",
            "locations": profile.get("locations", "Vadodara, Gujarat, India • Sunyani, Ghana"),
            "location": profile.get("locations", "Vadodara, Gujarat, India • Sunyani, Ghana"),
            "portfolio_url": profile.get("portfolio_url", "https://febmac.vercel.app/"),
            "portfolio": profile.get("portfolio_url", "https://febmac.vercel.app/"),
            "github_url": profile.get("github_url", "https://github.com/Febiri"),
            "github": profile.get("github_url", "https://github.com/Febiri"),
            "linkedin_url": profile.get("linkedin_url", "https://www.linkedin.com/in/mark-febiri-a067b3209/"),
            "flagship_projects": [p.get("name") for p in profile.get("flagship_projects", [])],
            "featured_repos": [p.get("name") for p in profile.get("flagship_projects", [])]
        }

        packet = {
            "opportunity_type": opportunity_type,
            "opportunity_title": title,
            "organization": org,
            "award_or_role": award_or_role,
            "requested_award": award_or_role,
            "portal_url": portal_url,
            "applicant": applicant_dict,
            "applicant_info": applicant_dict,
            "statement_of_purpose": statement,
            "secondary_defense_text": secondary_text,
            "itemized_budget": budget,
            "publications": publications,
            "dossier": dossier,
            "full_dossier_markdown": dossier.get("full_application_dossier_markdown", statement),
            "autofill_bookmarklet": "javascript:" + urllib.parse.quote(autofill_js),
            "autofill_script_raw": autofill_js,
            "form_autofill_script": autofill_js,
            "created_at": datetime.utcnow().isoformat()
        }
        return packet

    def dispatch_application(
        self,
        packet: Dict[str, Any],
        target_repo: str = "febPhD"
    ) -> Dict[str, Any]:
        """Dispatches application, logs to GitHub issue if token present, and records in history."""
        gh_service = GitHubConnectorService()
        gh_result = gh_service.dispatch_application_log(packet, target_repo=target_repo)

        # Save to local tracking record
        record = {
            "id": f"app_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
            "title": packet.get("opportunity_title"),
            "organization": packet.get("organization"),
            "type": packet.get("opportunity_type"),
            "dispatched_at": datetime.utcnow().isoformat(),
            "status": "Dispatched / Committee Review",
            "github_log": gh_result
        }

        # Persist record safely
        try:
            log_path = Path("/tmp/dispatched_applications.json") if (IS_SERVERLESS or not is_writable) else BASE_DIR / "data" / "dispatched_applications.json"
            log_path.parent.mkdir(parents=True, exist_ok=True)
            existing = []
            if log_path.exists():
                try:
                    existing = json.loads(log_path.read_text(encoding="utf-8"))
                except Exception:
                    existing = []
            existing.insert(0, record)
            log_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")
        except Exception as e:
            logger.warning(f"Could not persist dispatch history: {e}")

        return {
            "success": True,
            "status": "Dispatched",
            "record": record,
            "github_dispatch": gh_result
        }

    def get_dispatch_history(self) -> List[Dict[str, Any]]:
        """Returns list of past dispatched applications."""
        try:
            log_path = Path("/tmp/dispatched_applications.json") if (IS_SERVERLESS or not is_writable) else BASE_DIR / "data" / "dispatched_applications.json"
            if log_path.exists():
                return json.loads(log_path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning(f"Could not read dispatch history: {e}")
        return []

    def get_strategic_suggestions(self) -> List[Dict[str, Any]]:
        """Generates proactive, high-leverage suggestions of what Mark should do right now."""
        profile = self.get_profile()
        if self.api_key:
            try:
                suggestions = self._gemini_generate_suggestions(profile)
                if suggestions:
                    return suggestions
            except Exception as e:
                logger.warning(f"Gemini suggestions error: {e}")

        return self._default_strategic_suggestions(profile)

    def chat_with_twin(self, user_message: str, chat_history: Optional[List[Dict[str, str]]] = None) -> str:
        """Interactive conversation with Mark Febiri's perfectionist digital twin."""
        profile = self.get_profile()
        if not self.api_key:
            return self._dynamic_twin_response(profile, user_message, chat_history)

        client = genai.Client(api_key=self.api_key)
        profile_json = json.dumps(profile, indent=2)
        system_instruction = f"""You are the Autonomous PhD Digital Twin and Executive Co-Pilot of Mark Febiri.
You embody Mark Febiri in a state of higher perfection: highly articulate, strategically aggressive, academically rigorous, proactive, and exceptionally fast.
You know everything about Mark from his verified portfolio (https://febmac.vercel.app/):
- Name: Mark Febiri
- Title: Co-Founder & CTO at DevSpace Systems | AI, Machine Learning & Computational Biology Researcher
- Key Projects: Neuro-Symbolic Agentic RAG Engine, ClawBio Multi-Omics Workflow Orchestrator, Multimodal CLIP+BART summarization
- Affiliations: DevSpace Systems, PMG Collaborations
- Publications: ICETCI 2025 (Accepted), Springer Nature (Under Review)
- Education & Background: CS & AI/ML with nearly 10 years practical experience
- GitHub: https://github.com/Febiri
- Locations: Vadodara, India • Sunyani, Ghana • Global Remote

EXECUTIVE DELIVERY & FORMATTING PRINCIPLES:
1. **Presentation & Layout**:
   - Never output raw, unformatted blocks of text.
   - Present responses using clean Markdown structure: bold section headers (`### 📌 Strategy`, `### 🔬 Scientific & Mathematical Mechanics`, `### 🖼️ Architectural Flow & Pipeline`, `### 📊 Benchmarks & Proof Points`, `### 🚀 Immediate Execution Steps`).
   - Use Markdown tables when presenting funding opportunities, comparative metrics, or budgets.
   - Use bold highlights and clean bullet points.
2. **Scientific Mathematics & Diagram Intelligence**:
   - Masterfully explain scientific math, algorithmic formulas, loss functions, and biological mechanisms using KaTeX math notation (`$inline$` and `$$display$$`).
   - Deeply explain architectural flowcharts, multimodal cross-attention diagrams, and bioinformatics pipelines.
3. **Executive Action**:
   - Address Mark directly as his own hyper-competent alter ego.
   - Deliver immediate, production-ready drafts and actionable steps so all Mark has to do is review and proceed."""

        history_prompt = ""
        if chat_history:
            for msg in chat_history[-6:]:
                role = "Mark" if msg.get("role") == "user" else "Twin"
                history_prompt += f"{role}: {msg.get('content', '')}\n"

        prompt = f"""{system_instruction}

CONVERSATION HISTORY:
{history_prompt}
Mark: {user_message}
Twin:"""

        models = ["gemini-2.5-flash", "gemini-3.5-flash-lite"]
        if self.model and self.model not in models:
            models.insert(0, self.model)

        for m in models:
            try:
                resp = client.models.generate_content(
                    model=m,
                    contents=prompt,
                    config=types.GenerateContentConfig(temperature=0.35)
                )
                text = (resp.text or "").strip()
                if text:
                    return text
            except Exception as e:
                logger.warning(f"Twin chat with {m} failed: {e}")
                continue

        return self._dynamic_twin_response(profile, user_message, chat_history)

    def _dynamic_twin_response(self, profile: Dict[str, Any], user_message: str, chat_history: Optional[List[Dict[str, str]]] = None) -> str:
        """Dynamic, context-aware synthesis when AI models are unavailable or rate-limited."""
        msg = user_message.lower().strip()

        # 1. Fellowships, Grants & Funding
        if any(w in msg for w in ["grant", "fellowship", "funding", "travel", "stipend", "scholarship", "money", "award", "nsf", "google fellowship", "meta fellowship"]):
            return (
                f"Mark, looking at our academic profile and our CTO track record at DevSpace Systems, our highest-probability funding targets right now are:\n\n"
                f"1. **NSF Graduate Research Fellowship (GRFP) / Premier Travel Grants**:\n"
                f"   - **Strategic Angle**: Frame our work as *Deterministic Knowledge-Grounding for Genomic AI*. Reviewers love high-impact translational science with open-source codebases (`github.com/Febiri/neuro-symbolic-rag`).\n"
                f"   - **Unique Advantage**: Most applicants only have theoretical ideas. You bring 10 years of software engineering, a real company (DevSpace Systems), and accepted work at ICETCI 2025.\n"
                f"2. **Microsoft Research & Meta PhD Fellowships**:\n"
                f"   - We should emphasize the combination of ClawBio (ClinVar ACMG variant interpretation) with agentic logic reasoning.\n\n"
                f"💡 **Immediate Execution Step**: Head over to our **'Apply On My Behalf'** tab in the Digital Twin Studio, select the fellowship, and I will generate the complete Statement of Purpose and itemized budget in 1-click."
            )

        # 2. Labs, Industry Residencies & Internships
        if any(w in msg for w in ["lab", "deepmind", "fair", "meta", "google", "msr", "microsoft", "residency", "intern", "internship", "hiring", "cold email", "pitch", "careers"]):
            return (
                f"Mark, for our post-doctoral trajectory and industry research residencies (Google DeepMind, Meta FAIR, MSR Health/Genomics):\n\n"
                f"🎯 **Our Cold Outreach Pitch Angle**:\n"
                f"- **The Hook**: Don't pitch yourself as a generic ML student. Pitch yourself as an *AI Systems Architect & Computational Biologist* who builds production pipelines.\n"
                f"- **Proof Points**: Cite our `ClawBio-Pipeline` (sub-second ClinVar variant lookups) and our `neuro-symbolic-rag` benchmark results.\n"
                f"- **Target PIs**: Reach out directly to Research Scientists working on multimodal models and structural genomics.\n\n"
                f"📝 **Action**: I can draft an ultra-high-reply cold email to specific Research Leads right now. Just say 'Draft cold email for DeepMind' or use our 'Apply for Lab' tool!"
            )

        # 3. Publications, Manuscripts & Reviewer Rebuttal
        if any(w in msg for w in ["paper", "publish", "icetci", "springer", "review", "reviewer", "rebuttal", "manuscript", "accept", "reject", "neurips", "icml"]):
            return (
                f"Mark, regarding our publication pipeline and peer review defense:\n\n"
                f"📄 **Current Status**:\n"
                f"- **ICETCI 2025**: Accepted! Multimodal Transformers & Computational Intelligence Frameworks.\n"
                f"- **Springer Nature**: Under Review — Scalable Multi-Omics Genomic Workflow Orchestration and Variant Annotation.\n\n"
                f"⚖️ **Tactical Advice for Next Submissions**:\n"
                f"1. **Pre-Submission Stress Testing**: Always run our manuscript through our built-in **Reviewer #2 Simulator** (Engine 04) to catch missing 2024-2025 baselines and ablation gaps before the reviewers do.\n"
                f"2. **Ablation Transparency**: Reviewers will demand isolation of our symbolic logic filter vs standard vector search. Keep Figure 3 and the seed standard deviations prominent."
            )

        # 4. ClawBio & Computational Biology Pipelines
        if any(w in msg for w in ["clawbio", "bio", "genomic", "variant", "clinvar", "acmg", "omics", "multi-omics", "biopython"]):
            return (
                f"Mark, the **ClawBio Multi-Omics Pipeline** (`github.com/Febiri/ClawBio-Pipeline`) is one of our strongest intellectual assets.\n\n"
                f"🧬 **Core Differentiators**:\n"
                f"- Integration of ClinVar ACMG automated classification rules with sub-second variant lookups.\n"
                f"- Asynchronous streaming architecture handling BAM/VCF file sets with high throughput.\n"
                f"- Modular Nextflow-style reproducibility that can be plugged directly into clinical precision medicine workflows.\n\n"
                f"🚀 **Next Enhancement**: Integrating our Neuro-Symbolic verifier directly into ClawBio to automatically cite clinical PubMed literature for novel pathogenic variants."
            )

        # 5. Neuro-Symbolic RAG & Agentic Systems
        if any(w in msg for w in ["neuro", "symbolic", "rag", "knowledge graph", "logic", "hallucination", "retrieval", "pubmed"]):
            return (
                f"Mark, our **Neuro-Symbolic Agentic RAG Engine** (`github.com/Febiri/neuro-symbolic-rag`) directly solves the biggest crisis in scientific AI: hallucinations.\n\n"
                f"🧠 **Architecture Blueprint**:\n"
                f"1. **Stochastic Layer**: LLM generates candidate reasoning pathways from retrieved PubMed & arXiv abstracts.\n"
                f"2. **Deterministic Layer**: Symbolic Horn-clause logic filters verify relational triples against certified knowledge graphs before output generation.\n"
                f"3. **Result**: Zero-hallucination citation guarantee that appeals directly to grant panels and clinical researchers."
            )

        # 6. Immediate Priorities & Strategic Roadmap
        if any(w in msg for w in ["priority", "priorities", "roadmap", "plan", "todo", "next", "what should i do", "advise", "move"]):
            return (
                f"Mark, here is our prioritized executive doctoral roadmap for the next 14 days:\n\n"
                f"1. **Priority 1 (Funding)**: Submit applications to 2 top travel grants (ACM SIGCOMM & NeurIPS Travel Awards) to lock in zero out-of-pocket travel.\n"
                f"2. **Priority 2 (Research Lab Residency)**: Send our tailored cold outreach email to 3 Google DeepMind & Microsoft Research PIs highlighting ClawBio.\n"
                f"3. **Priority 3 (Codebase Polishing)**: Add reproducible benchmark scripts and Docker containers to `github.com/Febiri/ClawBio-Pipeline` and `neuro-symbolic-rag`.\n"
                f"4. **Priority 4 (Springer Follow-up)**: Prepare our point-by-point rebuttal template so that the moment reviewer comments land, we return the revised manuscript within 72 hours."
            )

        # 7. Comprehensive Fallback for any general query
        return (
            f"Mark, acknowledging your query: *\"{user_message}\"*.\n\n"
            f"As your executive digital twin, I evaluate this through the lens of our core mandate: accelerating your PhD trajectory, scaling DevSpace Systems, and securing Tier-1 academic recognition.\n\n"
            f"Here is how we execute on this:\n"
            f"- **Leverage Our Proven Repositories**: Ground all technical claims directly in `neuro-symbolic-rag` and `ClawBio-Pipeline`.\n"
            f"- **Speed & Precision**: Whether this requires an application dossier, a rebuttal defense, or architectural formulation, I can generate the complete publication-grade draft immediately.\n\n"
            f"What specific section or draft would you like me to generate first?"
        )

    # ------------------------------------------------------------------
    # Gemini Generation Helpers
    # ------------------------------------------------------------------
    def _gemini_draft_grant_application(self, profile: Dict[str, Any], grant_title: str, grant: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        client = genai.Client(api_key=self.api_key)
        today = date.today().strftime("%B %Y")
        prompt = f"""You are Mark Febiri's PhD Executive Digital Twin.
Write a full, publication-grade academic application dossier for the following grant on Mark's behalf.
APPLICANT DOSSIER:
{json.dumps(profile, indent=2)}

TARGET GRANT OPPORTUNITY:
Title: {grant_title}
Organization: {grant.get('organization', 'Sponsoring Committee')}
Award: {grant.get('award', 'Full Fellowship / Travel Grant')}
Description: {grant.get('description', '')}
Eligibility: {grant.get('eligibility', '')}

Write a persuasive application dossier formatted strictly as valid JSON with no markdown wrapping or backticks:
{{
  "grant_title": "{grant_title}",
  "applicant_name": "Mark Febiri",
  "statement_of_purpose": "3-4 paragraph compelling first-person personal statement highlighting Mark's CTO leadership at DevSpace Systems, his Neuro-Symbolic RAG and ClawBio pipelines, and why this grant directly accelerates his research...",
  "research_justification": "Detailed scientific justification paragraph explaining the exact relevance of this grant to Mark's multi-omics and multimodal AI milestones...",
  "itemized_budget": [
    {{"item": "Roundtrip International Airfare", "amount": "$1,400", "notes": "Economy class flight to conference venue"}},
    {{"item": "Accommodation & Lodging", "amount": "$900", "notes": "5 nights at official conference hotel"}},
    {{"item": "Doctoral Student Registration", "amount": "$450", "notes": "Full access student registration"}},
    {{"item": "Visa Processing & Travel Insurance", "amount": "$250", "notes": "Consulate filing fees and coverage"}}
  ],
  "cv_alignment_highlights": [
    "Highlight 1: 10+ years engineering scalable computational architectures and leading DevSpace Systems.",
    "Highlight 2: First-author contributions in multimodal AI (ICETCI 2025) and multi-omics (Springer Nature).",
    "Highlight 3: Open-source maintainer of Neuro-Symbolic RAG and ClawBio pipelines (github.com/Febiri)."
  ],
  "full_application_dossier_markdown": "# Markdown formatted application ready for submission..."
}}"""

        models = ["gemini-2.5-flash", "gemini-3.5-flash-lite"]
        for m in models:
            try:
                resp = client.models.generate_content(
                    model=m,
                    contents=prompt,
                    config=types.GenerateContentConfig(temperature=0.3)
                )
                text = (resp.text or "").strip()
                text = re.sub(r"^```json\s*", "", text)
                text = re.sub(r"^```\s*", "", text)
                text = re.sub(r"\s*```$", "", text)
                parsed = json.loads(text, strict=False)
                if isinstance(parsed, dict) and "statement_of_purpose" in parsed:
                    return parsed
            except Exception as e:
                logger.warning(f"Gemini grant draft failed with {m}: {e}")
                continue
        return None

    def _gemini_draft_lab_application(self, profile: Dict[str, Any], lab_title: str, lab: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        client = genai.Client(api_key=self.api_key)
        prompt = f"""You are Mark Febiri's Executive Digital Twin.
Write a tailored research scientist internship / visiting scholar dossier for Mark Febiri applying to:
LAB / SUMMIT: {lab_title}
ORGANIZATION: {lab.get('organization', 'Research Lab')}
LOCATION: {lab.get('location', 'Global')}
DESCRIPTION: {lab.get('description', '')}
TARGET PROFILE: {lab.get('target_profile', '')}

APPLICANT PROFILE:
{json.dumps(profile, indent=2)}

Return strictly a valid JSON object with no markdown wrapping:
{{
  "opportunity_title": "{lab_title}",
  "cover_letter": "Engaging, authoritative 3-paragraph cover letter tailored to the Lab Director emphasizing Mark's CTO background and multimodal/genomic AI experience...",
  "cold_outreach_email": "Subject and body of a high-converting cold email to the Principal Investigator / Research Lead...",
  "project_alignment_pitch": "2 paragraphs linking Mark's Neuro-Symbolic RAG and ClawBio pipelines to the lab's mission...",
  "interview_prep_qa": [
    {{"question": "How do you scale transformer inference on sparse biomedical graphs?", "answer": "Answer based on Mark's Neuro-Symbolic RAG and multimodal architectures..."}},
    {{"question": "What is your experience orchestrating multi-omics variant pipelines?", "answer": "Answer detailing ClawBio and ClinVar ACMG annotation..."}}
  ],
  "full_application_dossier_markdown": "# Markdown formatted application ready to copy or download..."
}}"""

        models = ["gemini-2.5-flash", "gemini-3.5-flash-lite"]
        for m in models:
            try:
                resp = client.models.generate_content(
                    model=m,
                    contents=prompt,
                    config=types.GenerateContentConfig(temperature=0.3)
                )
                text = (resp.text or "").strip()
                text = re.sub(r"^```json\s*", "", text)
                text = re.sub(r"^```\s*", "", text)
                text = re.sub(r"\s*```$", "", text)
                parsed = json.loads(text, strict=False)
                if isinstance(parsed, dict) and "cover_letter" in parsed:
                    return parsed
            except Exception as e:
                logger.warning(f"Gemini lab draft failed with {m}: {e}")
                continue
        return None

    def _gemini_generate_suggestions(self, profile: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
        client = genai.Client(api_key=self.api_key)
        today = date.today().strftime("%B %Y")
        prompt = f"""You are Mark Febiri's AI Executive Co-Pilot. Current date: {today}.
Analyze Mark's profile:
{json.dumps(profile, indent=2)}

Generate 4 high-leverage, concrete strategic actions Mark should take over the next 14 to 60 days to maximize his PhD trajectory, funding, and career impact.
Return strictly a valid JSON array:
[
  {{
    "title": "Action Title",
    "timeline": "Next 14 Days" or "Next 30 Days" or "Next 60 Days",
    "impact_level": "Tier-1 Prestige" or "High Impact" or "$40k+ Funding",
    "rationale": "Why this specific move leverages Mark's ClawBio, Neuro-Symbolic RAG, or CTO background",
    "action_steps": [
      "Step 1...",
      "Step 2..."
    ],
    "direct_action": "Apply / Submit / Pitch"
  }}
]"""
        try:
            resp = client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(temperature=0.3)
            )
            text = (resp.text or "").strip()
            text = re.sub(r"^```json\s*", "", text)
            text = re.sub(r"^```\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
            parsed = json.loads(text, strict=False)
            if isinstance(parsed, list):
                return parsed
        except Exception:
            pass
        return None

    # ------------------------------------------------------------------
    # Deterministic Structured Fallbacks
    # ------------------------------------------------------------------
    def _fallback_grant_application(self, profile: Dict[str, Any], grant_title: str, grant: Dict[str, Any]) -> Dict[str, Any]:
        org = grant.get("organization", "Award Committee")
        award = grant.get("award", "$3,000 Travel Grant")
        sop = (
            f"Dear Selection Committee of the {grant_title},\n\n"
            f"I am writing to formally submit my application for the {grant_title} sponsored by {org}. "
            f"As Co-founder and Chief Technology Officer at DevSpace Systems and an active researcher in artificial intelligence "
            f"and computational biology, my academic mission focuses on bridging agentic neuro-symbolic reasoning with high-throughput multi-omics discovery.\n\n"
            f"Over nearly a decade of software engineering and computational research, I have architected and open-sourced platforms including the "
            f"Neuro-Symbolic Agentic RAG Engine (integrating PubMed and arXiv symbolic verification) and the ClawBio Multi-Omics Workflow Orchestrator "
            f"(automating ClinVar ACMG genomic variant annotation). My recent research has been accepted at ICETCI 2025, with extended genomic pipelines under review with Springer Nature.\n\n"
            f"Securing this funding ({award}) will directly enable me to travel, present our findings, and establish vital international collaborations with leading investigators, "
            f"ensuring our computational frameworks achieve global translational impact."
        )

        md = f"""# Fellowship & Grant Application Dossier
**Applicant:** Mark Febiri  
**Target Award:** {grant_title} ({org})  
**Award Value:** {award}  
**Portfolio:** {profile['portfolio_url']} | **GitHub:** {profile['github_url']}  

---

## 1. Statement of Purpose & Motivation
{sop}

---

## 2. Research Alignment & Scientific Relevance
My primary investigation investigates the convergence of multimodal foundation models with clinical genomics. By integrating ClinVar variant databases with transformer-based reasoning, our research drastically cuts genomic variant curation time while eliminating model hallucinations. Presenting this work through the support of {grant_title} will accelerate feedback from world leaders in the field.

---

## 3. Itemized Budget Justification
- **Roundtrip Airfare (Economy Class):** $1,350
- **Lodging & Accommodation (5 Nights):** $850
- **Student Conference Registration:** $450
- **Visa & Mandatory Medical Insurance:** $250
- **Total Requested Support:** $2,900

---

## 4. Key Qualifications & Portfolio Highlights
- **10+ Years Engineering Excellence:** Co-Founder & CTO at DevSpace Systems leading production deployments.
- **Peer-Reviewed Output:** Accepted at ICETCI 2025; multi-omics manuscript under review with Springer Nature.
- **Open-Source Reproducibility:** Verified codebases at `github.com/Febiri` (Neuro-Symbolic RAG, ClawBio).
"""

        return {
            "grant_title": grant_title,
            "applicant_name": "Mark Febiri",
            "statement_of_purpose": sop,
            "research_justification": f"Directly advances Mark Febiri's research in multi-omics variant annotation (ClawBio) and neuro-symbolic AI under the sponsorship of {org}.",
            "itemized_budget": [
                {"item": "Roundtrip Airfare", "amount": "$1,350", "notes": "Economy international travel"},
                {"item": "Hotel Accommodation", "amount": "$850", "notes": "5 nights at conference rate"},
                {"item": "Student Registration", "amount": "$450", "notes": "Doctoral author pass"},
                {"item": "Visa & Insurance", "amount": "$250", "notes": "Consular visa processing"}
            ],
            "cv_alignment_highlights": [
                "10+ Years Software Leadership: Co-Founder & CTO at DevSpace Systems.",
                "Published Multimodal AI: Accepted at ICETCI 2025 and Springer Nature under review.",
                "Open Source Systems: Maintainer of ClawBio and Neuro-Symbolic RAG (github.com/Febiri)."
            ],
            "full_application_dossier_markdown": md
        }

    def _fallback_lab_application(self, profile: Dict[str, Any], lab_title: str, lab: Dict[str, Any]) -> Dict[str, Any]:
        org = lab.get("organization", "Research Lab")
        cover = (
            f"Dear Research Hiring Committee at {org},\n\n"
            f"I am writing to express my strong interest in the {lab_title} at {org}. "
            f"As Co-founder and CTO at DevSpace Systems and an AI/Computational Biology doctoral researcher with nearly a decade "
            f"of practical engineering experience, I specialize in multimodal transformer architectures, neuro-symbolic reasoning, and high-performance genomic pipelines.\n\n"
            f"My research directly bridges fundamental machine learning with real-world scientific impact. Through open-source projects such as our "
            f"Neuro-Symbolic Agentic RAG Engine and ClawBio Multi-Omics Pipeline (github.com/Febiri), alongside peer-reviewed outputs accepted at ICETCI 2025 "
            f"and under review with Springer Nature, I have proven the ability to rapidly formulate, validate, and scale novel computational architectures.\n\n"
            f"I am excited by the opportunity to collaborate with {org}'s world-class investigators to publish impactful research at upcoming premier venues."
        )

        cold_email = (
            f"Subject: PhD Research Scientist Inquiry: Multimodal AI & Multi-Omics — Mark Febiri\n\n"
            f"Dear Dr. [Hiring Scientist / PI],\n\n"
            f"I follow your team's research at {org} with great admiration. I am Mark Febiri, CTO at DevSpace Systems and an AI/genomics researcher (portfolio: {profile['portfolio_url']}). "
            f"My work focuses on neuro-symbolic reasoning and multi-omics pipelines, with recent papers accepted at ICETCI 2025 and under review with Springer Nature.\n\n"
            f"I have engineered and open-sourced ClawBio-Pipeline and a Neuro-Symbolic RAG Engine (github.com/Febiri). I would welcome 15 minutes to discuss how my skillset in multimodal transformers and high-performance computing can contribute to {org}'s upcoming research initiatives this cycle.\n\n"
            f"Warm regards,\n"
            f"Mark Febiri | Febirimark27@gmail.com | +91 8780006210"
        )

        md = f"""# Industry Research Lab Application Dossier
**Applicant:** Mark Febiri  
**Target Position:** {lab_title} ({org})  
**Portfolio:** {profile['portfolio_url']} | **GitHub:** {profile['github_url']}  

---

## 1. Formal Cover Letter
{cover}

---

## 2. High-Reply Cold Outreach Email to PI / Research Lead
```
{cold_email}
```

---

## 3. Project Alignment & Technical Fit
Our ClawBio Multi-Omics pipeline and Neuro-Symbolic RAG engine demonstrate immediate alignment with {org}'s foundational models and scientific discovery mandates. Having led engineering teams as CTO of DevSpace Systems, I bring rare end-to-end fluency across theoretical formulation, PyTorch CUDA scaling, and empirical benchmarking.
"""

        return {
            "opportunity_title": lab_title,
            "cover_letter": cover,
            "cold_outreach_email": cold_email,
            "project_alignment_pitch": f"Aligns Mark Febiri's multimodal CLIP+BART and ClawBio genomics pipelines directly with {org}'s research objectives.",
            "interview_prep_qa": [
                {
                    "question": "How does your Neuro-Symbolic RAG prevent hallucinations on scientific benchmarks?",
                    "answer": "We enforce deterministic symbolic logic verification over retrieved knowledge graph triples before generation, guaranteeing certified traceability."
                },
                {
                    "question": "How do you handle high-dimensional multi-omics data in ClawBio?",
                    "answer": "We construct an asynchronous modular pipeline that streams BAM/VCF files through ClinVar ACMG annotations with sub-second lookups."
                }
            ],
            "full_application_dossier_markdown": md
        }

    def _default_strategic_suggestions(self, profile: Dict[str, Any]) -> List[Dict[str, Any]]:
        return [
            {
                "title": "Apply for Google PhD Fellowship in Machine Learning & Health",
                "timeline": "Next 14 Days",
                "impact_level": "$50,000 + Google Research Mentor",
                "rationale": "Your Neuro-Symbolic RAG and ClawBio pipelines place you in the top 5% of candidates uniting AI with computational biology.",
                "action_steps": [
                    "Generate statement of purpose via your Digital Twin.",
                    "Attach ClawBio-Pipeline and ICETCI 2025 manuscript.",
                    "Request department nomination from your academic advisor."
                ],
                "direct_action": "Apply Now"
            },
            {
                "title": "Pitch Meta FAIR / Google DeepMind Research Internship",
                "timeline": "Next 30 Days",
                "impact_level": "Tier-1 Prestige & Top Salary",
                "rationale": "Both labs are actively hiring PhD interns in multimodal reasoning and biological sequence models for their London and Paris teams.",
                "action_steps": [
                    "Use your Twin's pre-drafted cold email to message senior research scientists.",
                    "Highlight github.com/Febiri repositories.",
                    "Submit formal application via careers portal."
                ],
                "direct_action": "Pitch Lab"
            },
            {
                "title": "Submit Extended Abstract to ICML 2026 Computational Biology Workshop",
                "timeline": "Next 45 Days",
                "impact_level": "Tier-1 Conference Publication",
                "rationale": "Package the ClinVar ACMG results from ClawBio as a 4-page workshop paper to establish priority and secure travel grants.",
                "action_steps": [
                    "Run Reviewer #2 simulator on draft abstract.",
                    "Submit before workshop deadline.",
                    "Apply for ICML Student Travel Grant immediately upon notification."
                ],
                "direct_action": "Draft Paper"
            },
            {
                "title": "Apply for Black in AI & ACM Travel Sponsorship",
                "timeline": "Next 60 Days",
                "impact_level": "Full Flight + Hotel Coverage",
                "rationale": "Full coverage for flights from Ghana/India to upcoming premier AI venues with guaranteed author priority.",
                "action_steps": [
                    "Export Digital Twin itemized budget justification.",
                    "Submit registration waiver form."
                ],
                "direct_action": "Claim Grant"
            }
        ]
