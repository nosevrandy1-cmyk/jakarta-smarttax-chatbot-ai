"use client";

import { useId, useState } from "react";
import { BrainIcon } from "@phosphor-icons/react/dist/csr/Brain";
import { PauseIcon } from "@phosphor-icons/react/dist/csr/Pause";
import { PlayIcon } from "@phosphor-icons/react/dist/csr/Play";
import type { TaxDomainCode, VectorStoreTelemetry } from "@/types/audit";

const DOMAINS: TaxDomainCode[] = ["PBB-P2", "JPB", "PBJT", "BPHTB", "REKLAME", "PAT"];
const SOURCES = [
  { key: "pdf_regulasi", label: "Dokumen PDF", color: "#60a5fa" },
  { key: "excel_data", label: "Excel / CSV", color: "#fbbf24" },
  { key: "user_reasoning", label: "Contoh kasus", color: "#a78bfa" },
] as const;

export default function KnowledgeNeuralMap({ telemetry }: { telemetry?: VectorStoreTelemetry }) {
  const [selected, setSelected] = useState<TaxDomainCode>("PBB-P2");
  const [paused, setPaused] = useState(false);
  const id = useId().replace(/:/g, "");
  const selectedCounts = telemetry?.domain_matrix?.[selected];
  const total = SOURCES.reduce((sum, source) => sum + (selectedCounts?.[source.key] ?? 0), 0);
  const activeSlots = DOMAINS.reduce((sum, domain) => sum + SOURCES.filter(source =>
    (telemetry?.domain_matrix?.[domain]?.[source.key] ?? 0) > 0).length, 0);

  return (
    <section className={`audit-neural-map ${paused ? "is-paused" : ""}`} aria-labelledby={`${id}-title`}>
      <div className="neural-heading">
        <div>
          <div className="neural-eyebrow"><BrainIcon size={16} aria-hidden="true" /> HUBUNGAN DATA</div>
          <h2 id={`${id}-title`}>Hubungan antar sumber data</h2>
          <p>Pilih jenis pajak untuk melihat sumber yang tersedia.</p>
        </div>
        <button type="button" className="audit-secondary-btn" onClick={() => setPaused(!paused)} aria-pressed={paused} aria-label={paused ? "Lanjutkan animasi" : "Jeda animasi"} title={paused ? "Lanjutkan animasi" : "Jeda animasi"}>
          {paused ? <PlayIcon size={15} aria-hidden="true" /> : <PauseIcon size={15} aria-hidden="true" />}
          <span>{paused ? "Lanjutkan animasi" : "Jeda animasi"}</span>
        </button>
      </div>

      <div className="neural-layout">
        <figure className="neural-figure">
          <div className="neural-canvas" tabIndex={0} role="region" aria-label="Peta koneksi sumber dan kategori pajak. Geser horizontal pada layar kecil. Rincian tersedia pada pilihan kategori di bawah.">
            <svg viewBox="0 0 760 410" className="neural-svg" aria-hidden="true" focusable="false">
              <defs>
                <pattern id={`${id}-grid`} width="24" height="24" patternUnits="userSpaceOnUse"><circle cx="1" cy="1" r="1" fill="currentColor" opacity="0.12" /></pattern>
              </defs>
              <rect width="760" height="410" fill={`url(#${id}-grid)`} />
              <text x="50" y="28" className="neural-column-title">SUMBER</text>
              <text x="354" y="28" className="neural-column-title">KATEGORI PAJAK</text>
              <text x="650" y="28" textAnchor="middle" className="neural-column-title">KONTEKS</text>
              {DOMAINS.map((domain, index) => {
                const y = 66 + index * 60;
                const hasData = SOURCES.some(source => (telemetry?.domain_matrix?.[domain]?.[source.key] ?? 0) > 0);
                return <g key={domain}>
                  <path d={`M 402 ${y} C 515 ${y}, 520 215, 625 215`} className={`neural-output ${hasData && domain === selected ? "is-active" : ""}`} />
                  {SOURCES.map((source, sourceIndex) => {
                    const sy = 85 + sourceIndex * 128;
                    const count = telemetry?.domain_matrix?.[domain]?.[source.key] ?? 0;
                    const active = domain === selected && count > 0;
                    const pathId = `${id}-${source.key}-${domain}`;
                    return <g key={source.key}>
                      <path id={pathId} d={`M 102 ${sy} C 225 ${sy}, 235 ${y}, 366 ${y}`} stroke={source.color}
                        className={`neural-link ${count ? "has-data" : "is-empty"} ${active ? "is-active" : ""}`} />
                      {active && <circle r="3" fill={source.color} className="neural-signal">
                        <animateMotion dur={`${4 + sourceIndex}s`} repeatCount="indefinite"><mpath href={`#${pathId}`} /></animateMotion>
                      </circle>}
                    </g>;
                  })}
                </g>;
              })}
              {SOURCES.map((source, index) => {
                const y = 85 + index * 128;
                return <g key={source.key}>
                  {[-1, 1].map(direction => <g key={direction} stroke={source.color} fill={source.color} opacity="0.65">
                    <path d={`M 80 ${y} Q 65 ${y + direction * 22}, 46 ${y + direction * 30}`} fill="none" />
                    <circle cx="46" cy={y + direction * 30} r="3" />
                  </g>)}
                  <circle cx="85" cy={y} r="23" fill="var(--audit-surface)" stroke={source.color} strokeWidth="1.5" />
                  <circle cx="85" cy={y} r="9" fill={source.color} opacity="0.85" />
                  <text x="120" y={y - 15} className="neural-node-label">{source.label}</text>
                </g>;
              })}
              {DOMAINS.map((domain, index) => {
                const y = 66 + index * 60;
                const active = domain === selected;
                return <g key={domain}>
                  <circle cx="384" cy={y} r={active ? 23 : 17} className={`neural-domain ${active ? "is-selected" : ""}`} />
                  <circle cx="384" cy={y} r="5" fill={active ? "var(--jst-network)" : "var(--audit-text-secondary)"} />
                  <text x="418" y={y + 5} className="neural-node-label">{domain}</text>
                </g>;
              })}
              <circle cx="650" cy="215" r="57" className="neural-halo" />
              <circle cx="650" cy="215" r="34" className="neural-core" />
              <text x="650" y="220" textAnchor="middle" className="neural-core-label">RAG</text>
              <text x="650" y="295" textAnchor="middle" className="neural-node-label">Pencarian konteks</text>
            </svg>
          </div>
          <figcaption>Garis berwarna: tersedia data. Garis putus-putus: belum tersedia. Gerakan sinyal hanya ilustrasi, bukan aktivitas neuron model.</figcaption>
        </figure>

      </div>
      <div className="neural-domain-picker" role="group" aria-label="Pilih kategori pada peta pengetahuan">
        {DOMAINS.map(domain => <button key={domain} type="button" aria-pressed={domain === selected} onClick={() => setSelected(domain)}>{domain}</button>)}
      </div>
      <div className="jst-neural-selection" aria-live="polite" aria-atomic="true">
        <strong>{selected} · {telemetry ? total : "—"} potongan</strong>
        {SOURCES.map(source => <span key={source.key}><i className="neural-legend-dot" style={{background:source.color}} />{source.label} {telemetry ? selectedCounts?.[source.key] ?? 0 : "—"}</span>)}
      </div>
      <p className="neural-disclaimer">{telemetry ? `${activeSlots}/18 koneksi sumber tersedia.` : "Menunggu data sumber."} {telemetry && total === 0 ? "Kategori ini belum memiliki sumber. " : ""}Peta menunjukkan ketersediaan rujukan, bukan aktivitas training model.</p>
    </section>
  );
}
