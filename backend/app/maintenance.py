"""Developer-only source reset with recoverable backups and physical index cleanup."""
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil


def reset_knowledge(store, engine, backup_root):
    backup = Path(backup_root) / datetime.now(timezone.utc).strftime('rag-reset-%Y%m%dT%H%M%S%fZ')
    backup.mkdir(parents=True, exist_ok=False)
    with store.archive.lock:
        rows = store.archive.export()
        from .db_core import backup as backup_database
        backup_database(store.archive.path, backup/'knowledge-before.sqlite')
        # Export original vectors too, including orphan points outside the archive.
        points = store.collection.get(include=['documents','metadatas','embeddings'])
        (backup/'sources.json').write_text(json.dumps(rows,ensure_ascii=False),encoding='utf-8')
        (backup/'vectors.json').write_text(json.dumps(points,ensure_ascii=False),encoding='utf-8')
        originals = []
        for row in rows:
            metadata = json.loads(row['metadata'])
            path = (store.archive.root / metadata['stored_name']).resolve()
            if path.parent != store.archive.root.resolve():
                raise ValueError('Invalid archived source path')
            if path.is_file():
                (backup/'files').mkdir(exist_ok=True)
                shutil.copy2(path,backup/'files'/path.name)
                originals.append(path)
        # Delete all physical points, not just IDs still listed in the archive.
        store.collection.clear()
        store.archive.clear()
        if hasattr(engine, 'clear_catalog'):
            engine.clear_catalog()
        for path in originals:
            path.unlink(missing_ok=True)
        # Old evaluation scores no longer describe the empty corpus.
        for index,path in enumerate({engine.history_path,engine.mirror_history_path,engine.golden_path}):
            path=Path(path)
            if path.is_file():shutil.copy2(path,backup/f'evaluation-{index}-{path.name}')
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text('[]\n',encoding='utf-8')
        store.last_ingested_source=None
    return {'sources_removed':len(rows),'vectors_removed':len(points['ids']),
            'remaining_vectors':store.collection.count(),'backup_dir':str(backup)}


def install_maintenance(app,store,engine,backup_root):
    from fastapi import HTTPException

    @app.delete('/api/rag/sources')
    async def reset_sources():
        # The authentication middleware restricts all /api/rag mutations to developers.
        try:
            return reset_knowledge(store,engine,backup_root)
        except (OSError,ValueError):
            raise HTTPException(503,'Pembersihan belum selesai. Cadangan dipertahankan; periksa penyimpanan lalu coba lagi.')
