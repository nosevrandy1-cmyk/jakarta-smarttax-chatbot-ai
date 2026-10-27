import os
from pathlib import Path
from typing import Any, Dict, List

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env", override=False)

DATA_DIR = BASE_DIR / "data"
QDRANT_STORAGE_DIR = BASE_DIR / "qdrant_storage"
CHROMA_STORAGE_DIR = Path(
    os.getenv("CHROMA_PERSIST_DIR", str(BASE_DIR / "smarttax_vectordb"))
).resolve()
CHROMA_COLLECTION = os.getenv("CHROMA_COLLECTION", "jakarta_smarttax_knowledge")

GOLDEN_DATASET_PATH = DATA_DIR / "golden_dataset.json"
INTELLIGENCE_HISTORY_PATH = BASE_DIR / "dashboard_intelligence_history.json"
UPLOAD_STAGING_DIR = DATA_DIR / "uploads"

OLLAMA_LOCAL_URL = os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
OLLAMA_SECONDARY_URL = os.getenv("OLLAMA_SECONDARY_HOST", OLLAMA_LOCAL_URL).rstrip("/")
OLLAMA_CLOUD_URL = os.getenv("OLLAMA_CLOUD_URL", "https://ollama.com").rstrip("/")
OLLAMA_API_KEY = os.getenv("OLLAMA_API_KEY", "").strip()

DEFAULT_CHAT_MODEL = os.getenv("OLLAMA_MODEL", "gemma4:12b")
DEEPSEEK_DRAFTING_MODEL = os.getenv("OLLAMA_DRAFTING_MODEL", DEFAULT_CHAT_MODEL)
OLLAMA_TIMEOUT = float(os.getenv("OLLAMA_TIMEOUT", "300"))

# Cap num_ctx at 4096 and enforce q8_0 KV cache to prevent spillover on RTX 5060 Ti (8GB VRAM).
OLLAMA_NUM_CTX = int(os.getenv("OLLAMA_NUM_CTX", "4096"))
OLLAMA_TEMPERATURE = float(os.getenv("OLLAMA_TEMPERATURE", "1.0"))
OLLAMA_TOP_P = float(os.getenv("OLLAMA_TOP_P", "0.95"))
OLLAMA_TOP_K = int(os.getenv("OLLAMA_TOP_K", "64"))
OLLAMA_THINK = os.getenv("OLLAMA_THINK", "true").lower() in ("1", "true", "yes")
OLLAMA_FLASH_ATTENTION = os.getenv("OLLAMA_FLASH_ATTENTION", "1")
OLLAMA_KV_CACHE_TYPE = os.getenv("OLLAMA_KV_CACHE_TYPE", "q8_0")
OLLAMA_EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")

HARDWARE_PROFILE: Dict[str, Any] = {
    "system": "MSI Infinite S3",
    "gpu": "NVIDIA RTX 5060 Ti",
    "vram_gb": 8,
    "primary_llm": DEFAULT_CHAT_MODEL,
    "embedding_model": OLLAMA_EMBED_MODEL,
    "flash_attention": OLLAMA_FLASH_ATTENTION == "1",
    "kv_cache_type": OLLAMA_KV_CACHE_TYPE,
    "num_ctx": OLLAMA_NUM_CTX,
    "temperature": OLLAMA_TEMPERATURE,
    "top_p": OLLAMA_TOP_P,
    "top_k": OLLAMA_TOP_K,
}

OLLAMA_MODEL_PROFILES: Dict[str, Dict[str, str]] = {
    "gemma": {
        "id": DEFAULT_CHAT_MODEL,
        "host": OLLAMA_LOCAL_URL,
        "label": "Gemma 4 12B (RAG Tarif, Rumus & Objek)",
        "role": "Konsultasi Tarif, Simulasi Rumus & Data Pajak",
    },
    "deepseek": {
        "id": DEEPSEEK_DRAFTING_MODEL,
        "host": OLLAMA_SECONDARY_URL,
        "label": f"{DEEPSEEK_DRAFTING_MODEL} (Analisis Pasal & Perumusan Hukum)",
        "role": "Telusur Pasal, Dasar Hukum & Legal Drafting",
    },
}

QDRANT_URL = os.getenv("QDRANT_URL", "").strip()
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "jakarta_smarttax_kb")

TRANSFORMERS_MODEL_NAME = os.getenv(
    "TRANSFORMERS_MODEL_NAME",
    "bert-base-multilingual-cased",
)
VECTOR_DIM = 384

TAX_DOMAINS: List[str] = ["PBB-P2", "JPB", "PBJT", "BPHTB", "REKLAME", "PAT"]
RAG_SOURCE_TYPES: List[str] = ["pdf_regulasi", "excel_data", "user_reasoning"]

CORS_ORIGINS: List[str] = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000",
    ).split(",")
    if origin.strip()
]
