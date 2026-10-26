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
- **Vector Database (Qdrant — `jakarta_smarttax_kb`):** Menyimpan indeks vektor berdimensi `384` untuk pencarian semantik yang difilter ketat berdasarkan `tema_pajak` dan `doc_type` (`objek_pajak`, `regulasi`, `pasal_hukum`).
- **Embedding Engine (`backend/app/embedder.py`):** Mendukung model lokal (`bge-m3` / HuggingFace `transformers`) dengan *fallback* deterministik 384-dimensi untuk lingkungan *offline*.

### 4. AI / LLM Runtime (Ollama — Gemma & DeepSeek)
- **Gemma (`gemma4:12b`):** Digunakan sebagai mesin utama untuk RAG cepat pada konsultasi tarif, rumus perhitungan, dan pengecekan data objek pajak.
- **Model drafting (`OLLAMA_DRAFTING_MODEL`):** Secara default memakai `gemma4:12b` juga. Bisa diganti menjadi `deepseek-r1:8b` jika model tersebut sudah tersedia untuk perumusan dasar hukum baru (*legal drafting*). Mendukung pembagian beban paralel 2 PC di jaringan LAN (`OLLAMA_HOST` & `OLLAMA_SECONDARY_HOST`).
- **Deterministic Grounded Fallback:** Jika layanan Ollama di mesin lokal belum aktif, backend otomatis menyajikan tabel data, bunyi pasal, dan kerangka *legal drafting* langsung dari SQLite & Qdrant.

---

## Struktur Folder Proyek

```text
.
├── backend/
│   ├── app/
│   │   ├── config.py           # Konfigurasi host Ollama (Gemma & DeepSeek), Qdrant, & CORS
│   │   ├── main.py             # Entrypoint FastAPI, endpoint chat, reindex, & korpus-hukum
│   │   ├── ollama_service.py   # Router kapabilitas (Tarif, Pasal, Perumusan) & streaming LLM
│   │   ├── tax_db.py           # Skema SQLite (pajak_dki_jakarta & korpus_hukum_dki)
│   │   ├── vector_store.py     # Qdrant client & filter payload (tema_pajak + doc_type)
│   │   └── embedder.py         # Pembangkit vektor 384-dimensi lokal
│   └── pyproject.toml          # Konfigurasi paket jakarta-smarttax-chatbot-ai-backend
├── frontend/
│   ├── src/
│   │   ├── config/
│   │   │   └── smarttaxConfig.ts # Konfigurasi modular tema pajak, mode kapabilitas & prompt
│   │   └── app/
│   │       ├── layout.tsx      # Root layout, font Inter, & konfigurasi viewport mobile
│   │       ├── page.tsx        # Komponen utama chat, pemilih mode, & pembaca stream NDJSON
│   │       └── globals.css     # Variabel desain, layout desktop, & drawer responsif mobile
│   └── package.json            # Konfigurasi paket jakarta-smarttax-chatbot-ai-frontend
└── docs/
    └── ENGINEERING_GUIDE.md    # Panduan teknis lengkap untuk Tim AI Jakarta SmartTax 2026
```

---

## Cara Menjalankan di Mesin Lokal

### Ollama lokal (Gemma 4 12B)

Pastikan Ollama berjalan di `http://localhost:11434` dan `ollama list` menampilkan
`gemma4:12b`. Jika belum terpasang, jalankan `ollama pull gemma4:12b`.
Backend otomatis membaca `backend/.env`; variabel lingkungan proses tetap lebih diutamakan.

```dotenv
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=gemma4:12b
OLLAMA_DRAFTING_MODEL=gemma4:12b
OLLAMA_TIMEOUT=300
OLLAMA_NUM_CTX=8192
OLLAMA_THINK=false
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

```bash
cd backend
cp .env.example .env
uv sync
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 2. Menjalankan Frontend (Port `3000`)

```bash
cd frontend
cp .env.example .env.local
npm install
npm run dev
```

Buka `http://localhost:3000` di *browser*.

---

## Panduan Teknis Tim Engineering

Penjelasan lengkap mengenai arsitektur kode, cara kerja *dual-model* **Gemma & DeepSeek**, serta panduan file mana yang harus diedit saat mengembangkan fitur baru tersedia di:

👉 **[Panduan Engineering Tim AI Jakarta SmartTax 2026 (`docs/ENGINEERING_GUIDE.md`)](docs/ENGINEERING_GUIDE.md)**
