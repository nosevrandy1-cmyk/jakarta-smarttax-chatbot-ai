"use client";
import { useCallback, useEffect, useState } from "react";
import { apiFetch, API_BASE } from "@/lib/api";

type Source = { id: string; doc_name: string; status: string; chunk_count: number;
  warnings: string[]; has_file: boolean; note?: string; page_count?: number };
type Detail = Source & { chunks: { text: string; page?: number; sheet?: string; row?: number }[] };
const labels: Record<string, string> = { pending: "Belum diproses", approved: "Aktif", rejected: "Ditolak (arsip lama)", failed: "Gagal diproses" };

export default function SourceReviewPanel({ onReviewed }: { onReviewed: () => void }) {
  const [items, setItems] = useState<Source[]>([]);
  const [detail, setDetail] = useState<Detail | null>(null);
  const [error, setError] = useState("");
    const [busy, setBusy] = useState(false);
  const [offset, setOffset] = useState(0);
  const load = useCallback(async () => {
    try {
      const response = await apiFetch("/api/rag/sources");
      if (!response.ok) throw new Error("Daftar pemeriksaan belum dapat dimuat.");
      setItems((await response.json()).items);
    } catch (e) { setError(e instanceof Error ? e.message : "Gagal memuat sumber."); }
  }, []);
  useEffect(() => {
    void load();
    const refresh = () => { void load(); };
    window.addEventListener("jst-source-uploaded", refresh);
    return () => window.removeEventListener("jst-source-uploaded", refresh);
  }, [load]);
  async function open(id: string) {
    setError(""); setDetail(null); setOffset(0);
    try {
      const response = await apiFetch(`/api/rag/sources/${id}`);
      if (!response.ok) throw new Error("Rincian sumber belum dapat dimuat.");
      setDetail(await response.json());
    } catch (e) { setError(e instanceof Error ? e.message : "Gagal memuat rincian."); }
  }
  async function processSource() {
    if (!detail || busy) return;
    setBusy(true); setError("");
    try {
      const response = await apiFetch(`/api/rag/sources/${detail.id}/process`, {
        method: "POST",
      });
      if (!response.ok) throw new Error((await response.json()).detail || "Pemrosesan belum berhasil.");
      setDetail(await response.json()); await load(); onReviewed();
    } catch (e) { setError(e instanceof Error ? e.message : "Gagal memproses sumber."); }
    finally { setBusy(false); }
  }
  return <section className="jst-section jst-review-panel" aria-labelledby="source-review-title">
    <h2 id="source-review-title">Status pemrosesan sumber</h2>
    <p className="jst-note">Unggahan developer langsung aktif setelah lolos pemeriksaan teknis dan berhasil diindeks. Lihat rincian jika ada peringatan atau proses gagal.</p>
    {error && <p role="alert">{error} <button className="jst-text-button" onClick={load}>Muat ulang</button></p>}
    {!items.length && <p className="jst-note">Belum ada unggahan.</p>}
    <div className="jst-source-list">{items.map(item => <div key={item.id}>
      <span><strong>{item.doc_name}</strong><small>{labels[item.status]} · {item.chunk_count} bagian teks{item.page_count ? ` · ${item.page_count} halaman` : ""}</small></span>
      <button className="jst-button" onClick={() => open(item.id)} disabled={busy}>Lihat detail</button>
    </div>)}</div>
    {detail && <div className="jst-review-detail">
      <h3>{detail.doc_name}</h3><p>{labels[detail.status]}</p>
      {detail.has_file && <a className="jst-text-button" href={`${API_BASE}/api/rag/sources/${detail.id}/file`} target="_blank" rel="noopener noreferrer">Unduh file asli</a>}
      {detail.warnings.map((warning, i) => <p role="status" key={i}>{warning}</p>)}
      <p className="jst-note">Halaman di bawah mengikuti urutan fisik PDF. Hasil ekstraksi tabel kompleks belum dijamin sempurna. OCR belum tersedia.</p>
      {detail.chunks.slice(offset, offset + 10).map((chunk, i) => <details key={`${detail.id}-${offset+i}`}>
        <summary>Bagian {offset+i+1}{chunk.page ? ` · Halaman ${chunk.page}` : ""}{chunk.sheet ? ` · ${chunk.sheet} · Baris ${chunk.row}` : ""}</summary>
        <pre style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere", fontFamily: "inherit" }}>{chunk.text}</pre>
      </details>)}
      {detail.chunks.length > 10 && <p><button className="jst-button" disabled={offset === 0} onClick={() => setOffset(offset-10)}>Sebelumnya</button> {offset+1}–{Math.min(offset+10,detail.chunks.length)} dari {detail.chunks.length} <button className="jst-button" disabled={offset+10 >= detail.chunks.length} onClick={() => setOffset(offset+10)}>Berikutnya</button></p>}
      <p className="jst-note">{detail.note}</p>
      {(detail.status === "pending" || detail.status === "failed") && <button className="jst-button" disabled={busy} onClick={processSource}>{busy ? "Memproses…" : "Proses ulang"}</button>}

    </div>}
  </section>;
}
