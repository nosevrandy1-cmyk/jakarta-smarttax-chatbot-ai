"use client";

import { apiFetch, ApiRequestLimitError } from "@/lib/api";

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ArrowsClockwiseIcon } from "@phosphor-icons/react/dist/csr/ArrowsClockwise";
import { BrainIcon } from "@phosphor-icons/react/dist/csr/Brain";
import { CaretDownIcon } from "@phosphor-icons/react/dist/csr/CaretDown";
import { CaretRightIcon } from "@phosphor-icons/react/dist/csr/CaretRight";
import { CheckCircleIcon } from "@phosphor-icons/react/dist/csr/CheckCircle";
import { DatabaseIcon } from "@phosphor-icons/react/dist/csr/Database";
import { FileTextIcon } from "@phosphor-icons/react/dist/csr/FileText";
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
import { ListIcon } from "@phosphor-icons/react/dist/csr/List";
import OperationsPanel from "@/components/OperationsPanel";
import SourceProcessingNotice from "@/components/SourceProcessingNotice";
import MarkdownImport from "@/components/MarkdownImport";
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



type StudioSource = RagSourceType | "markdown";

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
  sourceType: StudioSource;
  size?: number;
}) {
  if (sourceType === "markdown") return <FileTextIcon size={size} weight="bold" />;
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
  const [navOpen, setNavOpen] = useState(false);
  const [surfaceTheme, setSurfaceTheme] = useState<"dark" | "light">("dark");
  const [page, setPage] = useState<"overview" | "sources" | "evaluation" | "history" | "system" | "health" | "logs" | "health" | "logs">("overview");
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
  const [sourceProcessing,setSourceProcessing]=useState(false);
  const [isIngesting, setIsIngesting] = useState<boolean>(false);
  const [statusBanner, setStatusBanner] = useState<{
    type: "success" | "error";
    text: string;
  } | null>(null);

  const [activeStudioTab, setActiveStudioTab] =
    useState<StudioSource>("pdf_regulasi");

  const [pdfFile, setPdfFile] = useState<File | null>(null);
  const [pdfDomain, setPdfDomain] = useState<TaxDomainCode>("PBB-P2");
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
      const resp = await apiFetch(`/api/rag/telemetry?include_details=${page === "evaluation"}`);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const json: DashboardTelemetryState = await resp.json();
      setData(json);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setStatusBanner({
        type: "error",
        text: err instanceof ApiRequestLimitError ? msg : `Data belum dapat dimuat. ${msg}`,
      });
    } finally {
      setLoading(false);
    }
  }, [page]);

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
    if (!pdfFile || isIngesting || sourceProcessing || isEvaluating) return;
    const submittedForm = e.currentTarget;
    window.dispatchEvent(new CustomEvent("jst-ingestion-start"));
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
      window.dispatchEvent(new Event("jst-ingestion-end"));
    }
  }

  async function handleExcelSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!excelFile || isIngesting || sourceProcessing || isEvaluating) return;
    const submittedForm = e.currentTarget;
    window.dispatchEvent(new CustomEvent("jst-ingestion-start"));
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
      window.dispatchEvent(new Event("jst-ingestion-end"));
    }
  }

  async function handleReasoningSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (isIngesting || sourceProcessing) return;
    window.dispatchEvent(new CustomEvent("jst-ingestion-start"));
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
      window.dispatchEvent(new Event("jst-ingestion-end"));
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
  const busy = isEvaluating || isIngesting || sourceProcessing || !data;
  const missingDomains = TAX_DOMAINS.map(domain => ({ domain, missing: (Object.keys(SOURCE_TYPE_LABELS) as RagSourceType[]).filter(key => !((vs?.domain_matrix?.[domain]?.[key] ?? 0) > 0)) })).filter(item => item.missing.length);
  const titles = { overview: "Ringkasan", sources: "Dokumen", evaluation: "Data & evaluasi", history: "Riwayat evaluasi", system: "Pengaturan", health: "Kesehatan sistem", logs: "Log sistem" };
  const descriptions = { overview: "Pantau layanan, aktivitas, dan kesiapan pengetahuan chatbot.", sources: "Kelola dokumen, tabel, dan kasus yang menjadi rujukan chatbot.", evaluation: "Periksa hasil per soal, perubahan skor, dan sumber yang mendasari jawaban.", history: "Bandingkan hasil evaluasi setelah sumber data diperbarui.", system: "Konfigurasi model dan pencarian yang digunakan aplikasi.", health: "Koneksi layanan dan penggunaan perangkat server.", logs: "Telusuri aktivitas dan kegagalan tanpa membuka isi percakapan." };
  const formatDate = (value?: string) => value ? new Date(value).toLocaleString("id-ID", { timeZone: "Asia/Jakarta", day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" }) + " WIB" : "Belum ada evaluasi";
  const pct = (value?: number | null) => value == null ? "—" : value.toFixed(1);
  function chooseSourceTab(source: StudioSource) { setPdfFile(null); setExcelFile(null); setActiveStudioTab(source); }
  function openSource(domain?: TaxDomainCode) { if (domain) { setPdfDomain(domain); setExcelDomain(domain); } chooseSourceTab("pdf_regulasi"); setPage("sources"); }

  const coverageTable = <div className="jst-table-scroll"><table className="jst-table jst-coverage-table"><caption className="jst-sr-only">Ketersediaan sumber per kategori pajak</caption><thead><tr><th>Pajak</th><th>Dokumen</th><th>Tabel</th><th>Kasus</th><th>Cakupan</th></tr></thead><tbody>{TAX_DOMAINS.map(domain => {
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
    <aside className={`jst-sidebar ${navOpen ? "jst-nav-open" : ""}`}><button className="jst-mobile-menu" aria-label={navOpen ? "Tutup navigasi dashboard" : "Buka navigasi dashboard"} aria-expanded={navOpen} aria-controls="jst-dashboard-nav" onClick={() => setNavOpen(v=>!v)}><ListIcon size={21}/></button>
      <div className="jst-brand"><span className="jst-monogram">ST</span><div>Jakarta SmartTax</div></div>

      <nav id="jst-dashboard-nav" aria-label="Navigasi dashboard">{([
        ["overview", "Ringkasan", SquaresFourIcon], ["sources", "Dokumen", FoldersIcon], ["evaluation", "Data & evaluasi", ShieldCheckIcon], ["health", "Kesehatan sistem", DatabaseIcon], ["logs", "Log sistem", ClockCounterClockwiseIcon], ["system", "Pengaturan", SlidersHorizontalIcon],
      ] as const).map(([key, label, Icon]) => <button key={key} onClick={() => {setPage(key);setNavOpen(false);}} aria-current={page === key ? "page" : undefined}><Icon size={19} weight={page === key ? "fill" : "regular"} /><span>{label}</span>{key === "sources" && <small>{vs?.total_documents ?? "—"}</small>}</button>)}</nav>
      <div className="jst-sidebar-bottom"><div className="jst-model-status"><i className={hw?.ollama_online ? "is-online" : ""} /><div>{hw?.primary_llm || "Model lokal"}<small>{!data ? "Status belum tersedia" : hw?.ollama_online ? "Ollama terhubung" : "Ollama tidak terhubung"}</small></div></div>{onBackToChat && <button className="jst-chat-link" onClick={onBackToChat}><ArrowLeftIcon size={16} /> Buka ruang chat <ArrowUpRightIcon size={16} /></button>}</div>
    </aside>
    <div className="jst-content-scroll" key={page}>
      <div className="jst-topbar"><span>Jakarta SmartTax <span className="jst-breadcrumb-separator">/</span> <strong>{titles[page]}</strong></span><div className="jst-topbar-actions">{onBackToChat && <button className="jst-mobile-chat" onClick={onBackToChat} aria-label="Buka ruang chat"><ArrowUpRightIcon size={16} /><span>Chat</span></button>}<button className="jst-theme-button" onClick={() => setSurfaceTheme(theme => theme === "light" ? "dark" : "light")} aria-label={surfaceTheme === "light" ? "Aktifkan mode gelap" : "Aktifkan mode terang"}>{surfaceTheme === "light" ? <MoonIcon size={17} /> : <SunIcon size={17} />}</button></div></div>
      <main id="jst-main" className="jst-main" tabIndex={-1}>
        <header className="jst-page-header"><div><h1 tabIndex={-1}>{titles[page]}</h1><p>{descriptions[page]}</p></div>{(page === "evaluation" || page === "history") && <button className="jst-button jst-button-primary" disabled={busy} title={data?.evaluation_readiness?.reason} onClick={handleRunBenchmark}>{isEvaluating ? <ArrowsClockwiseIcon size={17} className="jst-spin" /> : <PlayIcon size={17} weight="fill" />}{isEvaluating ? "Mengevaluasi…" : "Jalankan evaluasi"}</button>}</header>
        <SourceProcessingNotice active={isIngesting} onBusyChange={setSourceProcessing} />
        {statusBanner && <div className={`jst-notice ${statusBanner.type === "error" ? "is-error" : ""}`} role={statusBanner.type === "error" ? "alert" : "status"}><span>{statusBanner.type === "error" ? <WarningIcon size={18} /> : <CheckCircleIcon size={18} />}{statusBanner.text}</span><button onClick={() => setStatusBanner(null)} aria-label="Tutup pemberitahuan"><XCircleIcon size={19} /></button></div>}
        {loading && !data && <div className="jst-loading" role="status">Memuat sumber dan hasil evaluasi…</div>}
        {!loading && !data && <div className="jst-empty-state"><DatabaseIcon size={28} /><h2>Data dashboard belum tersedia</h2><p>Periksa koneksi backend lalu muat ulang data.</p><button className="jst-button" onClick={fetchTelemetry}>Coba lagi</button></div>}

        {page === "sources" && data && vs?.total_chunks === 0 && <section className="jst-empty-data" aria-labelledby="empty-data-title"><DatabaseIcon size={24} /><div><h2 id="empty-data-title">Belum ada sumber yang siap digunakan</h2></div>{page !== "sources" && <button className="jst-button" onClick={() => openSource()}>Tambah sumber <PlusIcon size={15} /></button>}</section>}
        {page === "evaluation" && data && !snap && <p className="jst-readiness-note">{data.evaluation_readiness.reason} Skor dan riwayat evaluasi belum tersedia.</p>}
        {page === "overview" && <OperationsPanel view="overview" sourceCount={vs?.total_documents} onNavigate={destination=>setPage(destination)} knowledge={<section className="jst-section"><div className="jst-section-heading"><h2>Sumber jawaban</h2><button className="jst-button" onClick={() => setPage("sources")}>Kelola dokumen</button></div><div className="jst-operation-metrics"><div className="jst-operation-metric"><span>Sumber aktif</span><strong>{vs?.total_documents ?? "—"}</strong></div><div className="jst-operation-metric"><span>Bagian teks siap dicari</span><strong>{vs?.total_chunks ?? "—"}</strong></div><div className="jst-operation-metric"><span>Evaluasi terakhir</span><strong style={{fontSize:14}}>{formatDate(snap?.timestamp)}</strong></div></div></section>} />}
        {page === "health" && <OperationsPanel view="health"/>}
        {page === "logs" && <OperationsPanel view="logs"/>}

        {page === "sources" && <>
          <SourceReviewPanel onReviewed={() => { void fetchTelemetry(); }} />
          <details className="jst-section jst-add-source"><summary>Tambah sumber data</summary><div className="jst-source-single"><section className="jst-section jst-source-editor"><div className="jst-source-tabs" role="tablist" aria-label="Jenis sumber">{(["pdf_regulasi", "markdown", "excel_data", "user_reasoning"] as StudioSource[]).map(key => <button key={key} role="tab" aria-selected={activeStudioTab === key} aria-controls="jst-source-panel" id={`jst-tab-${key}`} tabIndex={activeStudioTab === key ? 0 : -1} onKeyDown={e => { if (["ArrowRight", "ArrowLeft", "Home", "End"].includes(e.key)) { e.preventDefault(); const keys: StudioSource[] = ["pdf_regulasi", "markdown", "excel_data", "user_reasoning"]; const next = e.key === "Home" ? 0 : e.key === "End" ? keys.length-1 : (keys.indexOf(key) + (e.key === "ArrowRight" ? 1 : keys.length-1)) % keys.length; chooseSourceTab(keys[next]); document.getElementById(`jst-tab-${keys[next]}`)?.focus(); } }} onClick={() => chooseSourceTab(key)}><SourceIcon sourceType={key} size={17} />{key === "pdf_regulasi" ? "PDF" : key === "markdown" ? "Markdown" : key === "excel_data" ? "Excel / CSV" : "Contoh kasus"}</button>)}</div>
            <div id="jst-source-panel" role="tabpanel" aria-labelledby={`jst-tab-${activeStudioTab}`}>
            {activeStudioTab === "markdown" ? <MarkdownImport blocked={sourceProcessing} onImported={() => { void fetchTelemetry(); }} /> : activeStudioTab !== "user_reasoning" ? <form onSubmit={activeStudioTab === "pdf_regulasi" ? handlePdfSubmit : handleExcelSubmit} className="jst-form" key={activeStudioTab}>
              <div className="jst-form-row"><label htmlFor="source-domain">Kategori pajak<select id="source-domain" value={activeStudioTab === "pdf_regulasi" ? pdfDomain : excelDomain} onChange={e => activeStudioTab === "pdf_regulasi" ? setPdfDomain(e.target.value as TaxDomainCode) : setExcelDomain(e.target.value as TaxDomainCode)}>{TAX_DOMAINS.map(domain => <option key={domain}>{domain}</option>)}</select></label><label htmlFor="source-contributor">Kontributor / unit kerja<input required id="source-contributor" value={activeStudioTab === "pdf_regulasi" ? pdfContributor : excelContributor} onChange={e => activeStudioTab === "pdf_regulasi" ? setPdfContributor(e.target.value) : setExcelContributor(e.target.value)} /></label></div>
              <label className="jst-upload-field" htmlFor="source-file"><strong>{activeStudioTab === "pdf_regulasi" ? "Pilih dokumen PDF" : "Pilih tabel data pajak"}</strong><span>{activeStudioTab === "pdf_regulasi" ? "PDF · Maksimal 20 MB" : "XLSX / XLS / CSV · Maksimal 20 MB"}</span><input required id="source-file" type="file" accept={activeStudioTab === "pdf_regulasi" ? ".pdf" : ".xlsx,.xls,.csv"} onChange={e => activeStudioTab === "pdf_regulasi" ? setPdfFile(e.target.files?.[0] ?? null) : setExcelFile(e.target.files?.[0] ?? null)} /></label>
              <p className="jst-note">File asli disimpan. Sumber langsung aktif setelah lolos pemeriksaan teknis dan berhasil diindeks.</p><div className="jst-form-actions"><button className="jst-button jst-button-primary" disabled={busy || !(activeStudioTab === "pdf_regulasi" ? pdfFile : excelFile)} type="submit"><PlusIcon size={17} />{isIngesting ? "Memproses sumber…" : "Unggah dan proses"}</button></div>
            </form> : <form className="jst-form jst-case-form" onSubmit={handleReasoningSubmit}><div className="jst-form-row"><label htmlFor="case-domain">Kategori pajak<select id="case-domain" value={reasoningForm.topik_pajak} onChange={e => setReasoningForm(form => ({...form,topik_pajak:e.target.value as TaxDomainCode}))}>{TAX_DOMAINS.map(domain => <option key={domain}>{domain}</option>)}</select></label><label htmlFor="case-contributor">Kontributor / unit kerja<input required id="case-contributor" value={reasoningForm.kontributor} onChange={e => setReasoningForm(form => ({...form,kontributor:e.target.value}))} /></label></div>{([ ["pertanyaan_kasus", "Pertanyaan kasus"], ["alur_penalaran", "Penjelasan & dasar rujukan"], ["jawaban_final", "Jawaban yang diharapkan"] ] as const).map(([key,label]) => <label key={key} htmlFor={`case-${key}`}>{label}<textarea id={`case-${key}`} required rows={key === "alur_penalaran" ? 5 : 3} value={reasoningForm[key]} onChange={e => setReasoningForm(form => ({...form,[key]:e.target.value}))} /></label>)}<p className="jst-note">Contoh kasus langsung diindeks sebagai rujukan chatbot. Proses ini belum mengubah bobot model.</p><button className="jst-button jst-button-primary" disabled={busy} type="submit"><PlusIcon size={17} />{isIngesting ? "Menyimpan…" : "Unggah dan proses"}</button></form>}
            </div>
          </section></div>
          </details>
          <section className="jst-section"><div className="jst-section-heading"><div><span className="jst-eyebrow">ARSIP MASUK</span><h2>Sumber terbaru</h2></div><span className="jst-count">{vs?.recent_sources.length ?? "—"}</span></div>{vs?.recent_sources.length ? <div className="jst-source-list">{vs.recent_sources.map((source,i) => <div key={`${source.doc_name}-${source.ingested_at}-${i}`}><span className="jst-file-icon"><SourceIcon sourceType={source.source_type} size={23} /></span><span><strong>{source.doc_name}</strong><small>{source.domain} · {source.contributor}</small></span><time>{formatDate(source.ingested_at)}</time></div>)}</div> : <p className="jst-note">Belum ada sumber yang tercatat.</p>}</section>
        </>}

        {page === "evaluation" && <>
          <div className="jst-evaluation-flow" aria-label="Alur pengujian"><span>1. Siapkan sumber</span><span>2. Uji pertanyaan</span><span>3. Tinjau hasil</span></div><div className="jst-operation-columns"><section className="jst-section"><h2>Rujukan dan pengujian</h2><p className="jst-note">Dokumen RAG menjadi rujukan jawaban. Dataset evaluasi dipakai menguji hasil. Penambahan sumber tidak melatih bobot model.</p><button className="jst-button" onClick={() => setPage("sources")}>Kelola sumber RAG</button></section><section className="jst-section"><h2>Pelatihan model</h2><p className="jst-note">Belum ada layanan fine-tuning terhubung. Percakapan pengguna tidak otomatis dijadikan data training.</p><button className="jst-button" onClick={() => setPage("history")}>Riwayat evaluasi</button></section></div>


          <div className="jst-evaluation-intro"><div><span className="jst-eyebrow">DATASET UJI</span><h2>{snap ? `${statusCounts.total} soal dalam pengujian ini.` : data?.evaluation_readiness.golden_items ? "Soal dan jawaban acuan belum diuji." : "Belum ada soal dan jawaban acuan."}</h2><p className="jst-note">{snap ? "Evaluasi menggunakan jawaban yang disusun dari korpus. Skor menunjukkan kecocokan dengan acuan pengujian. Ketepatan isi dan dasar hukum tetap perlu diperiksa." : "Siapkan sumber, soal, dan jawaban acuan resmi sebelum menjalankan evaluasi."}</p></div>{snap && <div className="jst-result-counts"><span><i className="is-pass" />{statusCounts.pass} memenuhi ambang</span><span><i className="is-partial" />{statusCounts.partial} mendekati ambang</span><span><i className="is-fail" />{statusCounts.fail} di bawah ambang</span></div>}</div>
          <section className="jst-section"><div className="jst-filters"><label className="jst-sr-only" htmlFor="filter-domain">Filter kategori pajak</label><select id="filter-domain" value={domainFilter} onChange={e => setDomainFilter(e.target.value)}><option value="ALL">Semua pajak</option>{TAX_DOMAINS.map(domain => <option key={domain}>{domain}</option>)}</select><label className="jst-sr-only" htmlFor="filter-status">Filter hasil</label><select id="filter-status" value={statusFilter} onChange={e => setStatusFilter(e.target.value)}><option value="ALL">Semua hasil</option><option value="PASS">Memenuhi ambang (≥75)</option><option value="PARTIAL">Mendekati ambang (60–74)</option><option value="FAIL">Belum lulus (&lt;60)</option></select><label className="jst-sr-only" htmlFor="filter-source">Filter sumber</label><select id="filter-source" value={sourceFilter} onChange={e => setSourceFilter(e.target.value)}><option value="ALL">Semua sumber</option>{(Object.keys(SOURCE_TYPE_LABELS) as RagSourceType[]).map(key => <option key={key} value={key}>{SOURCE_TYPE_LABELS[key]}</option>)}</select><label className="jst-sr-only" htmlFor="filter-search">Cari soal atau kata kunci</label><input id="filter-search" value={searchQuery} onChange={e => setSearchQuery(e.target.value)} placeholder="Cari soal atau kata kunci…" /></div>
            <div className="jst-evidence-list">{filteredItems.map(item => <article key={item.id} className={`jst-evidence-item ${expandedRows[item.id] ? "is-open" : ""}`}><button className="jst-evidence-toggle" onClick={() => toggleRowExpand(item.id)} aria-expanded={!!expandedRows[item.id]} aria-controls={`evidence-${item.id}`}><span className="jst-question-id">{item.id}<small>{item.domain}</small></span><span className="jst-question-text">{item.pertanyaan}</span><span className="jst-evidence-score">{item.current_score.toFixed(1)}<small>/100</small></span><span className={`jst-status-label is-${item.status.toLowerCase()}`}>{item.status === "PASS" ? "Lulus" : item.status === "PARTIAL" ? "Cukup" : "Belum lulus"}</span>{expandedRows[item.id] ? <CaretDownIcon size={17} /> : <CaretRightIcon size={17} />}</button>
              {expandedRows[item.id] && <div id={`evidence-${item.id}`} className="jst-evidence-detail"><p className="jst-reference"><strong>Acuan dataset</strong> {item.referensi_regulasi}</p><div className="jst-answer-comparison"><div><span className="jst-eyebrow">SEBELUM PENAMBAHAN SUMBER · {item.previous_score.toFixed(1)}</span><p>{item.previous_answer}</p></div><div><span className="jst-eyebrow">SETELAH PENAMBAHAN SUMBER · {item.current_score.toFixed(1)}</span><p>{item.current_answer}</p></div></div><div className="jst-reference-answer"><span className="jst-eyebrow">JAWABAN ACUAN DATASET</span><p>{item.kunci_jawaban}</p></div><dl className="jst-item-metrics"><div><dt>Kemiripan teks</dt><dd>{item.cosine_similarity_pct.toFixed(1)}%</dd></div><div><dt>Poin kunci</dt><dd>{item.keyword_hit_ratio_pct.toFixed(1)}%</dd></div><div><dt>Kemiripan sumber</dt><dd>{item.faithfulness_pct.toFixed(1)}%</dd></div><div><dt>Perubahan</dt><dd><DeltaPill delta={item.score_delta} /></dd></div></dl><p className="jst-note">Poin belum ditemukan: {item.missing_keywords.length ? item.missing_keywords.join(" · ") : "Seluruh poin kunci ditemukan."}</p><details className="jst-citations"><summary>{item.retrieved_sources.length} sumber rujukan</summary>{item.retrieved_sources.map((source,i) => <div key={`${source.chunk_id}-${i}`}><SourceIcon sourceType={source.source_type} size={18} /><div><strong>{source.doc_name}</strong><small>{source.domain} · Kemiripan {source.similarity.toFixed(1)}%</small><p>{source.excerpt}</p></div></div>)}</details></div>}
            </article>)}{!filteredItems.length && <div className="jst-empty-state"><ShieldCheckIcon size={28} /><h3>{snap ? "Tidak ada soal yang cocok" : "Belum ada hasil evaluasi"}</h3><p>{snap ? "Ubah filter atau kata kunci pencarian." : "Hasil per soal akan muncul setelah sumber dan dataset uji resmi tersedia."}</p></div>}</div>
          </section><p className="jst-note">Evaluasi terakhir: {formatDate(snap?.timestamp)}. Perubahan skor dinyatakan dalam poin persentase.</p>
        </>}

        {page === "history" && <><section className="jst-section"><div className="jst-section-heading"><div><span className="jst-eyebrow">RIWAYAT EVALUASI</span><h2>Hasil evaluasi dari waktu ke waktu</h2></div><span className="jst-count">{timeline.length} evaluasi</span></div><ScoreHistory points={timeline.map(point => ({id:point.snapshot_id,value:point.smarttax_iq_percentage,label:formatDate(point.timestamp)}))} /><p className="jst-note">Skor heuristik antar evaluasi; bukan kurva loss training model.</p></section><section className="jst-section"><div className="jst-table-scroll"><table className="jst-table jst-history-table"><caption className="jst-sr-only">Riwayat evaluasi RAG</caption><thead><tr><th>Waktu / WIB</th><th>Aktivitas</th><th>Sumber</th><th>Skor</th><th>Perubahan</th></tr></thead><tbody>{[...timeline].reverse().map(point => <tr key={point.snapshot_id}><td>{formatDate(point.timestamp)}</td><td>{point.trigger_event}</td><td>{point.total_chunks_indexed}</td><td><strong>{point.smarttax_iq_percentage.toFixed(2)}</strong></td><td><DeltaPill delta={point.delta_change} /></td></tr>)}</tbody></table></div>{!timeline.length && <p className="jst-note">Belum ada riwayat evaluasi.</p>}</section></>}

        {page === "system" && <><div className="jst-source-layout"><section className="jst-section"><span className="jst-eyebrow">MODEL LOKAL</span><h2 className="jst-aside-title">Koneksi & konfigurasi</h2><dl className="jst-system-ledger">{[["Model",hw?.primary_llm],["Status Ollama",!data ? "Belum tersedia" : hw?.ollama_online ? "Terhubung" : "Tidak terhubung"],["Embedding aktif",hw?.embedding_model],["Context window",hw?.num_ctx?.toLocaleString("id-ID")],["GPU (konfigurasi)",hw?.gpu],["VRAM (konfigurasi)",hw?.vram_gb != null ? `${hw.vram_gb} GB` : undefined],["KV cache",hw?.kv_cache_type],["Flash attention",hw ? hw.flash_attention ? "Aktif" : "Nonaktif" : undefined],["Koleksi",vs?.collection],["Metrik jarak",vs?.distance_metric]].map(([label,value]) => <div key={label}><dt>{label}</dt><dd>{value || "—"}</dd></div>)}</dl><p className="jst-note">Informasi perangkat berasal dari konfigurasi backend. Ini bukan pengukuran penggunaan GPU secara langsung.</p></section><section className="jst-section jst-training-panel"><BrainIcon size={34} weight="light" /><span className="jst-eyebrow">TRAINING MODEL</span><h2>Belum terhubung.</h2><p>Penambahan sumber saat ini memperbarui basis pengetahuan RAG. Bobot model tetap sama.</p><ul><li>Progres step & epoch <span>Belum tersedia</span></li><li>Training & validation loss <span>Belum tersedia</span></li><li>Checkpoint & adapter <span>Belum tersedia</span></li></ul><p className="jst-note">Hubungkan layanan trainer untuk menampilkan proses fine tuning yang sebenarnya.</p></section></div></>}
        <footer className="jst-footer"><span>JST <i>/</i> Jakarta SmartTax</span><span>Dokumen, kualitas jawaban, dan kondisi sistem</span></footer>
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
