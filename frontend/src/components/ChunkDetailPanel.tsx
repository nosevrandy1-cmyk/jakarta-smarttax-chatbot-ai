"use client";

import { useEffect, useRef, useState } from "react";
import { XIcon } from "@phosphor-icons/react/dist/csr/X";
import { MagnifyingGlassIcon } from "@phosphor-icons/react/dist/csr/MagnifyingGlass";
import { FileTextIcon } from "@phosphor-icons/react/dist/csr/FileText";

type Source = { id: string; name: string; chunk_count: number; source_type: string; domain: string };
type Part = { id: string; source_id: string; document_name: string; text: string;
  chunk_index: number | null; page: number | null; sheet: string | null; row: number | null; source_type: string };
type Result = { documents: Source[]; total_documents: number; total_chunks: number;
  matched_chunks: number; offset: number; limit: number; items: Part[] };
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function ChunkDetailPanel({ onClose }: { onClose: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [result, setResult] = useState<Result | null>(null);
  const [search, setSearch] = useState("");
  const [source, setSource] = useState("");
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(0);
  const limit = 12;
  useEffect(() => { dialog.current?.showModal(); }, []);
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError("");
    const timer = setTimeout(async () => {
      try {
        const params = new URLSearchParams({ q: search, offset: String(offset), limit: String(limit) });
        if (source) params.set("source_id", source);
        const response = await fetch(`${API_BASE}/api/rag/chunks?${params}`, { signal: controller.signal });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        setResult(await response.json());
      } catch (cause) {
        if (!controller.signal.aborted) setError("Rincian belum dapat dimuat. Coba lagi.");
      } finally { if (!controller.signal.aborted) setLoading(false); }
    }, 200);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [search, source, offset, retry]);

  return <dialog className="jst-chunk-dialog" ref={dialog} aria-labelledby="chunk-panel-title"
    onCancel={onClose} onClose={onClose} onClick={event => { if (event.target === dialog.current) {
      const rect = dialog.current.getBoundingClientRect();
      if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) onClose();
    } }}>
    <header className="jst-chunk-header"><div><h2 id="chunk-panel-title">Rincian bagian teks</h2>
      <p>{result ? `${result.total_chunks} bagian teks dari ${result.total_documents} sumber` : "Membaca data unggahan…"}</p></div>
      <button className="jst-icon-button" onClick={onClose} aria-label="Tutup rincian bagian teks" autoFocus><XIcon size={20} /></button></header>
    <div className="jst-chunk-body">
      <section className="jst-chunk-explanation"><p>Dokumen dibagi menjadi bagian kecil agar chatbot dapat mencari informasi yang relevan. Tabel diproses per baris, sedangkan kasus rujukan disimpan sebagai satu bagian.</p>
        <p>Sebagian teks dapat berulang di bagian yang berdekatan untuk menjaga konteks. Jumlah bagian menunjukkan banyaknya isi yang diproses, bukan kualitas atau tingkat kepintaran chatbot.</p></section>
      <div className="jst-chunk-filters"><label htmlFor="chunk-source-filter">Sumber asal<select id="chunk-source-filter" value={source} onChange={event => { setSource(event.target.value); setOffset(0); }}>
        <option value="">Semua sumber</option>{result?.documents.map(document => <option key={document.id} value={document.id}>{document.name} — {document.chunk_count} bagian</option>)}</select></label>
        <label htmlFor="chunk-search"><span><MagnifyingGlassIcon size={14} /> Cari isi atau nama sumber</span><input id="chunk-search" type="search" maxLength={200} placeholder="Ketik kata kunci…" value={search} onChange={event => { setSearch(event.target.value); setOffset(0); }} /></label></div>
      <div className="jst-chunk-status" role="status" aria-live="polite">{loading ? "Memuat bagian teks…" : error || (result ? `${result.matched_chunks} bagian ditemukan` : "")}</div>
      {error ? <div className="jst-empty-state"><p>{error}</p><button className="jst-button" onClick={() => setRetry(value => value + 1)}>Coba lagi</button></div> : !loading && result && <>
        {!result.items.length && <div className="jst-empty-state"><FileTextIcon size={28} /><h3>{result.total_chunks ? "Tidak ada bagian yang cocok" : "Belum ada bagian teks"}</h3><p>{result.total_chunks ? "Ubah kata kunci atau pilihan sumber." : "Rincian akan muncul setelah sumber data ditambahkan."}</p></div>}
        <div className="jst-chunk-list">{result.items.map((part, index) => <article key={part.id} className="jst-chunk-item">
          <div className="jst-chunk-item-header"><span>{part.chunk_index != null ? `Bagian ${part.chunk_index + 1}` : `Hasil ${offset + index + 1}`}</span><span>{part.source_type === "pdf_regulasi" ? (part.page != null ? `Halaman ${part.page}` : "Halaman asal belum tersimpan") : part.sheet ? `${part.sheet}${part.row != null ? ` · Baris ${part.row}` : ""}` : "Kasus rujukan"}</span></div>
          <h3><FileTextIcon size={17} />{part.document_name}</h3><p className="jst-chunk-preview">{part.text.length > 280 ? `${part.text.slice(0, 280)}…` : part.text}</p>
          <details><summary>Baca isi lengkap</summary><p className="jst-chunk-full">{part.text}</p></details>
        </article>)}</div>
        {result.matched_chunks > 0 && <nav className="jst-chunk-pagination" aria-label="Halaman bagian teks"><button className="jst-button" disabled={offset === 0} onClick={() => setOffset(value => Math.max(0, value - limit))}>Sebelumnya</button><span>{offset + 1}–{Math.min(offset + limit, result.matched_chunks)} dari {result.matched_chunks}</span><button className="jst-button" disabled={offset + limit >= result.matched_chunks} onClick={() => setOffset(value => value + limit)}>Berikutnya</button></nav>}
      </>}
    </div>
  </dialog>;
}
