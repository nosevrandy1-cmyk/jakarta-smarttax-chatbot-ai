"use client";
import { useRef, useState } from "react";
import { apiFetch } from "@/lib/api";
type Source = {title:string;url?:string;pages?:number;chunks?:number;duplicate?:boolean;status?:string};
export default function MarkdownImport({onImported,blocked=false}:{onImported:()=>void;blocked?:boolean}) {
  const submitting=useRef(false);
  const [busy,setBusy]=useState(false);
  const working=busy||blocked;
  const [file,setFile]=useState<File|null>(null);
  const [domain,setDomain]=useState("PBB-P2");
  const [contributor,setContributor]=useState("");
  const [sources,setSources]=useState<Source[]>([]);
  const [message,setMessage]=useState("");
  const [ready,setReady]=useState(false);
  function reset(){setReady(false);setSources([]);setMessage("");}
  async function submit(preview:boolean){
    if(!file||submitting.current||blocked)return;
    submitting.current=true;
    setBusy(true);setMessage("");
    window.dispatchEvent(new CustomEvent('jst-ingestion-start',{detail:{kind:'markdown'}}));
    try{
      const form=new FormData();form.append("file",file);form.append("domain",domain);
      form.append("kontributor",contributor);form.append("preview",String(preview));
      const res=await apiFetch("/api/rag/ingest-markdown",{method:"POST",body:form});
      const data=await res.json();if(!res.ok)throw new Error(data.detail||"Impor belum berhasil.");
      setSources(data.sources);setReady(preview);
      setMessage(preview?`${data.source_count} sumber · ${data.chunk_count} bagian teks. Periksa kategori dan sumber sebelum impor.`:
        `${data.sources.filter((s:Source)=>s.status==="active").length} aktif · ${data.sources.filter((s:Source)=>s.status==="skipped").length} dilewati · ${data.sources.filter((s:Source)=>s.status==="failed").length} gagal.`);
      if(!preview){onImported();window.dispatchEvent(new Event("jst-source-uploaded"));}
    }catch(e){setMessage(e instanceof Error?e.message:"Impor belum berhasil.");setReady(false);}
    finally{submitting.current=false;setBusy(false);window.dispatchEvent(new Event('jst-ingestion-end'));}
  }
  return <section className="jst-markdown-form"><p className="jst-note">Satu dokumen atau paket hasil crawling, UTF-8, maksimal 20 MB per file. Tabel panjang dibagi otomatis dengan header berulang.</p>
    <div className="jst-form jst-markdown-grid"><label>Kategori pajak<select value={domain} disabled={working} onChange={e=>{setDomain(e.target.value);reset();}}>{["PBB-P2","PBJT","BPHTB","REKLAME","PAT"].map(d=><option key={d}>{d}</option>)}</select></label>
    <label>Kontributor / unit kerja<input value={contributor} disabled={working} maxLength={120} onChange={e=>setContributor(e.target.value)}/></label>
    <label>File Markdown<input type="file" accept=".md" disabled={working} onChange={e=>{setFile(e.target.files?.[0]??null);reset();}}/></label>
    <div className="jst-form-actions"><button className="jst-button" disabled={!file||working} onClick={()=>submit(true)}>{busy?"Memproses…":"Periksa file"}</button>{ready&&<button className="jst-button jst-button-primary" disabled={working} onClick={()=>submit(false)}>Impor sumber</button>}</div>
    <p role="status">{message}</p><ul style={{maxHeight:320,overflowY:"auto"}}>{sources.map((s,i)=><li key={i}><strong>{s.title}</strong><small style={{display:"block"}}>{s.status||`${s.chunks} bagian · ${s.pages||0} halaman teridentifikasi${s.duplicate?" · sudah tersimpan":""}`}</small>{s.url&&<small style={{overflowWrap:"anywhere"}}>{s.url}</small>}</li>)}</ul></div></section>;
}
