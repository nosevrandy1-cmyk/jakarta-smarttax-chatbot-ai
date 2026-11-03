"use client";
import {useEffect,useRef} from "react";

export default function ContinuationOverlay(){
  const root=useRef<HTMLDivElement>(null);
  useEffect(()=>{
    const node=root.current;if(!node)return;
    const focused=document.activeElement as HTMLElement|null;
    // Block keyboard as well as pointer edits while adopting the server snapshot.
    const previous=[...(node.parentElement?.children||[])].filter(el=>el!==node).map(el=>({el:el as HTMLElement,inert:(el as HTMLElement).inert}));
    previous.forEach(({el})=>{el.inert=true;});node.focus();
    return ()=>{previous.forEach(({el,inert})=>{el.inert=inert;});if(focused?.isConnected)focused.focus();};
  },[]);
  return <div ref={root} tabIndex={-1} className="jst-memory-overlay" role="dialog" aria-modal="true" aria-label="Menyiapkan kelanjutan"><div role="status"><span className="jst-page-loader"/>Menyiapkan ringkasan untuk chat baru…</div></div>;
}
