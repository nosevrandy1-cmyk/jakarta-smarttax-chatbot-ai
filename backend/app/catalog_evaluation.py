"""Import legacy evaluation JSON once; runtime rows live in knowledge.sqlite."""
import json
import hashlib
import time
import uuid


def import_once(archive, golden_path, history_path):
    with archive.connect() as db:
        golden = json.loads(golden_path.read_text(encoding='utf-8')) if golden_path.is_file() else []
        key = 'golden:' + hashlib.sha256(json.dumps(golden,sort_keys=True).encode()).hexdigest()
        if not isinstance(golden,list):
            raise ValueError('Dataset evaluasi harus berupa daftar.')
        if not db.execute('SELECT 1 FROM legacy_imports WHERE key=?',(key,)).fetchone():
            save_golden(db,golden)
            # A changed operator-managed JSON file is an import input, never an
            # automatic fallback from an older mirror or an old dataset hash.
            db.execute("DELETE FROM legacy_imports WHERE key LIKE 'golden:%'")
            db.execute('INSERT INTO legacy_imports VALUES(?,?)',(key,int(time.time()*1000)))
        if not db.execute("SELECT 1 FROM legacy_imports WHERE key='evaluation-v1'").fetchone():
            history = json.loads(history_path.read_text(encoding='utf-8')) if history_path.is_file() else []
            if not isinstance(history,list):
                raise ValueError('Format riwayat evaluasi lama tidak valid.')
            save_history(db,history)
            db.execute('INSERT INTO legacy_imports VALUES(?,?)',('evaluation-v1',int(time.time()*1000)))


def save_golden(db,items):
    db.execute('DELETE FROM golden_items')
    for index,item in enumerate(items):
        db.execute('INSERT INTO golden_items VALUES(?,?,?)',(str(item.get('id',uuid.uuid4())),index,json.dumps(item,ensure_ascii=False)))


def save_history(db,history):
    db.execute('DELETE FROM evaluation_snapshots')
    for index,snapshot in enumerate(history):
        identity = str(snapshot.get('snapshot_id',uuid.uuid4()))
        meta = {k:v for k,v in snapshot.items() if k!='items'}
        db.execute('INSERT INTO evaluation_snapshots VALUES(?,?,?)',(identity,index,json.dumps(meta,ensure_ascii=False)))
        for position,item in enumerate(snapshot.get('items',[])):
            db.execute('INSERT INTO evaluation_snapshot_items VALUES(?,?,?)',(identity,position,json.dumps(item,ensure_ascii=False)))


def load_history(db):
    result = []
    for row in db.execute('SELECT * FROM evaluation_snapshots ORDER BY position'):
        snapshot = json.loads(row['metadata_json'])
        snapshot['items'] = [json.loads(i[0]) for i in db.execute('SELECT item_json FROM evaluation_snapshot_items WHERE snapshot_id=? ORDER BY position',(row['id'],))]
        result.append(snapshot)
    return result
