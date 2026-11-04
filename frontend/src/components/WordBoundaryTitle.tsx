"use client";
import {useLayoutEffect,useRef,useState} from "react";
import {fitTitleToWidth} from "@/lib/titleLayout";

/** Resize-aware ellipsis after the last complete word, without extra API requests. */
export default function WordBoundaryTitle({text}:{text:string}) {
  const ref=useRef<HTMLSpanElement>(null);
  const [fitted,setFitted]=useState({source:text,value:text});
  useLayoutEffect(()=>{
    const element=ref.current;if(!element)return;
    const canvas=document.createElement("canvas");const context=canvas.getContext("2d");
    if(!context)return;
    let frame=0,disposed=false;
    const fit=()=>{
      if(disposed)return;
      const style=getComputedStyle(element);
      context.font=style.font||`${style.fontWeight} ${style.fontSize} ${style.fontFamily}`;
      const spacing=parseFloat(style.letterSpacing)||0;
      const value=fitTitleToWidth(text,element.clientWidth,t=>context.measureText(t).width+Math.max(0,t.length-1)*spacing);
      setFitted(previous=>previous.source===text && previous.value===value?previous:{source:text,value});
    };
    const schedule=()=>{cancelAnimationFrame(frame);frame=requestAnimationFrame(fit);};
    fit();const observer=new ResizeObserver(schedule);observer.observe(element);
    void document.fonts.ready.then(()=>{if(!disposed)schedule();});
    return()=>{disposed=true;observer.disconnect();cancelAnimationFrame(frame);};
  },[text]);
  return <span ref={ref} className="jst-word-title" title={text} aria-label={text}>{fitted.source===text?fitted.value:text}</span>;
}
