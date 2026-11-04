from fastapi import HTTPException, Request
from fastapi.responses import FileResponse


def install_source_routes(app, knowledge_store, embedder):


    @app.get("/api/rag/sources")
    async def list_sources():
        return {"items": knowledge_store.archive.list()}


    @app.get("/api/rag/sources/{source_id}")
    async def source_detail(source_id: str):
        try:
            return knowledge_store.archive.detail(source_id)
        except KeyError:
            raise HTTPException(404, "Sumber tidak ditemukan.")


    @app.get("/api/rag/sources/{source_id}/file")
    async def source_file(source_id: str):
        try:
            path, name = knowledge_store.archive.file(source_id)
        except KeyError:
            raise HTTPException(404, "File sumber tidak ditemukan.")
        return FileResponse(path, filename=name, headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})


    @app.post("/api/rag/sources/{source_id}/process")
    async def process_source(source_id: str, request: Request):
        try:
            return knowledge_store.archive.activate(source_id, request.state.auth_user['id'],
                        knowledge_store.collection, embedder)
        except KeyError:
            raise HTTPException(404, "Sumber tidak ditemukan.")
        except ValueError as error:
            raise HTTPException(422, str(error))
        except Exception:
            raise HTTPException(503, "Pengindeksan belum berhasil. Sumber belum aktif; coba proses ulang.")
