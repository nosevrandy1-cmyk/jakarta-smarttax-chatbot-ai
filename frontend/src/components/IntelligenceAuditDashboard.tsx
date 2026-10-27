"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import { ArrowsClockwiseIcon } from "@phosphor-icons/react/dist/csr/ArrowsClockwise";
import { BrainIcon } from "@phosphor-icons/react/dist/csr/Brain";
import { CaretDownIcon } from "@phosphor-icons/react/dist/csr/CaretDown";
import { CaretRightIcon } from "@phosphor-icons/react/dist/csr/CaretRight";
import { ChartLineUpIcon } from "@phosphor-icons/react/dist/csr/ChartLineUp";
import { CheckCircleIcon } from "@phosphor-icons/react/dist/csr/CheckCircle";
import { DatabaseIcon } from "@phosphor-icons/react/dist/csr/Database";
import { FilePdfIcon } from "@phosphor-icons/react/dist/csr/FilePdf";
import { FileXlsIcon } from "@phosphor-icons/react/dist/csr/FileXls";
import { GitDiffIcon } from "@phosphor-icons/react/dist/csr/GitDiff";
import { MoonIcon } from "@phosphor-icons/react/dist/csr/Moon";
import { PlayIcon } from "@phosphor-icons/react/dist/csr/Play";
import { ShieldCheckIcon } from "@phosphor-icons/react/dist/csr/ShieldCheck";
import { SlidersHorizontalIcon } from "@phosphor-icons/react/dist/csr/SlidersHorizontal";
import { SunIcon } from "@phosphor-icons/react/dist/csr/Sun";
import { TerminalWindowIcon } from "@phosphor-icons/react/dist/csr/TerminalWindow";
import { UploadSimpleIcon } from "@phosphor-icons/react/dist/csr/UploadSimple";
import { WarningIcon } from "@phosphor-icons/react/dist/csr/Warning";
import { XCircleIcon } from "@phosphor-icons/react/dist/csr/XCircle";

import type {
  BenchmarkStatus,
  DashboardTelemetryState,
  GoldenAuditItem,
  LearnReasoningInput,
  RagSourceType,
  TaxDomainCode,
} from "@/types/audit";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const TAX_DOMAINS: TaxDomainCode[] = [
  "PBB-P2",
  "JPB",
  "PBJT",
  "BPHTB",
  "REKLAME",
  "PAT",
];

const REASONING_PRESETS: Record<string, LearnReasoningInput> = {
  JPB_SCBD: {
    topik_pajak: "JPB",
    kontributor: "Auditor Penilai JPB Bapenda DKI",
    pertanyaan_kasus:
      "Berapa tarif PBB-P2 untuk objek gedung perkantoran komersial (JPB Perkantoran) seperti SCBD Lot 9 dengan NJOP Rp 185 Miliar, dan bagaimana perhitungan sanksi denda keterlambatan per bulan?",
    alur_penalaran:
      "Berdasarkan Pasal 36-39 Perda Pajak Daerah DKI Jakarta dan Klasifikasi JPB Perkantoran Komersial: (1) Gedung Perkantoran SCBD Lot 9 memiliki NJOP Rp 185.000.000.000 dikurangi NJOPTKP Rp 60.000.000; (2) Dikenakan tarif komersial maksimal 0,5% dengan pokok ketetapan Rp 369.880.000; (3) Keterlambatan setelah jatuh tempo dikenakan bunga denda 1% per bulan (maksimal 24 bulan) senilai Rp 3.698.800 per bulan.",
    jawaban_final:
      "Objek gedung perkantoran komersial (JPB Perkantoran) seperti Gedung Perkantoran SCBD Lot 9 dengan NJOP Rp 185.000.000.000 dan pengurang NJOPTKP Rp 60.000.000 dikenakan tarif PBB-P2 sebesar 0,5% dengan pokok pajak Rp 369.880.000. Sanksi denda keterlambatan adalah 1% per bulan (maksimal 24 bulan).",
  },
  BPHTB_WARIS: {
    topik_pajak: "BPHTB",
    kontributor: "Analis Hukum BPHTB DKI",
    pertanyaan_kasus:
      "Berapa besaran NPOPTKP dan perhitungan BPHTB untuk perolehan hak karena Waris atau Hibah Wasiat dalam garis keturunan lurus satu derajat di DKI Jakarta dengan nilai objek Rp 2,4 Miliar?",
    alur_penalaran:
      "Mengacu Pasal 58-64 Ayat (3) Perda DKI Jakarta: Untuk perolehan hak karena Waris atau Hibah Wasiat hubungan keluarga sedarah lurus satu derajat, NPOPTKP ditetapkan sebesar Rp 350.000.000 (350 juta). Dari NPOP Rp 2.400.000.000 dikurangi NPOPTKP Waris Rp 350.000.000 diperoleh NPOPKP Rp 2.050.000.000 dikalikan tarif 5% = Rp 102.500.000.",
    jawaban_final:
      "NPOPTKP untuk perolehan hak karena Waris atau Hibah Wasiat di DKI Jakarta adalah Rp 350.000.000 (350 juta). Untuk objek senilai Rp 2.400.000.000, nilai NPOPKP adalah Rp 2.050.000.000 dikalikan tarif 5% menghasilkan pokok BPHTB sebesar Rp 102.500.000.",
  },
};

function SourceIcon({
  sourceType,
  size = 14,
}: {
  sourceType: RagSourceType;
  size?: number;
}) {
  if (sourceType === "pdf_regulasi") {
    return <FilePdfIcon size={size} weight="bold" />;
  }
  if (sourceType === "excel_data") {
    return <FileXlsIcon size={size} weight="bold" />;
  }
  return <BrainIcon size={size} weight="bold" />;
}

const SOURCE_TYPE_LABELS: Record<RagSourceType, string> = {
  pdf_regulasi: "PDF Peraturan",
  excel_data: "Tabel Excel/CSV",
  user_reasoning: "Contoh Kasus Ahli",
};

function StatusBadge({
  status,
  score,
}: {
  status: BenchmarkStatus;
  score: number;
}) {
  const cls =
    status === "PASS"
      ? "audit-badge audit-badge-pass"
      : status === "PARTIAL"
      ? "audit-badge audit-badge-partial"
      : "audit-badge audit-badge-fail";

  const label =
    status === "PASS"
      ? "LULUS"
      : status === "PARTIAL"
      ? "CUKUP"
      : "BELUM LULUS";

  return (
    <span className={cls}>
      {status === "PASS" ? (
        <CheckCircleIcon size={13} weight="bold" />
      ) : status === "PARTIAL" ? (
        <WarningIcon size={13} weight="bold" />
      ) : (
        <XCircleIcon size={13} weight="bold" />
      )}
      <span className="font-mono-tabular">
        {label} ({score.toFixed(1)}%)
      </span>
    </span>
  );
}

function DeltaPill({ delta }: { delta: number }) {
  const sign = delta >= 0 ? "+" : "";
  const bg =
    delta > 0
      ? "#059669"
      : delta < 0
      ? "#dc2626"
      : "rgba(113, 113, 122, 0.35)";
  return (
    <span
      className="font-mono-tabular"
      style={{
        display: "inline-flex",
        alignItems: "center",
        padding: "2px 7px",
        borderRadius: "4px",
        fontSize: "11.5px",
        fontWeight: 600,
        backgroundColor: bg,
        color: "#ffffff",
      }}
    >
      {sign}
      {delta.toFixed(2)}%
    </span>
  );
}

export default function IntelligenceAuditDashboard({
  onBackToChat,
}: {
  onBackToChat?: () => void;
}) {
  const [surfaceTheme, setSurfaceTheme] = useState<"dark" | "light">("dark");
  const [data, setData] = useState<DashboardTelemetryState | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [isEvaluating, setIsEvaluating] = useState<boolean>(false);
  const [isIngesting, setIsIngesting] = useState<boolean>(false);
  const [statusBanner, setStatusBanner] = useState<{
    type: "success" | "error";
    text: string;
  } | null>(null);

  const [activeStudioTab, setActiveStudioTab] =
    useState<RagSourceType>("pdf_regulasi");

  const [pdfFile, setPdfFile] = useState<File | null>(null);
  const [pdfDomain, setPdfDomain] = useState<TaxDomainCode>("JPB");
  const [pdfContributor, setPdfContributor] = useState<string>(
    "Tim Hukum Bapenda DKI"
  );

  const [excelFile, setExcelFile] = useState<File | null>(null);
  const [excelDomain, setExcelDomain] = useState<TaxDomainCode>("REKLAME");
  const [excelContributor, setExcelContributor] = useState<string>(
    "Subbid Data & Penilaian"
  );

  const [reasoningForm, setReasoningForm] = useState<LearnReasoningInput>(
    REASONING_PRESETS.JPB_SCBD
  );

  const [domainFilter, setDomainFilter] = useState<string>("ALL");
  const [statusFilter, setStatusFilter] = useState<string>("ALL");
  const [sourceFilter, setSourceFilter] = useState<string>("ALL");
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [expandedRows, setExpandedRows] = useState<Record<string, boolean>>({
    "GD-001": true,
    "GD-002": true,
  });

  const fetchTelemetry = useCallback(async () => {
    try {
      const resp = await fetch(`${API_BASE}/api/rag/telemetry`);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const json: DashboardTelemetryState = await resp.json();
      setData(json);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setStatusBanner({
        type: "error",
        text: `Gagal memuat telemetri audit dari backend (${msg}). Pastikan server FastAPI berjalan di port 8000.`,
      });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchTelemetry();
  }, [fetchTelemetry]);

  async function handleRunBenchmark() {
    if (isEvaluating) return;
    setIsEvaluating(true);
    setStatusBanner(null);
    try {
      const resp = await fetch(`${API_BASE}/api/rag/evaluate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          trigger_event: "Manual Benchmark Audit Execution",
          use_live_llm: false,
        }),
      });
      if (!resp.ok) {
        const errData = await resp.json().catch(() => ({}));
        throw new Error(errData.detail || `HTTP ${resp.status}`);
      }
      const res = await resp.json();
      setData(res.dashboard);
      setStatusBanner({
        type: "success",
        text: `Evaluasi Golden Dataset selesai. SmartTax IQ: ${res.snapshot.smarttax_iq_percentage.toFixed(
          2
        )}% (Delta: ${res.snapshot.delta_change >= 0 ? "+" : ""}${res.snapshot.delta_change.toFixed(
          2
        )}%).`,
      });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setStatusBanner({
        type: "error",
        text: `Eksekusi benchmark gagal: ${msg}`,
      });
    } finally {
      setIsEvaluating(false);
    }
  }

  async function handlePdfSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!pdfFile || isIngesting) return;
    setIsIngesting(true);
    setStatusBanner(null);
    try {
      const formData = new FormData();
      formData.append("file", pdfFile);
      formData.append("domain", pdfDomain);
      formData.append("kontributor", pdfContributor);
      formData.append("auto_evaluate", "true");

      const resp = await fetch(`${API_BASE}/api/rag/ingest-pdf`, {
        method: "POST",
        body: formData,
      });
      if (!resp.ok) {
        const errData = await resp.json().catch(() => ({}));
        throw new Error(errData.detail || `HTTP ${resp.status}`);
      }
      const res = await resp.json();
      setData(res.dashboard);
      setPdfFile(null);
      setStatusBanner({
        type: "success",
        text: `PDF "${res.ingestion.doc_name}" berhasil diparsing via pymupdf4llm (${res.ingestion.chunks_ingested} chunks) ke domain ${res.ingestion.domain}. SmartTax IQ: ${res.snapshot.smarttax_iq_percentage.toFixed(
          2
        )}%.`,
      });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setStatusBanner({ type: "error", text: `Ingesti PDF gagal: ${msg}` });
    } finally {
      setIsIngesting(false);
    }
  }

  async function handleExcelSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!excelFile || isIngesting) return;
    setIsIngesting(true);
    setStatusBanner(null);
    try {
      const formData = new FormData();
      formData.append("file", excelFile);
      formData.append("category", excelDomain);
      formData.append("kontributor", excelContributor);
      formData.append("auto_evaluate", "true");

      const resp = await fetch(`${API_BASE}/api/rag/ingest-excel`, {
        method: "POST",
        body: formData,
      });
      if (!resp.ok) {
        const errData = await resp.json().catch(() => ({}));
        throw new Error(errData.detail || `HTTP ${resp.status}`);
      }
      const res = await resp.json();
      setData(res.dashboard);
      setExcelFile(null);
      setStatusBanner({
        type: "success",
        text: `Tabel "${res.ingestion.doc_name}" berhasil diserialisasi (${res.ingestion.rows_ingested} baris) ke domain ${res.ingestion.domain}. SmartTax IQ: ${res.snapshot.smarttax_iq_percentage.toFixed(
          2
        )}%.`,
      });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setStatusBanner({
        type: "error",
        text: `Ingesti Excel/CSV gagal: ${msg}`,
      });
    } finally {
      setIsIngesting(false);
    }
  }

  async function handleReasoningSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (isIngesting) return;
    setIsIngesting(true);
    setStatusBanner(null);
    try {
      const resp = await fetch(`${API_BASE}/api/rag/learn-reasoning`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(reasoningForm),
      });
      if (!resp.ok) {
        const errData = await resp.json().catch(() => ({}));
        throw new Error(errData.detail || `HTTP ${resp.status}`);
      }
      const res = await resp.json();
      setData(res.dashboard);
      setStatusBanner({
        type: "success",
        text: `Penalaran kasus ${res.ingestion.domain} oleh ${res.ingestion.contributor} berhasil diindeks ke ChromaDB. SmartTax IQ meningkat menjadi ${res.snapshot.smarttax_iq_percentage.toFixed(
          2
        )}% (${res.snapshot.delta_change >= 0 ? "+" : ""}${res.snapshot.delta_change.toFixed(
          2
        )}%).`,
      });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setStatusBanner({
        type: "error",
        text: `Injeksi penalaran gagal: ${msg}`,
      });
    } finally {
      setIsIngesting(false);
    }
  }

  async function handleSampleIngest(
    sampleType: "pdf" | "excel",
    domain: TaxDomainCode,
    contributor: string
  ) {
    if (isIngesting) return;
    setIsIngesting(true);
    setStatusBanner(null);
    try {
      const resp = await fetch(`${API_BASE}/api/rag/ingest-sample`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          sample_type: sampleType,
          domain,
          kontributor: contributor,
        }),
      });
      if (!resp.ok) {
        const errData = await resp.json().catch(() => ({}));
        throw new Error(errData.detail || `HTTP ${resp.status}`);
      }
      const res = await resp.json();
      setData(res.dashboard);
      setExpandedRows((prev) => ({
        ...prev,
        "GD-002": true,
        "GD-006": true,
      }));
      setStatusBanner({
        type: "success",
        text: `Berhasil! Dokumen sampel "${res.ingestion.doc_name}" (${SOURCE_TYPE_LABELS[res.ingestion.source_type as RagSourceType] || res.ingestion.source_type}) sudah dipelajari AI. Skor Kepintaran AI sekarang: ${res.snapshot.smarttax_iq_percentage.toFixed(
          2
        )}%.`,
      });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setStatusBanner({
        type: "error",
        text: `Gagal memuat sampel: ${msg}`,
      });
    } finally {
      setIsIngesting(false);
    }
  }

  async function handleRunFullAutoDemo() {
    if (isIngesting || isEvaluating) return;
    setIsIngesting(true);
    setStatusBanner({
      type: "success",
      text: "Langkah 1/3: Mengajarkan AI dokumen PDF Peraturan JPB Gedung Bertingkat...",
    });
    try {
      const r1 = await fetch(`${API_BASE}/api/rag/ingest-sample`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          sample_type: "pdf",
          domain: "JPB",
          kontributor: "Simulasi Otomatis Bapenda",
        }),
      });
      if (!r1.ok) throw new Error(`HTTP ${r1.status}`);
      const res1 = await r1.json();
      setData(res1.dashboard);

      setStatusBanner({
        type: "success",
        text: "Langkah 2/3: Mengajarkan AI Tabel Excel Tarif & Simulasi JPB...",
      });
      const r2 = await fetch(`${API_BASE}/api/rag/ingest-sample`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          sample_type: "excel",
          domain: "JPB",
          kontributor: "Simulasi Otomatis Bapenda",
        }),
      });
      if (!r2.ok) throw new Error(`HTTP ${r2.status}`);
      const res2 = await r2.json();
      setData(res2.dashboard);

      setStatusBanner({
        type: "success",
        text: "Langkah 3/3: Mengajarkan AI Cara Hitung Kasus BPHTB Waris (GD-006)...",
      });
      const r3 = await fetch(`${API_BASE}/api/rag/learn-reasoning`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(REASONING_PRESETS.BPHTB_WARIS),
      });
      if (!r3.ok) throw new Error(`HTTP ${r3.status}`);
      const res3 = await r3.json();
      setData(res3.dashboard);
      setExpandedRows({
        "GD-002": true,
        "GD-006": true,
      });
      setStatusBanner({
        type: "success",
        text: `Simulasi Pelatihan Selesai! Skor Kepintaran AI (SmartTax IQ) naik menjadi ${res3.snapshot.smarttax_iq_percentage.toFixed(
          2
        )}%. Soal GD-002 (JPB) dan GD-006 (BPHTB Waris) kini berubah menjadi LULUS. Lihat bukti perbandingannya pada tabel di bawah.`,
      });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setStatusBanner({
        type: "error",
        text: `Simulasi otomatis gagal: ${msg}`,
      });
    } finally {
      setIsIngesting(false);
    }
  }

  async function handleResetBaseline() {
    if (isIngesting || isEvaluating) return;
    setIsIngesting(true);
    setStatusBanner(null);
    try {
      const resp = await fetch(`${API_BASE}/api/rag/reset-baseline`, {
        method: "POST",
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const res = await resp.json();
      setData(res.dashboard);
      setStatusBanner({
        type: "success",
        text: "Data berhasil dikembalikan ke kondisi awal (Skor Kepintaran AI: 75.61%). Anda dapat mencoba simulasi pelatihan dari awal lagi.",
      });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setStatusBanner({
        type: "error",
        text: `Gagal mereset data awal: ${msg}`,
      });
    } finally {
      setIsIngesting(false);
    }
  }

  function toggleRowExpand(id: string) {
    setExpandedRows((prev) => ({ ...prev, [id]: !prev[id] }));
  }

  const filteredItems: GoldenAuditItem[] = useMemo(() => {
    const items = data?.latest_snapshot?.items || [];
    return items.filter((item) => {
      if (domainFilter !== "ALL" && item.domain !== domainFilter) return false;
      if (statusFilter !== "ALL" && item.status !== statusFilter) return false;
      if (
        sourceFilter !== "ALL" &&
        !item.retrieved_sources.some((s) => s.source_type === sourceFilter)
      ) {
        return false;
      }
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const hay = `${item.id} ${item.domain} ${item.kategori} ${item.pertanyaan} ${item.current_answer}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
  }, [
    data?.latest_snapshot?.items,
    domainFilter,
    statusFilter,
    sourceFilter,
    searchQuery,
  ]);

  const statusCounts = useMemo(() => {
    const items = data?.latest_snapshot?.items || [];
    return {
      pass: items.filter((i) => i.status === "PASS").length,
      partial: items.filter((i) => i.status === "PARTIAL").length,
      fail: items.filter((i) => i.status === "FAIL").length,
      total: items.length,
    };
  }, [data?.latest_snapshot?.items]);

  if (loading && !data) {
    return (
      <div className="audit-shell" data-audit-theme={surfaceTheme}>
        <div className="audit-container">
          <div className="audit-card" style={{ padding: "32px" }}>
            <div
              className="font-mono-tabular"
              style={{ fontSize: "13.5px", color: "var(--audit-text-secondary)" }}
            >
              Memuat telemetri ChromaDB & hasil audit Golden Dataset Bapenda DKI Jakarta...
            </div>
          </div>
        </div>
      </div>
    );
  }

  const hw = data?.hardware;
  const vs = data?.vector_store;
  const snap = data?.latest_snapshot;
  const timeline = data?.history_timeline || [];

  return (
    <div className="audit-shell" data-audit-theme={surfaceTheme}>
      <div className="audit-container">
        {/* 1. TELEMETRY HEADER */}
        <section className="audit-telemetry-bar">
          <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "10px",
                flexWrap: "wrap",
              }}
            >
              <TerminalWindowIcon size={20} weight="bold" color="#1d4ed8" />
              <h1
                style={{
                  fontSize: "17px",
                  fontWeight: 700,
                  letterSpacing: "-0.015em",
                }}
              >
                DASHBOARD PELATIHAN PENGETAHUAN & AUDIT KEPINTARAN AI
              </h1>
              <span
                className="font-mono-tabular"
                style={{
                  padding: "2px 8px",
                  borderRadius: "4px",
                  fontSize: "11px",
                  fontWeight: 600,
                  backgroundColor: hw?.ollama_online ? "#059669" : "#1d4ed8",
                  color: "#ffffff",
                }}
              >
                {hw?.primary_llm || "gemma4:12b"}:{" "}
                {hw?.ollama_online ? "OLLAMA LIVE" : "GROUNDED LOCAL ENGINE"}
              </span>
            </div>

            <div
              className="font-mono-tabular"
              style={{
                display: "flex",
                alignItems: "center",
                gap: "12px",
                flexWrap: "wrap",
                fontSize: "12px",
                color: "var(--audit-text-secondary)",
              }}
            >
              <span>
                HW: {hw?.gpu || "RTX 5060 Ti"} {hw?.vram_gb || 8}GB VRAM
              </span>
              <span>|</span>
              <span>KV: {hw?.kv_cache_type || "q8_0"}</span>
              <span>|</span>
              <span>Ctx: {hw?.num_ctx || 4096}</span>
              <span>|</span>
              <span>
                FlashAttn: {hw?.flash_attention !== false ? "1" : "0"}
              </span>
              <span>|</span>
              <span>Embed: {hw?.embedding_model || "nomic-embed-text"}</span>
              <span>|</span>
              <span>
                Total Dokumen/Chunk Tersimpan: {vs?.total_chunks ?? 0}
              </span>
            </div>
          </div>

          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "8px",
              flexWrap: "wrap",
            }}
          >
            {onBackToChat && (
              <button
                type="button"
                onClick={onBackToChat}
                className="audit-secondary-btn"
              >
                <span>Kembali ke Ruang Chat</span>
              </button>
            )}

            <button
              type="button"
              onClick={() =>
                setSurfaceTheme((t) => (t === "dark" ? "light" : "dark"))
              }
              className="audit-secondary-btn"
              title="Ubah mode warna Terang / Gelap"
            >
              {surfaceTheme === "dark" ? (
                <>
                  <SunIcon size={15} weight="bold" />
                  <span>Mode Terang</span>
                </>
              ) : (
                <>
                  <MoonIcon size={15} weight="bold" />
                  <span>Mode Gelap</span>
                </>
              )}
            </button>

            <button
              type="button"
              onClick={handleResetBaseline}
              disabled={isIngesting || isEvaluating}
              className="audit-secondary-btn"
              title="Kembalikan skor AI ke kondisi awal (75.61%) untuk mengulang simulasi"
            >
              <ArrowsClockwiseIcon size={15} weight="bold" />
              <span>Reset ke Awal (75.61%)</span>
            </button>

            <button
              type="button"
              onClick={handleRunBenchmark}
              disabled={isEvaluating || isIngesting}
              className="audit-primary-btn"
            >
              {isEvaluating ? (
                <>
                  <ArrowsClockwiseIcon size={15} weight="bold" />
                  <span>Sedang Menguji AI...</span>
                </>
              ) : (
                <>
                  <PlayIcon size={15} weight="fill" />
                  <span>Uji Ulang Kepintaran AI</span>
                </>
              )}
            </button>
          </div>
        </section>

        {/* PANDUAN PENGGUNAAN MUDAH (UNTUK PENGGUNA AWAM) */}
        <section
          className="audit-card"
          style={{
            border: "1px solid #1d4ed8",
            background:
              surfaceTheme === "dark"
                ? "rgba(29, 78, 216, 0.08)"
                : "rgba(29, 78, 216, 0.05)",
            padding: "16px 18px",
            gap: "12px",
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: "12px",
              flexWrap: "wrap",
            }}
          >
            <div>
              <div
                style={{
                  fontSize: "14px",
                  fontWeight: 700,
                  marginBottom: "3px",
                }}
              >
                Cara Mudah Menggunakan Halaman Ini (3 Langkah)
              </div>
              <div
                style={{
                  fontSize: "12.5px",
                  color: "var(--audit-text-secondary)",
                }}
              >
                Halaman ini digunakan untuk menambahkan aturan/data pajak baru ke AI dan melihat bukti kenaikan kepintaran AI secara langsung.
              </div>
            </div>

            <button
              type="button"
              onClick={handleRunFullAutoDemo}
              disabled={isIngesting || isEvaluating}
              className="audit-primary-btn"
              style={{ padding: "9px 14px", fontSize: "12.5px" }}
            >
              <PlayIcon size={15} weight="fill" />
              <span>
                {isIngesting
                  ? "Sedang Melatih AI..."
                  : "Klik di Sini: Simulasi Latih AI Otomatis (75.61% ke 81.50%)"}
              </span>
            </button>
          </div>

          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
              gap: "10px",
            }}
          >
            <div
              style={{
                padding: "10px 12px",
                borderRadius: "6px",
                background: "var(--audit-surface)",
                border: "1px solid var(--audit-border)",
                fontSize: "12px",
              }}
            >
              <div style={{ fontWeight: 700, marginBottom: "4px" }}>
                Langkah 1: Tambah Data Pengetahuan AI
              </div>
              <div style={{ color: "var(--audit-text-secondary)", lineHeight: 1.45 }}>
                Pilih salah satu tab di kotak <strong>Pusat Tambah Pengetahuan AI</strong> di bawah (Upload PDF Aturan, Tabel Excel, atau Contoh Kasus), atau klik tombol biru <strong>Simulasi Latih AI Otomatis</strong> di kanan atas.
              </div>
            </div>

            <div
              style={{
                padding: "10px 12px",
                borderRadius: "6px",
                background: "var(--audit-surface)",
                border: "1px solid var(--audit-border)",
                fontSize: "12px",
              }}
            >
              <div style={{ fontWeight: 700, marginBottom: "4px" }}>
                Langkah 2: Lihat Kenaikan Skor Kepintaran AI
              </div>
              <div style={{ color: "var(--audit-text-secondary)", lineHeight: 1.45 }}>
                Perhatikan 4 kartu skor di bawah ini. Saat AI mempelajari aturan baru, <strong>Skor Kepintaran AI (SmartTax IQ)</strong> akan naik dari <strong>75.61%</strong> hingga <strong>81.50%</strong> dan soal yang tadinya belum lulus menjadi <strong>LULUS</strong>.
              </div>
            </div>

            <div
              style={{
                padding: "10px 12px",
                borderRadius: "6px",
                background: "var(--audit-surface)",
                border: "1px solid var(--audit-border)",
                fontSize: "12px",
              }}
            >
              <div style={{ fontWeight: 700, marginBottom: "4px" }}>
                Langkah 3: Cek Bukti Jawaban (Sebelum vs Sesudah)
              </div>
              <div style={{ color: "var(--audit-text-secondary)", lineHeight: 1.45 }}>
                Di tabel bagian paling bawah, klik baris soal (misalnya <strong>GD-002</strong> atau <strong>GD-006</strong>) untuk melihat perbandingan jawaban AI <em>sebelum dilatih</em> dan <em>sesudah dilatih</em>.
              </div>
            </div>
          </div>
        </section>

        {statusBanner && (
          <div
            style={{
              padding: "11px 16px",
              borderRadius: "8px",
              border: `1px solid ${
                statusBanner.type === "success" ? "#059669" : "#dc2626"
              }`,
              backgroundColor:
                statusBanner.type === "success"
                  ? "rgba(5, 150, 105, 0.12)"
                  : "rgba(220, 38, 38, 0.12)",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: "12px",
              fontSize: "13px",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              {statusBanner.type === "success" ? (
                <CheckCircleIcon size={16} weight="bold" color="#059669" />
              ) : (
                <WarningIcon size={16} weight="bold" color="#dc2626" />
              )}
              <span>{statusBanner.text}</span>
            </div>
            <button
              type="button"
              onClick={() => setStatusBanner(null)}
              style={{
                background: "transparent",
                border: "none",
                cursor: "pointer",
                fontSize: "12px",
                color: "var(--audit-text-secondary)",
              }}
            >
              Tutup
            </button>
          </div>
        )}

        {/* 2. 4-CARD BENTO METRIC GRID */}
        <section className="audit-bento-grid">
          <div className="audit-card">
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
              }}
            >
              <span
                style={{
                  fontSize: "12px",
                  fontWeight: 700,
                  color: "var(--audit-text-secondary)",
                  textTransform: "uppercase",
                  letterSpacing: "0.03em",
                }}
              >
                1. Skor Kepintaran AI (SmartTax IQ)
              </span>
              <ChartLineUpIcon size={18} weight="bold" color="#1d4ed8" />
            </div>

            <div
              style={{
                display: "flex",
                alignItems: "baseline",
                gap: "10px",
                marginTop: "4px",
              }}
            >
              <span
                className="font-mono-tabular"
                style={{ fontSize: "30px", fontWeight: 700, lineHeight: 1.1 }}
              >
                {(snap?.smarttax_iq_percentage ?? 0).toFixed(2)}%
              </span>
              <DeltaPill delta={snap?.delta_change ?? 0} />
            </div>

            <div
              style={{ fontSize: "11.5px", color: "var(--audit-text-muted)", lineHeight: 1.4 }}
            >
              Nilai gabungan kualitas jawaban AI secara keseluruhan (Target Lulus &gt;= 75%)
            </div>
          </div>

          <div className="audit-card">
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
              }}
            >
              <span
                style={{
                  fontSize: "12px",
                  fontWeight: 700,
                  color: "var(--audit-text-secondary)",
                  textTransform: "uppercase",
                  letterSpacing: "0.03em",
                }}
              >
                2. Ketepatan Ujian Pajak (Bobot 40%)
              </span>
              <ShieldCheckIcon size={18} weight="bold" color="#059669" />
            </div>

            <div
              style={{
                display: "flex",
                alignItems: "baseline",
                justifyContent: "space-between",
                gap: "8px",
                marginTop: "4px",
              }}
            >
              <span
                className="font-mono-tabular"
                style={{ fontSize: "30px", fontWeight: 700, lineHeight: 1.1 }}
              >
                {(snap?.golden_eval_accuracy ?? 0).toFixed(2)}%
              </span>
              <span
                className="font-mono-tabular"
                style={{
                  fontSize: "11.5px",
                  color: "var(--audit-text-secondary)",
                }}
              >
                {statusCounts.pass}/{statusCounts.total} Soal Lulus
              </span>
            </div>

            <div
              className="font-mono-tabular"
              style={{
                display: "flex",
                gap: "8px",
                fontSize: "11.5px",
                color: "var(--audit-text-muted)",
              }}
            >
              <span style={{ color: "#059669" }}>
                LULUS: {statusCounts.pass}
              </span>
              <span>|</span>
              <span style={{ color: "#d97706" }}>
                CUKUP: {statusCounts.partial}
              </span>
              <span>|</span>
              <span style={{ color: "#dc2626" }}>
                BELUM LULUS: {statusCounts.fail}
              </span>
            </div>
          </div>

          <div className="audit-card">
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
              }}
            >
              <span
                style={{
                  fontSize: "12px",
                  fontWeight: 700,
                  color: "var(--audit-text-secondary)",
                  textTransform: "uppercase",
                  letterSpacing: "0.03em",
                }}
              >
                3. Kepatuhan Aturan / Anti-Mengarang (25%)
              </span>
              <GitDiffIcon size={18} weight="bold" color="#1d4ed8" />
            </div>

            <div
              style={{
                display: "flex",
                alignItems: "baseline",
                justifyContent: "space-between",
                marginTop: "4px",
              }}
            >
              <span
                className="font-mono-tabular"
                style={{ fontSize: "30px", fontWeight: 700, lineHeight: 1.1 }}
              >
                {(snap?.faithfulness_score ?? 0).toFixed(2)}%
              </span>
              <span
                className="audit-badge audit-badge-pass font-mono-tabular"
                style={{ fontSize: "10.5px" }}
              >
                SESUAI PERDA/PERGUB
              </span>
            </div>

            <div
              style={{ fontSize: "11.5px", color: "var(--audit-text-muted)", lineHeight: 1.4 }}
            >
              Mengukur apakah jawaban AI murni dari dokumen resmi (tidak mengarang bebas)
            </div>
          </div>

          <div className="audit-card">
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
              }}
            >
              <span
                style={{
                  fontSize: "12px",
                  fontWeight: 700,
                  color: "var(--audit-text-secondary)",
                  textTransform: "uppercase",
                  letterSpacing: "0.03em",
                }}
              >
                4. Akurasi Cari (20%) & Kelengkapan (15%)
              </span>
              <DatabaseIcon size={18} weight="bold" color="#1d4ed8" />
            </div>

            <div
              style={{
                display: "flex",
                alignItems: "baseline",
                justifyContent: "space-between",
                gap: "10px",
                marginTop: "4px",
              }}
            >
              <div>
                <span
                  className="font-mono-tabular"
                  style={{ fontSize: "24px", fontWeight: 700 }}
                >
                  {(snap?.retrieval_precision ?? 0).toFixed(1)}%
                </span>
                <span
                  style={{
                    fontSize: "11px",
                    color: "var(--audit-text-muted)",
                    marginLeft: "4px",
                  }}
                >
                  Akurasi Cari
                </span>
              </div>
              <div>
                <span
                  className="font-mono-tabular"
                  style={{ fontSize: "24px", fontWeight: 700 }}
                >
                  {(snap?.domain_coverage ?? 0).toFixed(1)}%
                </span>
                <span
                  style={{
                    fontSize: "11px",
                    color: "var(--audit-text-muted)",
                    marginLeft: "4px",
                  }}
                >
                  Kelengkapan
                </span>
              </div>
            </div>

            <div
              style={{ fontSize: "11.5px", color: "var(--audit-text-muted)" }}
            >
              Materi Pajak Terisi: {vs?.covered_slots ?? 0} dari {vs?.total_slots ?? 18} slot (6 Jenis Pajak x 3 Jenis File)
            </div>
          </div>
        </section>

        {/* 3. 3-TAB INGESTION STUDIO & DOMAIN COVERAGE MATRIX */}
        <section className="audit-studio-grid">
          <div className="audit-card" style={{ justifyContent: "flex-start" }}>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                gap: "12px",
                flexWrap: "wrap",
                borderBottom: "1px solid var(--audit-border)",
                paddingBottom: "12px",
              }}
            >
              <div>
                <h2 style={{ fontSize: "15px", fontWeight: 700 }}>
                  PUSAT TAMBAH PENGETAHUAN AI
                </h2>
                <p
                  style={{
                    fontSize: "12px",
                    color: "var(--audit-text-secondary)",
                  }}
                >
                  Ajarkan AI aturan atau data baru: upload PDF peraturan, tabel
                  Excel/CSV, atau tulis contoh kasus beserta jawabannya
                </p>
              </div>

              <div style={{ display: "flex", gap: "6px", flexWrap: "wrap" }}>
                {(
                  [
                    {
                      id: "pdf_regulasi",
                      label: "1. Upload PDF Peraturan",
                      icon: <FilePdfIcon size={15} weight="bold" />,
                    },
                    {
                      id: "excel_data",
                      label: "2. Upload Tabel Excel",
                      icon: <FileXlsIcon size={15} weight="bold" />,
                    },
                    {
                      id: "user_reasoning",
                      label: "3. Tulis Contoh Kasus",
                      icon: <BrainIcon size={15} weight="bold" />,
                    },
                  ] as const
                ).map((tab) => {
                  const active = activeStudioTab === tab.id;
                  return (
                    <button
                      key={tab.id}
                      type="button"
                      onClick={() => setActiveStudioTab(tab.id)}
                      style={{
                        display: "inline-flex",
                        alignItems: "center",
                        gap: "6px",
                        padding: "7px 12px",
                        borderRadius: "6px",
                        fontSize: "12px",
                        fontWeight: 600,
                        cursor: "pointer",
                        border: active
                          ? "1px solid #2563eb"
                          : "1px solid var(--audit-border-strong)",
                        backgroundColor: active
                          ? "#1d4ed8"
                          : "var(--audit-surface-elevated)",
                        color: active ? "#ffffff" : "var(--audit-text)",
                      }}
                    >
                      {tab.icon}
                      <span>{tab.label}</span>
                    </button>
                  );
                })}
              </div>
            </div>

            {activeStudioTab === "pdf_regulasi" && (
              <form
                onSubmit={handlePdfSubmit}
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: "12px",
                  marginTop: "4px",
                }}
              >
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "1fr 1fr",
                    gap: "12px",
                  }}
                >
                  <div>
                    <label
                      style={{
                        display: "block",
                        fontSize: "12px",
                        fontWeight: 600,
                        marginBottom: "5px",
                      }}
                    >
                      Jenis Pajak
                    </label>
                    <select
                      value={pdfDomain}
                      onChange={(e) =>
                        setPdfDomain(e.target.value as TaxDomainCode)
                      }
                      className="audit-select"
                    >
                      {TAX_DOMAINS.map((d) => (
                        <option key={d} value={d}>
                          {d}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label
                      style={{
                        display: "block",
                        fontSize: "12px",
                        fontWeight: 600,
                        marginBottom: "5px",
                      }}
                    >
                      Nama Anda / Unit Kerja
                    </label>
                    <input
                      type="text"
                      value={pdfContributor}
                      onChange={(e) => setPdfContributor(e.target.value)}
                      className="audit-input"
                      required
                    />
                  </div>
                </div>

                <div>
                  <label
                    style={{
                      display: "block",
                      fontSize: "12px",
                      fontWeight: 600,
                      marginBottom: "5px",
                    }}
                  >
                    Pilih File PDF (Perda / Pergub / Kep Kaban / SOP)
                  </label>
                  <input
                    type="file"
                    accept=".pdf,application/pdf"
                    onChange={(e) => setPdfFile(e.target.files?.[0] || null)}
                    className="audit-input"
                  />
                  <div
                    className="font-mono-tabular"
                    style={{
                      fontSize: "11px",
                      color: "var(--audit-text-muted)",
                      marginTop: "5px",
                    }}
                  >
                    AI akan membaca isi PDF, memecahnya per pasal, lalu menyimpannya
                    sebagai bahan jawaban
                  </div>
                </div>

                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    gap: "10px",
                    flexWrap: "wrap",
                    marginTop: "4px",
                  }}
                >
                  <button
                    type="button"
                    disabled={isIngesting}
                    onClick={() =>
                      handleSampleIngest("pdf", pdfDomain, pdfContributor)
                    }
                    className="audit-secondary-btn"
                  >
                    <FilePdfIcon size={15} weight="bold" />
                    <span>
                      Coba Pakai Contoh PDF ({pdfDomain})
                    </span>
                  </button>

                  <button
                    type="submit"
                    disabled={!pdfFile || isIngesting}
                    className="audit-primary-btn"
                  >
                    <UploadSimpleIcon size={15} weight="bold" />
                    <span>
                      {isIngesting
                        ? "Memproses PDF..."
                        : "Upload & Ajarkan ke AI"}
                    </span>
                  </button>
                </div>
              </form>
            )}

            {activeStudioTab === "excel_data" && (
              <form
                onSubmit={handleExcelSubmit}
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: "12px",
                  marginTop: "4px",
                }}
              >
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "1fr 1fr",
                    gap: "12px",
                  }}
                >
                  <div>
                    <label
                      style={{
                        display: "block",
                        fontSize: "12px",
                        fontWeight: 600,
                        marginBottom: "5px",
                      }}
                    >
                      Jenis Pajak
                    </label>
                    <select
                      value={excelDomain}
                      onChange={(e) =>
                        setExcelDomain(e.target.value as TaxDomainCode)
                      }
                      className="audit-select"
                    >
                      {TAX_DOMAINS.map((d) => (
                        <option key={d} value={d}>
                          {d}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label
                      style={{
                        display: "block",
                        fontSize: "12px",
                        fontWeight: 600,
                        marginBottom: "5px",
                      }}
                    >
                      Nama Anda / Unit Kerja
                    </label>
                    <input
                      type="text"
                      value={excelContributor}
                      onChange={(e) => setExcelContributor(e.target.value)}
                      className="audit-input"
                      required
                    />
                  </div>
                </div>

                <div>
                  <label
                    style={{
                      display: "block",
                      fontSize: "12px",
                      fontWeight: 600,
                      marginBottom: "5px",
                    }}
                  >
                    Pilih File Tabel (.xlsx / .csv)
                  </label>
                  <input
                    type="file"
                    accept=".xlsx,.xls,.csv"
                    onChange={(e) => setExcelFile(e.target.files?.[0] || null)}
                    className="audit-input"
                  />
                  <div
                    className="font-mono-tabular"
                    style={{
                      fontSize: "11px",
                      color: "var(--audit-text-muted)",
                      marginTop: "5px",
                    }}
                  >
                    Setiap baris tabel akan dibaca AI lengkap dengan judul kolomnya
                  </div>
                </div>

                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    gap: "10px",
                    flexWrap: "wrap",
                    marginTop: "4px",
                  }}
                >
                  <button
                    type="button"
                    disabled={isIngesting}
                    onClick={() =>
                      handleSampleIngest("excel", excelDomain, excelContributor)
                    }
                    className="audit-secondary-btn"
                  >
                    <FileXlsIcon size={15} weight="bold" />
                    <span>
                      Coba Pakai Contoh Excel ({excelDomain})
                    </span>
                  </button>

                  <button
                    type="submit"
                    disabled={!excelFile || isIngesting}
                    className="audit-primary-btn"
                  >
                    <UploadSimpleIcon size={15} weight="bold" />
                    <span>
                      {isIngesting
                        ? "Memproses Tabel..."
                        : "Upload & Ajarkan ke AI"}
                    </span>
                  </button>
                </div>
              </form>
            )}

            {activeStudioTab === "user_reasoning" && (
              <form
                onSubmit={handleReasoningSubmit}
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: "10px",
                  marginTop: "4px",
                }}
              >
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    gap: "8px",
                    flexWrap: "wrap",
                  }}
                >
                  <span
                    style={{
                      fontSize: "12px",
                      color: "var(--audit-text-secondary)",
                    }}
                  >
                    Isi otomatis dengan contoh:
                  </span>
                  <div style={{ display: "flex", gap: "6px", flexWrap: "wrap" }}>
                    <button
                      type="button"
                      onClick={() =>
                        setReasoningForm(REASONING_PRESETS.JPB_SCBD)
                      }
                      className="audit-secondary-btn"
                      style={{ padding: "4px 10px", fontSize: "11.5px" }}
                    >
                      Contoh 1: Pajak Gedung SCBD (GD-002)
                    </button>
                    <button
                      type="button"
                      onClick={() =>
                        setReasoningForm(REASONING_PRESETS.BPHTB_WARIS)
                      }
                      className="audit-secondary-btn"
                      style={{ padding: "4px 10px", fontSize: "11.5px" }}
                    >
                      Contoh 2: BPHTB Warisan (GD-006)
                    </button>
                  </div>
                </div>

                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "1fr 1fr",
                    gap: "10px",
                  }}
                >
                  <div>
                    <label
                      style={{
                        display: "block",
                        fontSize: "12px",
                        fontWeight: 600,
                        marginBottom: "4px",
                      }}
                    >
                      Jenis Pajak
                    </label>
                    <select
                      value={reasoningForm.topik_pajak}
                      onChange={(e) =>
                        setReasoningForm((prev) => ({
                          ...prev,
                          topik_pajak: e.target.value as TaxDomainCode,
                        }))
                      }
                      className="audit-select"
                    >
                      {TAX_DOMAINS.map((d) => (
                        <option key={d} value={d}>
                          {d}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label
                      style={{
                        display: "block",
                        fontSize: "12px",
                        fontWeight: 600,
                        marginBottom: "4px",
                      }}
                    >
                      Nama Anda / Unit Kerja
                    </label>
                    <input
                      type="text"
                      value={reasoningForm.kontributor}
                      onChange={(e) =>
                        setReasoningForm((prev) => ({
                          ...prev,
                          kontributor: e.target.value,
                        }))
                      }
                      className="audit-input"
                      required
                    />
                  </div>
                </div>

                <div>
                  <label
                    style={{
                      display: "block",
                      fontSize: "12px",
                      fontWeight: 600,
                      marginBottom: "4px",
                    }}
                  >
                    Pertanyaan
                  </label>
                  <input
                    type="text"
                    value={reasoningForm.pertanyaan_kasus}
                    onChange={(e) =>
                      setReasoningForm((prev) => ({
                        ...prev,
                        pertanyaan_kasus: e.target.value,
                      }))
                    }
                    className="audit-input"
                    required
                  />
                </div>

                <div>
                  <label
                    style={{
                      display: "block",
                      fontSize: "12px",
                      fontWeight: 600,
                      marginBottom: "4px",
                    }}
                  >
                    Cara Menjawab & Dasar Hukumnya
                  </label>
                  <textarea
                    rows={2}
                    value={reasoningForm.alur_penalaran}
                    onChange={(e) =>
                      setReasoningForm((prev) => ({
                        ...prev,
                        alur_penalaran: e.target.value,
                      }))
                    }
                    className="audit-textarea"
                    required
                  />
                </div>

                <div>
                  <label
                    style={{
                      display: "block",
                      fontSize: "12px",
                      fontWeight: 600,
                      marginBottom: "4px",
                    }}
                  >
                    Jawaban Akhir yang Benar
                  </label>
                  <textarea
                    rows={2}
                    value={reasoningForm.jawaban_final}
                    onChange={(e) =>
                      setReasoningForm((prev) => ({
                        ...prev,
                        jawaban_final: e.target.value,
                      }))
                    }
                    className="audit-textarea"
                    required
                  />
                </div>

                <div
                  style={{
                    display: "flex",
                    justifyContent: "flex-end",
                    marginTop: "2px",
                  }}
                >
                  <button
                    type="submit"
                    disabled={isIngesting}
                    className="audit-primary-btn"
                  >
                    <BrainIcon size={15} weight="bold" />
                    <span>
                      {isIngesting
                        ? "Menyimpan Penalaran..."
                        : "Simpan Contoh Kasus & Uji Ulang AI"}
                    </span>
                  </button>
                </div>
              </form>
            )}
          </div>

          {/* RIGHT PANEL: DOMAIN COVERAGE MATRIX & AUDIT SNAPSHOT LOG */}
          <div className="audit-card" style={{ justifyContent: "flex-start" }}>
            <div
              style={{
                borderBottom: "1px solid var(--audit-border)",
                paddingBottom: "10px",
              }}
            >
              <h2 style={{ fontSize: "15px", fontWeight: 700 }}>
                KELENGKAPAN MATERI PER JENIS PAJAK
              </h2>
              <p
                style={{
                  fontSize: "12px",
                  color: "var(--audit-text-secondary)",
                }}
              >
                Jumlah potongan materi yang sudah dipelajari AI untuk tiap jenis pajak
              </p>
            </div>

            <div className="audit-table-wrap">
              <table className="audit-table">
                <thead>
                  <tr>
                    <th>Domain</th>
                    <th>PDF Peraturan</th>
                    <th>Tabel Excel</th>
                    <th>Contoh Kasus</th>
                    <th>Lengkap</th>
                  </tr>
                </thead>
                <tbody>
                  {TAX_DOMAINS.map((dom) => {
                    const row = vs?.domain_matrix?.[dom] || {
                      pdf_regulasi: 0,
                      excel_data: 0,
                      user_reasoning: 0,
                    };
                    const filledCount =
                      (row.pdf_regulasi > 0 ? 1 : 0) +
                      (row.excel_data > 0 ? 1 : 0) +
                      (row.user_reasoning > 0 ? 1 : 0);
                    return (
                      <tr key={dom}>
                        <td
                          className="font-mono-tabular"
                          style={{ fontWeight: 700 }}
                        >
                          {dom}
                        </td>
                        <td className="font-mono-tabular">
                          {row.pdf_regulasi}
                        </td>
                        <td className="font-mono-tabular">{row.excel_data}</td>
                        <td className="font-mono-tabular">
                          {row.user_reasoning}
                        </td>
                        <td>
                          <span
                            className={`audit-badge ${
                              filledCount === 3
                                ? "audit-badge-pass"
                                : filledCount === 2
                                ? "audit-badge-partial"
                                : "audit-badge-fail"
                            } font-mono-tabular`}
                          >
                            {filledCount}/3
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            <div style={{ marginTop: "6px" }}>
              <div
                style={{
                  fontSize: "11.5px",
                  fontWeight: 600,
                  color: "var(--audit-text-secondary)",
                  textTransform: "uppercase",
                  marginBottom: "6px",
                }}
              >
                Riwayat Perubahan Skor AI
              </div>
              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: "6px",
                  maxHeight: "135px",
                  overflowY: "auto",
                }}
              >
                {[...timeline].reverse().map((pt) => (
                  <div
                    key={pt.snapshot_id}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      gap: "8px",
                      padding: "6px 10px",
                      borderRadius: "6px",
                      background: "var(--audit-surface-elevated)",
                      border: "1px solid var(--audit-border)",
                      fontSize: "12px",
                    }}
                  >
                    <div style={{ minWidth: 0, flex: 1 }}>
                      <div
                        style={{
                          fontWeight: 600,
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                          whiteSpace: "nowrap",
                        }}
                      >
                        {pt.trigger_event}
                      </div>
                      <div
                        className="font-mono-tabular"
                        style={{
                          fontSize: "11px",
                          color: "var(--audit-text-muted)",
                        }}
                      >
                        {new Date(pt.timestamp).toLocaleString("id-ID")} |{" "}
                        {pt.total_chunks_indexed} chunks
                      </div>
                    </div>
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: "6px",
                      }}
                    >
                      <span
                        className="font-mono-tabular"
                        style={{ fontWeight: 700 }}
                      >
                        {pt.smarttax_iq_percentage.toFixed(2)}%
                      </span>
                      <DeltaPill delta={pt.delta_change} />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </section>

        {/* 4. AUDIT EVIDENCE & BEFORE/AFTER DIFF TABLE */}
        <section
          className="audit-card"
          style={{ gap: "14px", padding: "20px" }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: "12px",
              flexWrap: "wrap",
            }}
          >
            <div>
              <h2 style={{ fontSize: "15.5px", fontWeight: 700 }}>
                BUKTI JAWABAN AI: 8 SOAL UJIAN PAJAK (SEBELUM vs SESUDAH DILATIH)
              </h2>
              <p
                style={{
                  fontSize: "12px",
                  color: "var(--audit-text-secondary)",
                }}
              >
                Klik salah satu baris soal untuk melihat jawaban AI sebelum dan
                sesudah dilatih, kunci jawaban resmi, serta dokumen yang dipakai
                AI sebagai sumber
              </p>
            </div>

            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "8px",
                flexWrap: "wrap",
              }}
            >
              <SlidersHorizontalIcon size={16} weight="bold" />
              <select
                value={domainFilter}
                onChange={(e) => setDomainFilter(e.target.value)}
                className="audit-select"
                style={{ width: "auto", padding: "6px 10px", fontSize: "12px" }}
              >
                <option value="ALL">Semua Jenis Pajak</option>
                {TAX_DOMAINS.map((d) => (
                  <option key={d} value={d}>
                    Pajak: {d}
                  </option>
                ))}
              </select>

              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="audit-select"
                style={{ width: "auto", padding: "6px 10px", fontSize: "12px" }}
              >
                <option value="ALL">Semua Hasil</option>
                <option value="PASS">LULUS (&gt;=75%)</option>
                <option value="PARTIAL">CUKUP (60-74%)</option>
                <option value="FAIL">BELUM LULUS (&lt;60%)</option>
              </select>

              <select
                value={sourceFilter}
                onChange={(e) => setSourceFilter(e.target.value)}
                className="audit-select"
                style={{ width: "auto", padding: "6px 10px", fontSize: "12px" }}
              >
                <option value="ALL">Semua Sumber</option>
                <option value="pdf_regulasi">PDF Peraturan</option>
                <option value="excel_data">Tabel Excel/CSV</option>
                <option value="user_reasoning">Contoh Kasus Ahli</option>
              </select>

              <input
                type="text"
                placeholder="Cari soal / kata kunci..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="audit-input"
                style={{ width: "180px", padding: "6px 10px", fontSize: "12px" }}
              />
            </div>
          </div>

          <div className="audit-table-wrap">
            <table className="audit-table">
              <thead>
                <tr>
                  <th style={{ width: "36px" }} />
                  <th>No. Soal</th>
                  <th>Pertanyaan Ujian</th>
                  <th>Sumber yang Dipakai AI</th>
                  <th>Rincian Nilai</th>
                  <th>Nilai & Perubahan</th>
                  <th>Hasil</th>
                </tr>
              </thead>
              <tbody>
                {filteredItems.map((item) => {
                  const isExpanded = !!expandedRows[item.id];
                  return (
                    <React.Fragment key={item.id}>
                      <tr
                        onClick={() => toggleRowExpand(item.id)}
                        style={{ cursor: "pointer" }}
                      >
                        <td>
                          {isExpanded ? (
                            <CaretDownIcon size={15} weight="bold" />
                          ) : (
                            <CaretRightIcon size={15} weight="bold" />
                          )}
                        </td>
                        <td>
                          <div
                            className="font-mono-tabular"
                            style={{ fontWeight: 700, fontSize: "13px" }}
                          >
                            {item.id}
                          </div>
                          <span
                            className="font-mono-tabular"
                            style={{
                              display: "inline-block",
                              marginTop: "3px",
                              padding: "1px 6px",
                              borderRadius: "4px",
                              fontSize: "11px",
                              background: "var(--audit-surface-elevated)",
                              border: "1px solid var(--audit-border-strong)",
                            }}
                          >
                            {item.domain}
                          </span>
                        </td>
                        <td style={{ maxWidth: "420px" }}>
                          <div style={{ fontWeight: 600, marginBottom: "4px" }}>
                            {item.pertanyaan}
                          </div>
                          <div
                            style={{
                              fontSize: "11.5px",
                              color: "var(--audit-text-muted)",
                            }}
                          >
                            Acuan: {item.referensi_regulasi}
                          </div>
                        </td>
                        <td>
                          <div
                            style={{
                              display: "flex",
                              flexWrap: "wrap",
                              gap: "5px",
                            }}
                          >
                            {item.retrieved_sources.map((src) => (
                              <button
                                key={src.chunk_id}
                                type="button"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  setExpandedRows((prev) => ({
                                    ...prev,
                                    [item.id]: true,
                                  }));
                                }}
                                className="audit-source-pill font-mono-tabular"
                                title={`${src.doc_name} (Sim: ${src.similarity}%)`}
                              >
                                <SourceIcon sourceType={src.source_type} />
                                <span>{SOURCE_TYPE_LABELS[src.source_type]}</span>
                                <span
                                  style={{ color: "var(--audit-text-muted)" }}
                                >
                                  {src.similarity}%
                                </span>
                              </button>
                            ))}
                          </div>
                        </td>
                        <td className="font-mono-tabular">
                          <div style={{ fontSize: "11.5px" }}>
                            Kemiripan: {item.cosine_similarity_pct.toFixed(1)}%
                          </div>
                          <div style={{ fontSize: "11.5px" }}>
                            Poin Kunci: {item.keyword_hit_ratio_pct.toFixed(1)}% (
                            {item.matched_keywords.length}/
                            {item.matched_keywords.length +
                              item.missing_keywords.length}
                            )
                          </div>
                          <div
                            style={{
                              fontSize: "11.5px",
                              color: "var(--audit-text-muted)",
                            }}
                          >
                            Patuh Sumber: {item.faithfulness_pct.toFixed(1)}%
                          </div>
                        </td>
                        <td className="font-mono-tabular">
                          <div
                            style={{
                              fontSize: "14px",
                              fontWeight: 700,
                              marginBottom: "4px",
                            }}
                          >
                            {item.current_score.toFixed(2)}%
                          </div>
                          <DeltaPill delta={item.score_delta} />
                        </td>
                        <td>
                          <StatusBadge
                            status={item.status}
                            score={item.current_score}
                          />
                        </td>
                      </tr>

                      {isExpanded && (
                        <tr>
                          <td
                            colSpan={7}
                            style={{
                              background: "var(--audit-bg)",
                              padding: "16px 20px",
                            }}
                          >
                            <div
                              style={{
                                display: "flex",
                                flexDirection: "column",
                                gap: "14px",
                              }}
                            >
                              <div
                                style={{
                                  display: "flex",
                                  alignItems: "center",
                                  justifyContent: "space-between",
                                  flexWrap: "wrap",
                                  gap: "8px",
                                  padding: "8px 12px",
                                  borderRadius: "6px",
                                  background: "var(--audit-surface)",
                                  border: "1px solid var(--audit-border)",
                                  fontSize: "12px",
                                }}
                              >
                                <div
                                  style={{
                                    display: "flex",
                                    alignItems: "center",
                                    gap: "8px",
                                  }}
                                >
                                  <GitDiffIcon
                                    size={16}
                                    weight="bold"
                                    color="#1d4ed8"
                                  />
                                  <span style={{ fontWeight: 600 }}>
                                    Perbandingan Jawaban Sebelum vs Sesudah Dilatih
                                  </span>
                                </div>
                                <div
                                  className="font-mono-tabular"
                                  style={{
                                    color: "var(--audit-text-secondary)",
                                  }}
                                >
                                  Materi Terakhir Ditambahkan:{" "}
                                  {item.ingested_source_meta.doc_name} (
                                  {item.ingested_source_meta.source_type}) oleh{" "}
                                  {item.ingested_source_meta.contributor}
                                </div>
                              </div>

                              <div className="audit-diff-grid">
                                <div
                                  style={{
                                    background: "var(--audit-surface)",
                                    border: "1px solid var(--audit-border)",
                                    borderRadius: "8px",
                                    padding: "12px 14px",
                                  }}
                                >
                                  <div
                                    style={{
                                      display: "flex",
                                      justifyContent: "space-between",
                                      marginBottom: "6px",
                                      fontSize: "11.5px",
                                      fontWeight: 700,
                                      color: "var(--audit-text-secondary)",
                                    }}
                                  >
                                    <span>JAWABAN AI SEBELUM DILATIH</span>
                                    <span className="font-mono-tabular">
                                      Skor: {item.previous_score.toFixed(2)}%
                                    </span>
                                  </div>
                                  <p
                                    style={{
                                      fontSize: "12.5px",
                                      lineHeight: 1.55,
                                      color: "var(--audit-text-secondary)",
                                      whiteSpace: "pre-wrap",
                                    }}
                                  >
                                    {item.previous_answer}
                                  </p>
                                </div>

                                <div
                                  style={{
                                    background: "var(--audit-surface)",
                                    border: "1px solid #1d4ed8",
                                    borderRadius: "8px",
                                    padding: "12px 14px",
                                  }}
                                >
                                  <div
                                    style={{
                                      display: "flex",
                                      justifyContent: "space-between",
                                      marginBottom: "6px",
                                      fontSize: "11.5px",
                                      fontWeight: 700,
                                      color: "#1d4ed8",
                                    }}
                                  >
                                    <span>JAWABAN AI SESUDAH DILATIH</span>
                                    <span className="font-mono-tabular">
                                      Skor: {item.current_score.toFixed(2)}% (
                                      {item.score_delta >= 0 ? "+" : ""}
                                      {item.score_delta.toFixed(2)}%)
                                    </span>
                                  </div>
                                  <p
                                    style={{
                                      fontSize: "12.5px",
                                      lineHeight: 1.55,
                                      whiteSpace: "pre-wrap",
                                    }}
                                  >
                                    {item.current_answer}
                                  </p>
                                </div>
                              </div>

                              <div
                                style={{
                                  background: "var(--audit-surface)",
                                  border: "1px solid var(--audit-border)",
                                  borderRadius: "8px",
                                  padding: "12px 14px",
                                  fontSize: "12.5px",
                                }}
                              >
                                <div
                                  style={{
                                    fontWeight: 700,
                                    fontSize: "11.5px",
                                    color: "var(--audit-text-secondary)",
                                    marginBottom: "4px",
                                  }}
                                >
                                  KUNCI JAWABAN RESMI:
                                </div>
                                <p style={{ marginBottom: "8px" }}>
                                  {item.kunci_jawaban}
                                </p>
                                <div
                                  style={{
                                    display: "flex",
                                    flexWrap: "wrap",
                                    gap: "6px",
                                    alignItems: "center",
                                  }}
                                >
                                  <span
                                    style={{
                                      fontSize: "11.5px",
                                      color: "var(--audit-text-muted)",
                                    }}
                                  >
                                    Poin Wajib Disebut:
                                  </span>
                                  {item.matched_keywords.map((kw) => (
                                    <span
                                      key={kw}
                                      className="audit-badge audit-badge-pass font-mono-tabular"
                                      style={{ fontSize: "11px" }}
                                    >
                                      ADA: {kw}
                                    </span>
                                  ))}
                                  {item.missing_keywords.map((kw) => (
                                    <span
                                      key={kw}
                                      className="audit-badge audit-badge-fail font-mono-tabular"
                                      style={{ fontSize: "11px" }}
                                    >
                                      TIDAK ADA: {kw}
                                    </span>
                                  ))}
                                </div>
                              </div>

                              <div
                                style={{
                                  display: "grid",
                                  gridTemplateColumns:
                                    "repeat(auto-fit, minmax(260px, 1fr))",
                                  gap: "10px",
                                }}
                              >
                                {item.retrieved_sources.map((chunk) => (
                                  <div
                                    key={chunk.chunk_id}
                                    style={{
                                      background: "var(--audit-surface)",
                                      border: "1px solid var(--audit-border)",
                                      borderRadius: "7px",
                                      padding: "10px 12px",
                                      fontSize: "12px",
                                    }}
                                  >
                                    <div
                                      style={{
                                        display: "flex",
                                        alignItems: "center",
                                        justifyContent: "space-between",
                                        marginBottom: "4px",
                                      }}
                                    >
                                      <span
                                        className="font-mono-tabular"
                                        style={{
                                          display: "inline-flex",
                                          alignItems: "center",
                                          gap: "5px",
                                          fontWeight: 700,
                                        }}
                                      >
                                        <SourceIcon
                                          sourceType={chunk.source_type}
                                        />
                                        {chunk.source_type}
                                      </span>
                                      <span
                                        className="font-mono-tabular"
                                        style={{
                                          color: "#059669",
                                          fontWeight: 700,
                                        }}
                                      >
                                        Sim: {chunk.similarity}% (dist:{" "}
                                        {chunk.cosine_distance})
                                      </span>
                                    </div>
                                    <div
                                      style={{
                                        fontWeight: 600,
                                        marginBottom: "4px",
                                        color: "var(--audit-text-secondary)",
                                      }}
                                    >
                                      {chunk.doc_name}
                                    </div>
                                    <div
                                      style={{
                                        fontSize: "11.5px",
                                        color: "var(--audit-text-muted)",
                                        lineHeight: 1.45,
                                      }}
                                    >
                                      {chunk.excerpt}
                                    </div>
                                  </div>
                                ))}
                              </div>
                            </div>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </div>
  );
}
