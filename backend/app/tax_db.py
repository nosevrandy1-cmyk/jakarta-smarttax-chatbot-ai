import json
import sqlite3
from typing import Any, Dict, List

from .config import DATA_DIR

DB_PATH = DATA_DIR / "pajak_jst.sqlite"

# Thematic definitions for Bapenda Provinsi DKI Jakarta
TAX_THEMES: Dict[str, Dict[str, str]] = {
    "PBB-P2": {
        "code": "PBB-P2",
        "name": "PBB-P2 (Pajak Bumi & Bangunan)",
        "short_desc": "SPPT, NOP, NJOP, NJOPTKP & Tunggakan PBB-P2 DKI Jakarta",
    },
    "PBJT": {
        "code": "PBJT",
        "name": "PBJT (Restoran, Hotel, Parkir, Hiburan)",
        "short_desc": "SPTPD/NOPD Makanan & Minuman, Perhotelan, Parkir, Hiburan & Listrik DKI",
    },
    "BPHTB": {
        "code": "BPHTB",
        "name": "BPHTB (Perolehan Hak Tanah & Bangunan)",
        "short_desc": "SSPD BPHTB Jual Beli, Waris/Hibah, NPOP & NPOPTKP DKI Jakarta",
    },
    "REKLAME": {
        "code": "REKLAME",
        "name": "Pajak Reklame",
        "short_desc": "SKPD Reklame LED/Videotron/Billboard & NSR Kawasan DKI Jakarta",
    },
    "PAT": {
        "code": "PAT",
        "name": "Pajak Air Tanah (PAT)",
        "short_desc": "SKPD Air Tanah, Volume Meter Air, NPAT & Tarif 20% DKI Jakarta",
    },
}

# No bundled records or regulatory claims. Sources must be supplied explicitly.
DKI_TAX_RECORDS: List[Dict[str, Any]] = []
DKI_REGULASI_CHUNKS: List[Dict[str, str]] = []
DKI_LEGAL_CORPUS: List[Dict[str, Any]] = []

def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_tax_db() -> int:
    """Create empty tables without replacing data or inserting fixtures."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with get_connection() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS pajak_dki_jakarta (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tema_pajak TEXT NOT NULL,
            nomor_identitas TEXT NOT NULL,
            nama_wp TEXT NOT NULL,
            nama_objek TEXT NOT NULL,
            alamat_objek TEXT NOT NULL,
            kelurahan TEXT NOT NULL,
            kecamatan TEXT NOT NULL,
            kota_administrasi TEXT NOT NULL,
            kategori_subjek TEXT NOT NULL,
            dpp_atau_njop_rp INTEGER NOT NULL,
            pengurang_tak_kena_pajak_rp INTEGER NOT NULL,
            tarif_persen REAL NOT NULL,
            pokok_pajak_rp INTEGER NOT NULL,
            denda_rp INTEGER NOT NULL,
            total_tagihan_rp INTEGER NOT NULL,
            masa_atau_tahun_pajak TEXT NOT NULL,
            status_bayar TEXT NOT NULL,
            jatuh_tempo TEXT NOT NULL,
            keterangan TEXT NOT NULL
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS korpus_hukum_dki (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kode_pasal TEXT NOT NULL,
            tema_pajak TEXT NOT NULL,
            jenis_instrumen TEXT NOT NULL,
            hierarki_level INTEGER NOT NULL,
            bab_bagian TEXT NOT NULL,
            pasal_ayat TEXT NOT NULL,
            tentang TEXT NOT NULL,
            bunyi_norma TEXT NOT NULL,
            kaidah_perumusan TEXT NOT NULL,
            kata_kunci TEXT NOT NULL
        )""")
        return conn.execute("SELECT COUNT(*) FROM pajak_dki_jakarta").fetchone()[0]


def get_all_sppt_records(tema_pajak: str = "") -> List[Dict[str, Any]]:
    if not DB_PATH.exists():
        init_tax_db()
    conn = get_connection()
    if tema_pajak and tema_pajak.upper() in TAX_THEMES:
        rows = conn.execute(
            "SELECT * FROM pajak_dki_jakarta WHERE tema_pajak = ? ORDER BY id ASC",
            (tema_pajak.upper(),),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM pajak_dki_jakarta ORDER BY tema_pajak ASC, id ASC"
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_regulasi_chunks(tema_pajak: str = "") -> List[Dict[str, str]]:
    if tema_pajak and tema_pajak.upper() in TAX_THEMES:
        return [c for c in DKI_REGULASI_CHUNKS if c["tema_pajak"] == tema_pajak.upper()]
    return DKI_REGULASI_CHUNKS


def get_all_legal_corpus(tema_pajak: str = "") -> List[Dict[str, Any]]:
    """Return structured legal provisions (Pasal, Ayat, Dasar Hukum, Kaidah Perumusan) from SQLite."""
    if not DB_PATH.exists():
        init_tax_db()
    conn = get_connection()
    try:
        if tema_pajak and tema_pajak.upper() in TAX_THEMES:
            rows = conn.execute(
                "SELECT * FROM korpus_hukum_dki WHERE tema_pajak = ? ORDER BY hierarki_level ASC, id ASC",
                (tema_pajak.upper(),),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM korpus_hukum_dki ORDER BY tema_pajak ASC, hierarki_level ASC, id ASC"
            ).fetchall()
    except sqlite3.OperationalError:
        conn.close()
        init_tax_db()
        return get_all_legal_corpus(tema_pajak)
    conn.close()
    return [dict(r) for r in rows]


def telusuri_pasal_hukum_dki(kata_kunci: str = "", tema_pajak: str = "") -> str:
    """Cari bunyi pasal, ayat, dasar hukum, dan kaidah perumusan regulasi pajak daerah DKI Jakarta."""
    items = get_all_legal_corpus(tema_pajak)
    if kata_kunci and kata_kunci.strip():
        q_tokens = [
            t
            for t in kata_kunci.lower().split()
            if len(t) >= 3 and t not in ("pasal", "ayat", "dasar", "hukum", "tentang", "pajak", "dki", "jakarta")
        ]
        if q_tokens:
            matched = [
                it
                for it in items
                if any(
                    tok in (
                        f"{it['pasal_ayat']} {it['tentang']} {it['bunyi_norma']} {it['kaidah_perumusan']} {it['kata_kunci']}"
                    ).lower()
                    for tok in q_tokens
                )
            ]
            if matched:
                items = matched
    return json.dumps(items, ensure_ascii=False)


def susun_rancangan_hukum_dki(topik_perumusan: str, tema_pajak: str = "PBB-P2") -> Dict[str, Any]:
    """Return available references only; no canned legislative language."""
    return {"tema_pajak": tema_pajak, "topik_perumusan": topik_perumusan,
            "pasal_induk_acuan": get_all_legal_corpus(tema_pajak),
            "ringkasan_tarif_dan_ketentuan": get_regulasi_chunks(tema_pajak)}


# --- Local Tool Functions for Ollama Tool Calling ---

def cari_data_pajak_dki(kata_kunci: str, tema_pajak: str = "") -> str:
    """Cari data objek pajak / Wajib Pajak di database lokal DKI Jakarta berdasarkan NOP/NPWPD/SSPD/SKPD, nama WP, objek, kelurahan, kecamatan, atau kota administrasi.

    Args:
        kata_kunci: NOP, NPWPD, nama Wajib Pajak, nama usaha/objek, kelurahan, kecamatan, atau kota administrasi DKI Jakarta
        tema_pajak: Tema pajak aktif (PBB-P2, PBJT, BPHTB, REKLAME, PAT)

    Returns:
        JSON string berisi data pajak DKI Jakarta lokal yang cocok.
    """
    conn = get_connection()
    q = f"%{kata_kunci.strip()}%"
    if tema_pajak and tema_pajak.upper() in TAX_THEMES:
        rows = conn.execute(
            """
            SELECT * FROM pajak_dki_jakarta
            WHERE tema_pajak = ?
              AND (nomor_identitas LIKE ? OR nama_wp LIKE ? OR nama_objek LIKE ?
                   OR alamat_objek LIKE ? OR kelurahan LIKE ? OR kecamatan LIKE ?
                   OR kota_administrasi LIKE ? OR kategori_subjek LIKE ?)
            ORDER BY id ASC
            """,
            (tema_pajak.upper(), q, q, q, q, q, q, q, q),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT * FROM pajak_dki_jakarta
            WHERE nomor_identitas LIKE ? OR nama_wp LIKE ? OR nama_objek LIKE ?
               OR alamat_objek LIKE ? OR kelurahan LIKE ? OR kecamatan LIKE ?
               OR kota_administrasi LIKE ? OR kategori_subjek LIKE ?
            ORDER BY id ASC
            """,
            (q, q, q, q, q, q, q, q),
        ).fetchall()
    conn.close()
    return json.dumps([dict(r) for r in rows], ensure_ascii=False)


def daftar_tunggakan_pajak_dki(tema_pajak: str = "", wilayah: str = "") -> str:
    """Ambil daftar ketetapan pajak DKI Jakarta yang berstatus BELUM LUNAS (tunggakan) beserta pokok pajak dan dendanya dari database lokal.

    Args:
        tema_pajak: Tema pajak aktif (PBB-P2, PBJT, BPHTB, REKLAME, PAT)
        wilayah: Opsional filter kelurahan, kecamatan, atau kota administrasi DKI Jakarta

    Returns:
        JSON string daftar tunggakan pajak DKI Jakarta lokal dan total keseluruhan.
    """
    conn = get_connection()
    params: List[Any] = []
    where_clauses = ["status_bayar LIKE 'BELUM LUNAS%'"]

    if tema_pajak and tema_pajak.upper() in TAX_THEMES:
        where_clauses.append("tema_pajak = ?")
        params.append(tema_pajak.upper())

    if wilayah and wilayah.strip() and wilayah.strip().lower() not in ("semua", "all", "-", "dki", "jakarta"):
        q = f"%{wilayah.strip()}%"
        where_clauses.append("(kelurahan LIKE ? OR kecamatan LIKE ? OR kota_administrasi LIKE ?)")
        params.extend([q, q, q])

    sql = f"SELECT * FROM pajak_dki_jakarta WHERE {' AND '.join(where_clauses)} ORDER BY total_tagihan_rp DESC"
    rows = conn.execute(sql, tuple(params)).fetchall()
    conn.close()

    items = [dict(r) for r in rows]
    total_pokok = sum(r["pokok_pajak_rp"] for r in items)
    total_denda = sum(r["denda_rp"] for r in items)
    total_tagihan = sum(r["total_tagihan_rp"] for r in items)
    return json.dumps(
        {
            "tema_pajak": tema_pajak or "SEMUA",
            "jumlah_objek_belum_lunas": len(items),
            "total_pokok_pajak_rp": total_pokok,
            "total_denda_rp": total_denda,
            "total_tagihan_keseluruhan_rp": total_tagihan,
            "daftar_tunggakan": items,
        },
        ensure_ascii=False,
    )


def rekapitulasi_pajak_dki(tema_pajak: str = "") -> str:
    """Ambil rekapitulasi ketetapan, realisasi LUNAS, dan sisa tunggakan pajak DKI Jakarta berdasarkan tema pajak dan kota administrasi.

    Args:
        tema_pajak: Tema pajak aktif (PBB-P2, PBJT, BPHTB, REKLAME, PAT)

    Returns:
        JSON string berisi rekapitulasi pajak DKI Jakarta per wilayah dan total keseluruhan.
    """
    conn = get_connection()
    if tema_pajak and tema_pajak.upper() in TAX_THEMES:
        rows = conn.execute(
            """
            SELECT
                tema_pajak,
                kota_administrasi,
                kecamatan,
                COUNT(*) AS jumlah_objek,
                SUM(pokok_pajak_rp) AS total_ketetapan_rp,
                SUM(CASE WHEN status_bayar LIKE 'LUNAS%' THEN pokok_pajak_rp ELSE 0 END) AS realisasi_lunas_rp,
                SUM(denda_rp) AS total_denda_rp,
                SUM(total_tagihan_rp) AS total_sisa_tagihan_rp
            FROM pajak_dki_jakarta
            WHERE tema_pajak = ?
            GROUP BY tema_pajak, kota_administrasi, kecamatan
            ORDER BY kota_administrasi ASC, kecamatan ASC
            """,
            (tema_pajak.upper(),),
        ).fetchall()
        totals = conn.execute(
            """
            SELECT
                COUNT(*) AS total_objek,
                SUM(CASE WHEN status_bayar LIKE 'LUNAS%' THEN 1 ELSE 0 END) AS objek_lunas,
                SUM(CASE WHEN status_bayar LIKE 'BELUM LUNAS%' THEN 1 ELSE 0 END) AS objek_belum_lunas,
                SUM(pokok_pajak_rp) AS total_ketetapan_rp,
                SUM(CASE WHEN status_bayar LIKE 'LUNAS%' THEN pokok_pajak_rp ELSE 0 END) AS total_realisasi_lunas_rp,
                SUM(total_tagihan_rp) AS total_tunggakan_dan_denda_rp
            FROM pajak_dki_jakarta
            WHERE tema_pajak = ?
            """,
            (tema_pajak.upper(),),
        ).fetchone()
    else:
        rows = conn.execute(
            """
            SELECT
                tema_pajak,
                kota_administrasi,
                kecamatan,
                COUNT(*) AS jumlah_objek,
                SUM(pokok_pajak_rp) AS total_ketetapan_rp,
                SUM(CASE WHEN status_bayar LIKE 'LUNAS%' THEN pokok_pajak_rp ELSE 0 END) AS realisasi_lunas_rp,
                SUM(denda_rp) AS total_denda_rp,
                SUM(total_tagihan_rp) AS total_sisa_tagihan_rp
            FROM pajak_dki_jakarta
            GROUP BY tema_pajak, kota_administrasi, kecamatan
            ORDER BY tema_pajak ASC, kota_administrasi ASC
            """
        ).fetchall()
        totals = conn.execute(
            """
            SELECT
                COUNT(*) AS total_objek,
                SUM(CASE WHEN status_bayar LIKE 'LUNAS%' THEN 1 ELSE 0 END) AS objek_lunas,
                SUM(CASE WHEN status_bayar LIKE 'BELUM LUNAS%' THEN 1 ELSE 0 END) AS objek_belum_lunas,
                SUM(pokok_pajak_rp) AS total_ketetapan_rp,
                SUM(CASE WHEN status_bayar LIKE 'LUNAS%' THEN pokok_pajak_rp ELSE 0 END) AS total_realisasi_lunas_rp,
                SUM(total_tagihan_rp) AS total_tunggakan_dan_denda_rp
            FROM pajak_dki_jakarta
            """
        ).fetchone()
    conn.close()
    return json.dumps(
        {
            "tema_pajak": tema_pajak or "SEMUA",
            "ringkasan_total": dict(totals) if totals else {},
            "rekap_per_wilayah": [dict(r) for r in rows],
        },
        ensure_ascii=False,
    )
