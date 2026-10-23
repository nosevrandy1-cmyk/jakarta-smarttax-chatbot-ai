from typing import Any, Dict, List, Optional
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
)

from .config import QDRANT_COLLECTION, QDRANT_STORAGE_DIR, QDRANT_URL, VECTOR_DIM
from .embedder import embedder
from .tax_db import (
    TAX_THEMES,
    get_all_legal_corpus,
    get_all_sppt_records,
    get_regulasi_chunks,
)


class SmartTaxVectorStore:
    """Qdrant vector store for Jakarta SmartTax Chatbot AI."""

    def __init__(self) -> None:
        if QDRANT_URL:
            self.client = QdrantClient(url=QDRANT_URL)
            self.mode = f"qdrant-server ({QDRANT_URL})"
        else:
            QDRANT_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
            self.client = QdrantClient(path=str(QDRANT_STORAGE_DIR))
            self.mode = f"qdrant-local-disk ({QDRANT_STORAGE_DIR.name})"
        self.collection_name = QDRANT_COLLECTION

    def reindex_all(self) -> Dict[str, int]:
        tax_records = get_all_sppt_records()
        regulasi_chunks = get_regulasi_chunks()
        legal_corpus = get_all_legal_corpus()

        if self.client.collection_exists(self.collection_name):
            self.client.delete_collection(self.collection_name)

        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=VectorParams(size=VECTOR_DIM, distance=Distance.COSINE),
        )

        texts: List[str] = []
        payloads: List[Dict[str, Any]] = []

        for row in tax_records:
            text_repr = (
                f"[{row['tema_pajak']} DKI Jakarta] Nomor Identitas/NOP/NPWPD: {row['nomor_identitas']} | "
                f"Masa/Tahun Pajak: {row['masa_atau_tahun_pajak']} | "
                f"Wajib Pajak: {row['nama_wp']} | Objek Pajak: {row['nama_objek']} ({row['kategori_subjek']}) | "
                f"Alamat: {row['alamat_objek']}, Kel. {row['kelurahan']}, Kec. {row['kecamatan']}, {row['kota_administrasi']} | "
                f"DPP/NJOP/NPOP/NSR: Rp {row['dpp_atau_njop_rp']:,} | Pengurang Tidak Kena Pajak: Rp {row['pengurang_tak_kena_pajak_rp']:,} | "
                f"Tarif: {row['tarif_persen']}% | Pokok Pajak: Rp {row['pokok_pajak_rp']:,} | Denda: Rp {row['denda_rp']:,} | "
                f"Total Sisa Tagihan: Rp {row['total_tagihan_rp']:,} | Status Bayar: {row['status_bayar']} (Jatuh Tempo: {row['jatuh_tempo']}) | "
                f"Keterangan: {row['keterangan']}"
            )
            texts.append(text_repr)
            payloads.append(
                {
                    "doc_type": "objek_pajak",
                    "tema_pajak": row["tema_pajak"],
                    "title": f"[{row['tema_pajak']}] {row['nomor_identitas']} - {row['nama_wp']}",
                    "text": text_repr,
                    "metadata": row,
                }
            )

        for chunk in regulasi_chunks:
            text_repr = f"Ketentuan Tarif & Rumus {chunk['tema_pajak']} DKI Jakarta - {chunk['title']}:\n{chunk['content']}"
            texts.append(text_repr)
            payloads.append(
                {
                    "doc_type": "regulasi",
                    "tema_pajak": chunk["tema_pajak"],
                    "title": chunk["title"],
                    "text": chunk["content"],
                    "metadata": chunk,
                }
            )

        for leg in legal_corpus:
            text_repr = (
                f"Korpus Pasal & Dasar Hukum {leg['tema_pajak']} DKI Jakarta | "
                f"{leg['jenis_instrumen']} | {leg['bab_bagian']} | {leg['pasal_ayat']} tentang {leg['tentang']}:\n"
                f"Bunyi Norma: {leg['bunyi_norma']}\n"
                f"Kaidah Perumusan / Legal Drafting: {leg['kaidah_perumusan']}"
            )
            texts.append(text_repr)
            payloads.append(
                {
                    "doc_type": "pasal_hukum",
                    "tema_pajak": leg["tema_pajak"],
                    "title": f"[{leg['kode_pasal']}] {leg['pasal_ayat']} — {leg['tentang']}",
                    "text": text_repr,
                    "metadata": leg,
                }
            )

        if texts:
            vectors = embedder.embed_texts(texts)
            points = [
                PointStruct(id=idx + 1, vector=vec, payload=payload)
                for idx, (vec, payload) in enumerate(zip(vectors, payloads))
            ]
            self.client.upsert(collection_name=self.collection_name, points=points)

        return {
            "sppt_indexed": len(tax_records),
            "regulasi_indexed": len(regulasi_chunks),
            "pasal_hukum_indexed": len(legal_corpus),
            "total_points": len(texts),
        }

    def search(
        self,
        query: str,
        limit: int = 6,
        tema_pajak: Optional[str] = None,
        doc_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        if not self.client.collection_exists(self.collection_name):
            self.reindex_all()

        query_vector = embedder.embed_query(query)
        must_conditions = []
        if tema_pajak and tema_pajak.upper() in TAX_THEMES:
            must_conditions.append(
                FieldCondition(key="tema_pajak", match=MatchValue(value=tema_pajak.upper()))
            )
        if doc_type:
            must_conditions.append(
                FieldCondition(key="doc_type", match=MatchValue(value=doc_type))
            )

        q_filter = Filter(must=must_conditions) if must_conditions else None

        res = self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            query_filter=q_filter,
            limit=limit,
            with_payload=True,
        )

        hits: List[Dict[str, Any]] = []
        for pt in res.points:
            payload = pt.payload or {}
            hits.append(
                {
                    "id": pt.id,
                    "score": round(float(pt.score), 4),
                    "doc_type": payload.get("doc_type", "unknown"),
                    "tema_pajak": payload.get("tema_pajak", ""),
                    "title": payload.get("title", ""),
                    "text": payload.get("text", ""),
                    "metadata": payload.get("metadata", {}),
                }
            )
        return hits


vector_store = SmartTaxVectorStore()
