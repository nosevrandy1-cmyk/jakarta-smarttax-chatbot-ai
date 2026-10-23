export type TaxThemeCode = "PBB-P2" | "PBJT" | "BPHTB" | "REKLAME" | "PAT";

export type CapabilityModeCode = "konsultasi" | "pasal_hukum" | "perumusan_hukum";

export interface StarterPrompt {
  title: string;
  desc: string;
  prompt: string;
}

export interface TaxThemeConfig {
  code: TaxThemeCode;
  shortLabel: string;
  fullName: string;
  badgeDesc: string;
  dotColor: string;
  placeholder: string;
  starters: StarterPrompt[];
  legalStarters: StarterPrompt[];
  draftingStarters: StarterPrompt[];
}

export interface CapabilityModeConfig {
  code: CapabilityModeCode;
  shortLabel: string;
  fullLabel: string;
  engineBadge: string;
  description: string;
  placeholderPrefix: string;
}

export const CAPABILITY_MODES: CapabilityModeConfig[] = [
  {
    code: "konsultasi",
    shortLabel: "Tarif & Data Pajak",
    fullLabel: "Konsultasi Tarif, Rumus & Objek Pajak",
    engineBadge: "Gemma RAG",
    description: "Cek ketetapan NOP/NPWPD, simulasi rumus, tunggakan, dan rekapitulasi wilayah.",
    placeholderPrefix: "Tanyakan tarif, rumus, atau cek NOP/NPWPD",
  },
  {
    code: "pasal_hukum",
    shortLabel: "Pasal & Dasar Hukum",
    fullLabel: "Telusur Pasal, Ayat & Dasar Hukum",
    engineBadge: "Gemma / DeepSeek",
    description: "Telusuri bunyi pasal, ayat, hierarki dasar hukum, dan norma regulasi pajak daerah.",
    placeholderPrefix: "Telusuri bunyi pasal, ayat, atau dasar hukum",
  },
  {
    code: "perumusan_hukum",
    shortLabel: "Perumusan Hukum",
    fullLabel: "Perumusan Dasar Hukum Baru (Legal Drafting)",
    engineBadge: "DeepSeek-R1",
    description: "Susun draf pasal baru, konsiderans Menimbang/Mengingat, dan matriks harmonisasi aturan.",
    placeholderPrefix: "Rumuskan draf pasal, konsiderans, atau kajian aturan",
  },
];

export const TAX_THEMES: TaxThemeConfig[] = [
  {
    code: "PBB-P2",
    shortLabel: "PBB-P2",
    fullName: "Pajak Bumi dan Bangunan (PBB-P2)",
    badgeDesc: "SPPT, NOP, NJOP, Pasal & Perumusan PBB-P2 DKI Jakarta",
    dotColor: "#10b981",
    placeholder: "PBB-P2 DKI Jakarta (misal: NOP, pasal NJOPTKP, atau draf insentif)...",
    starters: [
      {
        title: "Cek Tunggakan & Denda PBB-P2",
        desc: "Daftar SPPT PBB-P2 DKI yang belum lunas beserta denda",
        prompt: "Tampilkan daftar objek PBB-P2 DKI Jakarta yang masih berstatus BELUM LUNAS beserta rincian dendanya.",
      },
      {
        title: "Cek Objek SCBD Jakarta Selatan",
        desc: "Rincian NOP 31.74.010.003.008-0042.0",
        prompt: "Berapa rincian NJOP dan tagihan PBB-P2 untuk NOP 31.74.010.003.008-0042.0 di SCBD Jakarta Selatan?",
      },
      {
        title: "Syarat Bebas PBB-P2 100%",
        desc: "Ketentuan rumah tinggal di bawah Rp 2 Miliar & NJOPTKP",
        prompt: "Bagaimana ketentuan pembebasan pokok PBB-P2 100% untuk hunian di bawah Rp 2 Miliar dan NJOPTKP Rp 60 juta di DKI Jakarta?",
      },
      {
        title: "Rekap PBB-P2 per Wilayah",
        desc: "Total ketetapan & realisasi per Kota Administrasi",
        prompt: "Buatkan tabel rekapitulasi ketetapan dan realisasi PBB-P2 DKI Jakarta per Kota Administrasi.",
      },
    ],
    legalStarters: [
      {
        title: "Pasal Objek & Pengecualian PBB-P2",
        desc: "Bunyi Pasal 33 s.d. Pasal 35 korpus hukum PBB-P2 DKI",
        prompt: "Tampilkan bunyi pasal tentang objek, subjek, dan pengecualian objek PBB-P2 di DKI Jakarta.",
      },
      {
        title: "Dasar Hukum NJOPTKP & Rasio NJOP",
        desc: "Bunyi Pasal 36 s.d. Pasal 39 tentang NJOPTKP Rp 60 Juta",
        prompt: "Apa dasar hukum dan bunyi pasal penetapan NJOPTKP Rp 60 juta serta tarif PBB-P2 di DKI Jakarta?",
      },
      {
        title: "Norma Pembebasan 100% Hunian",
        desc: "Kaidah hukum pembebasan PBB-P2 rumah tinggal < Rp 2 Miliar",
        prompt: "Tampilkan bunyi pasal dan kaidah hukum pembebasan pokok PBB-P2 100% untuk rumah tinggal di bawah Rp 2 Miliar.",
      },
      {
        title: "Matriks Pasal PBB-P2 Lengkap",
        desc: "Seluruh daftar pasal & dasar hukum PBB-P2 di database",
        prompt: "Tampilkan seluruh korpus pasal dan dasar hukum PBB-P2 DKI Jakarta yang terdaftar.",
      },
    ],
    draftingStarters: [
      {
        title: "Draf Pasal Insentif Bangunan Hijau",
        desc: "Susun konsiderans & rancangan pasal pengurangan PBB-P2 Green Building",
        prompt: "Rumuskan draf pasal dan konsiderans Menimbang/Mengingat untuk pemberian insentif pengurangan PBB-P2 bagi Bangunan Gedung Hijau (Green Building) di DKI Jakarta.",
      },
      {
        title: "Rancangan Pergub Bebas PBB-P2 Hunian",
        desc: "Susun batang tubuh pasal pembebasan PBB-P2 Orang Pribadi",
        prompt: "Rumuskan rancangan dasar hukum (Menimbang, Mengingat, dan Batang Tubuh Pasal) untuk pembebasan PBB-P2 hunian Orang Pribadi berbasis validasi NIK.",
      },
      {
        title: "Draf Penghapusan Sanksi Bunga PBB-P2",
        desc: "Klausul keringanan denda administratif 1% per bulan",
        prompt: "Rumuskan draf pasal penghapusan sanksi administratif bunga keterlambatan PBB-P2 dalam rangka HUT Kota Jakarta.",
      },
      {
        title: "Klausul Pengurangan PBB Pendidikan/RS",
        desc: "Rancangan pasal kriteria fasilitas sosial, sekolah, dan rumah sakit",
        prompt: "Rumuskan draf pasal kriteria teknis pemberian pengurangan PBB-P2 bagi penyelenggara pendidikan dan rumah sakit di DKI Jakarta.",
      },
    ],
  },
  {
    code: "PBJT",
    shortLabel: "PBJT",
    fullName: "PBJT (Restoran, Hotel, Parkir, Hiburan)",
    badgeDesc: "Makanan/Minuman, Hotel, Parkir, Hiburan, Pasal & Perumusan PBJT",
    dotColor: "#3b82f6",
    placeholder: "PBJT DKI Jakarta (Restoran, Hotel, Parkir, Pasal, atau Perumusan)...",
    starters: [
      {
        title: "Cek Tunggakan PBJT DKI",
        desc: "Restoran, hotel, atau tempat hiburan yang belum lunas",
        prompt: "Tampilkan daftar Wajib Pajak PBJT di DKI Jakarta yang masih menunggak (BELUM LUNAS) beserta dendanya.",
      },
      {
        title: "Tarif PBJT Restoran vs Hiburan",
        desc: "Perbandingan tarif 10% umum dan 40% hiburan tertentu",
        prompt: "Jelaskan rincian tarif PBJT di DKI Jakarta untuk Restoran, Hotel, Parkir, serta tarif khusus 40% Hiburan tertentu.",
      },
      {
        title: "Cek NPWPD Restoran Senopati",
        desc: "Rincian ketetapan PT Kuliner Senopati Nusantara",
        prompt: "Tampilkan rincian ketetapan PBJT untuk PT Kuliner Senopati Nusantara (Restoran Senopati Bistro) di Jakarta Selatan.",
      },
      {
        title: "Rekap Penerimaan PBJT",
        desc: "Ringkasan ketetapan & realisasi PBJT per wilayah",
        prompt: "Buatkan rekapitulasi ketetapan dan realisasi PBJT DKI Jakarta per Kota Administrasi.",
      },
    ],
    legalStarters: [
      {
        title: "Pasal Ruang Lingkup 5 Sektor PBJT",
        desc: "Bunyi Pasal 45 s.d. Pasal 52 tentang objek & pengecualian PBJT",
        prompt: "Tampilkan bunyi pasal dan dasar hukum ruang lingkup 5 sektor objek PBJT di DKI Jakarta.",
      },
      {
        title: "Dasar Hukum Tarif 10% & 40% PBJT",
        desc: "Bunyi Pasal 53 s.d. Pasal 57 tentang tarif PBJT & hiburan tertentu",
        prompt: "Apa dasar hukum dan bunyi pasal yang mengatur tarif PBJT 10% serta tarif khusus hiburan 40% di DKI Jakarta?",
      },
      {
        title: "Norma Pengecualian Omzet UMKM",
        desc: "Kaidah perlindungan usaha mikro kuliner dari pemungutan PBJT",
        prompt: "Tampilkan bunyi pasal pengecualian objek PBJT Makanan dan Minuman bagi pelaku usaha mikro di DKI Jakarta.",
      },
      {
        title: "Dasar Hukum Service Charge PBJT",
        desc: "Kedudukan biaya pelayanan dalam Dasar Pengenaan PBJT",
        prompt: "Bagaimana bunyi pasal mengenai masuknya biaya pelayanan (service charge) sebagai dasar pengenaan PBJT?",
      },
    ],
    draftingStarters: [
      {
        title: "Draf Pasal Alat Perekam Transaksi (e-POS)",
        desc: "Susun pasal kewajiban integrasi kasir online Wajib Pajak PBJT",
        prompt: "Rumuskan draf pasal dan konsiderans untuk kewajiban pemasangan alat perekam data transaksi elektronik (e-POS) pada Wajib Pajak PBJT Restoran, Hotel, dan Parkir.",
      },
      {
        title: "Rancangan Pasal Batas Omzet UMKM",
        desc: "Klausul batas peredaran usaha bebas PBJT Makanan/Minuman",
        prompt: "Rumuskan rancangan pasal penetapan batas omzet bulanan pelaku UMKM yang dikecualikan dari pemungutan PBJT Makanan dan Minuman di DKI Jakarta.",
      },
      {
        title: "Draf Pengawasan e-SPTPD PBJT",
        desc: "Susun klausul verifikasi pelaporan masa pajak elektronik",
        prompt: "Rumuskan draf pasal tata cara pelaporan e-SPTPD masa PBJT dan pengenaan sanksi keterlambatan setor di DKI Jakarta.",
      },
      {
        title: "Rancangan Insentif PBJT Kesenian Lokal",
        desc: "Klausul keringanan tarif untuk pertunjukan budaya/tradisional",
        prompt: "Rumuskan draf pasal pemberian keringanan PBJT Jasa Kesenian dan Hiburan bagi penyelenggaraan kesenian tradisional di DKI Jakarta.",
      },
    ],
  },
  {
    code: "BPHTB",
    shortLabel: "BPHTB",
    fullName: "Bea Perolehan Hak atas Tanah & Bangunan (BPHTB)",
    badgeDesc: "SSPD, AJB, Waris/Hibah, Pasal & Perumusan BPHTB DKI Jakarta",
    dotColor: "#8b5cf6",
    placeholder: "BPHTB DKI Jakarta (NPOPTKP, AJB, Waris, Pasal, atau Perumusan)...",
    starters: [
      {
        title: "Rumus & NPOPTKP BPHTB DKI",
        desc: "Batas tidak kena pajak Jual Beli (Rp 80 Jt) vs Waris (Rp 350 Jt)",
        prompt: "Bagaimana cara menghitung BPHTB di DKI Jakarta beserta besaran NPOPTKP untuk Jual Beli dan Waris?",
      },
      {
        title: "Cek SSPD BPHTB Belum Lunas",
        desc: "Daftar transaksi perolehan hak yang menunggu pembayaran",
        prompt: "Tampilkan daftar transaksi SSPD BPHTB di DKI Jakarta yang masih berstatus BELUM LUNAS.",
      },
      {
        title: "Rincian Transaksi AJB Cilandak",
        desc: "Cek SSPD-BPHTB-3174-2026-00912",
        prompt: "Tampilkan rincian perhitungan BPHTB untuk nomor SSPD-BPHTB-3174-2026-00912 atas nama Andi Wijaya Kusuma.",
      },
      {
        title: "Rekapitulasi BPHTB DKI",
        desc: "Total ketetapan & realisasi BPHTB per Kota Administrasi",
        prompt: "Buatkan tabel rekapitulasi ketetapan dan realisasi BPHTB di Provinsi DKI Jakarta.",
      },
    ],
    legalStarters: [
      {
        title: "Pasal Objek & Pemindahan Hak BPHTB",
        desc: "Bunyi Pasal 58 s.d. Pasal 64 tentang Jual Beli, Waris & Hibah",
        prompt: "Tampilkan bunyi pasal dan dasar hukum objek perolehan hak serta tarif 5% BPHTB di DKI Jakarta.",
      },
      {
        title: "Norma NPOPTKP Rp 80 Juta vs Waris",
        desc: "Dasar hukum pembedaan pengurang NPOPTKP umum dan waris",
        prompt: "Apa dasar hukum dan bunyi pasal penetapan NPOPTKP Rp 80 juta (umum) dan Rp 350 juta (waris/hibah wasiat)?",
      },
      {
        title: "Kaidah Perbandingan NPOP vs NJOP",
        desc: "Aturan jika nilai transaksi di bawah NJOP PBB-P2 tahun berjalan",
        prompt: "Bagaimana bunyi pasal apabila Nilai Perolehan Objek Pajak (NPOP) lebih rendah daripada NJOP PBB-P2 tahun berjalan?",
      },
      {
        title: "Kewajiban Validasi SSPD Sebelum AJB",
        desc: "Kaidah hukum keterkaitan validasi BPHTB dengan PPAT/Notaris",
        prompt: "Tampilkan kaidah hukum mengenai validasi pembayaran SSPD-BPHTB sebelum penandatanganan Akta Jual Beli oleh PPAT.",
      },
    ],
    draftingStarters: [
      {
        title: "Draf Pasal BPHTB 0% Rumah Pertama",
        desc: "Susun rancangan pasal insentif BPHTB masyarakat berpenghasilan rendah",
        prompt: "Rumuskan draf pasal dan konsiderans untuk pemberian insentif BPHTB 0% atas perolehan hak rumah pertama bagi Masyarakat Berpenghasilan Rendah (MBR) di DKI Jakarta.",
      },
      {
        title: "Rancangan Pasal Integrasi e-BPHTB & BPN",
        desc: "Klausul verifikasi elektronik terpadu Bapenda, PPAT, dan BPN",
        prompt: "Rumuskan rancangan pasal tata cara validasi elektronik SSPD-BPHTB yang terintegrasi secara host-to-host dengan sistem PPAT dan Kantor Pertanahan (BPN).",
      },
      {
        title: "Draf Klausul Keringanan BPHTB Waris",
        desc: "Susun aturan teknis pengurangan BPHTB karena waris keluarga",
        prompt: "Rumuskan draf pasal mekanisme permohonan dan verifikasi pengurangan BPHTB atas perolehan hak karena waris di DKI Jakarta.",
      },
      {
        title: "Klausul Pemeriksaan Nilai Pasar (NPOP)",
        desc: "Rancangan pasal penelitian lapangan atas kewajaran harga transaksi",
        prompt: "Rumuskan draf pasal kewenangan penelitian kantor dan penelitian lapangan oleh Bapenda dalam menguji kewajaran NPOP BPHTB.",
      },
    ],
  },
  {
    code: "REKLAME",
    shortLabel: "Reklame",
    fullName: "Pajak Reklame DKI Jakarta",
    badgeDesc: "Videotron, Billboard, NSR, Pasal & Perumusan Pajak Reklame",
    dotColor: "#f59e0b",
    placeholder: "Pajak Reklame DKI (Videotron, NSR, Kawasan Protokol, atau Pasal)...",
    starters: [
      {
        title: "Cek Tunggakan SKPD Reklame",
        desc: "Objek reklame/videotron yang belum lunas beserta denda",
        prompt: "Tampilkan daftar SKPD Pajak Reklame di DKI Jakarta yang berstatus BELUM LUNAS beserta dendanya.",
      },
      {
        title: "Tarif 25% & Kawasan Kendali Ketat",
        desc: "Aturan NSR dan reklame LED di Sudirman-Thamrin",
        prompt: "Bagaimana aturan perhitungan Nilai Sewa Reklame (NSR), tarif 25%, dan ketentuan Kawasan Kendali Ketat di DKI Jakarta?",
      },
      {
        title: "Cek Videotron Bundaran HI",
        desc: "Rincian SKPD-REK-3171-2026-0402",
        prompt: "Tampilkan rincian ketetapan Pajak Reklame untuk Videotron Bundaran HI (SKPD-REK-3171-2026-0402).",
      },
      {
        title: "Rekapitulasi Pajak Reklame",
        desc: "Ringkasan ketetapan & realisasi Pajak Reklame DKI",
        prompt: "Buatkan rekapitulasi ketetapan dan realisasi Pajak Reklame DKI Jakarta per wilayah.",
      },
    ],
    legalStarters: [
      {
        title: "Pasal Objek & Nilai Sewa Reklame (NSR)",
        desc: "Bunyi Pasal 65 s.d. Pasal 71 tentang NSR dan tarif 25%",
        prompt: "Tampilkan bunyi pasal dan dasar hukum objek Pajak Reklame, perhitungan NSR, serta tarif 25% di DKI Jakarta.",
      },
      {
        title: "Norma Kawasan Kendali Ketat",
        desc: "Kaidah hukum kewajiban reklame LED menempel gedung protokol",
        prompt: "Bagaimana bunyi pasal mengenai penyelenggaraan reklame LED/Videotron pada Kawasan Kendali Ketat di DKI Jakarta?",
      },
      {
        title: "Dasar Hukum Reklame Pihak Ketiga",
        desc: "Penentuan NSR berdasarkan nilai kontrak vs tabel harga dasar",
        prompt: "Apa dasar hukum penentuan Nilai Sewa Reklame (NSR) untuk reklame yang diselenggarakan oleh biro reklame / pihak ketiga?",
      },
      {
        title: "Kaidah Pengecualian Pajak Reklame",
        desc: "Batas ukuran papan nama usaha/profesi yang dikecualikan",
        prompt: "Tampilkan kaidah hukum mengenai pengecualian objek Pajak Reklame untuk nama pengenal usaha atau profesi.",
      },
    ],
    draftingStarters: [
      {
        title: "Draf Pasal Penataan LED Fasad Gedung",
        desc: "Susun rancangan pasal standar teknis reklame digital protokol",
        prompt: "Rumuskan draf pasal dan konsiderans untuk pengaturan reklame LED/Videotron menempel pada fasad bangunan di Kawasan Kendali Ketat DKI Jakarta.",
      },
      {
        title: "Rancangan Kepgub Indeks NSR Baru",
        desc: "Klausul penyesuaian Harga Dasar Nilai Strategis Reklame",
        prompt: "Rumuskan rancangan pasal penetapan indeks Harga Dasar Nilai Strategis Reklame (HDNSR) berdasarkan kelas jalan di DKI Jakarta.",
      },
      {
        title: "Draf Pasal Sanksi Penertiban Reklame",
        desc: "Klausul koordinasi Bapenda & Satpol PP atas reklame belum bayar pajak",
        prompt: "Rumuskan draf pasal mekanisme sanksi administratif dan pembongkaran reklame yang tidak memperpanjang SKPD Pajak Reklame.",
      },
      {
        title: "Rancangan Pasal Reklame Kendaraan",
        desc: "Klausul pemungutan pajak reklame berjalan pada armada komersial",
        prompt: "Rumuskan draf pasal tata cara perhitungan dan pemungutan Pajak Reklame berjalan pada kendaraan operasional di DKI Jakarta.",
      },
    ],
  },
  {
    code: "PAT",
    shortLabel: "Air Tanah",
    fullName: "Pajak Air Tanah (PAT) DKI Jakarta",
    badgeDesc: "Sumur Bor, Volume m³, NPAT, Pasal & Perumusan PAT DKI",
    dotColor: "#06b6d4",
    placeholder: "Pajak Air Tanah DKI (NPAT, Sumur Bor, Tarif 20%, atau Pasal)...",
    starters: [
      {
        title: "Cek Tunggakan Pajak Air Tanah",
        desc: "SKPD PAT industri/gedung yang belum lunas",
        prompt: "Tampilkan daftar SKPD Pajak Air Tanah (PAT) di DKI Jakarta yang masih berstatus BELUM LUNAS beserta dendanya.",
      },
      {
        title: "Rumus NPAT & Tarif 20% PAT",
        desc: "Cara hitung Nilai Perolehan Air Tanah di DKI Jakarta",
        prompt: "Bagaimana ketentuan perhitungan Nilai Perolehan Air Tanah (NPAT) dan tarif Pajak Air Tanah 20% di DKI Jakarta?",
      },
      {
        title: "Cek Sumur Industri Pulo Gadung",
        desc: "Rincian SKPD-PAT-3175-2026-0881",
        prompt: "Tampilkan rincian tagihan Pajak Air Tanah untuk PT Tirta Manufaktur Cakung di Kawasan Industri Pulo Gadung.",
      },
      {
        title: "Rekapitulasi Pajak Air Tanah",
        desc: "Total ketetapan & realisasi PAT per Kota Administrasi",
        prompt: "Buatkan tabel rekapitulasi ketetapan dan realisasi Pajak Air Tanah (PAT) di DKI Jakarta.",
      },
    ],
    legalStarters: [
      {
        title: "Pasal Objek & Tarif 20% Air Tanah",
        desc: "Bunyi Pasal 72 s.d. Pasal 77 tentang NPAT, HDA, dan tarif PAT",
        prompt: "Tampilkan bunyi pasal dan dasar hukum objek Pajak Air Tanah, perhitungan NPAT, serta tarif 20% di DKI Jakarta.",
      },
      {
        title: "Norma Pengecualian Rumah Tangga",
        desc: "Dasar hukum bebas Pajak Air Tanah untuk kebutuhan dasar rumah tangga",
        prompt: "Bagaimana bunyi pasal mengenai pengecualian pengambilan air tanah untuk keperluan dasar rumah tangga dan pemadaman kebakaran?",
      },
      {
        title: "Dasar Hukum Meter Air Otomatis (AMR)",
        desc: "Kewajiban pemasangan alat ukur debit air tanah tersegel",
        prompt: "Apa dasar hukum kewajiban pemasangan meter air otomatis yang terhubung dengan sistem Bapenda DKI Jakarta?",
      },
      {
        title: "Kaidah Faktor Nilai Air (Zona Konservasi)",
        desc: "Pengaruh zona rawan penurunan tanah terhadap bobot NPAT",
        prompt: "Tampilkan kaidah hukum penetapan bobot komponen sumber daya alam pada zona konservasi air tanah di DKI Jakarta.",
      },
    ],
    draftingStarters: [
      {
        title: "Draf Pasal Zona Konservasi Air Tanah",
        desc: "Susun rancangan pasal bobot progresif NPAT di zona penurunan tanah",
        prompt: "Rumuskan draf pasal dan konsiderans untuk pengenaan bobot progresif Nilai Perolehan Air Tanah (NPAT) pada zona rawan penurunan muka tanah di DKI Jakarta.",
      },
      {
        title: "Rancangan Pasal Kewajiban Meter AMR",
        desc: "Klausul telemetri pencatatan volume air tanah real-time",
        prompt: "Rumuskan rancangan pasal kewajiban pemasangan Automatic Meter Reading (AMR) terintegrasi Bapenda bagi Wajib Pajak Air Tanah kategori industri dan gedung bertingkat.",
      },
      {
        title: "Draf Insentif Transisi Air Perpipaan",
        desc: "Klausul pengurangan pajak bagi gedung yang beralih ke PAM Jaya",
        prompt: "Rumuskan draf pasal pemberian insentif fiskal bagi Wajib Pajak gedung komersial yang menutup sumur bor dan beralih penuh ke jaringan perpipaan PAM Jaya.",
      },
      {
        title: "Klausul Sanksi Pengambilan Tanpa Izin",
        desc: "Rancangan pasal denda administratif atas abstraksi melebihi kuota",
        prompt: "Rumuskan draf pasal pengenaan ketetapan pajak secara jabatan dan sanksi administratif bagi pengambilan air tanah yang melebihi batas kuota izin.",
      },
    ],
  },
];

export function getStartersForThemeAndMode(
  theme: TaxThemeConfig,
  mode: CapabilityModeCode
): StarterPrompt[] {
  if (mode === "pasal_hukum") {
    return theme.legalStarters;
  }
  if (mode === "perumusan_hukum") {
    return theme.draftingStarters;
  }
  return theme.starters;
}
