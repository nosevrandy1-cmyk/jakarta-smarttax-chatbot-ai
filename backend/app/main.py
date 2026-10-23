from contextlib import asynccontextmanager
from typing import Any, Dict, List, Literal, Optional
import httpx
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from .config import (
    CORS_ORIGINS,
    DEEPSEEK_DRAFTING_MODEL,
    DEFAULT_CHAT_MODEL,
    OLLAMA_LOCAL_URL,
    OLLAMA_MODEL_PROFILES,
)
from .embedder import embedder
from .ollama_service import (
    CAPABILITY_MODES,
    run_smarttax_chat,
    stream_smarttax_chat,
)
from .tax_db import (
    TAX_THEMES,
    get_all_legal_corpus,
    get_all_sppt_records,
    get_regulasi_chunks,
    init_tax_db,
)
from .vector_store import vector_store


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_tax_db()
    vector_store.reindex_all()
    try:
        yield
    finally:
        vector_store.client.close()


app = FastAPI(
    title="Jakarta SmartTax 2026 API — Tim AI Jakarta SmartTax",
    description="Strictly grounded local RAG, legal basis retrieval, and regulatory drafting service (Gemma & DeepSeek on Ollama).",
    version="2.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)


@app.middleware("http")
async def security_headers_middleware(request: Request, call_next) -> Response:
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    return response


class ChatMessageInput(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(..., min_length=1, max_length=8000)


class ChatRequestInput(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    history: List[ChatMessageInput] = Field(default_factory=list, max_length=20)
    model: Optional[str] = Field(default=DEFAULT_CHAT_MODEL, max_length=80)
    tema_pajak: Optional[str] = Field(default="PBB-P2", max_length=20)
    mode_kapabilitas: Optional[str] = Field(default="konsultasi", max_length=32)


@app.get("/api/health")
async def health_check() -> Dict[str, Any]:
    local_models: List[str] = []
    ollama_running = False
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(f"{OLLAMA_LOCAL_URL}/api/tags")
            if r.status_code == 200:
                ollama_running = True
                data = r.json()
                local_models = [m.get("name", "") for m in data.get("models", [])]
    except Exception:
        ollama_running = False

    sppt_rows = get_all_sppt_records()
    reg_chunks = get_regulasi_chunks()
    legal_rows = get_all_legal_corpus()

    return {
        "status": "ok",
        "service": "Jakarta SmartTax 2026",
        "team": "Tim AI Jakarta SmartTax 2026",
        "region": "Provinsi DKI Jakarta",
        "themes": list(TAX_THEMES.values()),
        "capability_modes": list(CAPABILITY_MODES.values()),
        "strict_local_only": True,
        "ollama": {
            "running": ollama_running,
            "default_model": DEFAULT_CHAT_MODEL,
            "drafting_model": DEEPSEEK_DRAFTING_MODEL,
            "profiles": OLLAMA_MODEL_PROFILES,
            "installed_local_models": local_models,
        },
        "qdrant": {
            "mode": vector_store.mode,
            "collection": vector_store.collection_name,
            "records_indexed": len(sppt_rows),
            "regulasi_chunks": len(reg_chunks),
            "pasal_hukum_indexed": len(legal_rows),
        },
        "embedder": {
            "engine": embedder.engine_name,
            "dimension": embedder.dim,
        },
    }


@app.get("/api/korpus-hukum")
async def get_korpus_hukum_endpoint(tema_pajak: Optional[str] = None) -> Dict[str, Any]:
    tema = (tema_pajak or "").upper()
    rows = get_all_legal_corpus(tema if tema in TAX_THEMES else "")
    return {
        "tema_pajak": tema or "SEMUA",
        "total": len(rows),
        "items": rows,
    }


@app.post("/api/reindex")
async def reindex_endpoint() -> Dict[str, Any]:
    init_tax_db()
    stats = vector_store.reindex_all()
    return {"status": "reindexed", **stats}


@app.post("/api/chat")
async def chat_endpoint(req: ChatRequestInput) -> Dict[str, Any]:
    clean_msg = req.message.strip()
    if not clean_msg:
        raise HTTPException(status_code=400, detail="Pesan tidak boleh kosong.")
    tema = (req.tema_pajak or "PBB-P2").upper()
    if tema not in TAX_THEMES:
        tema = "PBB-P2"
    mode_kap = (req.mode_kapabilitas or "konsultasi").lower()
    history_dicts = [{"role": m.role, "content": m.content} for m in req.history]
    return await run_smarttax_chat(
        user_message=clean_msg,
        history=history_dicts,
        model=req.model or DEFAULT_CHAT_MODEL,
        tema_pajak=tema,
        mode_kapabilitas=mode_kap,
    )


@app.post("/api/chat/stream")
async def chat_stream_endpoint(req: ChatRequestInput) -> StreamingResponse:
    clean_msg = req.message.strip()
    if not clean_msg:
        raise HTTPException(status_code=400, detail="Pesan tidak boleh kosong.")
    tema = (req.tema_pajak or "PBB-P2").upper()
    if tema not in TAX_THEMES:
        tema = "PBB-P2"
    mode_kap = (req.mode_kapabilitas or "konsultasi").lower()
    history_dicts = [{"role": m.role, "content": m.content} for m in req.history]
    return StreamingResponse(
        stream_smarttax_chat(
            user_message=clean_msg,
            history=history_dicts,
            model=req.model or DEFAULT_CHAT_MODEL,
            tema_pajak=tema,
            mode_kapabilitas=mode_kap,
        ),
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
