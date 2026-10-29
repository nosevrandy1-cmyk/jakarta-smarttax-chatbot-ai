from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from fastapi import FastAPI, File, Form, HTTPException, Query, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import httpx
from pydantic import BaseModel, Field

from .config import (
    DEEPSEEK_DRAFTING_MODEL,
    DEFAULT_CHAT_MODEL,
    HARDWARE_PROFILE,
    OLLAMA_LOCAL_URL,
    OLLAMA_MODEL_PROFILES,
)
from .embedder import embedder
from .eval_engine import eval_engine
from .ollama_service import (
    CAPABILITY_MODES,
    run_smarttax_chat,
    stream_smarttax_chat,
)
from .rag_ingestion import (
    LearnReasoningPayload,
    chroma_store,
)
from .tax_db import (
    TAX_THEMES,
    get_all_legal_corpus,
    get_all_sppt_records,
    get_regulasi_chunks,
    init_tax_db,
)
from .vector_store import vector_store

from .auth import install_auth
from .chat_history import install_history

MAX_UPLOAD_BYTES = 20 * 1024 * 1024


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_all_sppt_records()
    get_all_legal_corpus()
    vector_store.reindex_all()
    eval_engine.load_history()
    try:
        yield
    finally:
        vector_store.client.close()


app = FastAPI(
    title="Jakarta SmartTax 2026 API — Tim AI Jakarta SmartTax",
    description="Strictly grounded local RAG, ChromaDB multi-source ingestion, and AI Intelligence Audit Engine (Gemma 4 12B on Ollama).",
    version="2.4.0",
    lifespan=lifespan,
)

install_auth_settings, _auth_store = install_auth(app)
install_history(app, _auth_store)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[install_auth_settings.public_url],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-CSRF-Token", "X-JST-Account-ID"],
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


class EvaluateRequestInput(BaseModel):
    trigger_event: str = Field(
        default="Manual Benchmark Evaluation", min_length=3, max_length=160
    )
    use_live_llm: bool = Field(default=False)


@app.get("/api/health")
async def health_check(request: Request) -> Dict[str, Any]:
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

    if not install_auth_settings.is_developer(request.state.auth_user):
        return {"status": "ok", "ollama": {"running": ollama_running,
            "default_model": DEFAULT_CHAT_MODEL, "installed_local_models": local_models}}
    sppt_rows = get_all_sppt_records()
    reg_chunks = get_regulasi_chunks()
    legal_rows = get_all_legal_corpus()
    chroma_telemetry = chroma_store.get_collection_telemetry()

    return {
        "status": "ok",
        "service": "Jakarta SmartTax 2026",
        "team": "Tim AI Jakarta SmartTax 2026",
        "region": "Provinsi DKI Jakarta",
        "themes": list(TAX_THEMES.values()),
        "capability_modes": list(CAPABILITY_MODES.values()),
        "strict_local_only": True,
        "hardware": HARDWARE_PROFILE,
        "ollama": {
            "running": ollama_running,
            "default_model": DEFAULT_CHAT_MODEL,
            "drafting_model": DEEPSEEK_DRAFTING_MODEL,
            "profiles": OLLAMA_MODEL_PROFILES,
            "installed_local_models": local_models,
        },
        "chromadb": {
            "collection": chroma_telemetry["collection"],
            "total_chunks": chroma_telemetry["total_chunks"],
            "domain_coverage_percentage": chroma_telemetry["domain_coverage_percentage"],
            "by_source_type": chroma_telemetry["by_source_type"],
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
    chroma_stats = chroma_store.get_collection_telemetry()
    return {"status": "reindexed", **stats, "chromadb": chroma_stats}


@app.get("/api/rag/telemetry")
async def get_rag_telemetry_endpoint() -> Dict[str, Any]:
    return await eval_engine.get_dashboard_state()


@app.get("/api/rag/chunks")
async def get_source_chunks_endpoint(
    source_id: Optional[str] = Query(None, max_length=100),
    q: str = Query("", max_length=200),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
) -> Dict[str, Any]:
    return chroma_store.get_chunk_details(source_id=source_id, query=q, offset=offset, limit=limit)


@app.get("/api/rag/golden-dataset")
async def get_golden_dataset_endpoint() -> Dict[str, Any]:
    items = eval_engine.load_golden_dataset()
    return {"total": len(items), "items": items}


@app.post("/api/rag/evaluate")
@app.post("/api/eval/run")
async def run_benchmark_evaluation_endpoint(
    req: Optional[EvaluateRequestInput] = None,
) -> Dict[str, Any]:
    payload = req or EvaluateRequestInput()
    try:
        snapshot = await eval_engine.run_evaluation(
            trigger_event=payload.trigger_event,
            use_live_llm=payload.use_live_llm,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    dashboard = await eval_engine.get_dashboard_state()
    return {
        "status": "evaluated",
        "snapshot": snapshot,
        "dashboard": dashboard,
    }


@app.post("/api/rag/ingest-pdf")
async def ingest_pdf_endpoint(
    file: UploadFile = File(...),
    domain: str = Form("PBB-P2"),
    kontributor: str = Form("Tim Regulasi Bapenda"),
    auto_evaluate: bool = Form(True),
) -> Dict[str, Any]:
    raw_name = Path(file.filename or "regulasi.pdf").name
    if not raw_name.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400, detail="Hanya file berformat .pdf yang diizinkan."
        )
    file_bytes = await file.read(MAX_UPLOAD_BYTES + 1)
    if not file_bytes or len(file_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=400,
            detail="Ukuran file PDF tidak valid atau melebihi batas 20MB.",
        )
    if not file_bytes.startswith(b"%PDF"):
        raise HTTPException(
            status_code=400, detail="Header biner file bukan dokumen PDF yang valid."
        )

    try:
        summary = chroma_store.ingest_pdf(
            file_bytes=file_bytes,
            filename=raw_name,
            domain=domain,
            contributor=kontributor,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    snapshot = None
    if auto_evaluate and eval_engine.evaluation_readiness()["ready"]:
        snapshot = await eval_engine.run_evaluation(
            trigger_event=f"Ingesti PDF Regulasi: {raw_name} ({summary['domain']})",
            ingested_source_meta=summary,
        )
    dashboard = await eval_engine.get_dashboard_state()
    return {
        "status": "ingested",
        "ingestion": summary,
        "snapshot": snapshot,
        "dashboard": dashboard,
    }


@app.post("/api/rag/ingest-excel")
async def ingest_excel_endpoint(
    file: UploadFile = File(...),
    category: str = Form("PBB-P2"),
    kontributor: str = Form("Analis Data Pajak"),
    auto_evaluate: bool = Form(True),
) -> Dict[str, Any]:
    raw_name = Path(file.filename or "data_pajak.xlsx").name
    suffix = Path(raw_name).suffix.lower()
    if suffix not in (".xlsx", ".xls", ".csv"):
        raise HTTPException(
            status_code=400,
            detail="Hanya file berformat .xlsx, .xls, atau .csv yang diizinkan.",
        )
    file_bytes = await file.read(MAX_UPLOAD_BYTES + 1)
    if not file_bytes or len(file_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=400,
            detail="Ukuran file tabel tidak valid atau melebihi batas 20MB.",
        )

    try:
        summary = chroma_store.ingest_excel(
            file_bytes=file_bytes,
            filename=raw_name,
            category=category,
            contributor=kontributor,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    snapshot = None
    if auto_evaluate and eval_engine.evaluation_readiness()["ready"]:
        snapshot = await eval_engine.run_evaluation(
            trigger_event=f"Ingesti Tabel Pajak: {raw_name} ({summary['domain']})",
            ingested_source_meta=summary,
        )
    dashboard = await eval_engine.get_dashboard_state()
    return {
        "status": "ingested",
        "ingestion": summary,
        "snapshot": snapshot,
        "dashboard": dashboard,
    }


@app.post("/api/rag/learn-reasoning")
async def learn_reasoning_endpoint(payload: LearnReasoningPayload) -> Dict[str, Any]:
    summary = chroma_store.ingest_user_reasoning(payload)
    snapshot = None
    if eval_engine.evaluation_readiness()["ready"]:
        snapshot = await eval_engine.run_evaluation(
            trigger_event=f"Penambahan kasus rujukan: {summary['domain']}",
            ingested_source_meta=summary,
        )
    dashboard = await eval_engine.get_dashboard_state()
    return {
        "status": "learned",
        "ingestion": summary,
        "snapshot": snapshot,
        "dashboard": dashboard,
    }


@app.post("/api/rag/ingest-sample")
@app.post("/api/rag/reset-baseline")
async def demo_data_disabled_endpoint() -> Dict[str, Any]:
    raise HTTPException(status_code=410, detail="Data contoh dinonaktifkan. Gunakan sumber data resmi.")


@app.post("/api/chat")
async def chat_endpoint(req: ChatRequestInput, request: Request) -> Dict[str, Any]:
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
        model=(req.model or DEFAULT_CHAT_MODEL) if install_auth_settings.is_developer(request.state.auth_user) else DEFAULT_CHAT_MODEL,
        tema_pajak=tema,
        mode_kapabilitas=mode_kap,
    )


@app.post("/api/chat/stream")
async def chat_stream_endpoint(req: ChatRequestInput, request: Request) -> StreamingResponse:
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
            model=(req.model or DEFAULT_CHAT_MODEL) if install_auth_settings.is_developer(request.state.auth_user) else DEFAULT_CHAT_MODEL,
            tema_pajak=tema,
            mode_kapabilitas=mode_kap,
        ),
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
