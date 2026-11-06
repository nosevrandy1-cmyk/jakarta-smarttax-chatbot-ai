import json
import asyncio
from fastapi.concurrency import run_in_threadpool
from .markdown_import import parse_markdown, markdown_chunks, import_progress
from datetime import datetime, timezone
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
    chat_context_policy,
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
    init_tax_db,
)

from .auth import install_auth
from .chat_history import install_history
from .room_memory import install_room_memory, continuation_context
from .source_routes import install_source_routes
from .maintenance import install_maintenance
from .config import BASE_DIR
from .chat_models import ChatRequestInput
from .room_context import resolve_room_history
from .context_budget import room_fits

MAX_UPLOAD_BYTES = 20 * 1024 * 1024


@asynccontextmanager
async def lifespan(app: FastAPI):
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
install_room_memory(app, _auth_store)
install_source_routes(app, knowledge_store, embedder)
install_maintenance(app, knowledge_store, eval_engine, BASE_DIR / ".runtime-backups")
from .operations import install_operations
from .ollama_service import inference_queue
_operations = install_operations(app, knowledge_store, inference_queue, install_auth_settings)

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
        return {"status": "ok", "context_policy": chat_context_policy(), "ollama": {"running": ollama_running,
            "default_model": DEFAULT_CHAT_MODEL, "installed_local_models": local_models}}
    knowledge_telemetry = await run_in_threadpool(knowledge_store.get_collection_telemetry)

    return {
        "status": "ok",
        "context_policy": chat_context_policy(),
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
async def get_rag_telemetry_endpoint(include_details: bool = Query(False)) -> Dict[str, Any]:
    state = await eval_engine.get_dashboard_state()
    if not include_details and state.get('latest_snapshot'):
        state = {**state, 'latest_snapshot': {**state['latest_snapshot'], 'items': [], 'ingested_source_meta': {}}}
    return state


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



markdown_import_lock = asyncio.Lock()

@asynccontextmanager
async def source_processing(kind):
    if markdown_import_lock.locked():
        raise HTTPException(409, 'Sumber lain sedang diproses. Tunggu sampai selesai.')
    async with markdown_import_lock:
        import_progress.update(phase='checking', kind=kind, total=1, completed=0, failed=0, skipped=0)
        try:
            yield
        except BaseException:
            import_progress.update(phase='failed', failed=1)
            raise
        else:
            import_progress.update(phase='completed', completed=1)


@app.get('/api/rag/import-status')
async def markdown_import_status(response: Response):
    response.headers['Cache-Control'] = 'no-store'
    return import_progress.snapshot()


@app.post('/api/rag/ingest-markdown')
async def ingest_markdown_endpoint(request: Request, file: UploadFile = File(...),
                                   domain: str = Form('PBB-P2'), kontributor: str = Form(''),
                                   preview: bool = Form(True)):
    if domain not in {'PBB-P2','JPB','PBJT','BPHTB','REKLAME','PAT'}:
        raise HTTPException(400, 'Kategori pajak tidak valid.')
    name = Path(file.filename or '').name
    if not name.lower().endswith('.md'):
        raise HTTPException(400, 'Gunakan file .md UTF-8.')
    if markdown_import_lock.locked():
        raise HTTPException(409, 'Impor Markdown sedang berjalan. Tunggu sampai selesai.')
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if markdown_import_lock.locked():
        raise HTTPException(409, 'Impor Markdown sedang berjalan. Tunggu sampai selesai.')
    async with markdown_import_lock:
        try:
            import_progress.update(phase="checking", kind="markdown", total=0, completed=0, failed=0, skipped=0)
            try:
                records = await run_in_threadpool(parse_markdown, content, name)
                prepared = await run_in_threadpool(lambda: [(rec, markdown_chunks(rec, knowledge_store.splitter)) for rec in records])
                if sum(len(chunks) for _, chunks in prepared) > 20000:
                    raise ValueError('Paket melebihi 20.000 bagian teks; pisahkan paket.')
            except ValueError as exc:
                import_progress.update(phase="failed")
                raise HTTPException(422, str(exc)) from exc
            inventory = await run_in_threadpool(knowledge_store.archive.list)
            existing = {item.get('markdown_digest'): item for item in inventory if item.get('domain') == domain}
            sources = [{'title':rec['title'], 'url':rec['url'], 'chunks':len(chunks),
                        'pages':len({p for p,_,_ in chunks if p is not None}),
                        'duplicate':rec['digest'] in existing and existing[rec['digest']].get('status') == 'approved'} for rec,chunks in prepared]
            import_progress.update(total=len(sources))
            if preview:
                import_progress.update(phase="ready")
                return {'status':'preview', 'sources':sources, 'source_count':len(sources),
                        'chunk_count':sum(s['chunks'] for s in sources)}
            results = []
            import_progress.update(phase="indexing")
            for rec, chunks in prepared:
                prior = existing.get(rec['digest'])
                if prior and prior.get('status') == 'approved':
                    results.append({'title':rec['title'],'status':'skipped','source_id':prior['id']})
                    import_progress.update(completed=len(results), skipped=sum(r["status"] == "skipped" for r in results))
                    continue
                source_id = None
                try:
                    metas = [{'source_type':'pdf_regulasi','source_format':'markdown',
                              'doc_name':rec['title'],'domain':domain,
                              'tema_pajak':'PBB-P2' if domain == 'JPB' else domain,
                              'contributor':kontributor.strip()[:120], 'source_url':rec['url'],
                              'markdown_digest':rec['digest'], 'declared_hash':rec['declared_hash'],
                              'package_name':name, 'extraction_engine':rec['extraction_engine'],
                              'ingested_at':datetime.now(timezone.utc).isoformat(),
                              'chunk_index':i, **({'page_number':p} if p else {}), 'section':h}
                             for i,(p,h,t) in enumerate(chunks)]
                    texts = [f"[SUMBER REGULASI: {rec['title']}]\n{h}\n{t}" for p,h,t in chunks]
                    source_id = prior['id'] if prior else await run_in_threadpool(knowledge_store.archive.stage, texts, metas,
                                                         rec['original'], 'source.md')
                    await run_in_threadpool(knowledge_store.archive.activate, source_id,
                                           request.state.auth_user['id'],knowledge_store.collection,embedder)
                    existing[rec['digest']] = {'id':source_id,'status':'approved'}
                    results.append({'title':rec['title'],'status':'active','source_id':source_id})
                except Exception:
                    results.append({'title':rec['title'],'status':'failed','source_id':source_id})
                import_progress.update(completed=len(results), failed=sum(r["status"] == "failed" for r in results))
            import_progress.update(phase="completed")
            return {'status':'completed', 'sources':results, 'dashboard':await eval_engine.get_dashboard_state()}
        except BaseException:
            import_progress.update(phase="failed")
            raise


@app.post("/api/rag/ingest-pdf")
async def ingest_pdf_endpoint(
    request: Request,
    file: UploadFile = File(...),
    domain: str = Form("PBB-P2"),
    kontributor: str = Form("Tim Regulasi Bapenda"),
    auto_evaluate: bool = Form(True),
) -> Dict[str, Any]:
    async with source_processing('pdf'):
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
            summary = await run_in_threadpool(knowledge_store.ingest_pdf,
                file_bytes=file_bytes,
                filename=raw_name,
                domain=domain,
                contributor=kontributor,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        import_progress.update(phase='indexing')
        summary = await run_in_threadpool(activate_uploaded_source, summary, request)
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
    async with source_processing('table'):
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
            summary = await run_in_threadpool(knowledge_store.ingest_excel,
                file_bytes=file_bytes,
                filename=raw_name,
                category=category,
                contributor=kontributor,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        import_progress.update(phase='indexing')
        summary = await run_in_threadpool(activate_uploaded_source, summary, request)
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
    async with source_processing('case'):
        summary = await run_in_threadpool(knowledge_store.ingest_user_reasoning, payload)
        import_progress.update(phase='indexing')
        summary = await run_in_threadpool(activate_uploaded_source, summary, request)
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


def check_room_context(req: ChatRequestInput, request: Request):
    incoming = [m.model_dump(exclude_none=True) for m in req.history]
    room = _auth_store.history.room(request.state.auth_user['id'], req.room_id) if req.room_id else None
    messages = resolve_room_history(incoming, room, req.message)
    policy = chat_context_policy()
    if not room_fits(messages, req.message, policy):
        raise HTTPException(status_code=409, detail={"code":"room_context_limit",
            "message":"Konteks percakapan ini sudah penuh. Lanjutkan di chat baru.", "context_policy":policy})
    return messages


@app.post("/api/chat")
async def chat_endpoint(req: ChatRequestInput, request: Request) -> Dict[str, Any]:
    history_dicts = await run_in_threadpool(check_room_context, req, request)
    clean_msg = req.message.strip()
    if not clean_msg:
        raise HTTPException(status_code=400, detail="Pesan tidak boleh kosong.")
    tema = (req.tema_pajak or "PBB-P2").upper()
    if tema not in TAX_THEMES:
        tema = "PBB-P2"
    mode_kap = (req.mode_kapabilitas or "konsultasi").lower()
    memory = continuation_context(_auth_store, request.state.auth_user["id"], req.room_id)
    return await run_smarttax_chat(
        user_message=clean_msg,
        actor_id=request.state.auth_user["id"], room_id=req.room_id,
        history=history_dicts,
        memory=memory,
        model=(req.model or DEFAULT_CHAT_MODEL) if install_auth_settings.is_developer(request.state.auth_user) else DEFAULT_CHAT_MODEL,
        tema_pajak=tema,
        mode_kapabilitas=mode_kap,
    )


@app.post("/api/chat/stream")
async def chat_stream_endpoint(req: ChatRequestInput, request: Request) -> StreamingResponse:
    history_dicts = await run_in_threadpool(check_room_context, req, request)
    clean_msg = req.message.strip()
    if not clean_msg:
        raise HTTPException(status_code=400, detail="Pesan tidak boleh kosong.")
    tema = (req.tema_pajak or "PBB-P2").upper()
    if tema not in TAX_THEMES:
        tema = "PBB-P2"
    mode_kap = (req.mode_kapabilitas or "konsultasi").lower()
    memory = continuation_context(_auth_store, request.state.auth_user["id"], req.room_id)
    return StreamingResponse(
        stream_smarttax_chat(
            user_message=clean_msg,
            actor_id=request.state.auth_user["id"], room_id=req.room_id,
            history=history_dicts,
            memory=memory,
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
