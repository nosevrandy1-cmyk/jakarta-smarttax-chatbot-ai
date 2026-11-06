"use client";
import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { FileTextIcon } from "@phosphor-icons/react/dist/csr/FileText";
import { XIcon } from "@phosphor-icons/react/dist/csr/X";

type Source={id:string;doc_name:string;status:string;chunk_count:number;domain?:string;source_format?:string;page_count?:number};
type Chunk={id:string;number:number;page?:number;sheet?:string;row?:number};
type Detail=Source & {chunks:Chunk[];total:number;offset:number;limit:number};
const labels:Record<string,string>={pending:"Belum diproses",approved:"Aktif",rejected:"Ditolak",failed:"Gagal diproses"};
export default function SourceReviewPanel({onReviewed}:{onReviewed:()=>void}){
 const [items,setItems]=useState<Source[]>([]),[total,setTotal]=useState(0),[offset,setOffset]=useState(0);
 const [query,setQuery]=useState(""),[search,setSearch]=useState(""),[domain,setDomain]=useState("");
 const [detail,setDetail]=useState<Detail|null>(null),[texts,setTexts]=useState<Record<string,string>>({}),[expanded,setExpanded]=useState<string|null>(null);
 const [busy,setBusy]=useState(false),[error,setError]=useState("");
 const load=useCallback(async(signal?:AbortSignal)=>{
  try{const params=new URLSearchParams({offset:String(offset),limit:"20",q:search,domain});
   const res=await apiFetch(`/api/rag/sources?${params}`,{signal});if(!res.ok)throw new Error("Daftar dokumen belum dapat dimuat.");
   const data=await res.json();if(signal?.aborted)return;setItems(data.items);setTotal(data.total);setError("");
  }catch(e){if(signal?.aborted)return;setError(e instanceof Error?e.message:"Daftar belum tersedia.");}
 },[offset,search,domain]);
 useEffect(()=>{const abort=new AbortController();void load(abort.signal);const refresh=()=>{void load(abort.signal);};window.addEventListener("jst-source-uploaded",refresh);return()=>{abort.abort();window.removeEventListener("jst-source-uploaded",refresh);};},[load]);
 async function open(id:string,start=0){if(busy)return;setBusy(true);setError("");setTexts({});setExpanded(null);setDetail(null);
  try{const res=await apiFetch(`/api/rag/sources/${id}?offset=${start}&limit=10`);if(!res.ok)throw new Error("Rincian dokumen belum dapat dimuat.");setDetail(await res.json());}
  catch(e){setError(e instanceof Error?e.message:"Rincian belum tersedia.");}finally{setBusy(false);}}
 async function read(chunk:Chunk){if(busy||!detail)return;if(expanded===chunk.id){setExpanded(null);return;}setExpanded(chunk.id);if(texts[chunk.id])return;setBusy(true);setError("");
  try{const res=await apiFetch(`/api/rag/sources/${detail.id}/chunks/${chunk.id}`);if(!res.ok)throw new Error("Isi bagian belum dapat dimuat.");const data=await res.json();setTexts(current=>({...current,[chunk.id]:data.text}));}
  catch(e){setExpanded(null);setError(e instanceof Error?e.message:"Isi belum tersedia.");}finally{setBusy(false);}}
 async function process(){if(!detail||busy)return;setBusy(true);setError("");try{const res=await apiFetch(`/api/rag/sources/${detail.id}/process`,{method:"POST"});if(!res.ok)throw new Error("Pemrosesan belum berhasil. Coba lagi setelah memeriksa sumber.");setDetail(await res.json());setTexts({});setExpanded(null);await load();onReviewed();}catch(e){setError(e instanceof Error?e.message:"Pemrosesan gagal.");}finally{setBusy(false);}}
 return <section className="jst-section jst-document-browser" aria-labelledby="source-review-title">
  <div className="jst-section-heading"><div><h2 id="source-review-title">Dokumen</h2><p className="jst-note">{total} sumber. Buka dokumen untuk memeriksa bagian yang diperlukan.</p></div><FileTextIcon size={22}/></div>
  <form className="jst-document-search" onSubmit={e=>{e.preventDefault();setOffset(0);setSearch(query.trim());setDetail(null);setTexts({});}}>
   <input aria-label="Cari judul dokumen" placeholder="Cari judul dokumen" value={query} maxLength={120} onChange={e=>setQuery(e.target.value)}/>
   <select aria-label="Kategori dokumen" value={domain} onChange={e=>{setDomain(e.target.value);setOffset(0);setDetail(null);setTexts({});}}><option value="">Semua kategori</option>{["PBB-P2","PBJT","BPHTB","REKLAME","PAT"].map(d=><option key={d}>{d}</option>)}</select><button className="jst-button" type="submit">Cari</button>
  </form>
  {error&&<p role="alert">{error}</p>}
  <div className="jst-source-list">{items.map(item=><div key={item.id}><span><strong>{item.doc_name}</strong><small>{item.domain} · {labels[item.status]||item.status} · {item.chunk_count} bagian{item.source_format?` · ${item.source_format}`:""}</small></span><button className="jst-button" disabled={busy} onClick={()=>open(item.id)}>Lihat detail</button></div>)}</div>
  {!items.length&&<p className="jst-note">Tidak ada dokumen yang ditampilkan.</p>}
  {total>20&&<div className="jst-document-pagination"><button className="jst-button" disabled={busy||offset===0} onClick={()=>setOffset(Math.max(0,offset-20))}>Sebelumnya</button><span>{offset+1}-{Math.min(offset+20,total)} dari {total}</span><button className="jst-button" disabled={busy||offset+20>=total} onClick={()=>setOffset(offset+20)}>Berikutnya</button></div>}
  {detail&&<div className="jst-review-detail"><div className="jst-section-heading"><div><h3>{detail.doc_name}</h3><p className="jst-note">{labels[detail.status]} · {detail.total} bagian</p></div><button className="jst-icon-button" aria-label="Tutup rincian dokumen" disabled={busy} onClick={()=>{setDetail(null);setTexts({});setExpanded(null);}}><XIcon size={18}/></button></div>
   {detail.chunks.map(chunk=><div className="jst-document-chunk" key={chunk.id}><button className="jst-text-button" aria-expanded={expanded===chunk.id} aria-controls={`text-${chunk.id}`} disabled={busy} onClick={()=>read(chunk)}>Bagian {chunk.number}{chunk.page?` · Halaman ${chunk.page}`:""}{chunk.sheet?` · ${chunk.sheet} · Baris ${chunk.row}`:""}</button>{expanded===chunk.id&&<pre id={`text-${chunk.id}`}>{texts[chunk.id]||"Memuat…"}</pre>}</div>)}
   {detail.total>10&&<div className="jst-document-pagination"><button className="jst-button" disabled={busy||detail.offset===0} onClick={()=>open(detail.id,Math.max(0,detail.offset-10))}>Sebelumnya</button><span>{detail.offset+1}-{Math.min(detail.offset+10,detail.total)} dari {detail.total}</span><button className="jst-button" disabled={busy||detail.offset+10>=detail.total} onClick={()=>open(detail.id,detail.offset+10)}>Berikutnya</button></div>}
   {(detail.status==="pending"||detail.status==="failed")&&<button className="jst-button" disabled={busy} onClick={process}>{busy?"Memproses…":"Proses ulang"}</button>}
  </div>}
 </section>;
}
