# Jakarta SmartTax

Jakarta SmartTax (JST) adalah chatbot untuk membahas pajak daerah DKI Jakarta berdasarkan dokumen yang dimasukkan oleh pengelola. Kategori yang tersedia di tampilan mencakup PBB-P2, PBJT, BPHTB, Pajak Reklame, dan Pajak Air Tanah.

Aplikasi ini masih dikembangkan. Jawaban bergantung pada isi dokumen, hasil pencarian sumber, dan model yang digunakan. Pilihan kategori tidak berarti datanya sudah tersedia. Informasi penting tetap perlu diperiksa kembali melalui sumbernya.

## Yang sudah tersedia

Pengguna bisa memulai percakapan dari Home, membuka kembali riwayat, mengganti nama, menyimpan, dan menyematkan percakapan. Chat yang disematkan tetap berada di atas. Halaman Disimpan dan Semua percakapan tersedia terpisah, sedangkan pencarian dapat dibuka dari sidebar.

Jawaban tampil bertahap dan dapat dihentikan. Jika ada referensi, pengguna bisa membuka panel sumber untuk melihat nama dokumen dan halaman yang dirujuk. Pada layar kecil, panel ini terbuka dari bawah. Tampilan mendukung mode terang dan gelap, dengan pengaturan tema di sidebar.

Chat menerima pesan teks. Upload dokumen dan pengelolaan sumber dilakukan melalui dashboard developer. Tombol Bagikan masih dinonaktifkan; tautan percakapan publik belum tersedia.

## Cara kerja aplikasi

Frontend menggunakan Next.js, React, dan TypeScript. Backend menggunakan FastAPI dan menjalankan permintaan model melalui Ollama. Model bawaan pada contoh konfigurasi adalah `gemma4:12b`.

Dokumen yang diunggah diproses menjadi potongan teks, lalu disimpan bersama metadata sumbernya. Qdrant menyimpan indeks vektor untuk pencarian dokumen dan contoh kasus. Konfigurasi bawaan memakai penyimpanan embedded lokal, sehingga tidak membutuhkan server Qdrant terpisah.

Embedding yang aktif masih menggunakan hashing khusus aplikasi. BGE-M3 belum diterapkan. PDF dibaca menggunakan pypdf, sementara data tabel diproses menggunakan pandas. OCR untuk PDF scan belum tersedia.

Ketika pengguna bertanya, backend mencari sumber yang relevan dan mengirim konteks tersebut ke model. Sapaan sederhana melewati pencarian dokumen, tetapi jawabannya tetap dibuat oleh model. Pembatasan kategori pajak diberikan melalui instruksi model dan masih perlu diuji kepatuhannya.

Akun, sesi, dan riwayat percakapan disimpan di SQLite. Riwayat tetap ada setelah aplikasi dijalankan ulang selama file datanya tidak dihapus. Memory lintas percakapan belum tersedia.

## Persiapan di Windows

Siapkan Python 3.12 dari python.org, uv, Node.js beserta npm, dan Ollama. Perintah di bawah menggunakan PowerShell dan dimulai dari folder utama proyek.

### Setup pertama

Langkah ini dilakukan setelah clone atau saat menyiapkan PC baru. Salin contoh konfigurasi hanya jika file tujuan belum ada. Jangan menjalankan perintah penyalinan pada konfigurasi yang sudah dipakai karena isinya dapat tertimpa.

Buka terminal untuk backend:

```powershell
cd backend
Copy-Item .env.example .env
uv sync --locked --python (py -3.12 -c "import sys; print(sys.executable)") --no-python-downloads
```

Sesuaikan `backend/.env` sebelum menjalankan aplikasi. Pilih pengaturan login sesuai kebutuhan pada bagian akses akun di bawah.

Buka terminal lain untuk frontend:

```powershell
cd frontend
Copy-Item .env.example .env.local
npm ci
```

Contoh konfigurasi frontend menggunakan backend di `http://localhost:8000`.

Unduh model jika belum tersedia:

```powershell
ollama pull gemma4:12b
```

Pastikan Ollama berjalan. Nama model dan ukuran konteks mengikuti pengaturan pada `backend/.env`; contoh konfigurasi menggunakan `OLLAMA_NUM_CTX=4096`. Pemakaian RAM dan VRAM akan berubah mengikuti model dan ukuran konteks yang dipilih.

### Menjalankan aplikasi

Jika setup sudah pernah dilakukan, cukup buka dua terminal. Tidak perlu menyalin ulang konfigurasi atau mengunduh model yang sudah ada.

Pada terminal backend:

```powershell
cd backend
uv run --locked uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Pada terminal frontend:

```powershell
cd frontend
npm run dev
```

Buka [chatbot](http://localhost:3000). Dashboard tersedia di [halaman admin](http://localhost:3000/admin) untuk pengguna yang memiliki akses developer.

## Akses akun dan dashboard

Dengan `AUTH_ENABLED=true`, pengguna perlu mendaftar melalui Google sebelum bisa login. Dashboard dan API pengelolaan hanya dapat digunakan oleh akun developer yang ditentukan di konfigurasi backend.

Untuk menyiapkan Google Auth, buat OAuth Client jenis Web application. Gunakan `http://localhost:3000` sebagai alamat frontend dan `http://localhost:8000/api/auth/google/callback` sebagai redirect URI untuk pengembangan lokal. Isi `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `AUTH_PUBLIC_URL`, `GOOGLE_REDIRECT_URI`, dan `AUTH_DEVELOPER_EMAILS` pada file `.env` yang sudah ada. Konfigurasi Google dan aplikasi harus memakai alamat yang sama.

Mode pengembangan tanpa login tersedia melalui `AUTH_ENABLED=false`, khusus localhost. Mode ini menggunakan satu identitas developer lokal, sehingga pengguna lokal tidak memiliki riwayat terpisah. Aktifkan kembali autentikasi sebelum menyiapkan akses publik. Setelah mengubah pengaturan autentikasi, restart backend dan muat ulang browser.

Jangan memasukkan `.env`, client secret, atau data akun ke Git.

## Penyimpanan lokal

| Isi | Lokasi bawaan |
| :--- | :--- |
| Akun, sesi, dan riwayat chat | `backend/data/auth.sqlite` |
| File asli dan arsip sumber | `backend/data/uploads/` |
| Indeks pengetahuan Qdrant | `backend/qdrant_knowledge_storage/` |

Lokasi relatif pada konfigurasi penyimpanan ditentukan dari folder backend. Menjalankan ulang aplikasi tidak menghapus data. Jangan menghapus file atau folder tersebut jika tujuannya hanya me-restart server.

Folder `docs/` dan skrip `start.sh` digunakan secara lokal dan diabaikan oleh Git. Keduanya tidak diperlukan untuk mengikuti perintah menjalankan aplikasi di README ini.

## Bagian kode yang sering digunakan

| Lokasi | Kegunaan |
| :--- | :--- |
| `frontend/src/app/page.tsx` | Home, percakapan, dan navigasi chat |
| `frontend/src/app/globals.css` | Tampilan dan penyesuaian ukuran layar |
| `frontend/src/components/SourcePanel.tsx` | Panel referensi jawaban |
| `frontend/src/lib/useServerHistory.ts` | Pemuatan dan penyimpanan riwayat |
| `frontend/src/lib/api.ts` | Permintaan API dan pembatas klik berulang |
| `backend/app/main.py` | Endpoint utama FastAPI |
| `backend/app/auth.py` | Login, sesi, dan pemeriksaan akses |
| `backend/app/chat_history.py` | Penyimpanan riwayat per akun |
| `backend/app/ollama_service.py` | Konteks jawaban dan streaming Ollama |
| `backend/app/rag_ingestion.py` | Pengolahan sumber dan pencarian pengetahuan |
| `backend/app/vector_store.py` | Penyimpanan indeks Qdrant |
| `backend/app/embedder.py` | Pembentukan vektor teks |

## Pengujian

Jalankan pengujian backend dari folder `backend`:

```powershell
uv run --locked python -m unittest discover -s tests
```

Jalankan pengujian interaksi API dan riwayat dari folder `frontend`:

```powershell
node --test tests/chat-history-state.test.cjs tests/api-request-limits.test.cjs tests/api-local-recovery.test.cjs
```

Untuk memeriksa build frontend:

```powershell
npm run build
```

Hentikan frontend development sebelum menjalankan build di folder yang sama agar keduanya tidak menulis ke folder `.next` secara bersamaan.
