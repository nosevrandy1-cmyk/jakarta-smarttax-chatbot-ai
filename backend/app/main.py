from contextlib import asynccontextmanager
from typing import Any, Dict, List, Literal, Optional
import httpx
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from .config import CORS_ORIGINS, DEFAULT_CHAT_MODEL, OLLAMA_LOCAL_URL
from .embedder import embedder
from .ollama_service import chat_with_local_pbb, stream_chat_with_local_pbb
from .tax_db import (
    TAX_THEMES,
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
    title="Bapenda DKI Jakarta Tax Service API",
    description="Local RAG and structured SQLite lookup service for DKI Jakarta regional taxes.",
    version="2.1.0",
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

    return {
        "status": "ok",
        "region": "Provinsi DKI Jakarta",
        "themes": list(TAX_THEMES.values()),
        "strict_local_only": True,
        "ollama": {
            "running": ollama_running,
            "default_model": DEFAULT_CHAT_MODEL,
            "installed_local_models": local_models,
        },
        "qdrant": {
            "mode": vector_store.mode,
            "collection": vector_store.collection_name,
            "records_indexed": len(sppt_rows),
            "regulasi_chunks": len(reg_chunks),
        },
        "embedder": {
            "engine": embedder.engine_name,
            "dimension": embedder.dim,
        },
    }


@app.post("/api/chat")
async def chat_endpoint(req: ChatRequestInput) -> Dict[str, Any]:
    clean_msg = req.message.strip()
    if not clean_msg:
        raise HTTPException(status_code=400, detail="Pesan tidak boleh kosong.")
    tema = (req.tema_pajak or "PBB-P2").upper()
    if tema not in TAX_THEMES:
        tema = "PBB-P2"
    history_dicts = [{"role": m.role, "content": m.content} for m in req.history]
    return await chat_with_local_pbb(
        user_message=clean_msg,
        history=history_dicts,
        model=req.model or DEFAULT_CHAT_MODEL,
        tema_pajak=tema,
    )


@app.post("/api/chat/stream")
async def chat_stream_endpoint(req: ChatRequestInput) -> StreamingResponse:
    clean_msg = req.message.strip()
    if not clean_msg:
        raise HTTPException(status_code=400, detail="Pesan tidak boleh kosong.")
    tema = (req.tema_pajak or "PBB-P2").upper()
    if tema not in TAX_THEMES:
        tema = "PBB-P2"
    history_dicts = [{"role": m.role, "content": m.content} for m in req.history]
    return StreamingResponse(
        stream_chat_with_local_pbb(
            user_message=clean_msg,
            history=history_dicts,
            model=req.model or DEFAULT_CHAT_MODEL,
            tema_pajak=tema,
        ),
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
