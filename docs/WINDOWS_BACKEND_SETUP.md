# Backend Windows dengan Smart App Control aktif

Perbaikan diverifikasi pada 29 Oktober 2026 dengan Python 3.12.10 dari instalasi resmi python.org. Tidak diperlukan WSL atau penonaktifan Smart App Control.

## Konfigurasi hanya pada setup pertama

Setelah clone baru, buat `.env` hanya jika belum ada. Dari folder backend:

```powershell
if (-not (Test-Path -LiteralPath '.env')) {
    Copy-Item -LiteralPath '.env.example' -Destination '.env'
}
```

Sesuaikan konfigurasi lokal setelah dibuat. Jangan menjalankan penyalinan ulang
setiap kali memulai backend pada komputer yang sama. Environment Python dapat
dibuat ulang tanpa menimpa `.env`.

Untuk penggunaan berikutnya cukup:

```powershell
uv run --locked uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

## Membuat environment baru

Gunakan Python 3.12 yang telah terpasang dari sumber resmi dan dapat memuat modul standar. Dari PowerShell pada folder backend:

```powershell
$pythonPath = py -3.12 -c "import sys; print(sys.executable)"
& $pythonPath -I -c "import ctypes, ssl, sqlite3; print('Runtime OK')"
uv sync --locked --python $pythonPath --no-python-downloads
uv run --locked uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Untuk environment lama yang sudah memakai runtime lain, hentikan backend dan cadangkan `.venv` sebelum membuat environment baru. Jangan menghapus database, file unggahan, `.env`, atau koleksi vektor. Pada mesin yang diperbaiki, environment sebelumnya tersimpan dalam `backend/.runtime-backups/` dan diabaikan Git. Environment cadangan tersebut mempertahankan file lama untuk pemulihan; pemindahan folder tidak menjamin launcher venv lama dapat langsung dijalankan dari lokasi barunya.

## Versi yang dikunci untuk Windows

| Komponen | Versi |
| --- | --- |
| Python yang diuji | 3.12.10 |
| Pandas | 2.3.3 |
| NumPy | 2.2.6 |
| PyMuPDF | 1.26.6 |
| PyMuPDF4LLM | 0.0.27 |

Pin di `pyproject.toml` menggunakan marker Windows. Batas dependensi platform lain dipertahankan. Rentang Python proyek menjadi 3.11 sampai sebelum 3.14 karena resolver dan ketersediaan wheel pada platform yang diwajibkan belum mendukung semua versi Python yang sebelumnya diiklankan. Python 3.11/3.13 belum diuji langsung dalam perbaikan ini.

DLL Pandas/PyMuPDF dan runtime Python sebelumnya ditolak oleh kebijakan Windows pada perangkat yang diperiksa. Versi di atas berhasil dimuat tanpa perubahan kebijakan. Hasil kepercayaan Smart App Control dapat berbeda di perangkat lain; daftar ini bukan jaminan semua perangkat akan mengizinkannya.

## Pemeriksaan

```powershell
uv run --locked python -c "import ctypes, pandas, numpy, pymupdf, chromadb; print('Imports OK')"
uv run --locked python -m unittest discover -s tests -v
Invoke-RestMethod http://127.0.0.1:8000/api/health
```

Perbaikan ini lolos 21 tes, termasuk PDF/Excel melalui database sementara dan pelepasan file PDF pada jalur berhasil maupun error. `rag_ingestion.py` sekarang memiliki kepemilikan eksplisit atas handle dokumen PDF agar berkas sementara bisa dihapus pada Windows.

Peringatan PyTorch tidak terpasang tidak menghentikan backend: inferensi model berjalan melalui Ollama, sedangkan tokenizer/embedding CPU tetap tersedia sesuai implementasi proyek. Ollama harus berjalan terpisah agar model dapat menjawab.

Jika DLL kembali ditolak, tinjau CodeIntegrity Event 3077 bersama pengelola perangkat dan gunakan komponen yang diizinkan. Jangan mematikan proteksi atau mengubah kebijakan kepercayaan sebagai bagian dari menjalankan proyek.
