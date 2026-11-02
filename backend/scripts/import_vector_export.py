"""Import a pre-migration vector export without requiring ChromaDB.

The original source archive must remain in data/uploads. Run with the backend
stopped when using embedded Qdrant. Repeated imports upsert stable chunk IDs.
"""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.vector_store import QdrantRecords


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--export',required=True,type=Path)
    parser.add_argument('--storage',required=True,type=Path)
    parser.add_argument('--collection',default='jakarta_smarttax_knowledge')
    parser.add_argument('--dimension',type=int,default=384)
    args=parser.parse_args()
    data=json.loads(args.export.read_text(encoding='utf-8'))
    keys=['ids','embeddings','documents','metadatas']
    if any(key not in data for key in keys) or len({len(data[k]) for k in keys})!=1:
        raise ValueError('Invalid vector export fields')
    if len(set(data['ids']))!=len(data['ids']):raise ValueError('Duplicate chunk IDs')
    if any(len(v)!=args.dimension for v in data['embeddings']):raise ValueError('Vector dimension mismatch')
    records=QdrantRecords(args.storage.resolve(),'',args.collection,args.dimension)
    try:
        for start in range(0,len(data['ids']),100):
            records.upsert(**{key:data[key][start:start+100] for key in keys})
        restored=records.get(ids=data['ids'],include=['documents','metadatas'])
        expected={cid:(text,meta) for cid,text,meta in zip(data['ids'],data['documents'],data['metadatas'])}
        if len(restored['ids'])!=len(expected):raise RuntimeError('Import count verification failed')
        for cid,text,meta in zip(restored['ids'],restored['documents'],restored['metadatas']):
            if expected[cid]!=(text,meta):raise RuntimeError('Import content verification failed')
        print(json.dumps({'verified_chunks':len(expected),'collection':args.collection}))
    finally:records.client.close()


if __name__=='__main__':main()
