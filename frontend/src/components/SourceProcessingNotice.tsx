"use client";
import {useEffect,useRef,useState} from 'react';
import {apiFetch} from '@/lib/api';
type Status={phase:string;kind?:string;total:number;completed:number;failed:number;skipped:number};
const running=(phase:string)=>phase==='checking'||phase==='indexing';
export default function SourceProcessingNotice({active,onBusyChange}:{active:boolean;onBusyChange:(busy:boolean)=>void}){
  const [status,setStatus]=useState<Status|null>(null);
  const [pending,setPending]=useState(false);
  const [seconds,setSeconds]=useState(0);
  const refresh=useRef<()=>void>(()=>{});
  const observed=useRef(false);
  useEffect(()=>{
    const start=(event:Event)=>{observed.current=true;setPending(true);setStatus({phase:'uploading',kind:(event as CustomEvent).detail?.kind,total:0,completed:0,failed:0,skipped:0});refresh.current();};
    const end=()=>{setPending(false);refresh.current();};
    window.addEventListener('jst-ingestion-start',start);window.addEventListener('jst-ingestion-end',end);
    return()=>{window.removeEventListener('jst-ingestion-start',start);window.removeEventListener('jst-ingestion-end',end);};
  },[]);
  const busy=active||pending||running(status?.phase||'');
  useEffect(()=>{onBusyChange(busy);},[busy,onBusyChange]);
  useEffect(()=>{
    if(!busy)return;
    setSeconds(0);const since=Date.now();const timer=setInterval(()=>setSeconds(Math.floor((Date.now()-since)/1000)),1000);
    return()=>clearInterval(timer);
  },[busy]);
  useEffect(()=>{
    let stopped=false,fetching=false;let timer:ReturnType<typeof setTimeout>;
    const controller=new AbortController();
    async function poll(){
      if(fetching||stopped)return;fetching=true;clearTimeout(timer);
      try{
        if(document.visibilityState==='visible'){
          const res=await apiFetch('/api/rag/import-status',{signal:AbortSignal.any([controller.signal,AbortSignal.timeout(8000)])});
          if(res.ok&&!stopped){const value:Status=await res.json();if(running(value.phase))observed.current=true;setStatus(value);}
        }
      }catch{/* A failed status read must not retry the upload. */}
      finally{fetching=false;if(!stopped)timer=setTimeout(poll,busy?4000:15000);}
    }
    refresh.current=()=>{void poll();};void poll();
    return()=>{stopped=true;clearTimeout(timer);controller.abort();};
  },[busy]);
  if(!busy&&!observed.current)return null;
  const phase=status?.phase;
  const label=busy?(phase==='indexing'?'Menyiapkan sumber untuk chatbot…':phase==='checking'?'Memeriksa isi sumber…':'Mengirim sumber…'):phase==='completed'?'Sumber selesai diproses':phase==='ready'?'Pemeriksaan selesai':phase==='failed'?'Sumber belum selesai diproses':'Proses unggahan berakhir';
  return <section className="jst-processing-notice" role="status" aria-live="polite">
    <div><strong>{label}</strong>{busy&&<span>{seconds} detik</span>}</div>
    {busy?<p>{phase==='indexing'&&status&&status.total>0?`${status.completed} dari ${status.total} sumber selesai. `:''}Paket besar memerlukan waktu lebih lama. Tidak perlu mengunggah ulang.</p>:<p>{phase==='completed'&&status?`${status.total-status.failed-status.skipped} aktif · ${status.skipped} dilewati · ${status.failed} gagal.`:phase==='ready'?'Periksa daftar sumber sebelum melanjutkan impor.':'Periksa pesan hasil dan status sumber sebelum mencoba lagi.'}</p>}
    {busy&&<progress aria-label="Pemrosesan sumber" {...(phase==='indexing'&&status&&status.total>0?{value:status.completed,max:status.total}:{})}/>}
  </section>;
}
