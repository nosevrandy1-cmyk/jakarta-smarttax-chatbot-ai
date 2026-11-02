# Qdrant-only knowledge index

Implemented 2 November 2026. The active vector database is Qdrant; ChromaDB is removed from application code, dependency manifests, lockfile, and the installed runtime. SQLite remains responsible for accounts, sessions, chat history and the source archive. It is not a vector database migration target.

## Runtime architecture

Developer upload -> existing format/size/parsing checks -> original file and extracted archive -> hashing embeddings -> Qdrant vectors and payload -> grounded retrieval -> Ollama -> answer and source references.

- `backend/app/vector_store.py`: Qdrant persistence, metadata filtering, scroll pagination, upsert/delete/query and stable UUID mapping from original chunk IDs.
- `backend/app/rag_ingestion.py`: common PDF/table/reference-case knowledge store. Text, domain, document ID, physical page, sheet/row, content hash and contributor metadata are preserved.
- `backend/app/ollama_service.py`: retrieves from the Qdrant-backed knowledge store. Source events and JSON responses use `qdrant_sources`.
- Dashboard telemetry/chunk details/evaluation and source processing routes use the same store. The developer health endpoint exposes `qdrant`; obsolete `chromadb` health fields are removed.
- Legacy SQL/Qdrant fixture reindexing is removed. Startup never deletes or automatically rebuilds the active collection. `/api/reindex` upserts only approved/active archived sources without deleting the collection.
- A committed active archive ID remains required for retrieval. Failed, pending and rejected records cannot become evidence, including interrupted index writes.
- Embeddings remain the existing explicit application hashing vectors; this change does not introduce a trained embedding model or automatically improve semantic retrieval.

## Configuration

```
QDRANT_STORAGE_DIR=./qdrant_knowledge_storage
QDRANT_KNOWLEDGE_COLLECTION=jakarta_smarttax_knowledge
QDRANT_URL=
```

Relative storage paths resolve against the backend directory. Empty URL uses embedded local disk Qdrant. The app shares one client per path within a process; embedded mode supports one owning backend process, so do not run multiple workers or a separate maintenance client against the live directory. A separately administered server can use QDRANT_URL; embedded defaults expose no Qdrant HTTP service.

The old QDRANT_ACTIVE_COLLECTION and CHROMA settings are no longer used. Existing .env values unrelated to this migration were retained. Do not overwrite .env with the example on every start. Original uploads and source archive stay in backend/data/uploads. New Qdrant storage is ignored by Git.

## Data migration on this PC

A dated backup was written outside the repository under the local JST workspace `database-backups/qdrant-migration-20261102-103300`. It contains a JSON export of original IDs/vectors/text/metadata, a SQLite backup of the source archive and original uploaded files. No auth database or credentials are included.

Nine chunks from two active dummy PDFs were imported into the new Qdrant knowledge collection. IDs, text and metadata were verified after import. Existing normalized hashing vectors were reused. Original PDF bytes and stored source references were preserved. Legacy Chroma and old Qdrant directories are inactive rollback material; they are not read or reindexed by the new application. No source files, accounts or chat history were deleted.

For a future recovery, stop the backend first and use the supplied importer with an explicit backup path and destination:

```
uv run python scripts/import_vector_export.py --export <backup>/vectors.json --storage ./qdrant_knowledge_storage --collection jakarta_smarttax_knowledge --dimension 384
```

Restore the matching original-file/source archive backup as well if those files were lost. The importer needs Qdrant only, validates dimensions and IDs, verifies text/metadata, and upserts without deleting the target collection. It does not import untrusted data automatically at startup. Runtime data and backups are not committed.

## Verification

- 101 backend tests passed on Qdrant, including upload/archive, PDF pages, source activation/failure, auth, per-account history, reference handling and conversation alignment.
- Adapter-specific tests cover stable IDs and repeat imports, exact counts, metadata filters with no unrelated-domain fallback, dimensions, more than 256 scroll records, deletion, and persistence across independent processes.
- Export recovery CLI was tested twice against an isolated temporary Qdrant directory; all nine chunks were verified on both imports without duplication.
- Frontend TypeScript/noUnusedLocals and an isolated Next.js production build passed.
- uv lock/sync completed offline after removing ChromaDB and unused dependencies; uv pip check reports all installed packages compatible.
- Live health reports qdrant-local-disk and nine active PDF chunks, without a chromadb field.
- A live `/api/chat` request answered Kampus Arunika as Rp2.448.000 and returned references to page 3 and the dummy disclaimer on page 1, with six retrieved Qdrant sources. The test did not write an account conversation.
- No claim is made that this small migration test establishes model accuracy on real tax documents. OCR, complex-table recovery, retrieval benchmarking and trained embedding evaluation remain separate work.

## Security and operations

Existing developer authorization, localhost-only temporary auth mode, CSRF/Origin, rate limits and upload limits remain in place. Qdrant vectors and source archives are local runtime data, not encrypted by this application. Keep filesystem access restricted and back up originals plus archive/index together. Historical audit documents describe earlier technology and are retained as history; this document describes the current vector storage.
