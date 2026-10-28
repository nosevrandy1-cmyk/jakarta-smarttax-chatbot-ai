"use client";

import { FileTextIcon } from "@phosphor-icons/react/dist/csr/FileText";

export interface AnswerReference {
  number: number;
  chunk_id: string;
  document_name: string;
  source_type: string;
  text: string;
  page: number | null;
  chunk_index: number | null;
  sheet: string | null;
  row: number | null;
}

export default function AnswerReferences({ references }: { references?: AnswerReference[] }) {
  if (!references?.length) return null;
  return <section className="chat-references" aria-label="Referensi jawaban">
    <h3>Referensi jawaban</h3>
    <p>Sumber yang dirujuk dalam jawaban. Buka untuk membaca kutipannya.</p>
    <ol>{references.map(reference => <li key={`${reference.number}-${reference.chunk_id}`}>
      <details>
        <summary><span className="chat-reference-number">[{reference.number}]</span><FileTextIcon size={16} aria-hidden="true" />
          <span className="chat-reference-title">{reference.document_name}<small>
            {reference.page != null ? `Halaman ${reference.page}` : reference.source_type === "pdf_regulasi" ? "Halaman asal belum tersimpan" : ""}
            {reference.chunk_index != null ? ` · Bagian ${reference.chunk_index + 1}` : ""}
            {reference.sheet ? `${reference.sheet}${reference.row != null ? ` · Baris ${reference.row}` : ""}` : ""}
          </small></span></summary>
        <blockquote>{reference.text}</blockquote>
      </details>
    </li>)}</ol>
  </section>;
}
