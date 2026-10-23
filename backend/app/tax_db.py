import json
import sqlite3
from typing import Any, Dict, List

from .config import DATA_DIR

DB_PATH = DATA_DIR / "pajak_dki.sqlite"

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

DKI_TAX_RECORDS: List[Dict[str, Any]] = [
    # ==================== 1. PBB-P2 DKI JAKARTA ====================
    {
        "tema_pajak": "PBB-P2",
        "nomor_identitas": "31.71.020.004.012-0108.0",
        "nama_wp": "Dr. Hendra Kusuma",
        "nama_objek": "Rumah Tinggal Menteng",
        "alamat_objek": "Jl. Teuku Umar No. 24 RT 01/RW 04",
        "kelurahan": "Menteng",
        "kecamatan": "Menteng",
        "kota_administrasi": "Jakarta Pusat",
        "kategori_subjek": "Orang Pribadi - Hunian",
        "dpp_atau_njop_rp": 14500000000,
        "pengurang_tak_kena_pajak_rp": 60000000,
        "tarif_persen": 0.25,
        "pokok_pajak_rp": 18050000,
        "denda_rp": 0,
        "total_tagihan_rp": 0,
        "masa_atau_tahun_pajak": "2026",
        "status_bayar": "LUNAS",
        "jatuh_tempo": "2026-09-30",
        "keterangan": "Luas Bumi 420 m2, Bangunan 350 m2. Bebas denda.",
    },
    {
        "tema_pajak": "PBB-P2",
        "nomor_identitas": "31.74.010.003.008-0042.0",
        "nama_wp": "PT Graha Sudirman Internasional",
        "nama_objek": "Gedung Perkantoran SCBD Lot 9",
        "alamat_objek": "Jl. Jend. Sudirman Kav. 52-53",
        "kelurahan": "Senayan",
        "kecamatan": "Kebayoran Baru",
        "kota_administrasi": "Jakarta Selatan",
        "kategori_subjek": "Badan - Komersial Perkantoran",
        "dpp_atau_njop_rp": 185000000000,
        "pengurang_tak_kena_pajak_rp": 60000000,
        "tarif_persen": 0.50,
        "pokok_pajak_rp": 369880000,
        "denda_rp": 3698800,
        "total_tagihan_rp": 373578800,
        "masa_atau_tahun_pajak": "2026",
        "status_bayar": "BELUM LUNAS",
        "jatuh_tempo": "2026-09-30",
        "keterangan": "Luas Bumi 2.800 m2, Bangunan 14.500 m2. Menunggak 1 bulan (denda 1%).",
    },
    {
        "tema_pajak": "PBB-P2",
        "nomor_identitas": "31.74.040.002.015-0219.0",
        "nama_wp": "Hj. Siti Rahmawati",
        "nama_objek": "Rumah Tinggal Tebet Timur",
        "alamat_objek": "Jl. Tebet Timur Dalam Raya No. 45",
        "kelurahan": "Tebet Timur",
        "kecamatan": "Tebet",
        "kota_administrasi": "Jakarta Selatan",
        "kategori_subjek": "Orang Pribadi - Hunian",
        "dpp_atau_njop_rp": 1850000000,
        "pengurang_tak_kena_pajak_rp": 60000000,
        "tarif_persen": 0.0,
        "pokok_pajak_rp": 0,
        "denda_rp": 0,
        "total_tagihan_rp": 0,
        "masa_atau_tahun_pajak": "2026",
            "status_bayar": "LUNAS (INSENTIF 100%)",
        "jatuh_tempo": "2026-09-30",
        "keterangan": "Mendapat pembebasan pokok 100% (1 rumah tinggal orang pribadi NJOP di bawah Rp 2 Miliar di DKI Jakarta).",
    },
    {
        "tema_pajak": "PBB-P2",
        "nomor_identitas": "31.72.060.005.019-0088.0",
        "nama_wp": "Budianto Halim",
        "nama_objek": "Ruko Boulevard Kelapa Gading",
        "alamat_objek": "Jl. Boulevard Raya Blok QJ-3 No. 11",
        "kelurahan": "Kelapa Gading Barat",
        "kecamatan": "Kelapa Gading",
        "kota_administrasi": "Jakarta Utara",
        "kategori_subjek": "Orang Pribadi - Komersial Ruko",
        "dpp_atau_njop_rp": 6400000000,
        "pengurang_tak_kena_pajak_rp": 60000000,
        "tarif_persen": 0.50,
        "pokok_pajak_rp": 12680000,
        "denda_rp": 253600,
        "total_tagihan_rp": 12933600,
        "masa_atau_tahun_pajak": "2025",
        "status_bayar": "BELUM LUNAS",
        "jatuh_tempo": "2025-09-30",
        "keterangan": "Luas Bumi 135 m2, Bangunan 405 m2. Tunggakan SPPT 2025.",
    },
    {
        "tema_pajak": "PBB-P2",
        "nomor_identitas": "31.73.050.001.007-0312.0",
        "nama_wp": "Ir. Bambang Prasetyo",
        "nama_objek": "Hunian Puri Indah",
        "alamat_objek": "Jl. Puri Kencana Blok K7 No. 9",
        "kelurahan": "Kembangan Selatan",
        "kecamatan": "Kembangan",
        "kota_administrasi": "Jakarta Barat",
        "kategori_subjek": "Orang Pribadi - Hunian",
        "dpp_atau_njop_rp": 5800000000,
        "pengurang_tak_kena_pajak_rp": 60000000,
        "tarif_persen": 0.15,
        "pokok_pajak_rp": 4305000,
        "denda_rp": 43050,
        "total_tagihan_rp": 4348050,
        "masa_atau_tahun_pajak": "2026",
        "status_bayar": "BELUM LUNAS",
        "jatuh_tempo": "2026-09-30",
        "keterangan": "Luas Bumi 300 m2, Bangunan 260 m2.",
    },

    # ==================== 2. PBJT DKI JAKARTA ====================
    {
        "tema_pajak": "PBJT",
        "nomor_identitas": "NPWPD-31.74.88102.001",
        "nama_wp": "PT Kuliner Senopati Nusantara",
        "nama_objek": "Restoran Senopati Bistro & Grill",
        "alamat_objek": "Jl. Senopati No. 68, Kebayoran Baru",
        "kelurahan": "Selong",
        "kecamatan": "Kebayoran Baru",
        "kota_administrasi": "Jakarta Selatan",
        "kategori_subjek": "PBJT - Makanan dan/atau Minuman (Restoran)",
        "dpp_atau_njop_rp": 1450000000,
        "pengurang_tak_kena_pajak_rp": 0,
        "tarif_persen": 10.0,
        "pokok_pajak_rp": 145000000,
        "denda_rp": 1450000,
        "total_tagihan_rp": 146450000,
        "masa_atau_tahun_pajak": "September 2026",
        "status_bayar": "BELUM LUNAS",
        "jatuh_tempo": "2026-10-15",
        "keterangan": "Omzet bruto masa September 2026 Rp 1,45 Miliar. Tarif PBJT Restoran DKI Jakarta 10%.",
    },
    {
        "tema_pajak": "PBJT",
        "nomor_identitas": "NPWPD-31.71.44019.002",
        "nama_wp": "PT Grand Thamrin Hospitality",
        "nama_objek": "Hotel Grand Thamrin Suites",
        "alamat_objek": "Jl. M.H. Thamrin No. 30",
        "kelurahan": "Gondangdia",
        "kecamatan": "Menteng",
        "kota_administrasi": "Jakarta Pusat",
        "kategori_subjek": "PBJT - Jasa Perhotelan",
        "dpp_atau_njop_rp": 4200000000,
        "pengurang_tak_kena_pajak_rp": 0,
        "tarif_persen": 10.0,
        "pokok_pajak_rp": 420000000,
        "denda_rp": 0,
        "total_tagihan_rp": 0,
        "masa_atau_tahun_pajak": "September 2026",
        "status_bayar": "LUNAS",
        "jatuh_tempo": "2026-10-15",
        "keterangan": "SPTPD Masa September 2026 telah dilaporkan dan disetor tepat waktu via e-SPTPD DKI.",
    },
    {
        "tema_pajak": "PBJT",
        "nomor_identitas": "NPWPD-31.72.99210.005",
        "nama_wp": "PT Pantai Indah Hiburan Malam",
        "nama_objek": "Emerald Club & Karaoke PIK",
        "alamat_objek": "Kawasan Pantai Indah Kapuk Boulevard Blok B",
        "kelurahan": "Kamal Muara",
        "kecamatan": "Penjaringan",
        "kota_administrasi": "Jakarta Utara",
        "kategori_subjek": "PBJT - Jasa Kesenian & Hiburan (Diskotek/Karaoke)",
        "dpp_atau_njop_rp": 950000000,
        "pengurang_tak_kena_pajak_rp": 0,
        "tarif_persen": 40.0,
        "pokok_pajak_rp": 380000000,
        "denda_rp": 3800000,
        "total_tagihan_rp": 383800000,
        "masa_atau_tahun_pajak": "September 2026",
        "status_bayar": "BELUM LUNAS",
        "jatuh_tempo": "2026-10-15",
        "keterangan": "Tarif khusus PBJT hiburan diskotek/karaoke/klab malam di DKI Jakarta sebesar 40%.",
    },
    {
        "tema_pajak": "PBJT",
        "nomor_identitas": "NPWPD-31.75.33104.008",
        "nama_wp": "PT Sentra Parkir Mandiri",
        "nama_objek": "Pengelola Parkir Mall Cipinang Indah",
        "alamat_objek": "Jl. Raya Kalimalang No. 88",
        "kelurahan": "Pondok Bambu",
        "kecamatan": "Duren Sawit",
        "kota_administrasi": "Jakarta Timur",
        "kategori_subjek": "PBJT - Jasa Parkir",
        "dpp_atau_njop_rp": 620000000,
        "pengurang_tak_kena_pajak_rp": 0,
        "tarif_persen": 10.0,
        "pokok_pajak_rp": 62000000,
        "denda_rp": 0,
        "total_tagihan_rp": 0,
        "masa_atau_tahun_pajak": "September 2026",
        "status_bayar": "LUNAS",
        "jatuh_tempo": "2026-10-15",
        "keterangan": "Tarif PBJT Jasa Parkir di DKI Jakarta sebesar 10%.",
    },

    # ==================== 3. BPHTB DKI JAKARTA ====================
    {
        "tema_pajak": "BPHTB",
        "nomor_identitas": "SSPD-BPHTB-3174-2026-00912",
        "nama_wp": "Andi Wijaya Kusuma",
        "nama_objek": "Perolehan Jual Beli (AJB) Rumah Cilandak",
        "alamat_objek": "Jl. Cilandak Tengah No. 18",
        "kelurahan": "Cilandak Barat",
        "kecamatan": "Cilandak",
        "kota_administrasi": "Jakarta Selatan",
        "kategori_subjek": "BPHTB - Jual Beli (AJB)",
        "dpp_atau_njop_rp": 3500000000,
        "pengurang_tak_kena_pajak_rp": 80000000,
        "tarif_persen": 5.0,
        "pokok_pajak_rp": 171000000,
        "denda_rp": 0,
        "total_tagihan_rp": 0,
        "masa_atau_tahun_pajak": "Oktober 2026",
        "status_bayar": "LUNAS (TERVALIDASI)",
        "jatuh_tempo": "2026-10-20",
        "keterangan": "NPOP Rp 3,5 Miliar - NPOPTKP Umum DKI Rp 80 Juta = NPOPKP Rp 3,42 Miliar x 5% = Rp 171.000.000.",
    },
    {
        "tema_pajak": "BPHTB",
        "nomor_identitas": "SSPD-BPHTB-3171-2026-01145",
        "nama_wp": "Ratna Sari Dewi",
        "nama_objek": "Perolehan Waris Tanah & Bangunan Cempaka Putih",
        "alamat_objek": "Jl. Cempaka Putih Tengah XXVII No. 9",
        "kelurahan": "Cempaka Putih Timur",
        "kecamatan": "Cempaka Putih",
        "kota_administrasi": "Jakarta Pusat",
        "kategori_subjek": "BPHTB - Waris / Hibah Wasiat",
        "dpp_atau_njop_rp": 2400000000,
        "pengurang_tak_kena_pajak_rp": 350000000,
        "tarif_persen": 5.0,
        "pokok_pajak_rp": 102500000,
        "denda_rp": 0,
        "total_tagihan_rp": 102500000,
        "masa_atau_tahun_pajak": "Oktober 2026",
        "status_bayar": "BELUM LUNAS (MENUNGGU PEMBAYARAN)",
        "jatuh_tempo": "2026-10-31",
        "keterangan": "NPOP Rp 2,4 Miliar - NPOPTKP Waris Rp 350 Juta = NPOPKP Rp 2,05 Miliar x 5% = Rp 102.500.000.",
    },

    # ==================== 4. PAJAK REKLAME DKI JAKARTA ====================
    {
        "tema_pajak": "REKLAME",
        "nomor_identitas": "SKPD-REK-3171-2026-0402",
        "nama_wp": "PT Media Visi Digital Jakarta",
        "nama_objek": "Reklame LED Videotron Bundaran HI / Thamrin",
        "alamat_objek": "Jl. M.H. Thamrin Kav. 9 (Kawasan Kendali Ketat)",
        "kelurahan": "Kebon Melati",
        "kecamatan": "Tanah Abang",
        "kota_administrasi": "Jakarta Pusat",
        "kategori_subjek": "Pajak Reklame - Megatron/Videotron LED",
        "dpp_atau_njop_rp": 960000000,
        "pengurang_tak_kena_pajak_rp": 0,
        "tarif_persen": 25.0,
        "pokok_pajak_rp": 240000000,
        "denda_rp": 2400000,
        "total_tagihan_rp": 242400000,
        "masa_atau_tahun_pajak": "2026",
        "status_bayar": "BELUM LUNAS",
        "jatuh_tempo": "2026-09-25",
        "keterangan": "Ukuran 8m x 12m (96 m2), Kelas Jalan Protokol A DKI Jakarta. NSR Rp 960 Juta x Tarif 25%.",
    },
    {
        "tema_pajak": "REKLAME",
        "nomor_identitas": "SKPD-REK-3174-2026-0519",
        "nama_wp": "PT Ritel Modern Indonesia",
        "nama_objek": "Papan Nama / Neon Box Toko Kemang",
        "alamat_objek": "Jl. Kemang Raya No. 41",
        "kelurahan": "Bangka",
        "kecamatan": "Mampang Prapatan",
        "kota_administrasi": "Jakarta Selatan",
        "kategori_subjek": "Pajak Reklame - Papan/Billboard",
        "dpp_atau_njop_rp": 48000000,
        "pengurang_tak_kena_pajak_rp": 0,
        "tarif_persen": 25.0,
        "pokok_pajak_rp": 12000000,
        "denda_rp": 0,
        "total_tagihan_rp": 0,
        "masa_atau_tahun_pajak": "2026",
        "status_bayar": "LUNAS",
        "jatuh_tempo": "2026-08-30",
        "keterangan": "Ukuran 2m x 6m. Telah lunas via Bank DKI.",
    },

    # ==================== 5. PAJAK AIR TANAH (PAT) DKI JAKARTA ====================
    {
        "tema_pajak": "PAT",
        "nomor_identitas": "SKPD-PAT-3175-2026-0881",
        "nama_wp": "PT Tirta Manufaktur Cakung",
        "nama_objek": "Sumur Bor Industri Kawasan Pulo Gadung",
        "alamat_objek": "Jl. Pulo Ayang Raya Blok OR-4, Kawasan Industri Pulo Gadung",
        "kelurahan": "Jatinegara",
        "kecamatan": "Cakung",
        "kota_administrasi": "Jakarta Timur",
        "kategori_subjek": "Pajak Air Tanah - Industri Besar",
        "dpp_atau_njop_rp": 185000000,
        "pengurang_tak_kena_pajak_rp": 0,
        "tarif_persen": 20.0,
        "pokok_pajak_rp": 37000000,
        "denda_rp": 370000,
        "total_tagihan_rp": 37370000,
        "masa_atau_tahun_pajak": "September 2026",
        "status_bayar": "BELUM LUNAS",
        "jatuh_tempo": "2026-10-15",
        "keterangan": "Volume pengambilan 4.200 m3. NPAT Rp 185.000.000 x Tarif PAT DKI Jakarta 20% = Rp 37.000.000.",
    },
    {
        "tema_pajak": "PAT",
        "nomor_identitas": "SKPD-PAT-3174-2026-0904",
        "nama_wp": "PT Menara Kuningan Properti",
        "nama_objek": "Sumur Dalam Gedung Menara Kuningan",
        "alamat_objek": "Jl. H.R. Rasuna Said Kav. C-11",
        "kelurahan": "Karet Kuningan",
        "kecamatan": "Setiabudi",
        "kota_administrasi": "Jakarta Selatan",
        "kategori_subjek": "Pajak Air Tanah - Niaga/Gedung Bertingkat",
        "dpp_atau_njop_rp": 92000000,
        "pengurang_tak_kena_pajak_rp": 0,
        "tarif_persen": 20.0,
        "pokok_pajak_rp": 18400000,
        "denda_rp": 0,
        "total_tagihan_rp": 0,
        "masa_atau_tahun_pajak": "September 2026",
        "status_bayar": "LUNAS",
        "jatuh_tempo": "2026-10-15",
        "keterangan": "Volume pengambilan 1.950 m3. Lunas tepat waktu.",
    },
]

DKI_REGULASI_CHUNKS: List[Dict[str, str]] = [
    {
        "id": "reg_dki_pbb_1",
        "tema_pajak": "PBB-P2",
        "title": "Ketentuan PBB-P2 Provinsi DKI Jakarta",
        "content": (
            "### Ketentuan PBB-P2 Provinsi DKI Jakarta\n"
            "- **NJOPTKP DKI Jakarta**: Ditetapkan sebesar **Rp 60.000.000** (enam puluh juta rupiah) per Wajib Pajak untuk 1 objek pajak dengan nilai NJOP terbesar.\n"
            "- **Dasar Pengenaan**: Paling rendah 20% dan paling tinggi 100% dari NJOP setelah dikurangi NJOPTKP.\n"
            "- **Tarif PBB-P2 DKI Jakarta**:\n"
            "  - Tarif dasar maksimal **0,5%**.\n"
            "  - Tarif efektif hunian rumah tinggal di DKI Jakarta berkisar **0,1% s.d. 0,25%**, sedangkan objek komersial/perkantoran hingga **0,5%**.\n"
            "  - **Kebijakan Pembebasan 100% DKI Jakarta**: Rumah tinggal milik Orang Pribadi dengan NJOP sampai dengan **Rp 2.000.000.000 (Rp 2 Miliar)** diberikan pembebasan pokok PBB-P2 sebesar 100% untuk 1 (satu) objek pajak utama.\n"
            "- **Denda Keterlambatan**: Keterlambatan pembayaran setelah jatuh tempo dikenakan bunga **1% per bulan** (maksimal 24 bulan)."
        ),
    },
    {
        "id": "reg_dki_pbjt_1",
        "tema_pajak": "PBJT",
        "title": "Ketentuan PBJT Provinsi DKI Jakarta (Makanan/Minuman, Hotel, Parkir, Hiburan, Listrik)",
        "content": (
            "### Ketentuan Pajak Barang dan Jasa Tertentu (PBJT) Provinsi DKI Jakarta\n"
            "PBJT mencakup Pajak Restoran, Pajak Hotel, Pajak Parkir, Pajak Hiburan, dan Pajak Tenaga Listrik di DKI Jakarta:\n"
            "- **Tarif PBJT Makanan dan/atau Minuman (Restoran/Kafe/Boga)**: **10%** dari jumlah pembayaran yang diterima.\n"
            "- **Tarif PBJT Jasa Perhotelan**: **10%**.\n"
            "- **Tarif PBJT Jasa Parkir**: **10%**.\n"
            "- **Tarif PBJT Jasa Kesenian dan Hiburan**:\n"
            "  - Tarif umum hiburan: **10%**.\n"
            "  - Tarif khusus hiburan tertentu (diskotek, karaoke, kelab malam, bar, dan mandi uap/spa) di DKI Jakarta: **40%**.\n"
            "- **Tarif PBJT Tenaga Listrik**: Umum **3%**, dihasilkan sendiri **1,5%**, industri/migas **3%**.\n"
            "- **Jatuh Tempo Pembayaran & Pelaporan e-SPTPD**: Tanggal 15 bulan berikutnya (pembayaran) dan tanggal 20 (pelaporan)."
        ),
    },
    {
        "id": "reg_dki_bphtb_1",
        "tema_pajak": "BPHTB",
        "title": "Ketentuan BPHTB Provinsi DKI Jakarta",
        "content": (
            "### Ketentuan BPHTB Provinsi DKI Jakarta\n"
            "- **Tarif BPHTB DKI Jakarta**: **5%** dari Nilai Perolehan Objek Pajak Kena Pajak (`NPOPKP = NPOP − NPOPTKP`).\n"
            "- **NPOPTKP (Nilai Perolehan Objek Pajak Tidak Kena Pajak) DKI Jakarta**:\n"
            "  - Perolehan hak umum (Jual Beli / AJB, Tukar Menukar, Hibah, dll.): **Rp 80.000.000** untuk perolehan pertama.\n"
            "  - Perolehan hak karena **Waris atau Hibah Wasiat** dalam hubungan keluarga sedarah lurus satu derajat (termasuk suami/istri): **Rp 350.000.000** s.d. **Rp 1.000.000.000**.\n"
            "- **Rumus Perhitungan BPHTB**: `5% × (NPOP − NPOPTKP)`."
        ),
    },
    {
        "id": "reg_dki_reklame_1",
        "tema_pajak": "REKLAME",
        "title": "Ketentuan Pajak Reklame Provinsi DKI Jakarta",
        "content": (
            "### Ketentuan Pajak Reklame Provinsi DKI Jakarta\n"
            "- **Dasar Pengenaan**: Nilai Sewa Reklame (NSR) yang dihitung berdasarkan lokasi penempatan (Kelas Jalan Protokol A/B/C, Ekonomi I/II/III), ukuran media reklame, jangka waktu penyelenggaraan, dan ketinggian.\n"
            "- **Tarif Pajak Reklame DKI Jakarta**: **25%** dari Nilai Sewa Reklame (NSR).\n"
            "- **Kawasan Kendali Ketat (Sudirman, Thamrin, Rasuna Said, Gatot Subroto)**: Diwajibkan menggunakan media reklame LED/Videotron menempel pada bangunan (*building-attached*)."
        ),
    },
    {
        "id": "reg_dki_pat_1",
        "tema_pajak": "PAT",
        "title": "Ketentuan Pajak Air Tanah (PAT) Provinsi DKI Jakarta",
        "content": (
            "### Ketentuan Pajak Air Tanah (PAT) Provinsi DKI Jakarta\n"
            "- **Dasar Pengenaan**: Nilai Perolehan Air Tanah (NPAT) yang dihitung dari volume pengambilan air tanah (m³) dikalikan Harga Dasar Air (HDA) dan Bobot Komponen Sumber Daya Alam + Komponen Peruntukan.\n"
            "- **Tarif Pajak Air Tanah DKI Jakarta**: **20%** dari NPAT.\n"
            "- **Kewajiban Wajib Pajak PAT**: Wajib memasang meter air tersegel resmi dan melaporkan volume pemakaian bulanan."
        ),
    },
]

# Structured Legal Corpus (Pasal, Ayat, Dasar Hukum & Kaidah Perumusan) for Scaling Legal Intelligence
DKI_LEGAL_CORPUS: List[Dict[str, Any]] = [
    # ==================== PBB-P2 ====================
    {
        "kode_pasal": "PASAL-PBB-01",
        "tema_pajak": "PBB-P2",
        "jenis_instrumen": "Peraturan Daerah Provinsi DKI Jakarta",
        "hierarki_level": 1,
        "bab_bagian": "Bagian Kesatu — Objek, Subjek, dan Wajib Pajak PBB-P2",
        "pasal_ayat": "Pasal 33 s.d. Pasal 35",
        "tentang": "Objek, Pengecualian Objek, dan Subjek PBB-P2 DKI Jakarta",
        "bunyi_norma": (
            "(1) Objek PBB-P2 adalah Bumi dan/atau Bangunan yang dimiliki, dikuasai, dan/atau dimanfaatkan oleh orang pribadi atau Badan, kecuali kawasan yang digunakan untuk kegiatan usaha perkebunan, perhutanan, dan pertambangan.\n"
            "(2) Dikecualikan dari objek PBB-P2 adalah kepemilikan/pemanfaatan untuk kantor pemerintah, ibadah, pemakaman umum, hutan lindung/taman kota, serta perwakilan diplomatik berdasarkan asas timbal balik.\n"
            "(3) Subjek Pajak dan Wajib Pajak PBB-P2 adalah orang pribadi atau Badan yang secara nyata mempunyai suatu hak atas Bumi dan/atau memperoleh manfaat atas Bumi, dan/atau memiliki, menguasai, dan/atau memperoleh manfaat atas Bangunan."
        ),
        "kaidah_perumusan": (
            "Gunakan pasal ini sebagai dasar hukum utama (Konsiderans Mengingat) saat merumuskan Peraturan Gubernur mengenai kriteria teknis bangunan fasilitas sosial, pendidikan, atau kesehatan yang diberikan pengurangan PBB-P2."
        ),
        "kata_kunci": "objek subjek wajib pajak pbb-p2 pengecualian fasilitas umum sosial",
    },
    {
        "kode_pasal": "PASAL-PBB-02",
        "tema_pajak": "PBB-P2",
        "jenis_instrumen": "Peraturan Daerah & Peraturan Gubernur DKI Jakarta",
        "hierarki_level": 1,
        "bab_bagian": "Bagian Kedua — Dasar Pengenaan, NJOPTKP, dan Tarif PBB-P2",
        "pasal_ayat": "Pasal 36 s.d. Pasal 39",
        "tentang": "NJOP, Batas NJOPTKP Rp 60 Juta, Rasio Assessment (20%-100%), dan Tarif PBB-P2",
        "bunyi_norma": (
            "(1) Dasar pengenaan PBB-P2 adalah Nilai Jual Objek Pajak (NJOP) yang ditetapkan setiap tahun atau setiap 3 (tiga) tahun oleh Gubernur.\n"
            "(2) Besaran NJOPTKP ditetapkan sebesar Rp 60.000.000,00 (enam puluh juta rupiah) untuk setiap Wajib Pajak atas 1 (satu) objek pajak dengan nilai NJOP tertinggi.\n"
            "(3) Dasar pengenaan PBB-P2 yang digunakan untuk perhitungan pajak ditetapkan paling rendah 20% (dua puluh persen) dan paling tinggi 100% (seratus persen) dari NJOP setelah dikurangi NJOPTKP.\n"
            "(4) Tarif PBB-P2 ditetapkan sebesar 0,5% (nol koma lima persen), dengan tarif khusus berupa keringanan/insentif bagi objek hunian rumah tinggal dan lahan produksi pangan/ternak."
        ),
        "kaidah_perumusan": (
            "Kaidah delegasi: Pasal ini mendelegasikan kewenangan kepada Gubernur untuk menetapkan persentase NJOP yang dikenakan pajak (Assessment Ratio) dan klasterisasi tarif efektif hunian melalui Peraturan Gubernur setiap tahun pajak."
        ),
        "kata_kunci": "njop njoptkp 60 juta tarif 0.5 persen rasio pengenaan insentif hunian rumah tinggal",
    },
    {
        "kode_pasal": "PASAL-PBB-03",
        "tema_pajak": "PBB-P2",
        "jenis_instrumen": "Peraturan Gubernur DKI Jakarta",
        "hierarki_level": 2,
        "bab_bagian": "Bab Insentif Fiskal & Pembebasan Pokok PBB-P2",
        "pasal_ayat": "Pasal 4 s.d. Pasal 9 (Regulasi Insentif PBB-P2 Tahunan)",
        "tentang": "Pembebasan Pokok 100% Hunian di Bawah Rp 2 Miliar & Keringanan Pembayaran",
        "bunyi_norma": (
            "(1) Gubernur memberikan pembebasan pokok PBB-P2 sebesar 100% (seratus persen) atas 1 (satu) objek pajak berupa rumah tinggal milik Orang Pribadi dengan NJOP sampai dengan Rp 2.000.000.000,00 (dua miliar rupiah).\n"
            "(2) Apabila Wajib Pajak Orang Pribadi memiliki lebih dari 1 (satu) objek rumah tinggal, pembebasan 100% diberikan secara otomatis terhadap objek dengan NJOP terbesar di bawah batas Rp 2.000.000.000,00 yang tervalidasi NIK.\n"
            "(3) Terhadap objek kedua dan seterusnya, diberikan faktor pengurang transisi agar kenaikan beban pajak terkendali."
        ),
        "kaidah_perumusan": (
            "Acuan utama ketika merumuskan pembaruan Peraturan Gubernur tentang Insentif Fiskal PBB-P2, penghapusan sanksi administratif bunga 1% per bulan, atau penyesuaian ambang batas NJOP bebas pajak."
        ),
        "kata_kunci": "bebas pbb 100 persen 2 miliar nik orang pribadi keringanan sanksi bunga denda",
    },

    # ==================== PBJT ====================
    {
        "kode_pasal": "PASAL-PBJT-01",
        "tema_pajak": "PBJT",
        "jenis_instrumen": "Peraturan Daerah Provinsi DKI Jakarta",
        "hierarki_level": 1,
        "bab_bagian": "Bab PBJT — Objek dan Subjek Pajak Barang dan Jasa Tertentu",
        "pasal_ayat": "Pasal 45 s.d. Pasal 52",
        "tentang": "Ruang Lingkup 5 Sektor PBJT (Makanan/Minuman, Perhotelan, Parkir, Hiburan, Tenaga Listrik)",
        "bunyi_norma": (
            "(1) Objek PBJT merupakan penjualan, penyerahan, dan/atau konsumsi barang dan jasa tertentu yang meliputi: a. Makanan dan/atau Minuman; b. Tenaga Listrik; c. Jasa Perhotelan; d. Jasa Parkir; dan e. Jasa Kesenian dan Hiburan.\n"
            "(2) Penjualan Makanan dan/atau Minuman mencakup restoran, kafe, rumah makan, warung, katering/jasa boga, serta penjualan melalui platform daring.\n"
            "(3) Dikecualikan dari objek PBJT Makanan/Minuman adalah penyerahan dengan peredaran usaha (omzet) tidak melebihi batas tertentu yang ditetapkan untuk perlindungan pelaku usaha mikro."
        ),
        "kaidah_perumusan": (
            "Gunakan pasal ini saat menyusun regulasi turunan mengenai batas omzet minimum usaha mikro (UMKM) yang dikecualikan dari pemungutan PBJT Restoran maupun integrasi alat perekam transaksi elektronik (e-POS)."
        ),
        "kata_kunci": "objek pbjt restoran makanan minuman hotel parkir hiburan listrik katering umkm omzet",
    },
    {
        "kode_pasal": "PASAL-PBJT-02",
        "tema_pajak": "PBJT",
        "jenis_instrumen": "Peraturan Daerah Provinsi DKI Jakarta",
        "hierarki_level": 1,
        "bab_bagian": "Bagian Tarif dan Dasar Pengenaan PBJT",
        "pasal_ayat": "Pasal 53 s.d. Pasal 57",
        "tentang": "Dasar Pengenaan dan Struktur Tarif PBJT (10%, 40% Hiburan Tertentu, 3%/1,5% Listrik)",
        "bunyi_norma": (
            "(1) Dasar pengenaan PBJT adalah jumlah yang dibayarkan oleh konsumen barang atau jasa tertentu, termasuk biaya pelayanan (service charge).\n"
            "(2) Tarif PBJT atas Makanan dan/atau Minuman, Jasa Perhotelan, Jasa Parkir, dan Jasa Kesenian dan Hiburan umum ditetapkan sebesar 10% (sepuluh persen).\n"
            "(3) Khusus tarif PBJT atas Jasa Hiburan pada diskotek, karaoke, kelab malam, bar, dan mandi uap/spa ditetapkan sebesar 40% (empat puluh persen).\n"
            "(4) Tarif PBJT atas konsumsi Tenaga Listrik ditetapkan sebesar 3% (umum/industri) dan 1,5% (dihasilkan sendiri)."
        ),
        "kaidah_perumusan": (
            "Pasal ini menjadi rujukan mutlak (mandatory norm) dalam penyusunan Peraturan Gubernur tentang Tata Cara Pelaporan e-SPTPD, pengawasan transaksi online (fiscal device), dan pengenaan sanksi bunga keterlambatan setor."
        ),
        "kata_kunci": "tarif pbjt 10 persen 40 persen hiburan diskotek karaoke spa hotel restoran listrik service charge",
    },

    # ==================== BPHTB ====================
    {
        "kode_pasal": "PASAL-BPHTB-01",
        "tema_pajak": "BPHTB",
        "jenis_instrumen": "Peraturan Daerah Provinsi DKI Jakarta",
        "hierarki_level": 1,
        "bab_bagian": "Bab Bea Perolehan Hak atas Tanah dan Bangunan (BPHTB)",
        "pasal_ayat": "Pasal 58 s.d. Pasal 64",
        "tentang": "Objek Perolehan Hak, NPOP, NPOPTKP Rp 80 Juta / Rp 350 Juta, dan Tarif 5% BPHTB",
        "bunyi_norma": (
            "(1) Objek BPHTB adalah Perolehan Hak atas Tanah dan/atau Bangunan yang meliputi pemindahan hak (jual beli, tukar-menukar, hibah, hibah wasiat, waris, pemasukan dalam perseroan, lelang) dan pemberian hak baru.\n"
            "(2) Dasar pengenaan BPHTB adalah Nilai Perolehan Objek Pajak (NPOP); apabila NPOP lebih rendah dari NJOP PBB-P2 tahun berjalan, maka yang digunakan adalah NJOP PBB-P2.\n"
            "(3) Besaran NPOPTKP ditetapkan sebesar Rp 80.000.000,00 untuk perolehan hak umum pertama, dan paling sedikit Rp 350.000.000,00 untuk perolehan hak karena waris atau hibah wasiat dalam garis keturunan lurus satu derajat.\n"
            "(4) Tarif BPHTB ditetapkan sebesar 5% (lima persen) dari NPOP Kena Pajak (NPOP dikurangi NPOPTKP)."
        ),
        "kaidah_perumusan": (
            "Gunakan pasal ini sebagai landasan saat merumuskan Peraturan Gubernur tentang Validasi Elektronik SSPD-BPHTB terintegrasi PPAT/BPN, atau pemberian insentif BPHTB 0% bagi rumah pertama masyarakat berpenghasilan rendah (MBR)."
        ),
        "kata_kunci": "pasal bphtb npop npoptkp 80 juta 350 juta waris hibah jual beli ajb ppat bpn tarif 5 persen",
    },

    # ==================== PAJAK REKLAME ====================
    {
        "kode_pasal": "PASAL-REK-01",
        "tema_pajak": "REKLAME",
        "jenis_instrumen": "Peraturan Daerah & Peraturan Gubernur DKI Jakarta",
        "hierarki_level": 1,
        "bab_bagian": "Bab Pajak Reklame & Penataan Kawasan Kendali Ketat",
        "pasal_ayat": "Pasal 65 s.d. Pasal 71",
        "tentang": "Objek Pajak Reklame, Perhitungan Nilai Sewa Reklame (NSR), dan Tarif 25%",
        "bunyi_norma": (
            "(1) Objek Pajak Reklame adalah semua penyelenggaraan reklame meliputi reklame papan/billboard, videotron/megatron LED, kain, melekat/stiker, selebaran, berjalan pada kendaraan, udara, dan film/slide.\n"
            "(2) Dasar pengenaan Pajak Reklame adalah Nilai Sewa Reklame (NSR) yang dihitung dari Nilai Kontrak Reklame (pihak ketiga) atau dihitung berdasarkan faktor kelas jalan, luas bidang, ketinggian, dan durasi tayang.\n"
            "(3) Tarif Pajak Reklame ditetapkan sebesar 25% (dua puluh lima persen) dari NSR.\n"
            "(4) Penyelenggaraan reklame pada Kawasan Kendali Ketat wajib berbentuk LED/Videotron yang menempel pada fasad gedung (building-attached) sesuai standar tata ruang provinsi."
        ),
        "kaidah_perumusan": (
            "Gunakan pasal ini untuk merumuskan Keputusan Gubernur mengenai pembaruan indeks Harga Dasar Nilai Strategis Reklame (HDNSR), reklame digital di transportasi publik, atau sanksi penertiban reklame tanpa SKPD."
        ),
        "kata_kunci": "pasal reklame nsr tarif 25 persen videotron megatron billboard kawasan kendali ketat kelas jalan",
    },

    # ==================== PAJAK AIR TANAH (PAT) ====================
    {
        "kode_pasal": "PASAL-PAT-01",
        "tema_pajak": "PAT",
        "jenis_instrumen": "Peraturan Daerah & Peraturan Gubernur DKI Jakarta",
        "hierarki_level": 1,
        "bab_bagian": "Bab Pajak Air Tanah (PAT) & Pengendalian Ekstraksi Air Tanah",
        "pasal_ayat": "Pasal 72 s.d. Pasal 77",
        "tentang": "Objek Pengambilan Air Tanah, Rumus NPAT (HDA & FNA), dan Tarif 20% PAT",
        "bunyi_norma": (
            "(1) Objek Pajak Air Tanah (PAT) adalah pengambilan dan/atau pemanfaatan Air Tanah untuk tujuan komersial maupun industri, kecuali untuk keperluan dasar rumah tangga, pertanian rakyat, dan pemadaman kebakaran.\n"
            "(2) Dasar pengenaan PAT adalah Nilai Perolehan Air Tanah (NPAT) yang dihitung berdasarkan Harga Dasar Air (HDA), volume pengambilan (m³), bobot komponen sumber daya alam (zona konservasi/rawan penurunan tanah), dan bobot peruntukan progresif.\n"
            "(3) Tarif Pajak Air Tanah ditetapkan sebesar 20% (dua puluh persen) dari NPAT.\n"
            "(4) Setiap Wajib Pajak PAT wajib memasang alat meter air otomatis (automatic water meter) yang terhubung dengan sistem pemantauan Bapenda DKI Jakarta."
        ),
        "kaidah_perumusan": (
            "Landasan utama untuk merumuskan Peraturan Gubernur tentang Zona Bebas Air Tanah (Zero Groundwater Zone), kenaikan bobot FNA pada zona penurunan muka tanah kritis, dan insentif transisi ke jaringan perpipaan PAM Jaya."
        ),
        "kata_kunci": "pasal pajak air tanah pat npat hda fna tarif 20 persen sumur bor meter air zona konservasi",
    },
]



def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_tax_db() -> int:
    """Initialize local SQLite database for Bapenda DKI Jakarta thematic taxes."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DROP TABLE IF EXISTS pajak_dki_jakarta")
    cur.execute(
        """
        CREATE TABLE pajak_dki_jakarta (
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
        )
        """
    )

    for row in DKI_TAX_RECORDS:
        cur.execute(
            """
            INSERT INTO pajak_dki_jakarta (
                tema_pajak, nomor_identitas, nama_wp, nama_objek, alamat_objek,
                kelurahan, kecamatan, kota_administrasi, kategori_subjek,
                dpp_atau_njop_rp, pengurang_tak_kena_pajak_rp, tarif_persen,
                pokok_pajak_rp, denda_rp, total_tagihan_rp,
                masa_atau_tahun_pajak, status_bayar, jatuh_tempo, keterangan
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row["tema_pajak"],
                row["nomor_identitas"],
                row["nama_wp"],
                row["nama_objek"],
                row["alamat_objek"],
                row["kelurahan"],
                row["kecamatan"],
                row["kota_administrasi"],
                row["kategori_subjek"],
                row["dpp_atau_njop_rp"],
                row["pengurang_tak_kena_pajak_rp"],
                row["tarif_persen"],
                row["pokok_pajak_rp"],
                row["denda_rp"],
                row["total_tagihan_rp"],
                row["masa_atau_tahun_pajak"],
                row["status_bayar"],
                row["jatuh_tempo"],
                row["keterangan"],
            ),
        )

    cur.execute("DROP TABLE IF EXISTS korpus_hukum_dki")
    cur.execute(
        """
        CREATE TABLE korpus_hukum_dki (
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
        )
        """
    )

    for leg in DKI_LEGAL_CORPUS:
        cur.execute(
            """
            INSERT INTO korpus_hukum_dki (
                kode_pasal, tema_pajak, jenis_instrumen, hierarki_level,
                bab_bagian, pasal_ayat, tentang, bunyi_norma,
                kaidah_perumusan, kata_kunci
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                leg["kode_pasal"],
                leg["tema_pajak"],
                leg["jenis_instrumen"],
                leg["hierarki_level"],
                leg["bab_bagian"],
                leg["pasal_ayat"],
                leg["tentang"],
                leg["bunyi_norma"],
                leg["kaidah_perumusan"],
                leg["kata_kunci"],
            ),
        )

    conn.commit()
    conn.close()
    return len(DKI_TAX_RECORDS)


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
    """Susun kerangka perumusan dasar hukum / Legal Drafting (Menimbang, Mengingat, dan Rancangan Pasal) berbasis korpus hukum lokal DKI Jakarta."""
    tema = tema_pajak.upper() if tema_pajak.upper() in TAX_THEMES else "PBB-P2"
    theme_name = TAX_THEMES[tema]["name"]
    corpus_rows = get_all_legal_corpus(tema)
    reg_chunks = get_regulasi_chunks(tema)

    dasar_mengingat = [
        f"{r['jenis_instrumen']} — {r['pasal_ayat']} tentang {r['tentang']}"
        for r in corpus_rows
    ]
    kaidah_acuan = [
        {
            "kode_pasal": r["kode_pasal"],
            "pasal_ayat": r["pasal_ayat"],
            "tentang": r["tentang"],
            "bunyi_norma": r["bunyi_norma"],
            "kaidah_perumusan": r["kaidah_perumusan"],
        }
        for r in corpus_rows
    ]

    return {
        "tema_pajak": tema,
        "nama_kategori": theme_name,
        "topik_perumusan": topik_perumusan,
        "instrumen_disarankan": f"Rancangan Peraturan Gubernur / Keputusan Kepala Bapenda Provinsi DKI Jakarta tentang {theme_name}",
        "konsiderans_menimbang": [
            f"a. bahwa untuk mengoptimalkan tata kelola pemungutan dan kepastian hukum pada {theme_name} di Provinsi DKI Jakarta, diperlukan pengaturan teknis yang adaptif, berkeadilan, dan akuntabel;",
            f"b. bahwa ketentuan teknis pelaksanaan pemungutan, pemberian insentif fiskal, dan pengawasan {tema} perlu disesuaikan dengan dinamika perekonomian daerah serta kepatuhan Wajib Pajak di Provinsi DKI Jakarta;",
            f"c. bahwa berdasarkan pertimbangan sebagaimana dimaksud dalam huruf a dan huruf b, perlu menetapkan regulasi pelaksanaan tentang {theme_name};",
        ],
        "dasar_hukum_mengingat": dasar_mengingat,
        "pasal_induk_acuan": kaidah_acuan,
        "ringkasan_tarif_dan_ketentuan": [c["content"] for c in reg_chunks],
    }


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
