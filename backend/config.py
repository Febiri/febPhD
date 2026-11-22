import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from project root or backend directory if present
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = BASE_DIR / "backend"
FRONTEND_DIR = BASE_DIR / "frontend"
STATIC_DIR = BASE_DIR / "static"

# Robust detection of serverless / read-only environment
IS_SERVERLESS = (
    bool(os.getenv("VERCEL"))
    or bool(os.getenv("VERCEL_ENV"))
    or bool(os.getenv("AWS_LAMBDA_FUNCTION_NAME"))
    or bool(os.getenv("LAMBDA_TASK_ROOT"))
)

# Test if local base directory is writable
def _check_writable(dir_path: Path) -> bool:
    try:
        test_file = dir_path / ".test_write_perm"
        test_file.touch()
        test_file.unlink()
        return True
    except Exception:
        return False

is_writable = _check_writable(BASE_DIR)

if IS_SERVERLESS or not is_writable:
    # On serverless (Vercel, AWS Lambda) or read-only container, only /tmp is writable
    TMP_DIR = Path("/tmp")
    AUDIO_DIR = TMP_DIR / "audio"
    PDFS_DIR = TMP_DIR / "pdfs"
    default_db_path = "/tmp/zotero_audio.db"
    initial_db = BASE_DIR / "zotero_audio.db"
    if initial_db.exists() and not Path(default_db_path).exists():
        try:
            import shutil
            shutil.copy2(initial_db, default_db_path)
        except Exception:
            pass
    DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{default_db_path}")
else:
    AUDIO_DIR = STATIC_DIR / "audio"
    PDFS_DIR = STATIC_DIR / "pdfs"
    DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'zotero_audio.db'}")

# Ensure directories exist safely without raising uncaught exceptions
try:
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    PDFS_DIR.mkdir(parents=True, exist_ok=True)
except Exception:
    pass

# Gemini API Configuration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# Zotero API Configuration
ZOTERO_LIBRARY_ID = os.getenv("ZOTERO_LIBRARY_ID", "")
ZOTERO_API_KEY = os.getenv("ZOTERO_API_KEY", "")
ZOTERO_LIBRARY_TYPE = os.getenv("ZOTERO_LIBRARY_TYPE", "user")

# Text-to-Speech Configuration (edge-tts voices)
DEFAULT_TTS_VOICE = os.getenv("DEFAULT_TTS_VOICE", "en-NG-AbeoNeural")

# GitHub Personal Access Token (PAT) for Autonomous Digital Twin Execution
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "").strip()
GITHUB_USERNAME = os.getenv("GITHUB_USERNAME", "Febiri").strip()

AVAILABLE_VOICES = [
    {"id": "en-NG-AbeoNeural", "name": "🇬🇭 Abeo (West Africa / Ghana - Male, Expressive & Natural)", "gender": "Male", "region": "Africa"},
    {"id": "en-NG-EzinneNeural", "name": "🇬🇭 Ezinne (West Africa / Ghana - Female, Melodic & Clear)", "gender": "Female", "region": "Africa"},
    {"id": "en-KE-ChilembaNeural", "name": "🇰🇪 Chilemba (East Africa / Kenya - Male, Scholarly)", "gender": "Male", "region": "Africa"},
    {"id": "en-KE-AsiliaNeural", "name": "🇰🇪 Asilia (East Africa / Kenya - Female, Articulate)", "gender": "Female", "region": "Africa"},
    {"id": "en-ZA-LukeNeural", "name": "🇿🇦 Luke (South Africa - Male, Crisp & Modern)", "gender": "Male", "region": "Africa"},
    {"id": "en-ZA-LeahNeural", "name": "🇿🇦 Leah (South Africa - Female, Warm)", "gender": "Female", "region": "Africa"},
    {"id": "en-TZ-ElimuNeural", "name": "🇹🇿 Elimu (Tanzania - Male, Calm & Clear)", "gender": "Male", "region": "Africa"},
    {"id": "en-US-ChristopherNeural", "name": "🇺🇸 Christopher (US - Authoritative, Mentor)", "gender": "Male", "region": "US"},
    {"id": "en-US-JennyNeural", "name": "🇺🇸 Jenny (US - Warm, Engaging)", "gender": "Female", "region": "US"},
    {"id": "en-US-GuyNeural", "name": "🇺🇸 Guy (US - Natural, Conversational)", "gender": "Male", "region": "US"},
    {"id": "en-US-AriaNeural", "name": "🇺🇸 Aria (US - Professional, Clear)", "gender": "Female", "region": "US"},
    {"id": "en-GB-RyanNeural", "name": "🇬🇧 Ryan (UK - Academic, Articulate)", "gender": "Male", "region": "UK"},
    {"id": "en-GB-SoniaNeural", "name": "🇬🇧 Sonia (UK - Formal, Scholarly)", "gender": "Female", "region": "UK"},
    {"id": "en-AU-WilliamNeural", "name": "🇦🇺 William (Australia - Relaxed, Direct)", "gender": "Male", "region": "AU"},
]

