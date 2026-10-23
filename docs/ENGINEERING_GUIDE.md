# Engineering & Maintenance Guide

Dokumen ini ditujukan bagi tim *Backend*, *Frontend*, dan *Infrastructure* yang akan memelihara atau mengembangkan layanan **Asisten Pajak Daerah DKI Jakarta**.

---

## 1. Arsitektur Backend (`backend/app/`)

Backend dibangun menggunakan **FastAPI** dengan pemisahan tanggung jawab (*separation of concerns*) menjadi lima modul utama:

### 1.1 `config.py` — Konfigurasi Terpusat
Seluruh variabel lingkungan dibaca melalui `config.py`:
- `OLLAMA_HOST`: Endpoint instance Ollama lokal (default: `http://localhost:11434`).
- `OLLAMA_MODEL`: Model default yang digunakan jika klien tidak mengirimkan parameter model.
- `QDRANT_URL`: Jika dikosongkan, sistem menggunakan penyimpanan lokal `backend/qdrant_storage/`. Jika diisi (mis. `http://qdrant.internal:6333`), sistem otomatis beralih ke Qdrant Server terpisah.
- `CORS_ORIGINS`: Daftar domain frontend yang diizinkan mengakses API (dipisahkan dengan koma).

### 1.2 `tax_db.py` — Skema Data Relasional & Kueri Agregasi
Modul ini mengelola tabel `pajak_dki_jakarta` serta potongan aturan pajak (`DKI_REGULASI_CHUNKS`).
- **Menambah atau Mengubah Kategori Pajak (`TAX_THEMES`):**
  Tambahkan kode kategori baru pada dictionary `TAX_THEMES` di bagian atas `tax_db.py`.
- **Menambah Kolom atau Mengubah Kueri SQL:**
  Tiga fungsi utama yang dipanggil oleh *pre-lookup router* adalah:
  1. `cari_data_pajak_dki(kata_kunci, tema_pajak)`: Pencarian berdasarkan nomor identitas (`NOP`, `NPWPD`, `SSPD`, `SKPD`), nama Wajib Pajak, nama objek, kelurahan, kecamatan, atau kota administrasi.
  2. `daftar_tunggakan_pajak_dki(tema_pajak, wilayah)`: Mengambil seluruh objek dengan status `BELUM LUNAS%` beserta agregasi pokok pajak dan denda.
  3. `rekapitulasi_pajak_dki(tema_pajak)`: Mengelompokkan target ketetapan, realisasi lunas, dan sisa tagihan per Kota Administrasi dan Kecamatan.

### 1.3 `embedder.py` & `vector_store.py` — Pencarian Vektor (Qdrant)
- Saat aplikasi melakukan *startup* (`lifespan` di `main.py`), `vector_store.reindex_all()` membaca seluruh baris dari `tax_db.py`, mengubahnya menjadi representasi teks terstruktur, mengekstrak vektor berdimensi `384` melalui `embedder.py`, dan menyimpannya ke koleksi Qdrant `pbb_p2_local_kb`.
- Setiap dokumen di Qdrant memiliki payload `tema_pajak`. Saat `vector_store.search(query, limit=6, tema_pajak=tema)` dipanggil, Qdrant menerapkan filter ketat (`FieldCondition(key="tema_pajak", match=MatchValue(value=tema))`) sehingga data antar jenis pajak tidak pernah tercampur.

### 1.4 `ollama_service.py` — Orkestrasi RAG & Streaming
Alur eksekusi di dalam `stream_chat_with_local_pbb()`:
1. **Deteksi Lintas Kategori (`_detect_cross_theme`):** Memeriksa apakah kata kunci pengguna merujuk ke kategori pajak lain (misalnya menanyakan `restoran` saat berada di `PBB-P2`). Jika terdeteksi, sistem langsung mengembalikan sinyal `suggested_theme` agar UI menampilkan tombol pindah kategori.
2. **Pre-Lookup Deterministik (`_run_local_pre_lookup`) + Pencarian Qdrant (`vector_store.search`):** Mengambil fakta eksak dari SQLite dan konteks semantik dari Qdrant.
3. **Injeksi Prompt (`build_thematic_system_prompt`):** Menggabungkan hasil SQLite + Qdrant ke dalam prompt sistem yang melarang penggunaan sumber luar.
4. **Fallback Deterministik (`_build_local_deterministic_answer`):** Apabila mesin Ollama sedang tidak aktif atau model belum diunduh, sistem secara otomatis menyusun tabel Markdown langsung dari hasil kueri SQLite sehingga layanan tetap beroperasi 100% tanpa *downtime*.

---

## 2. Arsitektur Frontend (`frontend/src/app/`)

Frontend dibangun dengan **Next.js 15 (App Router)** dan **React 19** tanpa ketergantungan *library* komponen pihak ketiga yang berat, sehingga mudah dikustomisasi.

### 2.1 Cara Mengubah Konfigurasi Kategori Pajak di UI (`page.tsx`)
Buka `frontend/src/app/page.tsx` dan cari objek `DKI_TAX_THEMES`:
- `shortLabel` & `label`: Nama pendek pada pill *composer* dan nama lengkap pada menu *dropdown*.
- `iconColor`: Warna aksen ikon SVG pada komponen `ThemeIcon`.
- `greeting` & `subtitle`: Teks sapaan utama pada layar *empty state*.
- `placeholder`: Teks petunjuk di dalam kolom input pesan.
- `suggestions`: Empat kartu *quick-prompt* yang muncul pada layar awal untuk masing-masing kategori pajak.

### 2.2 Cara Mengubah Tampilan, Warna & Responsivitas Mobile (`globals.css`)
Seluruh variabel warna dan ukuran diatur pada `:root` di `frontend/src/app/globals.css`:
- `--bg-sidebar`: `#171717` (panel navigasi kiri)
- `--bg-main`: `#212121` (kanvas percakapan utama)
- `--bg-surface`: `#2f2f2f` (kotak input *composer* & gelembung pesan pengguna)
- **Responsivitas Mobile (`@media (max-width: 767px)`):**
  Pada layar `< 768px`, `.sidebar-shell` otomatis berubah menjadi *fixed off-canvas drawer* dengan `.mobile-backdrop` gelap di belakangnya agar tidak menyempitkan kanvas chat utama.

### 2.3 Format Tabel & Nomor Identitas Pajak Interaktif
Komponen `FormattedMarkdown` di `page.tsx` mem-parsing tabel GFM (`| ... |`) dan teks berkode (`` `...` ``). Setiap kode di dalam *backtick* (seperti NOP atau NPWPD) dirender menggunakan kelas `.copyable-code` yang otomatis menyalin teks ke *clipboard* saat diklik.

---

## 3. Keamanan & Praktik Produksi

1. **Pembatasan CORS:** Pastikan variabel `CORS_ORIGINS` di `backend/.env` hanya berisi domain resmi aplikasi frontend saat di-deploy ke produksi.
2. **Validasi Input:** `ChatRequestInput` di `backend/app/main.py` membatasi panjang pesan maksimal `2000` karakter dan riwayat maksimal `20` pesan untuk mencegah *payload flooding*.
3. **Parameterized SQL Queries:** Seluruh kueri pada `tax_db.py` wajib menggunakan *parameter binding* (`?` pada SQLite atau `$1` pada PostgreSQL). Jangan pernah menggabungkan input pengguna langsung ke dalam string SQL.
4. **HTTP Security Headers:** Baik Next.js (`next.config.mjs`) maupun FastAPI (`main.py`) telah menyertakan header `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, dan `Referrer-Policy: strict-origin-when-cross-origin`.
