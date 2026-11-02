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
    knowledge_store,
)
from .tax_db import (
    TAX_THEMES,
    get_all_legal_corpus,
    get_all_sppt_records,
    get_regulasi_chunks,
    init_tax_db,
)

from .auth import install_auth
from .chat_history import install_history
from .source_routes import install_source_routes
from .chat_models import ChatRequestInput

MAX_UPLOAD_BYTES = 20 * 1024 * 1024


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_all_sppt_records()
    get_all_legal_corpus()
    eval_engine.load_history()
    try:
        yield
    finally:
        knowledge_store.client.close()


app = FastAPI(
    title="Jakarta SmartTax 2026 API — Tim AI Jakarta SmartTax",
    description="Strictly grounded local RAG, Qdrant multi-source ingestion, and AI Intelligence Audit Engine (Gemma 4 12B on Ollama).",
    version="2.4.0",
    lifespan=lifespan,
)

install_auth_settings, _auth_store = install_auth(app)
install_history(app, _auth_store)
install_source_routes(app, knowledge_store, embedder)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[install_auth_settings.public_url],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "OPTIONS"],
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
    knowledge_telemetry = knowledge_store.get_collection_telemetry()

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
        "qdrant": {
            "mode": knowledge_store.mode,
            "collection": knowledge_telemetry["collection"],
            "total_chunks": knowledge_telemetry["total_chunks"],
            "domain_coverage_percentage": knowledge_telemetry["domain_coverage_percentage"],
            "by_source_type": knowledge_telemetry["by_source_type"],
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
    stats = knowledge_store.reindex_active_sources()
    knowledge_stats = knowledge_store.get_collection_telemetry()
    return {"status": "reindexed", **stats, "qdrant": knowledge_stats}


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
    return knowledge_store.get_chunk_details(source_id=source_id, query=q, offset=offset, limit=limit)


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


def activate_uploaded_source(summary, request):
    try:
        knowledge_store.archive.activate(summary['source_id'], request.state.auth_user['id'],
                                      knowledge_store.collection, embedder)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    except Exception:
        raise HTTPException(503, "Pengindeksan belum berhasil. Sumber belum aktif; coba proses ulang.") from None
    return {**summary, 'review_status': 'approved', 'activation_mode': 'automatic',
            'total_collection_chunks': knowledge_store.get_collection_telemetry()['total_chunks']}


@app.post("/api/rag/ingest-pdf")
async def ingest_pdf_endpoint(
    request: Request,
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
        summary = knowledge_store.ingest_pdf(
            file_bytes=file_bytes,
            filename=raw_name,
            domain=domain,
            contributor=kontributor,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    summary = activate_uploaded_source(summary, request)
    snapshot = None
    dashboard = await eval_engine.get_dashboard_state()
    return {
        "status": "active",
        "ingestion": summary,
        "snapshot": snapshot,
        "dashboard": dashboard,
    }


@app.post("/api/rag/ingest-excel")
async def ingest_excel_endpoint(
    request: Request,
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
        summary = knowledge_store.ingest_excel(
            file_bytes=file_bytes,
            filename=raw_name,
            category=category,
            contributor=kontributor,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    summary = activate_uploaded_source(summary, request)
    snapshot = None
    dashboard = await eval_engine.get_dashboard_state()
    return {
        "status": "active",
        "ingestion": summary,
        "snapshot": snapshot,
        "dashboard": dashboard,
    }


@app.post("/api/rag/learn-reasoning")
async def learn_reasoning_endpoint(payload: LearnReasoningPayload, request: Request) -> Dict[str, Any]:
    summary = knowledge_store.ingest_user_reasoning(payload)
    summary = activate_uploaded_source(summary, request)
    snapshot = None
    dashboard = await eval_engine.get_dashboard_state()
    return {
        "status": "active",
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
