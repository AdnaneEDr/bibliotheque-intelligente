"""Configuration locale, sans mot de passe inclus dans les sources."""
import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def load_env():
    path = ROOT / '.env'
    if path.exists():
        for line in path.read_text(encoding='utf-8-sig').splitlines():
            if line.strip() and not line.lstrip().startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))

load_env()

@dataclass
class Settings:
    data_dir: Path = ROOT / 'data'
    db_backend: str = os.getenv('DB_BACKEND', 'oracle')
    oracle_user: str = os.getenv('ORACLE_USER', '')
    oracle_password: str = os.getenv('ORACLE_PASSWORD', '')
    oracle_dsn: str = os.getenv('ORACLE_DSN', 'localhost:1521/orcl')
    ollama_url: str = os.getenv('OLLAMA_URL', 'http://127.0.0.1:11434')
    llm_model: str = os.getenv('LLM_MODEL', 'qwen3:4b')
    embedding_model: str = os.getenv('EMBEDDING_MODEL', 'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')
    chunk_size: int = int(os.getenv('CHUNK_SIZE', '900'))
    chunk_overlap: int = int(os.getenv('CHUNK_OVERLAP', '150'))
    top_k: int = int(os.getenv('TOP_K', '5'))
    max_distance: float = float(os.getenv('MAX_DISTANCE', '0.45'))
    max_pdf_mb: int = int(os.getenv('MAX_PDF_MB', '20'))
    token_hours: int = 8

    def __post_init__(self):
        self.data_dir = Path(self.data_dir)
        if self.db_backend not in {'sqlite', 'oracle'}:
            raise ValueError('DB_BACKEND doit être sqlite ou oracle')
        if not 0 <= self.chunk_overlap < self.chunk_size or self.top_k < 1:
            raise ValueError('Paramètres de découpage ou recherche invalides')

