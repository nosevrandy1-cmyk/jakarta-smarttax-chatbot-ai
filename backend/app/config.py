import os
from pathlib import Path
from typing import List

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
QDRANT_STORAGE_DIR = BASE_DIR / "qdrant_storage"

OLLAMA_LOCAL_URL = os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
OLLAMA_CLOUD_URL = os.getenv("OLLAMA_CLOUD_URL", "https://ollama.com").rstrip("/")
OLLAMA_API_KEY = os.getenv("OLLAMA_API_KEY", "").strip()

DEFAULT_CHAT_MODEL = os.getenv("OLLAMA_MODEL", "gemma4:cloud")
OLLAMA_EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "embeddinggemma")

QDRANT_URL = os.getenv("QDRANT_URL", "").strip()
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "pbb_p2_local_kb")

TRANSFORMERS_MODEL_NAME = os.getenv(
    "TRANSFORMERS_MODEL_NAME",
    "bert-base-multilingual-cased",
)
VECTOR_DIM = 384

CORS_ORIGINS: List[str] = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000",
    ).split(",")
    if origin.strip()
]
