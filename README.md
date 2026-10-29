# Jakarta SmartTax 2026 — Platform AI Chatbot Pajak Daerah DKI Jakarta

Repositori resmi **Tim AI Jakarta SmartTax 2026**. Proyek ini adalah platform *chat* interaktif berbasis RAG (*Retrieval-Augmented Generation*) untuk seluruh kategori pajak daerah **Bapenda Provinsi DKI Jakarta**:

- **PBB-P2** (Pajak Bumi dan Bangunan Perdesaan dan Perkotaan)
- **PBJT** (Pajak Barang dan Jasa Tertentu — Restoran, Perhotelan, Parkir, Kesenian & Hiburan)
- **BPHTB** (Bea Perolehan Hak atas Tanah dan Bangunan)
- **REKLAME** (Pajak Reklame — Videotron, Megatron, Billboard Kawasan Protokol & Kendali Ketat)
- **PAT** (Pajak Air Tanah — Sumur Bor Industri & Komersial)

Platform ini mendukung 3 kapabilitas utama:
1. **Konsultasi Tarif, Rumus & Data Pajak** (Simulasi perhitungan, pengecekan NOP/NPWPD, tunggakan, dan rekap wilayah)
2. **Telusur Pasal & Dasar Hukum** (Pencarian bunyi pasal, ayat, dan kaidah regulasi pajak daerah)
3. **Perumusan Dasar Hukum Baru (*Legal Drafting*)** (Penyusunan draf Konsiderans *Menimbang*, Dasar *Mengingat*, dan Batang Tubuh *Rancangan Pasal & Ayat*)

Seluruh pemrosesan berjalan **100% lokal (*On-Premise*)** menggunakan **Gemma** dan **DeepSeek** di atas **Ollama**, sehingga jawaban terkunci pada data dan korpus hukum resmi yang disediakan tanpa halusinasi.

---

## Ringkasan Tech Stack (Frontend, Backend, Data & AI)

### 1. Frontend (`frontend/`)
- **Framework:** **Next.js 15** (*App Router*) + **React 19** + **TypeScript 5** (`jakarta-smarttax-chatbot-ai-frontend`).
- **Arsitektur Konfigurasi Modular (`src/config/smarttaxConfig.ts`):** Seluruh daftar tema pajak, mode kapabilitas (`konsultasi`, `pasal_hukum`, `perumusan_hukum`), dan *starter prompts* dipisahkan ke satu file konfigurasi agar tim mudah menambah fitur atau kategori baru.
- **Styling & Mobile UX (`src/app/globals.css`):** Menggunakan **Native CSS Custom Properties** dengan dukungan *off-canvas drawer* responsif di layar HP, *tabular-nums* untuk tabel rupiah, dan transisi halus antar-tema.
- **Streaming Client:** Membaca aliran **NDJSON** (*Newline-Delimited JSON*) secara *real-time* menggunakan Web `ReadableStream` + `TextDecoder`.

### 2. Backend (`backend/`)
- **Framework API:** **FastAPI** (Python 3.11+) di atas server ASGI **Uvicorn** (`jakarta-smarttax-chatbot-ai-backend`).
- **Manajemen Paket:** Dikelola menggunakan **`uv`** (`pyproject.toml` & `uv.lock`).
- **Validasi & Keamanan:** Validasi *payload* menggunakan **Pydantic v2** ditambah *middleware* HTTP Security Headers (`X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`) serta pembatasan `CORS_ORIGINS`.

### 3. Database & Vector Engine (`backend/data/`)
- **Database Relasional (SQLite 3 — `pajak_dki.sqlite`):**
  - Tabel `pajak_dki_jakarta`: Menyimpan data ketetapan objek pajak, NOP/NPWPD/SSPD/SKPD, nilai DPP/NJOP, pokok pajak, denda, dan status pembayaran.
  - Tabel `korpus_hukum_dki`: Menyimpan struktur pasal, ayat, bab/bagian, bunyi norma hukum, dan kaidah perumusan (*legal drafting*) untuk tiap kategori pajak.
- **Vector Database (ChromaDB `./smarttax_vectordb` + Qdrant `jakarta_smarttax_kb`):**
  - **ChromaDB (`jakarta_smarttax_knowledge`, `hnsw:space = cosine`):** Mesin penyimpanan vektor persisten untuk 3 jalur ingesti RAG multi-sumber (`pdf_regulasi` melalui `pymupdf4llm` + `RecursiveCharacterTextSplitter`, `excel_data` melalui serialisasi baris semantik `pandas` + `openpyxl`, dan `user_reasoning` untuk *live few-shot learning* kasus pajak).
  - **Qdrant (`jakarta_smarttax_kb`):** Menyimpan indeks vektor berdimensi `384` untuk pencarian semantik objek pajak dan korpus hukum.
- **Embedding Engine (`backend/app/embedder.py`):** Menggunakan model `nomic-embed-text` yang terikat pada CPU (*CPU-bound embeddings*) agar VRAM GPU tetap 100% didedikasikan untuk inferensi LLM utama.

### 4. AI / LLM Runtime & Safeguard 8GB VRAM (MSI Infinite S3 — NVIDIA RTX 5060 Ti 8GB)
- **Primary LLM (`gemma4:12b`):** Berjalan di atas Ollama lokal dengan batasan ketat memori 8GB VRAM:
  - `OLLAMA_FLASH_ATTENTION=1` dan `OLLAMA_KV_CACHE_TYPE=q8_0`
  - Parameter inferensi terkunci pada `num_ctx: 4096`, `temperature: 1.0`, `top_p: 0.95`, `top_k: 64`
  - Prepend `<|think|>` pada *system prompt* untuk penalaran pajak multi-langkah, serta pembersihan otomatis blok `<|think|>` dari riwayat *multi-turn chat* sebelum pengiriman *request* guna mencegah *KV cache OOM*.
- **AI Intelligence Benchmark & Audit Evidence Engine (`backend/app/eval_engine.py`):**
  - Menghitung skor komposit **SmartTax IQ %**: `(0.40 * Golden Eval Accuracy) + (0.25 * Faithfulness) + (0.20 * Retrieval Precision) + (0.15 * Domain Coverage)` terhadap `golden_dataset.json` (8 kasus pajak daerah DKI Jakarta: PBB-P2, JPB, PBJT, BPHTB, Reklame, PAT, dan sanksi denda keterlambatan).
  - Mencatat bukti *Before vs. After Delta* ke `./dashboard_intelligence_history.json`.

---

## Struktur Folder Proyek

```text
.
├── backend/
│   ├── app/
│   │   ├── config.py           # Konfigurasi Ollama (RTX 5060 Ti 8GB safeguards), ChromaDB, & Qdrant
│   │   ├── main.py             # Entrypoint FastAPI, endpoint chat, RAG ingestion, & evaluasi audit
│   │   ├── rag_ingestion.py    # Multi-source ChromaDB RAG engine (PDF, Excel/CSV, User Reasoning)
│   │   ├── eval_engine.py      # Mesin evaluasi RAGAS / TruLens Triad & Golden Dataset Benchmark
│   │   ├── ollama_service.py   # Router kapabilitas, strip <|think|>, & streaming LLM
│   │   ├── tax_db.py           # Skema SQLite (pajak_dki_jakarta & korpus_hukum_dki)
│   │   ├── vector_store.py     # Qdrant client & filter payload (tema_pajak + doc_type)
│   │   └── embedder.py         # CPU-bound nomic-embed-text & semantic tax synonym vector engine
│   ├── golden_dataset.json     # 8 kasus benchmark resmi pajak daerah DKI Jakarta
│   └── pyproject.toml          # Konfigurasi paket jakarta-smarttax-chatbot-ai-backend
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   └── IntelligenceAuditDashboard.tsx # Dashboard RAG Ingestion & Audit Evidence
│   │   ├── types/
│   │   │   └── audit.ts        # Kontrak tipe TypeScript untuk telemetri & audit evaluasi
│   │   ├── config/
│   │   │   └── smarttaxConfig.ts # Konfigurasi modular tema pajak, mode kapabilitas & prompt
│   │   └── app/
│   │       ├── audit/page.tsx  # Halaman langsung RAG & Intelligence Audit Dashboard (/audit)
│   │       ├── layout.tsx      # Root layout, font Inter, & konfigurasi viewport mobile
│   │       ├── page.tsx        # Komponen utama chat, toggle Audit Terminal, & stream NDJSON
│   │       └── globals.css     # Variabel desain Civic-Tech / Financial Terminal & layout responsif
│   └── package.json            # Konfigurasi paket jakarta-smarttax-chatbot-ai-frontend
└── docs/
    └── ENGINEERING_GUIDE.md    # Panduan teknis lengkap untuk Tim AI Jakarta SmartTax 2026
```

---

## Cara Menjalankan di Mesin Lokal

### Ollama Lokal (Gemma 4 12B — Safeguard RTX 5060 Ti 8GB VRAM)

Pastikan Ollama dijalankan dengan *environment variable* optimasi memori VRAM 8GB berikut sebelum memuat model `gemma4:12b`:

```dotenv
OLLAMA_FLASH_ATTENTION=1
OLLAMA_KV_CACHE_TYPE=q8_0
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=gemma4:12b
OLLAMA_DRAFTING_MODEL=gemma4:12b
OLLAMA_EMBED_MODEL=nomic-embed-text
OLLAMA_TIMEOUT=300
OLLAMA_NUM_CTX=4096
OLLAMA_TEMPERATURE=1.0
OLLAMA_TOP_P=0.95
OLLAMA_TOP_K=64
OLLAMA_THINK=true
CHROMA_PERSIST_DIR=./smarttax_vectordb
CHROMA_COLLECTION=jakarta_smarttax_knowledge
```

Gemma secara default langsung menghasilkan jawaban (`OLLAMA_THINK=false`).
Ubah menjadi `true` jika ingin mengaktifkan penalaran tambahan.
Ketiga mode memakai Gemma lokal. Pilihan model di tampilan mengikuti model yang
terpasang pada Ollama. Permintaan pertama dapat lebih lama saat model dimuat ke memori.
Periksa `GET http://localhost:8000/api/health` untuk status koneksi dan model aktif.
Respons chat menyertakan `response_source`: `ollama` untuk keluaran LLM,
`local_fallback` untuk jawaban dari data lokal saat LLM gagal, atau `local_routing`
untuk arahan pindah kategori pajak.

Pada Windows, jalankan backend dari folder `backend`:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Jalankan frontend dari folder `frontend` dengan `npm run dev`.


### 1. Menjalankan Backend (Port `8000`)

Setup pertama setelah clone: buat `.env` hanya jika belum tersedia, lalu
sesuaikan konfigurasi lokal. Jangan salin ulang contoh saat menjalankan aplikasi
di komputer yang sama karena konfigurasi yang sudah disimpan dapat tertimpa.

```bash
cd backend
if [ ! -f .env ]; then cp .env.example .env; fi
uv sync --locked
```

Untuk menjalankan kembali backend yang sudah disiapkan:

```bash
cd backend
uv run --locked uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Pengguna Windows dapat mengikuti [panduan setup backend Windows](docs/WINDOWS_BACKEND_SETUP.md).

### 2. Menjalankan Frontend (Port `3000`)

Setup pertama setelah clone: buat `.env.local` hanya jika belum ada.

```bash
cd frontend
if [ ! -f .env.local ]; then cp .env.example .env.local; fi
npm install
```

Untuk menjalankan kembali frontend yang sudah disiapkan:

```bash
cd frontend
npm run dev
```

Buka `http://localhost:3000` di *browser*.

---

## Panduan Teknis Tim Engineering

Penjelasan lengkap mengenai arsitektur kode, cara kerja *dual-model* **Gemma & DeepSeek**, serta panduan file mana yang harus diedit saat mengembangkan fitur baru tersedia di:

👉 **[Panduan Engineering Tim AI Jakarta SmartTax 2026 (`docs/ENGINEERING_GUIDE.md`)](docs/ENGINEERING_GUIDE.md)**
