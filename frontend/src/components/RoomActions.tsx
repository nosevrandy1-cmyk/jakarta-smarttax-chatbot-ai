"use client";

import {useEffect,useRef,useState} from "react";
import {DotsThreeIcon} from "@phosphor-icons/react/dist/csr/DotsThree";
import {BookmarkSimpleIcon} from "@phosphor-icons/react/dist/csr/BookmarkSimple";
import {PushPinIcon} from "@phosphor-icons/react/dist/csr/PushPin";
import {PencilSimpleIcon} from "@phosphor-icons/react/dist/csr/PencilSimple";
import {TrashIcon} from "@phosphor-icons/react/dist/csr/Trash";

export default function RoomActions({title,saved,pinned,onSave,onPin,onRename,onDelete}:{
  title:string;saved?:boolean;pinned?:boolean;onSave:()=>void;onPin:()=>void;onRename:()=>void;onDelete:()=>void;
}) {
  const [open,setOpen]=useState(false);
  const [position,setPosition]=useState({top:0,left:0});
  const trigger=useRef<HTMLButtonElement>(null),menu=useRef<HTMLDivElement>(null);
  function close(){setOpen(false);trigger.current?.focus();}
  useEffect(()=>{
    if(!open)return;
    menu.current?.querySelector<HTMLButtonElement>("button")?.focus();
    const outside=(event:PointerEvent)=>{if(!menu.current?.contains(event.target as Node)&&!trigger.current?.contains(event.target as Node))setOpen(false);};
    const dismiss=()=>setOpen(false);
    document.addEventListener("pointerdown",outside);window.addEventListener("resize",dismiss);window.addEventListener("scroll",dismiss,true);
    return()=>{document.removeEventListener("pointerdown",outside);window.removeEventListener("resize",dismiss);window.removeEventListener("scroll",dismiss,true);};
  },[open]);
  const actions=[
    {label:saved?"Hapus dari Disimpan":"Simpan percakapan",Icon:BookmarkSimpleIcon,filled:!!saved,iconClass:saved?"jst-saved-icon":undefined,run:onSave},
    {label:pinned?"Lepas sematan":"Sematkan percakapan",Icon:PushPinIcon,filled:!!pinned,iconClass:pinned?"jst-pinned-icon":undefined,run:onPin},
    {label:"Ganti nama",Icon:PencilSimpleIcon,filled:false,iconClass:undefined,run:onRename},
    {label:"Hapus percakapan",Icon:TrashIcon,filled:false,iconClass:undefined,run:onDelete},
  ];
  return <><button ref={trigger} className={`icon-btn jst-room-actions-trigger ${open?"open":""}`} aria-label={`Aksi percakapan: ${title}`} aria-haspopup="menu" aria-expanded={open}
    onClick={()=>{const rect=trigger.current!.getBoundingClientRect();setPosition({left:Math.min(rect.right-190,window.innerWidth-198),top:Math.max(8,Math.min(rect.bottom+4,window.innerHeight-190))});setOpen(!open);}}><DotsThreeIcon size={19}/></button>
    {open&&<div ref={menu} role="menu" aria-label={`Aksi ${title}`} className="jst-room-action-menu" style={{top:position.top,left:Math.max(8,position.left)}}
      onKeyDown={event=>{const items=[...menu.current!.querySelectorAll<HTMLButtonElement>("button")];const index=items.indexOf(document.activeElement as HTMLButtonElement);
        if(event.key==="Escape"){event.preventDefault();event.stopPropagation();close();}
        if(event.key==="ArrowDown"||event.key==="ArrowUp"){event.preventDefault();items[(index+(event.key==="ArrowDown"?1:-1)+items.length)%items.length]?.focus();}
        if(event.key==="Tab")setOpen(false);
      }}>{actions.map(({label,Icon,filled,iconClass,run},index)=><button key={label} role="menuitem" className={index===3?"danger":""} onClick={()=>{close();run();}}><Icon size={16} weight={filled?"fill":"regular"} className={iconClass}/>{label}</button>)}</div>}
  </>;
}
