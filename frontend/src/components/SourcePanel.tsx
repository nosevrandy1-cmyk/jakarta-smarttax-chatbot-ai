"use client";

import { useEffect, useRef, useState } from "react";
import PanelResizeHandle, {usePanelSize} from "./PanelResizeHandle";
import { FileTextIcon } from "@phosphor-icons/react/dist/csr/FileText";
import { XIcon } from "@phosphor-icons/react/dist/csr/X";
export type { AnswerReference } from "@/types/sources";
import type { AnswerReference } from "@/types/sources";

export default function SourcePanel({message, selectedNumber, onClose}: {
  message?: {content: string; originalQuestion?: string; references?: AnswerReference[]};
  selectedNumber?: number; onClose: () => void;
}) {
  const panel = useRef<HTMLElement>(null);
  const closeButton = useRef<HTMLButtonElement>(null);
  const [expanded, setExpanded] = useState(false);
  const [mobile, setMobile] = useState(false);
  const [width,setWidth]=usePanelSize("jst-source-width",340,260,640);
  const [sheetHeight,setSheetHeight]=useState<number|null>(null);
  const groups = new Map<string, AnswerReference[]>();
  for (const reference of message?.references || []) {
    const existing = groups.get(reference.document_name) || [];
    groups.set(reference.document_name, [...existing, reference]);
  }
  useEffect(() => {
    const previouslyFocused = document.activeElement as HTMLElement | null;
    const query = window.matchMedia("(max-width: 1100px)");
    const update = () => setMobile(query.matches);
    update(); query.addEventListener("change", update);
    closeButton.current?.focus();
    return () => { query.removeEventListener("change", update); if (previouslyFocused?.isConnected) previouslyFocused.focus(); };
  }, []);
  useEffect(() => {
    if (selectedNumber == null) return;
    const target = panel.current?.querySelector<HTMLElement>(`[data-source-number="${selectedNumber}"]`);
    if (target) target.scrollIntoView({block:"nearest",behavior:"smooth"});
  }, [selectedNumber]);
  useEffect(() => {
    if (!mobile) return;
    const root = panel.current?.closest(".app-layout");
    const background = root ? [...root.children].filter(element => !element.classList.contains("jst-source-panel") && !element.classList.contains("jst-source-backdrop")) : [];
    const prior = background.map(element => ({element:element as HTMLElement,inert:(element as HTMLElement).inert}));
    prior.forEach(({element}) => {element.inert=true;});
    closeButton.current?.focus();
    return () => prior.forEach(({element,inert}) => {element.inert=inert;});
  }, [mobile]);
  return <>
    <button className="jst-source-backdrop" aria-label="Tutup sumber" tabIndex={-1} onClick={onClose}/>
    <aside ref={panel} className={`jst-source-panel ${expanded ? "expanded" : ""}`} style={{width:mobile?undefined:width,height:mobile&&sheetHeight?sheetHeight:undefined}} role={mobile ? "dialog" : "complementary"} aria-modal={mobile ? true : undefined} aria-labelledby="jst-source-heading"
      onKeyDown={event => {
        if (event.key === "Escape") {event.stopPropagation();onClose();}
        if (event.key !== "Tab" || !mobile) return;
        const items = [...(panel.current?.querySelectorAll<HTMLElement>('button, summary, [href], [tabindex="0"]') || [])].filter(element => element.getClientRects().length);
        const first=items[0],last=items.at(-1);
        if(event.shiftKey && document.activeElement===first){event.preventDefault();last?.focus();}
        else if(!event.shiftKey && document.activeElement===last){event.preventDefault();first?.focus();}
      }}>
      {mobile ? <PanelResizeHandle label="Atur tinggi panel sumber" value={sheetHeight || window.innerHeight*.75} min={240} max={window.innerHeight*.96} edge="top" axis="y" onChange={setSheetHeight}/> : <PanelResizeHandle label="Atur lebar panel sumber" value={width} min={260} max={640} edge="left" onChange={setWidth}/>}
      <header><div><span className="jst-source-eyebrow">REFERENSI JAWABAN</span><h2 id="jst-source-heading">Sumber <span>{groups.size}</span></h2></div><button ref={closeButton} className="icon-btn" onClick={onClose} aria-label="Tutup sumber" title="Tutup sumber"><XIcon size={19}/></button></header>
      <p className="jst-source-question">{message?.originalQuestion || message?.content.slice(0,160)}</p>
      <button className="jst-sheet-expand" onClick={() => {setSheetHeight(null);setExpanded(value=>!value);}}>{expanded ? "Perkecil panel" : "Perluas panel"}</button>
      <div className="jst-source-scroll">{[...groups].map(([name,references]) => <section key={name} className="jst-source-document"><h3><FileTextIcon size={18}/><span>{name}</span></h3>{references.map(reference => <div key={`${reference.number}-${reference.chunk_id}`} className={`jst-source-location ${selectedNumber===reference.number?"selected":""}`} data-source-number={reference.number}>
        <span className="chat-reference-number">[{reference.number}]</span><span>{reference.page != null ? `Halaman ${reference.page}` : reference.sheet ? `${reference.sheet}${reference.row != null ? ` · Baris ${reference.row}` : ""}` : "Lokasi sumber belum tersedia"}</span>
      </div>)}</section>)}{!groups.size && <p>Sumber untuk jawaban ini belum tersedia.</p>}</div>
    </aside>
  </>;
}
