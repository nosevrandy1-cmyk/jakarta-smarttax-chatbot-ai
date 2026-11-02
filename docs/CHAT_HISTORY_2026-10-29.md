# History chat per akun JST

Tanggal: 29 Oktober 2026. Branch: feat/google-auth.

## Perubahan

Percakapan disimpan di tabel `account_chat_history` pada `backend/data/auth.sqlite`, terpisah dari koleksi pengetahuan RAG. Database ini sudah diabaikan Git. Data history tidak otomatis menjadi sumber jawaban atau data training.

Setiap akun memiliki snapshot percakapannya sendiri. Isi mencakup judul, kategori pajak, pesan, dan referensi jawaban. Rename, hapus, dan pemulihan melalui Undo ikut disimpan. Logout mencabut sesi tetapi tidak menghapus history server. Akun lain, termasuk developer, tidak memperoleh akses history pengguna lain melalui API ini.

Riwayat localStorage dari implementasi lama tidak diimpor otomatis. Pengujian fitur ini dimulai dengan percakapan baru. Preferensi tema terang/gelap tetap lokal di browser.

## Cara penggunaan dan tes dua akun

1. Refresh aplikasi. Masuk sebagai akun A dan kirim pesan yang mudah dikenali.
2. Tunggu jawaban selesai dan status **Riwayat tersimpan di akun** muncul. Tombol Simpan dapat digunakan untuk mengulangi penyimpanan.
3. Refresh: judul, pesan, dan referensi harus kembali tampil. Coba rename percakapan dan refresh lagi.
4. Keluar, lalu masuk sebagai akun B. Percakapan A tidak boleh terlihat. Buat percakapan B dan tunggu tersimpan.
5. Keluar dari B dan masuk kembali sebagai A: percakapan A harus tersedia, sedangkan percakapan B tidak muncul.
6. Opsional: buka akun A di profil browser/perangkat lain dan refresh untuk memuat history yang sama. Gunakan profil terpisah jika ingin dua akun aktif bersamaan; tab dalam satu profil berbagi cookie login.

Akun baru tetap harus mendaftar Google terlebih dahulu. Allowlist lokal dan akses developer tetap mengikuti konfigurasi autentikasi.

## Penyimpanan dan keamanan

- GET/PUT `/api/history` memakai identitas sesi server; user ID dari payload ditolak.
- Mutasi memerlukan Origin dan CSRF yang sesuai, serta header akun dari UI. Header tersebut harus cocok dengan pemilik sesi; header tidak memberikan akses ke akun lain.
- Setiap baca/tulis dibatasi ke satu user ID. ID percakapan yang sama pada dua akun tidak menyebabkan keduanya berbagi data.
- Snapshot memakai revision dan transaksi SQLite. Tulis dari tab/perangkat dengan versi lama ditolak 409, sehingga tidak menimpa perubahan baru secara diam-diam.
- Saat load gagal, UI tidak membuat snapshot kosong yang menimpa history. Pengguna diminta memuat ulang.
- Penyimpanan otomatis dilakukan 500 ms setelah perubahan stabil; token streaming tetap dalam memori sampai jawaban selesai atau dihentikan. Logout menunggu penyimpanan terakhir; kegagalan simpan menunda logout untuk mencegah kehilangan perubahan.
- Request dibatasi, payload divalidasi, dan respons API memakai Cache-Control no-store.

## Batas tahap awal

Maksimal 200 percakapan, 500 pesan per percakapan, serta sekitar 900 KB JSON history per akun. Pesan dan referensi ikut berkontribusi terhadap batas tersebut. Snapshot belum memakai pagination atau sinkronisasi realtime antartab; muat ulang untuk mengambil perubahan dari perangkat lain. Saat konflik, simpan teks yang belum tersimpan sebelum memuat ulang.

Refresh/menutup browser sebelum status tersimpan muncul dapat kehilangan perubahan terbaru, terutama saat jawaban masih streaming. Database menyimpan history dalam bentuk teks, tanpa enkripsi khusus aplikasi; perlindungan file server dan backup tetap diperlukan. Penghapusan akun mandiri dan kontribusi history untuk training belum termasuk fitur ini.

## Verifikasi

- 72 tes backend lolos: 62 regresi dan 10 tes history.
- History dua akun diuji dengan akun sintetis pada database sementara, bukan akun Google pribadi pengguna.
- Tes mencakup isolasi baca/tulis dengan ID percakapan sama, pergantian akun pada tab lama, logout/login ulang, CSRF, Origin, sesi kedaluwarsa, snapshot basi, rename/hapus/restore, validasi payload, dan batas ukuran.
- TypeScript lolos setelah pengaman pergantian akun ditambahkan.
- Build production frontend terisolasi lolos pada implementasi terakhir, termasuk header pengaman pergantian akun.
- Pengguna mengonfirmasi hasil pengujian sudah sesuai setelah mencoba fitur. Ini merupakan konfirmasi pengguna, bukan rekaman UAT seluruh skenario browser. Tidak ada screenshot akun yang disimpan ke proyek.