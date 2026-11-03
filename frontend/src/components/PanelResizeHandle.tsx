"use client";

import { useEffect, useRef, useState } from "react";

export function usePanelSize(key: string, initial: number, min: number, max: number) {
  const [size,setSize]=useState(initial);
  const loaded=useRef(false);
  useEffect(() => {
    try {const saved=Number(localStorage.getItem(key));if(saved >= min && saved <= max)setSize(saved);} catch {}
    loaded.current=true;
  },[key,min,max]);
  function update(value: number) {
    const next=Math.round(Math.max(min,Math.min(max,value)));
    setSize(next);
    if(loaded.current)try{localStorage.setItem(key,String(next));}catch{}
  }
  return [size,update] as const;
}

export default function PanelResizeHandle({label,value,min,max,onChange,edge,axis="x"}:{
  label:string;value:number;min:number;max:number;onChange:(size:number)=>void;
  edge:"left"|"right"|"top";axis?:"x"|"y";
}) {
  const drag=useRef<{start:number;size:number}|null>(null);
  const direction=edge === "right" ? 1 : -1;
  function resize(next:number) {
    let limit=max;
    if(axis === "x") {
      const other=document.querySelector<HTMLElement>(edge === "right" ? ".jst-source-panel" : ".sidebar-open");
      limit=Math.min(max,Math.max(min,window.innerWidth-(other?.getBoundingClientRect().width || 0)-360));
    } else limit=Math.min(max,window.innerHeight*.96);
    onChange(Math.max(min,Math.min(limit,next)));
  }
  return <div role="separator" tabIndex={0} aria-label={label} title={label}
    aria-orientation={axis === "x" ? "vertical" : "horizontal"} aria-valuemin={Math.round(min)} aria-valuemax={Math.round(max)} aria-valuenow={Math.round(value)}
    className={`jst-resize-handle edge-${edge}`}
    onPointerDown={event=>{event.preventDefault();drag.current={start:axis === "x" ? event.clientX : event.clientY,size:value};event.currentTarget.setPointerCapture(event.pointerId);}}
    onPointerMove={event=>{if(drag.current)resize(drag.current.size+direction*((axis === "x" ? event.clientX : event.clientY)-drag.current.start));}}
    onPointerUp={event=>{drag.current=null;if(event.currentTarget.hasPointerCapture(event.pointerId))event.currentTarget.releasePointerCapture(event.pointerId);}}
    onPointerCancel={()=>{drag.current=null;}}
    onLostPointerCapture={()=>{drag.current=null;}}
    onKeyDown={event=>{
      const negative=axis === "x" ? "ArrowLeft" : "ArrowUp",positive=axis === "x" ? "ArrowRight" : "ArrowDown";
      if(event.key===negative||event.key===positive){event.preventDefault();resize(value+(event.key===positive?1:-1)*direction*(event.shiftKey?40:16));}
      if(event.key==="Home"){event.preventDefault();resize(min);}if(event.key==="End"){event.preventDefault();resize(max);}
    }}/>;
}
