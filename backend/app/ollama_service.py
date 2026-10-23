import asyncio
import json
import re
import time
from typing import Any, AsyncGenerator, Dict, List, Optional
import httpx

from .config import (
    DEFAULT_CHAT_MODEL,
    OLLAMA_API_KEY,
    OLLAMA_CLOUD_URL,
    OLLAMA_LOCAL_URL,
)
from .tax_db import (
    TAX_THEMES,
    daftar_tunggakan_pajak_dki,
    get_all_sppt_records,
    get_regulasi_chunks,
    rekapitulasi_pajak_dki,
)
from .vector_store import vector_store

THEME_KEYWORDS: Dict[str, List[str]] = {
    "PBB-P2": [
        "pbb",
        "sppt",
        "nop",
        "njop",
        "njoptkp",
        "bumi dan bangunan",
        "scbd",
        "menteng",
        "kelapa gading",
        "pondok indah",
    ],
    "PBJT": [
        "pbjt",
        "restoran",
        "rumah makan",
        "kafe",
        "hotel",
        "parkir",
        "hiburan",
        "karaoke",
        "diskotek",
        "makanan",
        "minuman",
        "sptpd",
        "senopati",
    ],
    "BPHTB": [
        "bphtb",
        "sspd",
        "ajb",
        "jual beli",
        "waris",
        "hibah",
        "npop",
        "npoptkp",
        "akta",
        "balik nama",
    ],
    "REKLAME": [
        "reklame",
        "videotron",
        "billboard",
        "baliho",
        "megatron",
        "nsr",
        "kawasan kendali ketat",
    ],
    "PAT": [
        "air tanah",
        "pat",
        "npat",
        "sumur bor",
        "abstraksi air",
        "volume air",
        "pulo gadung",
    ],
}


def _detect_cross_theme(question: str, active_tema: str) -> Optional[str]:
    """Check if the user prompt targets a different regional tax category."""
    q_lower = question.lower()
    active_hits = sum(1 for kw in THEME_KEYWORDS.get(active_tema, []) if kw in q_lower)
    if active_hits > 0:
        return None

    best_theme: Optional[str] = None
    best_score = 0
    for code, kws in THEME_KEYWORDS.items():
        if code == active_tema:
            continue
        score = sum(1 for kw in kws if kw in q_lower)
        if score > best_score:
            best_score = score
            best_theme = code

    return best_theme if best_score > 0 else None


def _generate_follow_ups(question: str, tema: str) -> List[str]:
    """Return 3 contextual follow-up queries for the active tax theme."""
    q_lower = question.lower()
    prompts_by_theme: Dict[str, List[str]] = {
        "PBB-P2": [
            "Tampilkan objek PBB-P2 DKI yang masih menunggak beserta dendanya",
            "Rekapitulasi realisasi PBB-P2 DKI Jakarta per Kota Administrasi",
            "Apa syarat bebas PBB-P2 100% dan NJOPTKP Rp 60 juta di DKI?",
            "Rincian SPPT NOP 31.74.010.003.008-0042.0 di SCBD Jakarta Selatan",
        ],
        "PBJT": [
            "Daftar Wajib Pajak PBJT yang belum lunas beserta denda e-SPTPD",
            "Perbandingan tarif PBJT Restoran (10%) dan Hiburan Tertentu (40%)",
            "Rekapitulasi ketetapan dan realisasi PBJT per Kota Administrasi",
            "Tampilkan seluruh objek PBJT Restoran, Hotel, dan Hiburan di DKI",
        ],
        "BPHTB": [
            "Berapa perbandingan NPOPTKP Jual Beli (Rp 80 Juta) vs Waris (Rp 350 Juta)?",
            "Cek transaksi SSPD BPHTB yang belum tervalidasi / belum lunas",
            "Rekapitulasi ketetapan dan realisasi BPHTB di DKI Jakarta",
            "Tampilkan seluruh data SSPD BPHTB di DKI Jakarta",
        ],
        "REKLAME": [
            "Cek SKPD Reklame yang belum lunas beserta rincian dendanya",
            "Bagaimana aturan kawasan protokol dan tarif 25% Pajak Reklame?",
            "Rekapitulasi ketetapan dan realisasi Pajak Reklame DKI Jakarta",
            "Tampilkan seluruh objek Videotron & Billboard di DKI Jakarta",
        ],
        "PAT": [
            "Tampilkan SKPD Pajak Air Tanah yang masih menunggak di DKI",
            "Bagaimana cara hitung NPAT dan tarif 20% Pajak Air Tanah?",
            "Rekapitulasi ketetapan dan realisasi Pajak Air Tanah per wilayah",
            "Tampilkan seluruh Wajib Pajak Air Tanah di DKI Jakarta",
        ],
    }
    candidates = prompts_by_theme.get(tema, prompts_by_theme["PBB-P2"])
    filtered = [p for p in candidates if p.lower()[:22] not in q_lower]
    return (filtered or candidates)[:3]


def build_thematic_system_prompt(tema_pajak: str) -> str:
    theme_info = TAX_THEMES.get(tema_pajak.upper(), TAX_THEMES["PBB-P2"])
    theme_code = theme_info["code"]
    theme_name = theme_info["name"]

    return f"""Anda adalah **Jakarta SmartTax 2026** (dikembangkan oleh **Tim AI Jakarta SmartTax 2026** — Bapenda Provinsi DKI Jakarta) pada kategori **{theme_name}**.
Panduan Jawaban:
1. Jawab pertanyaan seputar **{theme_name} Provinsi DKI Jakarta** hanya berdasarkan KONTEKS DATA LOKAL DKI JAKARTA yang diberikan.
2. Jangan menggunakan sumber eksternal, internet, situs web luar, atau asumsi di luar data lokal.
3. Jika pengguna menanyakan kategori pajak lain di luar **{theme_code}**, sampaikan secara singkat bahwa ruang percakapan sedang fokus pada **{theme_code}** dan sarankan menekan tombol pindah kategori di bawah pesan.
4. Jika data objek pajak atau NOP/NPWPD yang dicari tidak terdaftar di basis data lokal, sampaikan dengan jelas bahwa data tersebut belum terdaftar pada arsip lokal {theme_code} Bapenda DKI Jakarta.
5. Gunakan bahasa Indonesia yang lugas, ramah, mudah dipahami (tanpa perlu mengutip nomor peraturan daerah yang rumit), dan sajikan rincian angka dalam tabel Markdown yang rapi."""


def _run_local_pre_lookup(question: str, tema_pajak: str) -> List[Dict[str, Any]]:
    """Query SQLite tables scoped to the active DKI Jakarta tax theme."""
    q_lower = question.lower()
    tema = tema_pajak.upper() if tema_pajak.upper() in TAX_THEMES else "PBB-P2"
    tool_outputs: List[Dict[str, Any]] = []

    if any(k in q_lower for k in ["tunggakan", "belum lunas", "menunggak", "denda", "telat", "terlambat"]):
        res = json.loads(daftar_tunggakan_pajak_dki(tema_pajak=tema))
        tool_outputs.append({"tool": "daftar_tunggakan_pajak_dki", "tema": tema, "data": res})

    if any(k in q_lower for k in ["rekap", "total", "realisasi", "ringkasan", "kecamatan", "kelurahan", "kota", "wilayah"]):
        res = json.loads(rekapitulasi_pajak_dki(tema_pajak=tema))
        tool_outputs.append({"tool": "rekapitulasi_pajak_dki", "tema": tema, "data": res})

    theme_rows = get_all_sppt_records(tema_pajak=tema)
    matched_rows = []
    for r in theme_rows:
        for field in (
            r["nomor_identitas"],
            r["nama_wp"],
            r["nama_objek"],
            r["kelurahan"],
            r["kecamatan"],
            r["kota_administrasi"],
            r["alamat_objek"],
            r["kategori_subjek"],
        ):
            tokens = [
                t
                for t in re.split(r"[\s,\.\-/()]+", field.lower())
                if len(t) >= 3 and t not in ("jalan", "jakarta", "dki", "dan", "pajak", "pbjt", "pbb", "kota", "adm")
            ]
            if any(t in q_lower for t in tokens):
                matched_rows.append(r)
                break

    if not matched_rows and any(k in q_lower for k in ["tampilkan", "lihat", "daftar", "semua", "cek", "contoh", "data", "objek"]):
        matched_rows = theme_rows

    if matched_rows:
        tool_outputs.append({"tool": "cari_data_pajak_dki", "tema": tema, "data": matched_rows})

    reg_chunks = get_regulasi_chunks(tema_pajak=tema)
    if reg_chunks:
        tool_outputs.append({"tool": "regulasi_dki_lokal", "tema": tema, "data": reg_chunks})

    return tool_outputs


def _build_local_deterministic_answer(
    question: str,
    tema_pajak: str,
    qdrant_hits: List[Dict[str, Any]],
    tool_outputs: List[Dict[str, Any]],
    suggested_theme: Optional[str] = None,
) -> str:
    """Format a structured Markdown response from local SQLite and Qdrant results."""
    tema = tema_pajak.upper() if tema_pajak.upper() in TAX_THEMES else "PBB-P2"
    theme_name = TAX_THEMES[tema]["name"]
    lines: List[str] = []
    q_lower = question.lower()

    if suggested_theme and suggested_theme in TAX_THEMES:
        target_name = TAX_THEMES[suggested_theme]["name"]
        return (
            f"Pertanyaan Anda berkaitan dengan **{target_name}**, sedangkan ruang percakapan ini sedang berada pada kategori **{theme_name}**.\n\n"
            f"Silakan klik tombol **Pindah ke {suggested_theme}** di bawah pesan ini untuk langsung menanyakan ulang pada data **{suggested_theme} DKI Jakarta**."
        )

    for t in tool_outputs:
        if t["tool"] == "daftar_tunggakan_pajak_dki":
            d = t["data"]
            lines.append(f"### Daftar Tunggakan {theme_name} — DKI Jakarta")
            lines.append(
                f"Terdapat **{d['jumlah_objek_belum_lunas']} objek pajak** yang tercatat belum lunas pada arsip lokal Bapenda DKI Jakarta:\n\n"
                f"- **Pokok Pajak Tertunggak:** Rp {d['total_pokok_pajak_rp']:,}\n"
                f"- **Akumulasi Denda:** Rp {d['total_denda_rp']:,}\n"
                f"- **Total Tagihan Keseluruhan:** **Rp {d['total_tagihan_keseluruhan_rp']:,}**\n"
            )
            if d["daftar_tunggakan"]:
                lines.append("| Nomor Identitas | Wajib Pajak & Objek | Wilayah DKI Jakarta | Masa/Tahun | Pokok Pajak | Denda | Total Tagihan |")
                lines.append("| :--- | :--- | :--- | :---: | ---: | ---: | ---: |")
                for item in d["daftar_tunggakan"]:
                    lines.append(
                        f"| `{item['nomor_identitas']}` | **{item['nama_wp']}** ({item['nama_objek']}) | {item['kecamatan']}, {item['kota_administrasi']} | {item['masa_atau_tahun_pajak']} | Rp {item['pokok_pajak_rp']:,} | Rp {item['denda_rp']:,} | **Rp {item['total_tagihan_rp']:,}** |"
                    )

    for t in tool_outputs:
        if t["tool"] == "rekapitulasi_pajak_dki":
            d = t["data"]
            tot = d.get("ringkasan_total", {})
            lines.append(f"### Rekapitulasi {theme_name} per Wilayah — DKI Jakarta")
            lines.append(
                f"- **Cakupan Objek Terdaftar:** {tot.get('total_objek', 0)} Objek "
                f"({tot.get('objek_lunas', 0)} Lunas • {tot.get('objek_belum_lunas', 0)} Belum Lunas)\n"
                f"- **Total Ketetapan Pokok:** Rp {tot.get('total_ketetapan_rp', 0):,}\n"
                f"- **Realisasi Penerimaan (Lunas):** Rp {tot.get('total_realisasi_lunas_rp', 0):,}\n"
                f"- **Sisa Piutang + Denda:** Rp {tot.get('total_tunggakan_dan_denda_rp', 0):,}\n"
            )
            lines.append("| Kota Administrasi | Kecamatan | Objek | Ketetapan Pokok | Realisasi Lunas | Sisa Tagihan + Denda |")
            lines.append("| :--- | :--- | :---: | ---: | ---: | ---: |")
            for w in d.get("rekap_per_wilayah", []):
                lines.append(
                    f"| {w['kota_administrasi']} | {w['kecamatan']} | {w['jumlah_objek']} | Rp {w['total_ketetapan_rp']:,} | Rp {w['realisasi_lunas_rp']:,} | **Rp {w['total_sisa_tagihan_rp']:,}** |"
                )

    for t in tool_outputs:
        if t["tool"] == "cari_data_pajak_dki" and t["data"] and not lines:
            lines.append(f"### Rincian Objek {theme_name} — DKI Jakarta")
            lines.append("| Nomor Identitas | Wajib Pajak & Objek | Wilayah DKI | DPP / NJOP | Pokok Pajak | Denda | Status |")
            lines.append("| :--- | :--- | :--- | ---: | ---: | ---: | :--- |")
            for r in t["data"]:
                lines.append(
                    f"| `{r['nomor_identitas']}` | **{r['nama_wp']}** — {r['nama_objek']} | {r['kelurahan']}, {r['kota_administrasi']} | Rp {r['dpp_atau_njop_rp']:,} | Rp {r['pokok_pajak_rp']:,} | Rp {r['denda_rp']:,} | **{r['status_bayar']}** |"
                )
                if len(t["data"]) == 1 and r.get("keterangan"):
                    lines.append(f"\n> **Catatan Ketetapan:** {r['keterangan']} (Jatuh Tempo: `{r['jatuh_tempo']}`)")

    if any(k in q_lower for k in ["tarif", "rumus", "njoptkp", "npoptkp", "denda", "jatuh tempo", "aturan", "ketentuan", "insentif", "bebas", "hitung", "syarat"]) or not lines:
        for t in tool_outputs:
            if t["tool"] == "regulasi_dki_lokal":
                for reg in t["data"]:
                    lines.append(reg["content"])

    if not lines:
        lines.append(
            f"Data yang Anda cari belum terdaftar pada arsip lokal **{tema}** Bapenda DKI Jakarta. "
            f"Coba masukkan nomor identitas pajak, nama objek, atau kecamatan di wilayah DKI Jakarta."
        )

    return "\n\n".join(lines)


async def stream_chat_with_local_pbb(
    user_message: str,
    history: List[Dict[str, str]],
    model: str = DEFAULT_CHAT_MODEL,
    tema_pajak: str = "PBB-P2",
) -> AsyncGenerator[str, None]:
    """Stream NDJSON response chunks for the selected DKI Jakarta regional tax theme."""
    start_ts = time.perf_counter()
    tema = tema_pajak.upper() if (tema_pajak and tema_pajak.upper() in TAX_THEMES) else "PBB-P2"
    theme_label = TAX_THEMES[tema]["name"]

    yield json.dumps(
        {"type": "status", "text": f"Menelusuri arsip {tema} Bapenda DKI Jakarta..."},
        ensure_ascii=False,
    ) + "\n"

    suggested_theme = _detect_cross_theme(user_message, tema)
    qdrant_hits = vector_store.search(user_message, limit=6, tema_pajak=tema)
    pre_tool_outputs = _run_local_pre_lookup(user_message, tema_pajak=tema)
    sql_tools_used = [t["tool"] for t in pre_tool_outputs]
    follow_ups = _generate_follow_ups(user_message, tema)

    await asyncio.sleep(0.08)
    yield json.dumps(
        {"type": "status", "text": f"Mencocokkan rincian objek & ketetapan {tema}..."},
        ensure_ascii=False,
    ) + "\n"

    yield json.dumps(
        {
            "type": "sources",
            "tema_pajak": tema,
            "suggested_theme": suggested_theme,
            "qdrant_sources": qdrant_hits,
            "sql_tools_used": sql_tools_used,
        },
        ensure_ascii=False,
    ) + "\n"

    if suggested_theme:
        deterministic_text = _build_local_deterministic_answer(
            user_message,
            tema,
            qdrant_hits,
            pre_tool_outputs,
            suggested_theme=suggested_theme,
        )
        words = re.split(r"(\s+)", deterministic_text)
        batch = ""
        for idx, w in enumerate(words):
            batch += w
            if idx % 5 == 0 or idx == len(words) - 1:
                yield json.dumps({"type": "token", "delta": batch}, ensure_ascii=False) + "\n"
                batch = ""
                await asyncio.sleep(0.012)

        elapsed_ms = int((time.perf_counter() - start_ts) * 1000)
        yield json.dumps(
            {
                "type": "done",
                "tema_pajak": tema,
                "suggested_theme": suggested_theme,
                "follow_ups": follow_ups,
                "model_used": model,
                "duration_ms": elapsed_ms,
            },
            ensure_ascii=False,
        ) + "\n"
        return

    context_blocks: List[str] = [
        f"KATEGORI PAJAK AKTIF: {theme_label} — PROVINSI DKI JAKARTA"
    ]
    if pre_tool_outputs:
        context_blocks.append(
            f"=== DATA SQLITE LOKAL ({tema} DKI JAKARTA) ===\n"
            + json.dumps(pre_tool_outputs, ensure_ascii=False, indent=2)
        )
    if qdrant_hits:
        context_blocks.append(
            f"=== DOKUMEN VEKTOR QDRANT LOKAL ({tema} DKI JAKARTA) ===\n"
            + "\n\n".join(
                [
                    f"[{h['doc_type'].upper()} | score={h['score']}] {h['title']}\n{h['text']}"
                    for h in qdrant_hits
                ]
            )
        )

    grounded_user_prompt = (
        f"KONTEKS DATA LOKAL BAPENDA DKI JAKARTA:\n"
        f"{chr(10).join(context_blocks)}\n\n"
        f"PERTANYAAN PENGGUNA (Tema Aktif: {tema}):\n{user_message}\n\n"
        f"Jawab hanya dari konteks data lokal {tema} DKI Jakarta di atas tanpa sumber eksternal."
    )

    system_prompt = build_thematic_system_prompt(tema)
    messages: List[Dict[str, Any]] = [{"role": "system", "content": system_prompt}]
    for msg in history[-6:]:
        if msg.get("role") in ("user", "assistant") and msg.get("content"):
            messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": grounded_user_prompt})

    use_direct_cloud = bool(OLLAMA_API_KEY) and (
        ":cloud" in model or model.startswith("gemma4:31b")
    )
    if use_direct_cloud:
        base_url = OLLAMA_CLOUD_URL
        api_model = "gemma4:31b" if model == "gemma4:cloud" else model
        headers = {"Authorization": f"Bearer {OLLAMA_API_KEY}"}
    else:
        base_url = OLLAMA_LOCAL_URL
        api_model = model
        headers = {}

    streamed_any_token = False

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream(
                "POST",
                f"{base_url}/api/chat",
                headers=headers,
                json={
                    "model": api_model,
                    "messages": messages,
                    "stream": True,
                    "options": {"temperature": 0.0},
                },
            ) as resp:
                if resp.status_code == 200:
                    async for line in resp.aiter_lines():
                        if not line.strip():
                            continue
                        try:
                            chunk = json.loads(line)
                        except Exception:
                            continue

                        msg_part = chunk.get("message") or {}
                        thinking_delta = msg_part.get("thinking") or ""
                        content_delta = msg_part.get("content") or ""

                        if thinking_delta:
                            yield json.dumps(
                                {"type": "thinking", "delta": thinking_delta},
                                ensure_ascii=False,
                            ) + "\n"

                        if content_delta:
                            streamed_any_token = True
                            yield json.dumps(
                                {"type": "token", "delta": content_delta},
                                ensure_ascii=False,
                            ) + "\n"
    except Exception:
        pass

    if not streamed_any_token:
        deterministic_text = _build_local_deterministic_answer(
            user_message,
            tema,
            qdrant_hits,
            pre_tool_outputs,
            suggested_theme=suggested_theme,
        )
        words = re.split(r"(\s+)", deterministic_text)
        batch = ""
        for idx, w in enumerate(words):
            batch += w
            if idx % 6 == 0 or idx == len(words) - 1:
                yield json.dumps({"type": "token", "delta": batch}, ensure_ascii=False) + "\n"
                batch = ""
                await asyncio.sleep(0.014)

    elapsed_ms = int((time.perf_counter() - start_ts) * 1000)
    yield json.dumps(
        {
            "type": "done",
            "tema_pajak": tema,
            "suggested_theme": suggested_theme,
            "follow_ups": follow_ups,
            "model_used": api_model,
            "duration_ms": elapsed_ms,
        },
        ensure_ascii=False,
    ) + "\n"


async def chat_with_local_pbb(
    user_message: str,
    history: List[Dict[str, str]],
    model: str = DEFAULT_CHAT_MODEL,
    tema_pajak: str = "PBB-P2",
) -> Dict[str, Any]:
    full_text = ""
    qdrant_sources: List[Dict[str, Any]] = []
    sql_tools_used: List[str] = []
    model_used = model
    suggested_theme: Optional[str] = None
    follow_ups: List[str] = []
    async for raw_line in stream_chat_with_local_pbb(
        user_message, history, model, tema_pajak
    ):
        if not raw_line.strip():
            continue
        evt = json.loads(raw_line)
        if evt["type"] == "token":
            full_text += evt.get("delta", "")
        elif evt["type"] == "sources":
            qdrant_sources = evt.get("qdrant_sources", [])
            sql_tools_used = evt.get("sql_tools_used", [])
            suggested_theme = evt.get("suggested_theme")
        elif evt["type"] == "done":
            model_used = evt.get("model_used", model)
            follow_ups = evt.get("follow_ups", [])

    return {
        "answer": full_text.strip(),
        "tema_pajak": tema_pajak,
        "suggested_theme": suggested_theme,
        "follow_ups": follow_ups,
        "model_used": model_used,
        "qdrant_sources": qdrant_sources,
        "sql_tools_used": sql_tools_used,
    }
