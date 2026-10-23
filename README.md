# Bapenda DKI Jakarta — Regional Tax AI Service

Layanan konsultasi dan penelusuran data Pajak Daerah Provinsi DKI Jakarta berbasis **Local Retrieval-Augmented Generation (RAG)** dan **Structured SQL Lookup**. Sistem ini dirancang untuk menjawab kueri perpajakan daerah (`PBB-P2`, `PBJT`, `BPHTB`, `Pajak Reklame`, dan `Pajak Air Tanah`) secara eksklusif dari basis data internal tanpa mengakses sumber internet eksternal.

---

## Arsitektur Sistem

```text
┌──────────────────────────────────────────────────────────────────────┐
│                        Frontend (Next.js 15)                         │
│  • App Router (React 19, TypeScript)                                 │
│  • NDJSON Stream Consumer (/api/chat/stream)                         │
│  • Scoped Tax Category Switcher (PBB-P2, PBJT, BPHTB, REKLAME, PAT)  │
└──────────────────────────────────┬───────────────────────────────────┘
                                   │ HTTP POST (NDJSON Stream)
                                   ▼
┌──────────────────────────────────────────────────────────────────────┐
│                        Backend API (FastAPI)                         │
│  • Input Validation & Security Headers Middleware                    │
│  • Cross-Category Intent Detector & Pre-Lookup Router                │
└───────────┬──────────────────────┴───────────────────────┬───────────┘
            │                                              │
            ▼                                              ▼
┌───────────────────────────┐                  ┌───────────────────────┐
│   Relational Store        │                  │   Vector Store        │
│   • SQLite / PostgreSQL   │                  │   • Qdrant (Local/Srv)│
│   • Exact NOP/NPWPD/SKPD  │                  │   • 384-dim Subword & │
│   • Arrears & Area Recap  │                  │     Token Embeddings  │
└───────────┬───────────────┘                  └───────────┬───────────┘
            └──────────────────────┬───────────────────────┘
                                   │ Grounded Context Prompt
                                   ▼
┌──────────────────────────────────────────────────────────────────────┐
│                     Inference Engine (Ollama)                        │
│  • Local Models: gemma4:e2b, qwen3:4b                                │
│  • Cloud Models: gemma4:cloud                                        │
│  • Deterministic Fallback Formatter (Zero-Hallucination Guarantee)   │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Struktur Direktori

```text
.
├── backend/
│   ├── app/
│   │   ├── config.py          # Konfigurasi environment, host Ollama, Qdrant & CORS
│   │   ├── main.py            # Entrypoint FastAPI, middleware security, & route endpoints
│   │   ├── tax_db.py          # Skema tabel pajak DKI, seed data, & fungsi agregasi SQL
│   │   ├── embedder.py        # Engine ekstraksi vektor 384-dimensi (Transformers/Subword)
│   │   ├── vector_store.py    # Integrasi Qdrant & payload filtering per kategori pajak
│   │   └── ollama_service.py  # Orkestrasi RAG, deteksi lintas tema, & NDJSON streaming
│   ├── pyproject.toml         # Dependensi Python (dikelola via uv / pip)
│   └── .env.example           # Template konfigurasi environment backend
├── frontend/
│   ├── src/app/
│   │   ├── layout.tsx         # Root HTML layout & konfigurasi viewport mobile
│   │   ├── globals.css        # Design tokens, layout responsif desktop/mobile, & animasi
│   │   └── page.tsx           # Komponen utama antarmuka chat, state sesi, & stream reader
│   ├── next.config.mjs        # Konfigurasi Next.js & HTTP security headers
│   ├── package.json           # Dependensi frontend
│   └── .env.example           # Template konfigurasi environment frontend
├── docs/
│   └── ENGINEERING_GUIDE.md   # Dokumentasi teknis mendalam untuk tim developer & infra
└── start.sh                   # Skrip utilitas untuk menjalankan backend & frontend lokal
```

---

## Persiapan & Menjalankan Secara Lokal

### Prasyarat
- **Python** `>= 3.11` (disarankan menggunakan [`uv`](https://docs.astral.sh/uv/))
- **Node.js** `>= 20.x` & `npm`
- **Ollama** (`>= 0.6+`) berjalan pada port `11434`

### 1. Menjalankan Backend (FastAPI)

```bash
cd backend
cp .env.example .env

# Instalasi dependensi & jalankan server pada port 8000
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Verifikasi status layanan melalui endpoint health check:
```bash
curl http://localhost:8000/api/health
```

### 2. Menjalankan Frontend (Next.js)

```bash
cd frontend
cp .env.example .env.local

npm install
npm run dev
```

Buka `http://localhost:3000` pada browser desktop maupun perangkat mobile.

---

## Kontrak API Utama

### `GET /api/health`
Mengembalikan status koneksi Ollama, mode penyimpanan Qdrant, jumlah baris pajak yang terindeks, dan daftar kategori pajak aktif.

### `POST /api/chat/stream`
Menerima payload JSON dan mengalirkan respons dalam format **NDJSON (`application/x-ndjson`)**:

**Request Body:**
```json
{
  "message": "Tampilkan daftar tunggakan PBB-P2 di DKI Jakarta",
  "tema_pajak": "PBB-P2",
  "model": "gemma4:cloud",
  "history": []
}
```

**Stream Events (NDJSON):**
- `{"type": "status", "text": "..."}` — Indikator tahapan pencarian data lokal.
- `{"type": "sources", "tema_pajak": "PBB-P2", "suggested_theme": null, "qdrant_sources": [...], "sql_tools_used": [...]}` — Metadata sumber lokal yang digunakan.
- `{"type": "thinking", "delta": "..."}` — Token penalaran model (opsional).
- `{"type": "token", "delta": "..."}` — Token teks jawaban utama secara *real-time*.
- `{"type": "done", "tema_pajak": "PBB-P2", "follow_ups": [...], "model_used": "...", "duration_ms": 142}` — Penanda akhir stream beserta saran pertanyaan lanjutan.

---

## Panduan Pengembangan Tim

Untuk panduan lengkap mengenai cara memodifikasi kategori pajak, mengubah skema database, menyesuaikan prompt RAG, maupun konfigurasi server, silakan baca **[docs/ENGINEERING_GUIDE.md](docs/ENGINEERING_GUIDE.md)**.
