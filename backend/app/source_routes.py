from fastapi import HTTPException, Request, Query
from fastapi.responses import FileResponse


def install_source_routes(app, knowledge_store, embedder):


    @app.get("/api/rag/sources")
    async def list_sources(offset: int = Query(0,ge=0), limit: int = Query(20,ge=1,le=50),
                           q: str = Query('',max_length=120), domain: str = Query('',max_length=20)):
        if domain and domain not in {'PBB-P2','PBJT','BPHTB','REKLAME','PAT'}:
            raise HTTPException(400,'Kategori pajak tidak valid.')
        return knowledge_store.archive.browse(offset,limit,q,domain)


    @app.get("/api/rag/sources/{source_id}")
    async def source_detail(source_id: str, offset: int = Query(0,ge=0), limit: int = Query(10,ge=1,le=20)):
        try:
            return knowledge_store.archive.browse_detail(source_id,offset,limit)
        except KeyError:
            raise HTTPException(404, "Sumber tidak ditemukan.")


    @app.get('/api/rag/sources/{source_id}/chunks/{chunk_id}')
    async def source_chunk(source_id: str, chunk_id: str):
        try:
            return knowledge_store.archive.read_chunk(source_id,chunk_id)
        except KeyError:
            raise HTTPException(404,'Bagian sumber tidak ditemukan.')


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
            knowledge_store.archive.activate(source_id, request.state.auth_user['id'],
                        knowledge_store.collection, embedder)
            return knowledge_store.archive.browse_detail(source_id)
        except KeyError:
            raise HTTPException(404, "Sumber tidak ditemukan.")
        except ValueError as error:
            raise HTTPException(422, str(error))
        except Exception:
            raise HTTPException(503, "Pengindeksan belum berhasil. Sumber belum aktif; coba proses ulang.")
