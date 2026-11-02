"use client";

import { apiFetch } from "@/lib/api";

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ArrowsClockwiseIcon } from "@phosphor-icons/react/dist/csr/ArrowsClockwise";
import { BrainIcon } from "@phosphor-icons/react/dist/csr/Brain";
import { CaretDownIcon } from "@phosphor-icons/react/dist/csr/CaretDown";
import { CaretRightIcon } from "@phosphor-icons/react/dist/csr/CaretRight";
import { CheckCircleIcon } from "@phosphor-icons/react/dist/csr/CheckCircle";
import { DatabaseIcon } from "@phosphor-icons/react/dist/csr/Database";
import { FilePdfIcon } from "@phosphor-icons/react/dist/csr/FilePdf";
import { FileXlsIcon } from "@phosphor-icons/react/dist/csr/FileXls";
import { MoonIcon } from "@phosphor-icons/react/dist/csr/Moon";
import { PlayIcon } from "@phosphor-icons/react/dist/csr/Play";
import { ShieldCheckIcon } from "@phosphor-icons/react/dist/csr/ShieldCheck";
import { SlidersHorizontalIcon } from "@phosphor-icons/react/dist/csr/SlidersHorizontal";
import { SunIcon } from "@phosphor-icons/react/dist/csr/Sun";
import { UploadSimpleIcon } from "@phosphor-icons/react/dist/csr/UploadSimple";
import { WarningIcon } from "@phosphor-icons/react/dist/csr/Warning";
import { XCircleIcon } from "@phosphor-icons/react/dist/csr/XCircle";

import { ArrowUpRightIcon } from "@phosphor-icons/react/dist/csr/ArrowUpRight";
import { ArrowLeftIcon } from "@phosphor-icons/react/dist/csr/ArrowLeft";
import { SquaresFourIcon } from "@phosphor-icons/react/dist/csr/SquaresFour";
import { FoldersIcon } from "@phosphor-icons/react/dist/csr/Folders";
import { ClockCounterClockwiseIcon } from "@phosphor-icons/react/dist/csr/ClockCounterClockwise";
import { PlusIcon } from "@phosphor-icons/react/dist/csr/Plus";
import "@/app/dashboard.css";
import SourceReviewPanel from "@/components/SourceReviewPanel";
import ChunkDetailPanel from "@/components/ChunkDetailPanel";
import KnowledgeNeuralMap from "@/components/KnowledgeNeuralMap";

import type {
  DashboardTelemetryState,
  GoldenAuditItem,
  LearnReasoningInput,
  RagSourceType,
  TaxDomainCode,
} from "@/types/audit";



const TAX_DOMAINS: TaxDomainCode[] = [
  "PBB-P2",
  "JPB",
  "PBJT",
  "BPHTB",
  "REKLAME",
  "PAT",
];

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
  pdf_regulasi: "Dokumen PDF",
  excel_data: "Tabel Excel/CSV",
  user_reasoning: "Kasus Rujukan",
};

function DeltaPill({ delta }: { delta: number }) {
  return <span className={`jst-delta ${delta > 0 ? "is-positive" : delta < 0 ? "is-negative" : ""}`} title="Perubahan dalam poin persentase" aria-label={`${delta >= 0 ? "Plus" : "Minus"} ${Math.abs(delta).toFixed(2)} poin persentase`}>{delta > 0 ? "+" : ""}{delta.toFixed(2)} pp</span>;
}

export default function IntelligenceAuditDashboard({
  onBackToChat,
}: {
  onBackToChat?: () => void;
}) {
  const [surfaceTheme, setSurfaceTheme] = useState<"dark" | "light">("dark");
  const [page, setPage] = useState<"overview" | "sources" | "evaluation" | "history" | "system">("overview");
  const [chunksOpen, setChunksOpen] = useState(false);
  const firstPageRender = useRef(true);
  useEffect(() => {
    if (page !== "sources") { setPdfFile(null); setExcelFile(null); }
    if (firstPageRender.current) { firstPageRender.current = false; return; }
    document.querySelector<HTMLHeadingElement>(".jst-page-header h1")?.focus();
  }, [page]);
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
  const [pdfContributor, setPdfContributor] = useState<string>("");

  const [excelFile, setExcelFile] = useState<File | null>(null);
  const [excelDomain, setExcelDomain] = useState<TaxDomainCode>("REKLAME");
  const [excelContributor, setExcelContributor] = useState<string>("");

  const [reasoningForm, setReasoningForm] = useState<LearnReasoningInput>({ topik_pajak: "JPB", kontributor: "", pertanyaan_kasus: "", alur_penalaran: "", jawaban_final: "" });

  const [domainFilter, setDomainFilter] = useState<string>("ALL");
  const [statusFilter, setStatusFilter] = useState<string>("ALL");
  const [sourceFilter, setSourceFilter] = useState<string>("ALL");
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [expandedRows, setExpandedRows] = useState<Record<string, boolean>>({});

  const fetchTelemetry = useCallback(async () => {
    try {
      const resp = await apiFetch(`/api/rag/telemetry`);
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
      const resp = await apiFetch(`/api/rag/evaluate`, {
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
      window.dispatchEvent(new Event("jst-source-uploaded"));
      setStatusBanner({
        type: "success",
        text: `Evaluasi Golden Dataset selesai. Skor evaluasi RAG: ${res.snapshot.smarttax_iq_percentage.toFixed(
          2
        )}% (Delta: ${res.snapshot.delta_change >= 0 ? "+" : ""}${res.snapshot.delta_change.toFixed(
          2
        )} pp).`,
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

  async function handlePdfSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!pdfFile || isIngesting || isEvaluating) return;
    const submittedForm = e.currentTarget;
    setIsIngesting(true);
    setStatusBanner(null);
    try {
      const formData = new FormData();
      formData.append("file", pdfFile);
      formData.append("domain", pdfDomain);
      formData.append("kontributor", pdfContributor);

      const resp = await apiFetch(`/api/rag/ingest-pdf`, {
        method: "POST",
        body: formData,
      });
      if (!resp.ok) {
        const errData = await resp.json().catch(() => ({}));
        throw new Error(errData.detail || `HTTP ${resp.status}`);
      }
      const res = await resp.json();
      setData(res.dashboard);
      window.dispatchEvent(new Event("jst-source-uploaded"));
      setPdfFile(null);
      submittedForm.reset();
      setStatusBanner({
        type: "success",
        text: `PDF "${res.ingestion.doc_name}" aktif (${res.ingestion.chunks_ingested} bagian teks). File asli dan halaman sumber tersimpan.`,
      });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setStatusBanner({ type: "error", text: `Ingesti PDF gagal: ${msg}` });
    } finally {
      window.dispatchEvent(new Event("jst-source-uploaded"));
      setIsIngesting(false);
    }
  }

  async function handleExcelSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!excelFile || isIngesting || isEvaluating) return;
    const submittedForm = e.currentTarget;
    setIsIngesting(true);
    setStatusBanner(null);
    try {
      const formData = new FormData();
      formData.append("file", excelFile);
      formData.append("category", excelDomain);
      formData.append("kontributor", excelContributor);

      const resp = await apiFetch(`/api/rag/ingest-excel`, {
        method: "POST",
        body: formData,
      });
      if (!resp.ok) {
        const errData = await resp.json().catch(() => ({}));
        throw new Error(errData.detail || `HTTP ${resp.status}`);
      }
      const res = await resp.json();
      setData(res.dashboard);
      window.dispatchEvent(new Event("jst-source-uploaded"));
      setExcelFile(null);
      submittedForm.reset();
      setStatusBanner({
        type: "success",
        text: `Tabel "${res.ingestion.doc_name}" aktif (${res.ingestion.rows_ingested} baris).`,
      });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setStatusBanner({
        type: "error",
        text: `Ingesti Excel/CSV gagal: ${msg}`,
      });
    } finally {
      window.dispatchEvent(new Event("jst-source-uploaded"));
      setIsIngesting(false);
    }
  }

  async function handleReasoningSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (isIngesting) return;
    setIsIngesting(true);
    setStatusBanner(null);
    try {
      const resp = await apiFetch(`/api/rag/learn-reasoning`, {
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
      window.dispatchEvent(new Event("jst-source-uploaded"));
      setStatusBanner({
        type: "success",
        text: `Kasus rujukan ${res.ingestion.domain} aktif dan siap menjadi rujukan chatbot.`,
      });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setStatusBanner({
        type: "error",
        text: `Injeksi penalaran gagal: ${msg}`,
      });
    } finally {
      window.dispatchEvent(new Event("jst-source-uploaded"));
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

  const hw = data?.hardware;
  const vs = data?.vector_store;
  const snap = data?.latest_snapshot;
  const timeline = data?.history_timeline || [];
  const busy = isEvaluating || isIngesting || !data;
  const missingDomains = TAX_DOMAINS.map(domain => ({ domain, missing: (Object.keys(SOURCE_TYPE_LABELS) as RagSourceType[]).filter(key => !((vs?.domain_matrix?.[domain]?.[key] ?? 0) > 0)) })).filter(item => item.missing.length);
  const titles = { overview: "Dashboard Utama", sources: "Sumber data", evaluation: "Hasil evaluasi", history: "Riwayat evaluasi", system: "Pengaturan model" };
  const descriptions = { overview: "Lihat sumber data yang tersedia dan hasil evaluasi chatbot.", sources: "Kelola dokumen, tabel, dan kasus yang menjadi rujukan chatbot.", evaluation: "Periksa hasil per soal, perubahan skor, dan sumber yang mendasari jawaban.", history: "Bandingkan hasil evaluasi setelah sumber data diperbarui.", system: "Koneksi model lokal, konfigurasi pencarian, dan kesiapan layanan training." };
  const formatDate = (value?: string) => value ? new Date(value).toLocaleString("id-ID", { timeZone: "Asia/Jakarta", day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" }) + " WIB" : "Belum ada evaluasi";
  const pct = (value?: number | null) => value == null ? "—" : value.toFixed(1);
  function chooseSourceTab(source: RagSourceType) { setPdfFile(null); setExcelFile(null); setActiveStudioTab(source); }
  function openSource(domain?: TaxDomainCode) { if (domain) { setPdfDomain(domain); setExcelDomain(domain); } chooseSourceTab("pdf_regulasi"); setPage("sources"); }

  const coverageTable = <div className="jst-table-scroll"><table className="jst-table jst-coverage-table"><caption className="jst-sr-only">Ketersediaan sumber per kategori pajak</caption><thead><tr><th>Pajak</th><th>PDF</th><th>Tabel</th><th>Kasus</th><th>Cakupan</th></tr></thead><tbody>{TAX_DOMAINS.map(domain => {
    const row = vs?.domain_matrix?.[domain];
    const filled = (Object.keys(SOURCE_TYPE_LABELS) as RagSourceType[]).filter(key => (row?.[key] ?? 0) > 0).length;
    return <tr key={domain}><th scope="row">{domain}</th>{(["pdf_regulasi", "excel_data", "user_reasoning"] as RagSourceType[]).map(key => <td key={key} className={row?.[key] ? "" : "jst-empty-cell"}>{row?.[key] ?? (data ? 0 : "—")}</td>)}<td><span className="jst-coverage-dots" aria-label={`${filled} dari 3 jenis sumber tersedia`}>{[0, 1, 2].map(i => <i key={i} className={i < filled ? "is-filled" : ""} />)}</span></td></tr>;
  })}</tbody></table></div>;

  const scorePanel = <aside className="jst-score-panel" aria-label="Hasil evaluasi terakhir">
    <div className="jst-section-kicker">EVALUASI TERAKHIR <span>01</span></div>
    <div className="jst-main-score">{pct(snap?.smarttax_iq_percentage)}<span>/100</span></div>
    <div className="jst-score-caption"><strong>Skor evaluasi RAG</strong>{snap && <DeltaPill delta={snap.delta_change} />}</div>
    <p className="jst-note">{snap ? "Skor ini mengukur kecocokan teks dengan sumber. Belum menilai jawaban langsung dari model." : "Belum ada evaluasi. Skor akan tersedia setelah sumber dan dataset uji resmi siap."}</p>
    <div className="jst-score-rule"><span style={{ width: `${Math.min(100, Math.max(0, snap?.smarttax_iq_percentage ?? 0))}%` }} /><i /></div>
    <div className="jst-threshold">Ambang internal <strong>75 / 100</strong></div>
    <dl className="jst-metric-ledger">
      <div><dt>Rubrik soal <small>40%</small></dt><dd>{pct(snap?.golden_eval_accuracy)}<small>%</small></dd></div>
      <div><dt>Kemiripan sumber <small>25%</small></dt><dd>{pct(snap?.faithfulness_score)}<small>%</small></dd></div>
      <div><dt>Kemiripan pencarian <small>20%</small></dt><dd>{pct(snap?.retrieval_precision)}<small>%</small></dd></div>
      <div><dt>Kelengkapan sumber <small>15%</small></dt><dd>{pct(snap?.domain_coverage)}<small>%</small></dd></div>
    </dl>
    <button className="jst-text-button" onClick={() => setPage("evaluation")}>Lihat hasil per soal <ArrowUpRightIcon size={16} /></button>
  </aside>;

  return <div className="jst-workspace" data-jst-theme={surfaceTheme}>
    {chunksOpen && <ChunkDetailPanel onClose={() => setChunksOpen(false)} />}
    <a href="#jst-main" className="jst-skip-link">Lewati ke isi dashboard</a>
    <aside className="jst-sidebar">
      <div className="jst-brand"><span className="jst-monogram">ST</span><div>Jakarta SmartTax<small>PENGELOLAAN CHATBOT</small></div></div>
      <div className="jst-sidebar-label">ADMINISTRASI</div>
      <nav aria-label="Navigasi dashboard">{([
        ["overview", "Ringkasan", SquaresFourIcon], ["sources", "Sumber data", FoldersIcon], ["evaluation", "Evaluasi", ShieldCheckIcon], ["history", "Riwayat", ClockCounterClockwiseIcon], ["system", "Pengaturan", SlidersHorizontalIcon],
      ] as const).map(([key, label, Icon]) => <button key={key} onClick={() => setPage(key)} aria-current={page === key ? "page" : undefined}><Icon size={19} weight={page === key ? "fill" : "regular"} /><span>{label}</span>{key === "sources" && <small>{vs?.total_chunks ?? "—"}</small>}</button>)}</nav>
      <div className="jst-sidebar-bottom"><div className="jst-model-status"><i className={hw?.ollama_online ? "is-online" : ""} /><div>{hw?.primary_llm || "Model lokal"}<small>{!data ? "Status belum tersedia" : hw?.ollama_online ? "Ollama terhubung" : "Ollama tidak terhubung"}</small></div></div>{onBackToChat && <button className="jst-chat-link" onClick={onBackToChat}><ArrowLeftIcon size={16} /> Buka ruang chat <ArrowUpRightIcon size={16} /></button>}</div>
    </aside>
    <div className="jst-content-scroll" key={page}>
      <div className="jst-topbar"><span>Jakarta SmartTax <span className="jst-breadcrumb-separator">/</span> <strong>{page === "overview" ? "Ringkasan" : page === "sources" ? "Sumber data" : page === "evaluation" ? "Evaluasi" : page === "history" ? "Riwayat" : "Pengaturan"}</strong></span><div className="jst-topbar-actions">{onBackToChat && <button className="jst-mobile-chat" onClick={onBackToChat} aria-label="Buka ruang chat"><ArrowUpRightIcon size={16} /><span>Chat</span></button>}<button className="jst-theme-button" onClick={() => setSurfaceTheme(theme => theme === "light" ? "dark" : "light")} aria-label={surfaceTheme === "light" ? "Aktifkan mode gelap" : "Aktifkan mode terang"}>{surfaceTheme === "light" ? <MoonIcon size={17} /> : <SunIcon size={17} />}</button></div></div>
      <main id="jst-main" className="jst-main" tabIndex={-1}>
        <header className="jst-page-header"><div><div className="jst-eyebrow">JAKARTA SMARTTAX / DASHBOARD</div><h1 tabIndex={-1}>{titles[page]}</h1><p>{descriptions[page]}</p></div><button className="jst-button jst-button-primary" disabled={busy} title={data?.evaluation_readiness?.reason} onClick={handleRunBenchmark}>{isEvaluating ? <ArrowsClockwiseIcon size={17} className="jst-spin" /> : <PlayIcon size={17} weight="fill" />}{isEvaluating ? "Mengevaluasi…" : "Jalankan evaluasi"}</button></header>
        {statusBanner && <div className={`jst-notice ${statusBanner.type === "error" ? "is-error" : ""}`} role={statusBanner.type === "error" ? "alert" : "status"}><span>{statusBanner.type === "error" ? <WarningIcon size={18} /> : <CheckCircleIcon size={18} />}{statusBanner.text}</span><button onClick={() => setStatusBanner(null)} aria-label="Tutup pemberitahuan"><XCircleIcon size={19} /></button></div>}
        {loading && !data && <div className="jst-loading" role="status">Memuat sumber dan hasil evaluasi…</div>}
        {!loading && !data && <div className="jst-empty-state"><DatabaseIcon size={28} /><h2>Data dashboard belum tersedia</h2><p>Periksa koneksi backend lalu muat ulang data.</p><button className="jst-button" onClick={fetchTelemetry}>Coba lagi</button></div>}

        {data && vs?.total_chunks === 0 && <section className="jst-empty-data" aria-labelledby="empty-data-title"><DatabaseIcon size={24} /><div><h2 id="empty-data-title">Belum ada sumber yang siap digunakan</h2><p>Belum ada sumber data yang dapat digunakan chatbot.</p></div>{page !== "sources" && <button className="jst-button" onClick={() => openSource()}>Tambah sumber <PlusIcon size={15} /></button>}</section>}
        {data && !snap && <p className="jst-readiness-note">{data.evaluation_readiness.reason} Skor dan riwayat evaluasi belum tersedia.</p>}
        {page === "overview" && <>
          <section className="jst-summary-strip" aria-label="Ringkasan data"><div className="jst-text-summary"><div className="jst-text-summary-top"><strong>{vs?.total_chunks ?? "—"}</strong><span>Bagian teks<small>Dari {vs?.total_documents ?? "—"} sumber</small></span></div><p>Isi dibagi menjadi bagian kecil agar mudah dicari chatbot.</p><button className="jst-text-button" disabled={!vs} aria-haspopup="dialog" aria-expanded={chunksOpen} onClick={() => setChunksOpen(true)}>Lihat rincian <ArrowUpRightIcon size={14} /></button></div><div><strong>{vs ? `${vs.covered_slots}/${vs.total_slots}` : "—"}</strong><span>Jenis sumber tersedia<small>6 pajak × 3 jenis sumber</small></span></div><div><strong>{snap ? `${statusCounts.pass}/${statusCounts.total}` : "—"}</strong><span>Soal yang memenuhi ambang<small>berdasarkan rubrik internal</small></span></div><div className="jst-last-eval"><span>Evaluasi terakhir<small>{formatDate(snap?.timestamp)}</small></span><ClockCounterClockwiseIcon size={20} /></div></section>
          <div className="jst-knowledge-grid"><KnowledgeNeuralMap telemetry={vs} />{scorePanel}</div>
          <div className="jst-bottom-grid"><section className="jst-section"><div className="jst-section-heading"><div><span className="jst-eyebrow">KETERSEDIAAN SUMBER</span><h2>Sumber per jenis pajak</h2></div><button className="jst-icon-button" aria-label="Buka sumber data" onClick={() => openSource()}><ArrowUpRightIcon size={20} /></button></div>{coverageTable}<p className="jst-note jst-table-note">Angka menunjukkan potongan sumber; titik menunjukkan jenis sumber yang tersedia.</p></section>
          <section className="jst-section"><div className="jst-section-heading"><div><span className="jst-eyebrow">CATATAN KERJA</span><h2>Yang perlu dilengkapi</h2></div><span className="jst-count">{vs ? missingDomains.length : "—"}</span></div>{!vs ? <p className="jst-note">Menunggu data sumber.</p> : missingDomains.length ? <div className="jst-attention-list">{missingDomains.map((item, index) => <button key={item.domain} onClick={() => openSource(item.domain)}><span className="jst-list-index">0{index + 1}</span><span><strong>{item.domain}</strong><small>Belum ada {item.missing.map(key => ({pdf_regulasi:"Dokumen PDF",excel_data:"tabel data",user_reasoning:"contoh kasus"}[key])).join(" & ")}</small></span><ArrowUpRightIcon size={18} /></button>)}</div> : <div className="jst-empty-state"><CheckCircleIcon size={28} /><p>Semua jenis sumber tersedia. Lanjutkan pemeriksaan kualitas melalui evaluasi.</p></div>}<div className="jst-training-note"><span className="jst-training-dot" /><div><strong>Fine tuning belum terhubung</strong><p>Dashboard ini memantau sumber dan evaluasi RAG. Progres training akan tersedia setelah layanan trainer terintegrasi.</p></div></div></section></div>
        </>}

        {page === "sources" && <>
          <div className="jst-source-layout"><section className="jst-section jst-source-editor"><div className="jst-section-heading"><div><span className="jst-eyebrow">01 / TAMBAH RUJUKAN</span><h2>Tambah sumber data</h2></div><UploadSimpleIcon size={23} /></div><div className="jst-source-tabs" role="tablist" aria-label="Jenis sumber">{(["pdf_regulasi", "excel_data", "user_reasoning"] as RagSourceType[]).map(key => <button key={key} role="tab" aria-selected={activeStudioTab === key} aria-controls="jst-source-panel" id={`jst-tab-${key}`} tabIndex={activeStudioTab === key ? 0 : -1} onKeyDown={e => { if (["ArrowRight", "ArrowLeft", "Home", "End"].includes(e.key)) { e.preventDefault(); const keys: RagSourceType[] = ["pdf_regulasi", "excel_data", "user_reasoning"]; const next = e.key === "Home" ? 0 : e.key === "End" ? 2 : (keys.indexOf(key) + (e.key === "ArrowRight" ? 1 : 2)) % 3; chooseSourceTab(keys[next]); document.getElementById(`jst-tab-${keys[next]}`)?.focus(); } }} onClick={() => chooseSourceTab(key)}><SourceIcon sourceType={key} size={17} />{key === "pdf_regulasi" ? "Dokumen PDF" : key === "excel_data" ? "Tabel data" : "Contoh kasus"}</button>)}</div>
            <div id="jst-source-panel" role="tabpanel" aria-labelledby={`jst-tab-${activeStudioTab}`}>
            {activeStudioTab !== "user_reasoning" ? <form onSubmit={activeStudioTab === "pdf_regulasi" ? handlePdfSubmit : handleExcelSubmit} className="jst-form" key={activeStudioTab}>
              <div className="jst-form-row"><label htmlFor="source-domain">Kategori pajak<select id="source-domain" value={activeStudioTab === "pdf_regulasi" ? pdfDomain : excelDomain} onChange={e => activeStudioTab === "pdf_regulasi" ? setPdfDomain(e.target.value as TaxDomainCode) : setExcelDomain(e.target.value as TaxDomainCode)}>{TAX_DOMAINS.map(domain => <option key={domain}>{domain}</option>)}</select></label><label htmlFor="source-contributor">Kontributor / unit kerja<input required id="source-contributor" value={activeStudioTab === "pdf_regulasi" ? pdfContributor : excelContributor} onChange={e => activeStudioTab === "pdf_regulasi" ? setPdfContributor(e.target.value) : setExcelContributor(e.target.value)} /></label></div>
              <label className="jst-upload-field" htmlFor="source-file"><UploadSimpleIcon size={30} weight="light" /><strong>{activeStudioTab === "pdf_regulasi" ? "Pilih dokumen PDF" : "Pilih tabel data pajak"}</strong><span>{activeStudioTab === "pdf_regulasi" ? "PDF · Dokumen rujukan proyek" : "XLSX / XLS / CSV · Tarif, ketetapan, atau rekapitulasi"}</span><input required id="source-file" type="file" accept={activeStudioTab === "pdf_regulasi" ? ".pdf" : ".xlsx,.xls,.csv"} onChange={e => activeStudioTab === "pdf_regulasi" ? setPdfFile(e.target.files?.[0] ?? null) : setExcelFile(e.target.files?.[0] ?? null)} /></label>
              <p className="jst-note">File asli disimpan. Sumber langsung aktif setelah lolos pemeriksaan teknis dan berhasil diindeks.</p><div className="jst-form-actions"><button className="jst-button jst-button-primary" disabled={busy || !(activeStudioTab === "pdf_regulasi" ? pdfFile : excelFile)} type="submit"><PlusIcon size={17} />{isIngesting ? "Memproses sumber…" : "Unggah dan proses"}</button></div>
            </form> : <form className="jst-form" onSubmit={handleReasoningSubmit}><div className="jst-form-row"><label htmlFor="case-domain">Kategori pajak<select id="case-domain" value={reasoningForm.topik_pajak} onChange={e => setReasoningForm(form => ({...form,topik_pajak:e.target.value as TaxDomainCode}))}>{TAX_DOMAINS.map(domain => <option key={domain}>{domain}</option>)}</select></label><label htmlFor="case-contributor">Kontributor / unit kerja<input required id="case-contributor" value={reasoningForm.kontributor} onChange={e => setReasoningForm(form => ({...form,kontributor:e.target.value}))} /></label></div>{([ ["pertanyaan_kasus", "Pertanyaan kasus"], ["alur_penalaran", "Penjelasan & dasar rujukan"], ["jawaban_final", "Jawaban yang diharapkan"] ] as const).map(([key,label]) => <label key={key} htmlFor={`case-${key}`}>{label}<textarea id={`case-${key}`} required rows={key === "alur_penalaran" ? 5 : 3} value={reasoningForm[key]} onChange={e => setReasoningForm(form => ({...form,[key]:e.target.value}))} /></label>)}<p className="jst-note">Contoh kasus langsung diindeks sebagai rujukan chatbot. Proses ini belum mengubah bobot model.</p><button className="jst-button jst-button-primary" disabled={busy} type="submit"><PlusIcon size={17} />{isIngesting ? "Menyimpan…" : "Unggah dan proses"}</button></form>}
            </div>
          </section><aside className="jst-section"><span className="jst-eyebrow">02 / CAKUPAN</span><h2 className="jst-aside-title">Sumber yang tersedia</h2>{coverageTable}<p className="jst-note jst-table-note">{vs?.total_chunks ?? "—"} potongan sumber dalam koleksi {vs?.collection || "—"}.</p></aside></div>
          <SourceReviewPanel onReviewed={() => { void fetchTelemetry(); }} />
          <section className="jst-section"><div className="jst-section-heading"><div><span className="jst-eyebrow">ARSIP MASUK</span><h2>Sumber terbaru</h2></div><span className="jst-count">{vs?.recent_sources.length ?? "—"}</span></div>{vs?.recent_sources.length ? <div className="jst-source-list">{vs.recent_sources.map((source,i) => <div key={`${source.doc_name}-${source.ingested_at}-${i}`}><span className="jst-file-icon"><SourceIcon sourceType={source.source_type} size={23} /></span><span><strong>{source.doc_name}</strong><small>{source.domain} · {source.contributor}</small></span><time>{formatDate(source.ingested_at)}</time></div>)}</div> : <p className="jst-note">Belum ada sumber yang tercatat.</p>}</section>
        </>}

        {page === "evaluation" && <>
          <div className="jst-evaluation-intro"><div><span className="jst-eyebrow">DATASET UJI</span><h2>{snap ? `${statusCounts.total} soal untuk memeriksa pengetahuan.` : data?.evaluation_readiness.golden_items ? "Dataset uji belum dievaluasi." : "Dataset uji resmi belum tersedia."}</h2><p className="jst-note">{snap ? "Evaluasi menggunakan jawaban yang disusun dari korpus. Kemiripan sumber tidak membuktikan kebenaran hukum." : "Siapkan sumber, soal, dan jawaban acuan resmi sebelum menjalankan evaluasi."}</p></div>{snap && <div className="jst-result-counts"><span><i className="is-pass" />{statusCounts.pass} lulus</span><span><i className="is-partial" />{statusCounts.partial} cukup</span><span><i className="is-fail" />{statusCounts.fail} belum lulus</span></div>}</div>
          <section className="jst-section"><div className="jst-filters"><label className="jst-sr-only" htmlFor="filter-domain">Filter kategori pajak</label><select id="filter-domain" value={domainFilter} onChange={e => setDomainFilter(e.target.value)}><option value="ALL">Semua pajak</option>{TAX_DOMAINS.map(domain => <option key={domain}>{domain}</option>)}</select><label className="jst-sr-only" htmlFor="filter-status">Filter hasil</label><select id="filter-status" value={statusFilter} onChange={e => setStatusFilter(e.target.value)}><option value="ALL">Semua hasil</option><option value="PASS">Lulus (≥75)</option><option value="PARTIAL">Cukup (60–74)</option><option value="FAIL">Belum lulus (&lt;60)</option></select><label className="jst-sr-only" htmlFor="filter-source">Filter sumber</label><select id="filter-source" value={sourceFilter} onChange={e => setSourceFilter(e.target.value)}><option value="ALL">Semua sumber</option>{(Object.keys(SOURCE_TYPE_LABELS) as RagSourceType[]).map(key => <option key={key} value={key}>{SOURCE_TYPE_LABELS[key]}</option>)}</select><label className="jst-sr-only" htmlFor="filter-search">Cari soal atau kata kunci</label><input id="filter-search" value={searchQuery} onChange={e => setSearchQuery(e.target.value)} placeholder="Cari soal atau kata kunci…" /></div>
            <div className="jst-evidence-list">{filteredItems.map(item => <article key={item.id} className={`jst-evidence-item ${expandedRows[item.id] ? "is-open" : ""}`}><button className="jst-evidence-toggle" onClick={() => toggleRowExpand(item.id)} aria-expanded={!!expandedRows[item.id]} aria-controls={`evidence-${item.id}`}><span className="jst-question-id">{item.id}<small>{item.domain}</small></span><span className="jst-question-text">{item.pertanyaan}</span><span className="jst-evidence-score">{item.current_score.toFixed(1)}<small>/100</small></span><span className={`jst-status-label is-${item.status.toLowerCase()}`}>{item.status === "PASS" ? "Lulus" : item.status === "PARTIAL" ? "Cukup" : "Belum lulus"}</span>{expandedRows[item.id] ? <CaretDownIcon size={17} /> : <CaretRightIcon size={17} />}</button>
              {expandedRows[item.id] && <div id={`evidence-${item.id}`} className="jst-evidence-detail"><p className="jst-reference"><strong>Acuan dataset</strong> {item.referensi_regulasi}</p><div className="jst-answer-comparison"><div><span className="jst-eyebrow">SEBELUM PENAMBAHAN SUMBER · {item.previous_score.toFixed(1)}</span><p>{item.previous_answer}</p></div><div><span className="jst-eyebrow">SETELAH PENAMBAHAN SUMBER · {item.current_score.toFixed(1)}</span><p>{item.current_answer}</p></div></div><div className="jst-reference-answer"><span className="jst-eyebrow">JAWABAN ACUAN DATASET</span><p>{item.kunci_jawaban}</p></div><dl className="jst-item-metrics"><div><dt>Kemiripan teks</dt><dd>{item.cosine_similarity_pct.toFixed(1)}%</dd></div><div><dt>Poin kunci</dt><dd>{item.keyword_hit_ratio_pct.toFixed(1)}%</dd></div><div><dt>Kemiripan sumber</dt><dd>{item.faithfulness_pct.toFixed(1)}%</dd></div><div><dt>Perubahan</dt><dd><DeltaPill delta={item.score_delta} /></dd></div></dl><p className="jst-note">Poin belum ditemukan: {item.missing_keywords.length ? item.missing_keywords.join(" · ") : "Seluruh poin kunci ditemukan."}</p><details className="jst-citations"><summary>{item.retrieved_sources.length} sumber rujukan</summary>{item.retrieved_sources.map((source,i) => <div key={`${source.chunk_id}-${i}`}><SourceIcon sourceType={source.source_type} size={18} /><div><strong>{source.doc_name}</strong><small>{source.domain} · Kemiripan {source.similarity.toFixed(1)}%</small><p>{source.excerpt}</p></div></div>)}</details></div>}
            </article>)}{!filteredItems.length && <div className="jst-empty-state"><ShieldCheckIcon size={28} /><h3>{snap ? "Tidak ada soal yang cocok" : "Belum ada hasil evaluasi"}</h3><p>{snap ? "Ubah filter atau kata kunci pencarian." : "Hasil per soal akan muncul setelah sumber dan dataset uji resmi tersedia."}</p></div>}</div>
          </section><p className="jst-note">Evaluasi terakhir: {formatDate(snap?.timestamp)}. Perubahan skor dinyatakan dalam poin persentase.</p>
        </>}

        {page === "history" && <><section className="jst-section"><div className="jst-section-heading"><div><span className="jst-eyebrow">RIWAYAT EVALUASI</span><h2>Hasil evaluasi dari waktu ke waktu</h2></div><span className="jst-count">{timeline.length} evaluasi</span></div><ScoreHistory points={timeline.map(point => ({id:point.snapshot_id,value:point.smarttax_iq_percentage,label:formatDate(point.timestamp)}))} /><p className="jst-note">Skor heuristik antar evaluasi; bukan kurva loss training model.</p></section><section className="jst-section"><div className="jst-table-scroll"><table className="jst-table jst-history-table"><caption className="jst-sr-only">Riwayat evaluasi RAG</caption><thead><tr><th>Waktu / WIB</th><th>Aktivitas</th><th>Sumber</th><th>Skor</th><th>Perubahan</th></tr></thead><tbody>{[...timeline].reverse().map(point => <tr key={point.snapshot_id}><td>{formatDate(point.timestamp)}</td><td>{point.trigger_event}</td><td>{point.total_chunks_indexed}</td><td><strong>{point.smarttax_iq_percentage.toFixed(2)}</strong></td><td><DeltaPill delta={point.delta_change} /></td></tr>)}</tbody></table></div>{!timeline.length && <p className="jst-note">Belum ada riwayat evaluasi.</p>}</section></>}

        {page === "system" && <><div className="jst-source-layout"><section className="jst-section"><span className="jst-eyebrow">MODEL LOKAL</span><h2 className="jst-aside-title">Koneksi & konfigurasi</h2><dl className="jst-system-ledger">{[["Model",hw?.primary_llm],["Status Ollama",!data ? "Belum tersedia" : hw?.ollama_online ? "Terhubung" : "Tidak terhubung"],["Embedding (konfigurasi)",hw?.embedding_model],["Context window",hw?.num_ctx?.toLocaleString("id-ID")],["GPU (konfigurasi)",hw?.gpu],["VRAM (konfigurasi)",hw?.vram_gb != null ? `${hw.vram_gb} GB` : undefined],["KV cache",hw?.kv_cache_type],["Flash attention",hw ? hw.flash_attention ? "Aktif" : "Nonaktif" : undefined],["Koleksi",vs?.collection],["Metrik jarak",vs?.distance_metric]].map(([label,value]) => <div key={label}><dt>{label}</dt><dd>{value || "—"}</dd></div>)}</dl><p className="jst-note">Informasi perangkat berasal dari konfigurasi backend. Ini bukan pengukuran penggunaan GPU secara langsung.</p></section><section className="jst-section jst-training-panel"><BrainIcon size={34} weight="light" /><span className="jst-eyebrow">TRAINING MODEL</span><h2>Belum terhubung.</h2><p>Penambahan sumber saat ini memperbarui basis pengetahuan RAG. Bobot model tetap sama.</p><ul><li>Progres step & epoch <span>Belum tersedia</span></li><li>Training & validation loss <span>Belum tersedia</span></li><li>Checkpoint & adapter <span>Belum tersedia</span></li></ul><p className="jst-note">Hubungkan layanan trainer untuk menampilkan proses fine tuning yang sebenarnya.</p></section></div></>}
        <footer className="jst-footer"><span>JST <i>/</i> Jakarta SmartTax</span><span>Sumber data dan evaluasi chatbot</span></footer>
      </main>
    </div>

  </div>;
}

function ScoreHistory({points}:{points:{id:string;value:number;label:string}[]}) {
  if (!points.length) return <div className="jst-empty-state">Belum ada evaluasi untuk ditampilkan.</div>;
  const width = 1000, height = 230;
  const coords = points.map((point,index) => ({...point,x:48 + index * 904 / Math.max(1, points.length-1),y:190 - Math.max(0,Math.min(100,point.value))*1.6}));
  return <div className="jst-history-graph"><svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`Riwayat ${points.length} evaluasi, skor terakhir ${points[points.length-1].value.toFixed(1)} dari 100. Rincian ada pada tabel di bawah.`}>{[0,25,50,75,100].map(value => <g key={value}><line x1="48" x2="952" y1={190-value*1.6} y2={190-value*1.6} className={value === 75 ? "jst-chart-threshold" : "jst-chart-grid"} /><text x="14" y={195-value*1.6}>{value}</text></g>)}<polyline points={coords.map(point=>`${point.x},${point.y}`).join(" ")} className="jst-chart-line" />{coords.map(point => <g key={point.id}><title>{point.label}: {point.value.toFixed(1)}</title><circle cx={point.x} cy={point.y} r="5" /><text x={point.x} y={point.y-13} textAnchor="middle">{point.value.toFixed(1)}</text></g>)}</svg></div>;
}
