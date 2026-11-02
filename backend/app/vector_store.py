"""Qdrant persistence for document chunks, explicit vectors and source metadata."""
from functools import lru_cache
import uuid
from qdrant_client import QdrantClient, models


@lru_cache(maxsize=8)
def open_client(path, url):
    return QdrantClient(url=url) if url else QdrantClient(path=path)


class QdrantRecords:
    def __init__(self, path, url, name, dimension):
        self.client = open_client(str(path), url)
        self.name = name
        self.dimension = dimension
        if not self.client.collection_exists(name):
            self.client.create_collection(name, vectors_config=models.VectorParams(size=dimension, distance=models.Distance.COSINE))
        else:
            params=self.client.get_collection(name).config.params.vectors
            if not isinstance(params,models.VectorParams) or params.size != dimension or params.distance != models.Distance.COSINE:
                raise ValueError('Qdrant collection vector configuration does not match the application.')

    def point_id(self, chunk_id):
        return str(uuid.uuid5(uuid.NAMESPACE_URL, self.name + ':' + chunk_id))

    def metadata_filter(self, where):
        if not where: return None
        if '$and' in where:
            return models.Filter(must=[self.metadata_filter(item) for item in where['$and']])
        conditions=[]
        for key,value in where.items():
            if key.startswith('$'): raise ValueError('Unsupported metadata filter')
            if isinstance(value,dict):
                if set(value) != {'$in'}: raise ValueError('Unsupported metadata comparison')
                match=models.MatchAny(any=value['$in'])
            else: match=models.MatchValue(value=value)
            conditions.append(models.FieldCondition(key='metadata.'+key,match=match))
        return models.Filter(must=conditions)

    def count(self):
        return self.client.count(self.name,exact=True).count

    def upsert(self, ids, embeddings, documents, metadatas):
        if not (len(ids)==len(embeddings)==len(documents)==len(metadatas)):
            raise ValueError('Chunk fields must have equal lengths')
        if len(set(ids)) != len(ids): raise ValueError('Duplicate chunk IDs')
        points=[]
        for chunk_id,vector,text,meta in zip(ids,embeddings,documents,metadatas):
            if len(vector)!=self.dimension: raise ValueError('Embedding dimension mismatch')
            points.append(models.PointStruct(id=self.point_id(chunk_id),vector=vector,
                payload={'chunk_id':chunk_id,'text':text,'metadata':meta}))
        if points:self.client.upsert(self.name,points=points,wait=True)

    def get(self, ids=None, where=None, include=None):
        include=['documents','metadatas'] if include is None else include
        query_filter=self.metadata_filter(where)
        if ids is not None:
            if not ids:return {'ids':[],'documents':[],'metadatas':[],'embeddings':[]}
            id_filter=models.HasIdCondition(has_id=[self.point_id(i) for i in ids])
            query_filter=models.Filter(must=[id_filter]+([query_filter] if query_filter else []))
        records=[];offset=None
        while True:
            batch,offset=self.client.scroll(self.name,scroll_filter=query_filter,limit=256,offset=offset,
                with_payload=True,with_vectors='embeddings' in include)
            records.extend(batch)
            if offset is None: break
        records.sort(key=lambda point:point.payload['chunk_id'])
        return {'ids':[p.payload['chunk_id'] for p in records],
            'documents':[p.payload['text'] for p in records] if 'documents' in include else [],
            'metadatas':[p.payload['metadata'] for p in records] if 'metadatas' in include else [],
            'embeddings':[p.vector for p in records] if 'embeddings' in include else []}

    def delete(self, ids):
        if ids:self.client.delete(self.name,points_selector=models.PointIdsList(points=[self.point_id(i) for i in ids]),wait=True)

    def query(self, query_embeddings, n_results, where=None, include=None):
        result={'ids':[],'documents':[],'metadatas':[],'distances':[]}
        for vector in query_embeddings:
            hits=self.client.query_points(self.name,query=vector,query_filter=self.metadata_filter(where),
                limit=n_results,with_payload=True).points
            result['ids'].append([h.payload['chunk_id'] for h in hits])
            result['documents'].append([h.payload['text'] for h in hits])
            result['metadatas'].append([h.payload['metadata'] for h in hits])
            result['distances'].append([1.0-float(h.score) for h in hits])
        return result
