"use client";

import RoomActions from "@/components/RoomActions";
import PanelResizeHandle, {usePanelSize} from "@/components/PanelResizeHandle";
import { AccountMenu } from "@/components/AuthProvider";
import { apiFetch, ApiRequestLimitError, getChatWaitMs } from "@/lib/api";
import { useServerHistory } from "@/lib/useServerHistory";

import { BookmarkSimpleIcon } from "@phosphor-icons/react/dist/csr/BookmarkSimple";
import { PushPinIcon } from "@phosphor-icons/react/dist/csr/PushPin";
import { hasStartedConversation, orderSidebarConversations } from "@/lib/chatHistoryState";
import { ShareNetworkIcon } from "@phosphor-icons/react/dist/csr/ShareNetwork";
import { SunIcon } from "@phosphor-icons/react/dist/csr/Sun";
import { MoonIcon } from "@phosphor-icons/react/dist/csr/Moon";
import RenameChatDialog from "@/components/RenameChatDialog";
import SourcePanel, { type AnswerReference } from "@/components/SourcePanel";
import React, { useEffect, useRef, useState } from "react";
import { ArrowBendDownRightIcon } from "@phosphor-icons/react/dist/csr/ArrowBendDownRight";
import { ArrowDownIcon } from "@phosphor-icons/react/dist/csr/ArrowDown";
import { ArrowRightIcon } from "@phosphor-icons/react/dist/csr/ArrowRight";
import { ArrowUpIcon } from "@phosphor-icons/react/dist/csr/ArrowUp";
import { ArrowsClockwiseIcon } from "@phosphor-icons/react/dist/csr/ArrowsClockwise";
import { BuildingsIcon } from "@phosphor-icons/react/dist/csr/Buildings";
import { CaretRightIcon } from "@phosphor-icons/react/dist/csr/CaretRight";
import { CaretUpIcon } from "@phosphor-icons/react/dist/csr/CaretUp";
import { CheckIcon } from "@phosphor-icons/react/dist/csr/Check";
import { CoffeeIcon } from "@phosphor-icons/react/dist/csr/Coffee";
import { CopyIcon } from "@phosphor-icons/react/dist/csr/Copy";
import { DropIcon } from "@phosphor-icons/react/dist/csr/Drop";
import { FileTextIcon } from "@phosphor-icons/react/dist/csr/FileText";
import { MagnifyingGlassIcon } from "@phosphor-icons/react/dist/csr/MagnifyingGlass";
import { MonitorIcon } from "@phosphor-icons/react/dist/csr/Monitor";
import { NotePencilIcon } from "@phosphor-icons/react/dist/csr/NotePencil";
import { PencilSimpleIcon } from "@phosphor-icons/react/dist/csr/PencilSimple";
import { SidebarSimpleIcon } from "@phosphor-icons/react/dist/csr/SidebarSimple";
import { StopIcon } from "@phosphor-icons/react/dist/csr/Stop";
import { XIcon } from "@phosphor-icons/react/dist/csr/X";
import {
  CAPABILITY_MODES,
  CapabilityModeCode,
  TAX_THEMES as SCALABLE_TAX_THEMES,
  TaxThemeCode,
  getStartersForThemeAndMode,
} from "@/config/smarttaxConfig";






interface TaxThemeConfig {
  code: TaxThemeCode;
  shortLabel: string;
  label: string;
  desc: string;
  iconColor: string;
  greeting: string;
  subtitle: string;
  placeholder: string;
  suggestions: { title: string; subtitle: string; prompt: string }[];
}

function ThemeIcon({
  code,
  color = "currentColor",
}: {
  code: TaxThemeCode;
  color?: string;
}) {
  switch (code) {
    case "PBB-P2":
      return (
        <BuildingsIcon size={15} weight="regular" aria-hidden="true" color={color} />
      );
    case "PBJT":
      return (
        <CoffeeIcon size={15} weight="regular" aria-hidden="true" color={color} />
      );
    case "BPHTB":
      return (
        <FileTextIcon size={15} weight="regular" aria-hidden="true" color={color} />
      );
    case "REKLAME":
      return (
        <MonitorIcon size={15} weight="regular" aria-hidden="true" color={color} />
      );
    case "PAT":
      return (
        <DropIcon size={15} weight="regular" aria-hidden="true" color={color} />
      );
  }
}

const DKI_TAX_THEMES: Record<TaxThemeCode, TaxThemeConfig> = {
  "PBB-P2": {
    code: "PBB-P2",
    shortLabel: "PBB-P2",
    label: "PBB-P2 (Bumi & Bangunan)",
    desc: "SPPT, NOP, NJOP, Insentif & Tunggakan DKI Jakarta",
    iconColor: "#4da3ff",
    greeting: "Apa yang ingin kamu bahas?",
    subtitle: "Tanyakan informasi dari dokumen proyek yang tersedia.",
    placeholder: "Tulis pertanyaan tentang dokumen atau topik ini...",
    suggestions: [],
  },
  PBJT: {
    code: "PBJT",
    shortLabel: "PBJT",
    label: "PBJT (Restoran, Hotel, Parkir, Hiburan)",
    desc: "Makanan & Minuman, Perhotelan, Parkir, Hiburan & Listrik",
    iconColor: "#ffb224",
    greeting: "Apa yang ingin kamu bahas?",
    subtitle: "Tanyakan informasi dari dokumen proyek yang tersedia.",
    placeholder: "Tulis pertanyaan tentang dokumen atau topik ini...",
    suggestions: [],
  },
  BPHTB: {
    code: "BPHTB",
    shortLabel: "BPHTB",
    label: "BPHTB (Perolehan Hak Tanah/Bangunan)",
    desc: "SSPD Jual Beli (AJB), Waris/Hibah & NPOPTKP DKI Jakarta",
    iconColor: "#b18aff",
    greeting: "Apa yang ingin kamu bahas?",
    subtitle: "Tanyakan informasi dari dokumen proyek yang tersedia.",
    placeholder: "Tulis pertanyaan tentang dokumen atau topik ini...",
    suggestions: [],
  },
  REKLAME: {
    code: "REKLAME",
    shortLabel: "Reklame",
    label: "Pajak Reklame",
    desc: "SKPD Videotron LED, Billboard, NSR & Kawasan Kendali Ketat",
    iconColor: "#ff63b5",
    greeting: "Apa yang ingin kamu bahas?",
    subtitle: "Tanyakan informasi dari dokumen proyek yang tersedia.",
    placeholder: "Tulis pertanyaan tentang dokumen atau topik ini...",
    suggestions: [],
  },
  PAT: {
    code: "PAT",
    shortLabel: "Air Tanah",
    label: "Pajak Air Tanah (PAT)",
    desc: "Pajak Air Tanah dan dokumen terkait",
    iconColor: "#19d4f4",
    greeting: "Apa yang ingin kamu bahas?",
    subtitle: "Tanyakan informasi dari dokumen proyek yang tersedia.",
    placeholder: "Tulis pertanyaan tentang dokumen atau topik ini...",
    suggestions: [],
  },
};

interface ChatMessage {
  failed?: boolean;
  references?: AnswerReference[];
  id: string;
  role: "user" | "assistant";
  content: string;
  thinking?: string;
  statusText?: string;
  isStreaming?: boolean;
  modelUsed?: string;
  durationMs?: number;
  suggestedTheme?: TaxThemeCode;
  followUps?: string[];
  originalQuestion?: string;
}

interface ChatSession {
  pinned?: boolean;
  saved?: boolean;
  lastFailed?: boolean;
  messagesLoaded?: boolean;
  messageCount?: number;
  preview?: string;
  unread?: boolean;
  titleEdited?: boolean;
  id: string;
  title: string;
  theme: TaxThemeCode;
  updatedAt: number;
  messages: ChatMessage[];
}

function renderInline(
  text: string,
  onCopyCode?: (codeText: string) => void
): React.ReactNode[] {
  const parts = text.split(/(\*\*[^*]+\*\*|`[^`]+`|\[\d+(?:\s*,\s*\d+)*\])/g);
  return parts.map((part, i) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return (
        <strong key={i} style={{ color: "var(--text-primary)", fontWeight: 600 }}>
          {renderInline(part.slice(2, -2), onCopyCode)}
        </strong>
      );
    }
    if (part.startsWith("`") && part.endsWith("`")) {
      const cleanCode = part.slice(1, -1);
      return (
        <code
          key={i}
          className="copyable-code"
          title="Klik untuk menyalin nomor/kode ini"
          onClick={() => onCopyCode?.(cleanCode)}
        >
          {cleanCode}
        </code>
      );
    }
    if (/^\[\d+(?:\s*,\s*\d+)*\]$/.test(part)) {
      return <React.Fragment key={i}>{part.slice(1,-1).split(/\s*,\s*/).map((number,index) => <React.Fragment key={number}>{index > 0 ? ", " : ""}<button type="button" className="chat-inline-citation jst-citation-button" data-citation={number} aria-label={`Buka sumber ${number}`}>[{number}]</button></React.Fragment>)}</React.Fragment>;
    }
    return <React.Fragment key={i}>{part}</React.Fragment>;
  });
}

function FormattedMarkdown({
  content,
  isStreaming,
  onCopyCode,
}: {
  content: string;
  isStreaming?: boolean;
  onCopyCode?: (codeText: string) => void;
}) {
  if (!content && isStreaming) {
    return <span className="streaming-dot" />;
  }

  const lines = content.split("\n");
  const elements: React.ReactNode[] = [];
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];

    if (
      line.trim().startsWith("|") &&
      i + 1 < lines.length &&
      lines[i + 1].trim().startsWith("|") &&
      lines[i + 1].includes("---")
    ) {
      const headers = line
        .trim()
        .replace(/^\||\|$/g, "")
        .split("|")
        .map((h) => h.trim());
      i += 2;
      const rows: string[][] = [];
      while (i < lines.length && lines[i].trim().startsWith("|")) {
        const cells = lines[i]
          .trim()
          .replace(/^\||\|$/g, "")
          .split("|")
          .map((c) => c.trim());
        rows.push(cells);
        i++;
      }
      elements.push(
        <div key={`tbl-${i}`} className="gpt-table-wrap">
          <table className="gpt-table">
            <thead>
              <tr>
                {headers.map((h, idx) => (
                  <th key={idx}>{renderInline(h, onCopyCode)}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((r, rIdx) => (
                <tr key={rIdx}>
                  {r.map((c, cIdx) => (
                    <td key={cIdx}>{renderInline(c, onCopyCode)}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
      continue;
    }

    if (line.startsWith("### ")) {
      elements.push(<h3 key={i}>{renderInline(line.slice(4), onCopyCode)}</h3>);
      i++;
      continue;
    }
    if (line.startsWith("## ")) {
      elements.push(<h3 key={i}>{renderInline(line.slice(3), onCopyCode)}</h3>);
      i++;
      continue;
    }

    if (line.startsWith("> ")) {
      elements.push(
        <blockquote key={i}>{renderInline(line.slice(2), onCopyCode)}</blockquote>
      );
      i++;
      continue;
    }

    if (line.trim() === "---") {
      elements.push(
        <hr
          key={i}
          style={{
            border: "none",
            borderTop: "1px solid rgba(var(--chat-ink), 0.1)",
            margin: "14px 0",
          }}
        />
      );
      i++;
      continue;
    }

    if (/^\s*[-*]\s+/.test(line)) {
      const listItems: React.ReactNode[] = [];
      while (i < lines.length && /^\s*[-*]\s+/.test(lines[i])) {
        const itemText = lines[i].replace(/^\s*[-*]\s+/, "");
        const isSub = /^\s{2,}[-*]\s+/.test(lines[i]);
        listItems.push(
          <li
            key={i}
            style={{
              marginLeft: isSub ? "18px" : "0px",
              listStyleType: isSub ? "circle" : "disc",
            }}
          >
            {renderInline(itemText, onCopyCode)}
          </li>
        );
        i++;
      }
      elements.push(<ul key={`ul-${i}`}>{listItems}</ul>);
      continue;
    }

    if (/^\s*\d+\.\s+/.test(line)) {
      const listItems: React.ReactNode[] = [];
      while (i < lines.length && /^\s*\d+\.\s+/.test(lines[i])) {
        const itemText = lines[i].replace(/^\s*\d+\.\s+/, "");
        listItems.push(<li key={i}>{renderInline(itemText, onCopyCode)}</li>);
        i++;
      }
      elements.push(<ol key={`ol-${i}`}>{listItems}</ol>);
      continue;
    }

    if (!line.trim()) {
      i++;
      continue;
    }

    elements.push(
      <p key={i}>
        {renderInline(line, onCopyCode)}
        {isStreaming && i === lines.length - 1 && (
          <span className="streaming-dot" />
        )}
      </p>
    );
    i++;
  }

  return <div className="gpt-markdown">{elements}</div>;
}

export default function TaxAssistantView() {


  const [appearance, setAppearance] = useState<"dark" | "light">("dark");
  useEffect(() => {
    try {
      const saved = localStorage.getItem("jakarta_smarttax_chat_appearance");
      if (saved === "light" || saved === "dark") setAppearance(saved);
    } catch { /* Keep the default when browser storage is unavailable. */ }
  }, []);
  function toggleAppearance() {
    const next = appearance === "dark" ? "light" : "dark";
    setAppearance(next);
    try { localStorage.setItem("jakarta_smarttax_chat_appearance", next); } catch { /* The toggle still works without storage. */ }
  }

  const [sidebarOpen, setSidebarOpen] = useState<boolean>(true);
  const [selectedModel, setSelectedModel] = useState<string>("gemma4:12b");

  useEffect(() => {
    const controller = new AbortController();
    async function loadLocalModels() {
      try {
        const response = await apiFetch(`/api/health`, { signal: controller.signal });
        if (!response.ok) return;
        const health = await response.json();
        const installed: string[] = health.ollama?.installed_local_models || [];
        if (controller.signal.aborted || !installed.length) return;
        const configured = health.ollama?.default_model;
        setSelectedModel(installed.includes(configured) ? configured : installed[0]);
      } catch {
        // Keep the default model if the backend is still starting.
      }
    }
    void loadLocalModels();
    return () => controller.abort();
  }, []);

  const [capabilityMode] =
    useState<CapabilityModeCode>("konsultasi");
  const [themeMenuOpen, setThemeMenuOpen] = useState<boolean>(false);
  const [cmdOpen, setCmdOpen] = useState<boolean>(false);
  const [cmdQuery, setCmdQuery] = useState<string>("");

  const [renamingChat, setRenamingChat] = useState<{ id: string; title: string } | null>(null);
  const { sessions, setSessions, activeSessionId, setActiveSessionId, hydrated, loadError, syncStatus, flush, roomLoadError, retryRoomLoad } = useServerHistory<ChatSession>([
    { id: 'default-session', title: 'Percakapan Baru', theme: 'PBB-P2', updatedAt: Date.now(), messages: [] },
  ]);
  const [homeView,setHomeView]=useState(true);
  const sessionsRef=useRef(sessions);sessionsRef.current=sessions;
  const [historyView, setHistoryView] = useState(false);
  const [savedView,setSavedView]=useState(false);
  const [sidebarWidth,setSidebarWidth]=usePanelSize("jst-sidebar-width",260,220,420);
  const [historyLimit, setHistoryLimit] = useState(20);
  const [sourceSelection, setSourceSelection] = useState<{messageId: string; number?: number} | null>(null);
  useEffect(() => {
    if (!sourceSelection) return;
    const keepMobilePanelsSeparate = () => {if (window.innerWidth < 768) setSidebarOpen(false);};
    keepMobilePanelsSeparate(); window.addEventListener("resize", keepMobilePanelsSeparate);
    return () => window.removeEventListener("resize", keepMobilePanelsSeparate);
  }, [sourceSelection]);
  const activeViewRef = useRef({id: activeSessionId, history: historyView || homeView});
  activeViewRef.current = {id: activeSessionId, history: historyView || homeView};
  const generatingSessionRef = useRef<string | null>(null);
  useEffect(() => {
    if(!hydrated)return;
    const sync=()=>{
      const path=window.location.pathname;
      setHistoryView(path==="/history"||path==="/saved");setSavedView(path==="/saved");setSourceSelection(null);
      if(path==="/"){openBlankScreen(true);return;}
      setHomeView(false);
      if(path==="/chat"){
        const roomId=new URLSearchParams(window.location.search).get("room");
        if(roomId&&sessionsRef.current.some(room=>room.id===roomId))setActiveSessionId(roomId);
        else {openBlankScreen(true);window.history.replaceState(null,"","/");}
      }
    };
    sync();window.addEventListener("popstate",sync);
    return()=>window.removeEventListener("popstate",sync);
  },[hydrated]);
  function openBlankScreen(home:boolean){
    const draft=sessionsRef.current.find(room=>!hasStartedConversation(room));
    const room:ChatSession={id:draft?.id||`session-${Date.now()}`,title:"Chat baru",theme:draft?.theme||"PBB-P2",updatedAt:Date.now(),messages:[],messagesLoaded:true};
    setSessions(previous=>[room,...previous.filter(hasStartedConversation)]);
    setActiveSessionId(room.id);setHomeView(home);setInput("");setSourceSelection(null);setEditingMsgId(null);
  }
  function navigateHistory(open: boolean, saved=false) {
    window.history.pushState(null, "", open ? saved ? "/saved" : "/history" : "/chat");
    setHomeView(false);setSavedView(open && saved);setHistoryView(open); setHistoryLimit(20); setSourceSelection(null);
    closeSidebarOnMobile();
  }
  function openConversation(id: string) {
    setActiveSessionId(id); navigateHistory(false);window.history.replaceState(null,"",`/chat?room=${encodeURIComponent(id)}`); setInput("");
  }
  useEffect(() => {
    setSourceSelection(null);
    const markRead = () => {
      if (document.visibilityState !== "visible" || historyView || homeView) return;
      setSessions(previous => previous.some(room => room.id === activeSessionId && room.unread)
        ? previous.map(room => room.id === activeSessionId ? {...room, unread: false} : room) : previous);
    };
    markRead(); document.addEventListener("visibilitychange", markRead);
    return () => document.removeEventListener("visibilitychange", markRead);
  }, [activeSessionId, historyView, homeView, hydrated, setSessions]);
  const sortedSessions = sessions.filter(hasStartedConversation).sort((a,b) => b.updatedAt - a.updatedAt || a.id.localeCompare(b.id));
  const recentSessions = orderSidebarConversations(sortedSessions).slice(0,10);
  const historyMatches = orderSidebarConversations(sortedSessions).filter(room => !savedView || room.saved);
  function toggleRoomFlag(id: string, flag: "pinned" | "saved") {
    setSessions(previous => previous.map(room => room.id === id && hasStartedConversation(room) ? {...room, [flag]: !room[flag]} : room));
  }
  function openSavedChats() {navigateHistory(true,true);}
  function sidebarRoom(room: ChatSession) {
    return <div key={room.id} className={`session-item ${!homeView && !historyView && room.id === activeSessionId ? "active" : ""} ${room.unread ? "has-unread" : ""}`}>
      <button className="jst-room-open" onClick={() => openConversation(room.id)} title={room.title}><span>{room.title}</span>
        {roomStatus(room)}</button>
      <RoomActions title={room.title} saved={room.saved} pinned={room.pinned}
        onSave={()=>toggleRoomFlag(room.id,"saved")} onPin={()=>toggleRoomFlag(room.id,"pinned")}
        onRename={()=>setRenamingChat({id:room.id,title:room.title})}
        onDelete={()=>deleteSession(room.id)}/>
    </div>;
  }
  function roomStatus(room: ChatSession) {
    if (room.messages.some(message => message.isStreaming)) return <span className="room-status processing" role="status" aria-label="Sedang memproses" title="Sedang memproses" />;
    if (room.messagesLoaded === false ? room.lastFailed : room.messages.at(-1)?.failed) return <span className="room-status failed" role="img" aria-label="Jawaban gagal" title="Jawaban gagal">!</span>;
    if (room.unread) return <span className="room-status unread" role="img" aria-label="Jawaban baru belum dilihat" title="Jawaban baru belum dilihat" />;
    return null;
  }
  const [input, setInput] = useState<string>("");
  const [chatWaitSeconds,setChatWaitSeconds]=useState(0);
  useEffect(()=>{
    const update=()=>setChatWaitSeconds(Math.ceil(getChatWaitMs()/1000));
    update();const timer=setInterval(update,1000);
    window.addEventListener('jst-api-cooldown',update);window.addEventListener('storage',update);
    return()=>{clearInterval(timer);window.removeEventListener('jst-api-cooldown',update);window.removeEventListener('storage',update);};
  },[]);
  const [isGenerating, setIsGenerating] = useState<boolean>(false);
  const [copiedId, setCopiedId] = useState<string>("");

  const [editingMsgId, setEditingMsgId] = useState<string | null>(null);
  const [editingText, setEditingText] = useState<string>("");

  const [toast, setToast] = useState<{
    message: string;
    undoSession?: ChatSession;
  } | null>(null);

  const [showScrollBottom, setShowScrollBottom] = useState<boolean>(false);
  const userScrolledUpRef = useRef<boolean>(false);

  const abortControllerRef = useRef<AbortController | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const scrollContainerRef = useRef<HTMLDivElement | null>(null);
  const chatBottomRef = useRef<HTMLDivElement | null>(null);
  const themeDropdownRef = useRef<HTMLDivElement | null>(null);
  const toastTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const lastNewChatAtRef = useRef<number>(0);

  const activeSession =
    sessions.find((s) => s.id === activeSessionId) || sessions[0];
  const currentTheme: TaxThemeCode = activeSession.theme || "PBB-P2";
  const themeConfig = DKI_TAX_THEMES[currentTheme];
  const scalableTheme =
    SCALABLE_TAX_THEMES.find((t) => t.code === currentTheme) ||
    SCALABLE_TAX_THEMES[0];
  const activeStarters = getStartersForThemeAndMode(
    scalableTheme,
    capabilityMode
  );
  const activeModeInfo =
    CAPABILITY_MODES.find((m) => m.code === capabilityMode) ||
    CAPABILITY_MODES[0];

  useEffect(() => {
    if (typeof window !== "undefined" && window.innerWidth < 768) {
      setSidebarOpen(false);
    }
  }, []);

  useEffect(() => {
    if (!userScrolledUpRef.current) {
      chatBottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [activeSession.messages]);

  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setCmdOpen((v) => !v);
        setCmdQuery("");
      } else if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "b") {
        e.preventDefault();
        setSidebarOpen((v) => !v);
      } else if (e.key === "Escape") {
        if (cmdOpen) setCmdOpen(false);
        else if (themeMenuOpen) setThemeMenuOpen(false);
        else if (editingMsgId) setEditingMsgId(null);
        else if (sourceSelection) setSourceSelection(null);
        else if (isGenerating) stopGeneration();
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [cmdOpen, themeMenuOpen, editingMsgId, isGenerating, sourceSelection]);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (
        themeDropdownRef.current &&
        !themeDropdownRef.current.contains(e.target as Node)
      ) {
        setThemeMenuOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  function closeSidebarOnMobile() {
    if (typeof window !== "undefined" && window.innerWidth < 768) {
      setSidebarOpen(false);
    }
  }

  function showToastMessage(msg: string, undoSession?: ChatSession) {
    if (toastTimeoutRef.current) clearTimeout(toastTimeoutRef.current);
    setToast({ message: msg, undoSession });
    toastTimeoutRef.current = setTimeout(() => {
      setToast(null);
    }, 4000);
  }

  function handleScrollArea() {
    const el = scrollContainerRef.current;
    if (!el) return;
    const distanceFromBottom =
      el.scrollHeight - el.scrollTop - el.clientHeight;
    const isUp = distanceFromBottom > 120;
    userScrolledUpRef.current = isUp;
    setShowScrollBottom(isUp);
  }

  function scrollToBottomNow() {
    userScrolledUpRef.current = false;
    setShowScrollBottom(false);
    chatBottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }

  function switchTheme(newTheme: TaxThemeCode) {
    setThemeMenuOpen(false);
    setSessions((prev) =>
      prev.map((s) =>
        s.id === activeSessionId ? { ...s, theme: newTheme } : s
      )
    );
    setTimeout(() => textareaRef.current?.focus(), 40);
  }

  function createNewChat(themeOverride?:TaxThemeCode){
    const now=Date.now();if(now-lastNewChatAtRef.current<400)return;lastNewChatAtRef.current=now;
    window.history.pushState(null,"","/");setHistoryView(false);setSavedView(false);openBlankScreen(true);
    if(themeOverride)setSessions(previous=>previous.map(room=>!hasStartedConversation(room)?{...room,theme:themeOverride}:room));
    closeSidebarOnMobile();setTimeout(()=>textareaRef.current?.focus(),50);
  }

  function deleteSession(id: string, e?: React.MouseEvent) {
    e?.stopPropagation();
    if (generatingSessionRef.current === id) { showToastMessage("Hentikan jawaban sebelum menghapus percakapan ini."); return; }
    const target = sessions.find((s) => s.id === id);
    setSessions((prev) => {
      const filtered = prev.filter((s) => s.id !== id);
      if (filtered.length === 0) {
        const fallback: ChatSession = {
          id: `session-${Date.now()}`,
          title: "Percakapan Baru",
          theme: currentTheme,
          updatedAt: Date.now(),
          messages: [],
        };
        setActiveSessionId(fallback.id);
        return [fallback];
      }
      if (activeSessionId === id) {
        setActiveSessionId(filtered[0].id);
      }
      return filtered;
    });
    if (target) {
      showToastMessage("Percakapan dihapus", target);
    }
  }

  function undoDeleteSession() {
    if (!toast?.undoSession) return;
    const restored = toast.undoSession;
    setSessions((prev) => [restored, ...prev]);
    setActiveSessionId(restored.id);
    setToast(null);
  }

  function stopGeneration() {
    const owner = generatingSessionRef.current;
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setSessions((prev) =>
      prev.map((s) =>
        s.id === owner
          ? {
              ...s,
              messages: s.messages.map((m) =>
                m.isStreaming
                  ? { ...m, content: m.content.trim() ? m.content + "\n\nRespons dihentikan oleh pengguna." : "Respons dihentikan oleh pengguna.", isStreaming: false, statusText: undefined }
                  : m
              ),
            }
          : s
      )
    );
  }

  async function sendPrompt(
    promptText?: string,
    themeOverride?: TaxThemeCode
  ) {
    const query = (promptText ?? input).trim();
    if (!query || isGenerating || generatingSessionRef.current || activeSession.messagesLoaded === false) return;
    const wait=getChatWaitMs();if(wait>0){showToastMessage(`Tunggu ${Math.ceil(wait/1000)} detik sebelum mengirim pesan lagi.`);return;}

    if(homeView || !hasStartedConversation(activeSession)){
      setHomeView(false);window.history.pushState(null,"",`/chat?room=${encodeURIComponent(activeSessionId)}`);
    }
    const effectiveTheme = themeOverride || currentTheme;
    userScrolledUpRef.current = false;
    setShowScrollBottom(false);

    const userMsg: ChatMessage = {
      id: `user-${Date.now()}`,
      role: "user",
      content: query,
    };
    const assistantMsgId = `assistant-${Date.now() + 1}`;
    const placeholderAssistant: ChatMessage = {
      id: assistantMsgId,
      role: "assistant",
      content: "",
      statusText: "Menghubungi model lokal…",
      isStreaming: true,
      originalQuestion: query,
    };

    const historyForApi = activeSession.messages
      .filter((m) => m.content.trim() && !m.isStreaming && !m.failed)
      .slice(-6)
      .map((m) => ({ role: m.role, content: m.content }));

    setSessions((prev) =>
      prev.map((s) => {
        if (s.id !== activeSessionId) return s;
        const isFirst = s.messages.length === 0;
        return {
          ...s,
          theme: effectiveTheme,
          title: isFirst && !s.titleEdited ? query.slice(0, 34) : s.title,
          updatedAt: Date.now(),
          messages: [...s.messages, userMsg, placeholderAssistant],
        };
      })
    );

    if (!promptText) {
      setInput("");
      if (textareaRef.current) {
        textareaRef.current.style.height = "auto";
      }
    }

    setIsGenerating(true);
    generatingSessionRef.current = activeSessionId;
    let completed = false;
    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      const response = await apiFetch(`/api/chat/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: query,
          model: selectedModel,
          tema_pajak: effectiveTheme,
          mode_kapabilitas: capabilityMode,
          history: historyForApi,
        }),
        signal: controller.signal,
      });

      if (!response.ok || !response.body) {
        throw new Error(response.status >= 500 ? "Layanan sedang sibuk. Coba lagi sebentar." : `Permintaan belum berhasil (HTTP ${response.status}).`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const rawLine of lines) {
          if (!rawLine.trim()) continue;
          let evt: any;
          try {
            evt = JSON.parse(rawLine);
          } catch {
            continue;
          }

          if (evt.type === "error") {
            throw new Error(evt.text || "Model lokal tidak dapat dihubungi.");
          }
          if (evt.type === "done") completed = true;
          setSessions((prev) =>
            prev.map((s) => {
              if (s.id !== activeSessionId) return s;
              return {
                ...s,
                ...(evt.type === "done" ? {updatedAt: Date.now(), unread: activeViewRef.current.id !== s.id || activeViewRef.current.history || document.visibilityState !== "visible"} : {}),
                messages: s.messages.map((m) => {
                  if (m.id !== assistantMsgId) return m;
                  if (evt.type === "status") {
                    return { ...m, statusText: evt.text };
                  }
                  if (evt.type === "sources" && evt.suggested_theme) {
                    return {
                      ...m,
                      suggestedTheme: evt.suggested_theme as TaxThemeCode,
                    };
                  }
                  if (evt.type === "thinking") {
                    return {
                      ...m,
                      statusText: "Model sedang memproses jawaban…",
                      thinking: (m.thinking || "") + (evt.delta || ""),
                    };
                  }
                  if (evt.type === "token") {
                    return {
                      ...m,
                      statusText: undefined,
                      content: m.content + (evt.delta || ""),
                    };
                  }
                  if (evt.type === "done") {
                    return {
                      ...m,
                      isStreaming: false,
                      statusText: undefined,
                      modelUsed: evt.model_used,
                      references: evt.references || [],
                      content: typeof evt.answer === "string" ? evt.answer : m.content,
                      durationMs: evt.duration_ms,
                      suggestedTheme:
                        (evt.suggested_theme as TaxThemeCode) ||
                        m.suggestedTheme,
                      followUps: evt.follow_ups || [],
                    };
                  }
                  return m;
                }),
              };
            })
          );
        }
      }
      if (!completed) throw new Error("Jawaban terhenti sebelum selesai. Silakan coba lagi.");
    } catch (err: any) {
      if (err?.name !== "AbortError") {
        setSessions((prev) =>
          prev.map((s) =>
            s.id === activeSessionId
              ? {
                  ...s,
                  messages: s.messages.map((m) =>
                    m.id === assistantMsgId
                      ? {
                          ...m,
                          failed: true,
                          isStreaming: false,
                          statusText: undefined,
                          content:
                            m.content ||
                            (err instanceof ApiRequestLimitError ? err.message : err instanceof TypeError ? "Belum dapat terhubung ke server. Periksa koneksi lalu coba lagi." : err?.message || "Jawaban belum dapat diselesaikan. Coba lagi."),
                        }
                      : m
                  ),
                }
              : s
          )
        );
      }
    } finally {
      setSessions(previous => previous.map(room => room.id === activeSessionId
        ? {...room, messages: room.messages.map(message => message.id === assistantMsgId ? {...message, content: message.content.trim() ? message.content : controller.signal.aborted ? "Respons dihentikan oleh pengguna." : "Jawaban belum tersedia. Silakan coba lagi.", isStreaming: false, statusText: undefined} : message)} : room));
      generatingSessionRef.current = null;
      setIsGenerating(false);
      abortControllerRef.current = null;
    }
  }

  function submitEditedMessage(msgIndex: number) {
    const trimmed = editingText.trim();
    if (!trimmed || isGenerating) return;
    setEditingMsgId(null);
    setSessions((prev) =>
      prev.map((s) =>
        s.id === activeSessionId
          ? { ...s, messages: s.messages.slice(0, msgIndex) }
          : s
      )
    );
    setTimeout(() => sendPrompt(trimmed), 30);
  }

  function switchAndRetryQuestion(
    targetTheme: TaxThemeCode,
    questionText?: string
  ) {
    if (isGenerating) return;
    const q = questionText || "";
    if (!q) {
      switchTheme(targetTheme);
      return;
    }
    setSessions((prev) =>
      prev.map((s) =>
        s.id === activeSessionId
          ? {
              ...s,
              theme: targetTheme,
              messages: s.messages.slice(0, Math.max(0, s.messages.length - 2)),
            }
          : s
      )
    );
    setTimeout(() => sendPrompt(q, targetTheme), 40);
  }

  function regenerateLastResponse() {
    if (isGenerating) return;
    const msgs = activeSession.messages;
    const lastUserIdx = [...msgs]
      .reverse()
      .findIndex((m) => m.role === "user");
    if (lastUserIdx === -1) return;
    const actualIdx = msgs.length - 1 - lastUserIdx;
    const lastUserQuestion = msgs[actualIdx].content;

    setSessions((prev) =>
      prev.map((s) =>
        s.id === activeSessionId
          ? { ...s, messages: s.messages.slice(0, actualIdx) }
          : s
      )
    );
    setTimeout(() => sendPrompt(lastUserQuestion), 30);
  }

  function copyMessage(m: ChatMessage) {
    navigator.clipboard.writeText(m.content);
    setCopiedId(m.id);
    setTimeout(() => setCopiedId(""), 2000);
  }

  function handleCopyInlineCode(codeText: string) {
    navigator.clipboard.writeText(codeText);
    showToastMessage(`Disalin: ${codeText}`);
  }

  useEffect(() => () => abortControllerRef.current?.abort(), []);

  const isChatEmpty = activeSession.messagesLoaded !== false && activeSession.messages.length === 0;

  if (!hydrated) return <main className="auth-screen"><section className={loadError ? "auth-card" : "jst-loading-shell"}>
    {loadError ? <h1>Riwayat belum dapat dimuat</h1> : <span className="jst-page-loader" role="status" aria-label="Memuat percakapan"/>}
    {loadError && <><p>Periksa koneksi lalu muat ulang. Riwayat di server tidak akan ditimpa.</p><button className="auth-google-button" onClick={() => window.location.reload()}>Muat ulang</button></>}
  </section></main>;


  return (
    <div className="app-layout" data-chat-theme={appearance}
      onDragOver={(event) => {
        if (Array.from(event.dataTransfer.types).includes("Files")) event.preventDefault();
      }}
      onDrop={(event) => {
        if (Array.from(event.dataTransfer.types).includes("Files")) {
          event.preventDefault();
          showToastMessage("Chat hanya menerima teks. Upload dokumen tersedia di dashboard developer.");
        }
      }}
      onPaste={(event) => {
        if (Array.from(event.clipboardData.items).some(item => item.kind === "file")) {
          event.preventDefault();
          showToastMessage("Lampiran tidak didukung di chat. Silakan tulis pertanyaan dalam teks.");
        }
      }}>
<div className="history-sync-status" role="status">{syncStatus}<button type="button" onClick={() => { void flush().catch(() => {}); }}>Simpan</button></div>
      {renamingChat && <RenameChatDialog key={renamingChat.id} title={renamingChat.title}
        onCancel={() => setRenamingChat(null)} onSave={name => {
          setSessions(previous => previous.map(session => session.id === renamingChat.id
            ? { ...session, title: name, titleEdited: true, updatedAt: Date.now() } : session));
          setRenamingChat(null);
        }} />}

      {/* Mobile Drawer Backdrop */}
      {sidebarOpen && (
        <div
          className="mobile-backdrop"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Navigation Sidebar */}
      <aside
        className={`sidebar-shell ${
          sidebarOpen ? "sidebar-open" : "sidebar-closed"
        }`}
        style={{"--jst-sidebar-width":`${sidebarWidth}px`} as React.CSSProperties}
      >
        <PanelResizeHandle label="Atur lebar sidebar" value={sidebarWidth} min={220} max={420} edge="right" onChange={setSidebarWidth}/>
        <div className="jst-sidebar-brand"><strong>Jakarta SmartTax</strong><button className="icon-btn" title="Tutup sidebar" aria-label="Tutup sidebar" onClick={() => setSidebarOpen(false)}><SidebarSimpleIcon size={19}/></button></div>
        <button className="jst-nav-button" onClick={() => createNewChat()}><NotePencilIcon size={18}/>Chat baru</button>
        <button className="jst-nav-button" onClick={() => {setCmdQuery("");setCmdOpen(true);}}><MagnifyingGlassIcon size={18}/>Cari percakapan</button>
        <button className="jst-nav-button" onClick={openSavedChats}><BookmarkSimpleIcon size={18} weight="regular"/>Disimpan</button>
        <nav className="jst-recent-list" aria-label="Percakapan terbaru">
          <div className="jst-sidebar-label">Terbaru</div>
          {recentSessions.map(sidebarRoom)}
          {!sortedSessions.length && <p className="jst-sidebar-empty">Percakapanmu akan muncul di sini setelah mengirim pesan.</p>}
        </nav>
        <button className="jst-nav-button view-all" onClick={() => {navigateHistory(true);}}>Lihat semua<ArrowRightIcon size={16}/></button>
        <div
          style={{
            borderTop: "1px solid rgba(var(--chat-ink), 0.06)",
            paddingTop: "10px",
            marginTop: "8px",
            minWidth: "0",
          }}
        >
          <div className="jst-account-theme"><AccountMenu />          <button type="button" className="chat-appearance-toggle" onClick={toggleAppearance}
            aria-label={appearance === "dark" ? "Aktifkan mode terang" : "Aktifkan mode gelap"}
            title={appearance === "dark" ? "Aktifkan mode terang" : "Aktifkan mode gelap"}>
            {appearance === "dark" ? <SunIcon size={17} aria-hidden="true" /> : <MoonIcon size={17} aria-hidden="true" />}
          </button></div>
        </div>
      </aside>

      {/* Main Conversation Canvas */}
      <div className="main-canvas">
        <header className="top-header">
          <div style={{ display: "flex", alignItems: "center", gap: "4px" }}>
            {!sidebarOpen && (
              <>
                <button
                  onClick={() => setSidebarOpen(true)}
                  className="icon-btn"
                  title="Buka Sidebar (⌘B)"
                >
                  <SidebarSimpleIcon size={19} weight="regular" aria-hidden="true" />{sessions.some(room => room.unread) && <span className="sidebar-unread-badge" aria-label="Ada jawaban baru"/>}
                </button>
                <button
                  onClick={() => createNewChat()}
                  className="icon-btn"
                  title="Percakapan Baru"
                >
                  <NotePencilIcon size={19} weight="regular" aria-hidden="true" />
                </button>
              </>
            )}


          </div>

          <h1 className="jst-header-title" title={homeView ? "Jakarta SmartTax" : historyView ? savedView ? "Disimpan" : "Semua percakapan" : activeSession.title}>{homeView ? "Jakarta SmartTax" : historyView ? savedView ? "Disimpan" : "Semua percakapan" : isChatEmpty ? "Chat baru" : activeSession.title}</h1>
          <div className="jst-header-actions">
          <button className="jst-share-button" disabled aria-label="Bagikan"><ShareNetworkIcon size={15}/>Bagikan</button>
</div>
        </header>

        {historyView && <section className="jst-history-page" aria-label={savedView ? "Percakapan disimpan" : "Semua percakapan"}>
          <div className="jst-history-heading"><div><h2>{savedView ? "Disimpan" : "Semua percakapan"}</h2><p>{savedView ? "Percakapan yang kamu tandai untuk dibaca kembali." : "Temukan kembali pembahasan yang ingin dilanjutkan."}</p></div><button className="jst-nav-button" onClick={() => createNewChat()}><NotePencilIcon size={18}/>Chat baru</button></div>
          <p className="jst-history-count">{historyMatches.length} percakapan</p>
          {!historyMatches.length && <p className="jst-history-empty">{savedView ? "Belum ada percakapan yang disimpan." : "Belum ada percakapan. Mulai chat baru untuk berdiskusi."}</p>}
          {historyMatches.slice(0,historyLimit).map(room => <article className="jst-history-row" key={room.id}>
            <button className="jst-history-open" onClick={() => openConversation(room.id)}><span className="jst-history-row-title">{room.title}{roomStatus(room)}</span><span className="jst-history-preview">{room.messages.filter(message => message.role === "user").at(-1)?.content || room.preview || "Belum ada pesan"}</span><time>{new Date(room.updatedAt).toLocaleDateString("id-ID",{day:"numeric",month:"short",year:"numeric"})}</time></button>
            <div className="jst-history-row-actions"><button className={`icon-btn jst-flag-button ${room.saved ? "is-saved" : ""}`} title={room.saved ? "Hapus dari Disimpan" : "Simpan percakapan"} aria-label={`${room.saved ? "Batal simpan" : "Simpan"} ${room.title}`} aria-pressed={!!room.saved} onClick={() => toggleRoomFlag(room.id,"saved")}><BookmarkSimpleIcon size={17} weight={room.saved ? "fill" : "regular"}/></button>
            <button className={`icon-btn jst-flag-button ${room.pinned ? "is-pinned" : ""}`} title={room.pinned ? "Lepas sematan" : "Sematkan percakapan"} aria-label={`${room.pinned ? "Lepas sematan" : "Sematkan"} ${room.title}`} aria-pressed={!!room.pinned} onClick={() => toggleRoomFlag(room.id,"pinned")}><PushPinIcon size={17} weight={room.pinned ? "fill" : "regular"}/></button>
            <button className="icon-btn" title="Ganti nama" aria-label={`Ganti nama ${room.title}`} onClick={() => setRenamingChat({id:room.id,title:room.title})}><PencilSimpleIcon size={17}/></button>
            <button className="icon-btn" title="Hapus" aria-label={`Hapus ${room.title}`} onClick={event => deleteSession(room.id,event)}><XIcon size={17}/></button></div>
          </article>)}
          {historyMatches.length > historyLimit && <button className="jst-load-more" onClick={() => setHistoryLimit(limit => limit + 20)}>Tampilkan 20 berikutnya</button>}
        </section>}
        <div hidden={historyView} className="jst-conversation-body">
        <div
          ref={scrollContainerRef}
          onScroll={handleScrollArea}
          key={`${activeSessionId}-${currentTheme}-${capabilityMode}`}
          style={{
            flex: 1,
            overflowY: "auto",
            display: "flex",
            flexDirection: "column",
          }}
        >
          {activeSession.messagesLoaded === false ? <div className="jst-history-empty" role="status" style={{padding:32,textAlign:"center"}}>{roomLoadError || <span className="jst-page-loader" role="status" aria-label="Memuat percakapan"/>}{roomLoadError && <button className="jst-load-more" onClick={retryRoomLoad}>Coba lagi</button>}</div> : isChatEmpty ? (
            <div className="empty-hero">
              <h2 className="hero-title">{themeConfig.greeting}</h2>
              <p className="hero-subtitle">{activeModeInfo.description}</p>

              <div className="chip-row">
                {(Object.keys(DKI_TAX_THEMES) as TaxThemeCode[]).map((code) => {
                  const t = DKI_TAX_THEMES[code];
                  const isActive = currentTheme === code;
                  return (
                    <button
                      key={code}
                      type="button"
                      onClick={() => switchTheme(code)}
                      className={`chatgpt-chip ${isActive ? "active" : ""}`}
                    >
                      <ThemeIcon code={code} color={t.iconColor} />
                      <span>{t.shortLabel}</span>
                    </button>
                  );
                })}
              </div>

              <div className="suggestion-grid">
                {activeStarters.map((card, i) => (
                  <button
                    key={`${currentTheme}-${capabilityMode}-${i}`}
                    onClick={() => sendPrompt(card.prompt)}
                    className="suggestion-card"
                    style={{ animationDelay: `${i * 45}ms` }}
                  >
                    <div
                      style={{
                        fontSize: "13.5px",
                        fontWeight: 500,
                        color: "var(--text-primary)",
                      }}
                    >
                      {card.title}
                    </div>
                    <div
                      style={{
                        fontSize: "12px",
                        color: "var(--text-muted)",
                        marginTop: "2px",
                      }}
                    >
                      {card.desc}
                    </div>
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div
              style={{
                maxWidth: "740px",
                width: "100%",
                margin: "0 auto",
                padding: "18px 16px 32px",
                display: "flex",
                flexDirection: "column",
                gap: "24px",
              }}
            >
              {activeSession.messages.map((m, idx) => (
                <div
                  key={m.id}
                  className={
                    m.role === "user"
                      ? "msg-user-enter"
                      : "msg-assistant-enter"
                  }
                  style={{ display: "flex", flexDirection: "column" }}
                >
                  {m.role === "user" ? (
                    editingMsgId === m.id ? (
                      <div
                        style={{
                          alignSelf: "flex-end",
                          width: "100%",
                          maxWidth: "88%",
                          background: "var(--bg-surface)",
                          border: "1px solid rgba(var(--chat-ink), 0.16)",
                          borderRadius: "18px",
                          padding: "12px 14px",
                          display: "flex",
                          flexDirection: "column",
                          gap: "10px",
                        }}
                      >
                        <textarea
                          rows={2}
                          value={editingText}
                          onChange={(e) => setEditingText(e.target.value)}
                          style={{
                            width: "100%",
                            background: "transparent",
                            border: "none",
                            resize: "none",
                            color: "var(--text-primary)",
                            fontSize: "15px",
                            lineHeight: 1.5,
                          }}
                          autoFocus
                        />
                        <div
                          style={{
                            display: "flex",
                            justifyContent: "flex-end",
                            gap: "8px",
                          }}
                        >
                          <button
                            type="button"
                            onClick={() => setEditingMsgId(null)}
                            className="action-bar-btn"
                            style={{ padding: "6px 12px" }}
                          >
                            Batal
                          </button>
                          <button
                            type="button"
                            onClick={() => submitEditedMessage(idx)}
                            style={{
                              background: "var(--text-primary)",
                              color: "var(--bg-sidebar)",
                              border: "none",
                              borderRadius: "999px",
                              padding: "6px 14px",
                              fontSize: "12.5px",
                              fontWeight: 600,
                              cursor: "pointer",
                            }}
                          >
                            Kirim Ulang
                          </button>
                        </div>
                      </div>
                    ) : (
                      <div className="user-msg-row">
                        <button
                          type="button"
                          onClick={() => {
                            setEditingMsgId(m.id);
                            setEditingText(m.content);
                          }}
                          className="user-edit-trigger"
                          title="Edit pertanyaan"
                        >
                          <PencilSimpleIcon size={14} weight="regular" aria-hidden="true" />
                        </button>
                        <div
                          style={{
                            maxWidth: "82%",
                            background: "var(--bg-surface)",
                            color: "var(--text-primary)",
                            padding: "11px 16px",
                            borderRadius: "20px",
                            fontSize: "15px",
                            lineHeight: 1.55,
                            whiteSpace: "pre-wrap",
                          }}
                        >
                          {m.content}
                        </div>
                      </div>
                    )
                  ) : (
                    <div
                      style={{
                        display: "flex",
                        alignItems: "flex-start",
                        gap: "12px",
                        width: "100%",
                      }}
                    >
                      <div
                        style={{
                          width: "28px",
                          height: "28px",
                          minWidth: "28px",
                          borderRadius: "999px",
                          background: "var(--bg-raised)",
                          border: "1px solid rgba(var(--chat-ink), 0.12)",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          marginTop: "2px",
                        }}
                      >
                        <ThemeIcon
                          code={currentTheme}
                          color={themeConfig.iconColor}
                        />
                      </div>

                      <div style={{ flex: 1, minWidth: 0 }}>
                        {m.statusText && (
                          <div
                            style={{
                              display: "inline-flex",
                              alignItems: "center",
                              gap: "8px",
                              fontSize: "13.5px",
                              marginBottom: "6px",
                            }}
                          >
                            <span
                              style={{
                                width: "7px",
                                height: "7px",
                                borderRadius: "999px",
                                background: "var(--text-primary)",
                                animation: "pulseDot 1s infinite ease-in-out",
                              }}
                            />
                            <span className="shimmer-status">{m.statusText}</span>
                          </div>
                        )}

                        {m.thinking && (
                          <details
                            open={m.isStreaming}
                            style={{
                              marginBottom: "10px",
                              background: "rgba(var(--chat-ink), 0.03)",
                              border: "1px solid rgba(var(--chat-ink), 0.08)",
                              borderRadius: "10px",
                              padding: "8px 12px",
                              fontSize: "12.5px",
                              color: "var(--text-secondary)",
                            }}
                          >
                            <summary
                              className="thinking-summary"
                              style={{
                                cursor: "pointer",
                                userSelect: "none",
                                display: "inline-flex",
                                alignItems: "center",
                                gap: "6px",
                              }}
                            >
                              <CaretRightIcon size={13} className="thinking-caret" aria-hidden="true" />
                              <span style={{ fontWeight: 600, color: "var(--text-secondary)" }}>
                                {m.isStreaming && !m.content
                                  ? "Sedang menelaah regulasi & dasar hukum..."
                                  : "Alur Penalaran"}
                              </span>
                            </summary>
                            <div
                              style={{
                                marginTop: "6px",
                                whiteSpace: "pre-wrap",
                                lineHeight: 1.55,
                                color: "var(--text-secondary)",
                              }}
                            >
                              {m.thinking}
                            </div>
                          </details>
                        )}

                        <div onClick={event => { const marker = (event.target as HTMLElement).closest("[data-citation]"); if (marker && m.references?.some(reference => reference.number === Number(marker.getAttribute("data-citation")))) {closeSidebarOnMobile();setSourceSelection({messageId:m.id,number:Number(marker.getAttribute("data-citation"))});}}}>
                        <FormattedMarkdown
                          content={m.content}
                          isStreaming={m.isStreaming && !m.statusText}
                          onCopyCode={handleCopyInlineCode}
                        /></div>

                        {!m.isStreaming && !!m.references?.length && <button className="jst-sources-trigger" onClick={() => {closeSidebarOnMobile();setSourceSelection({messageId:m.id});}}><FileTextIcon size={15}/>Sumber · {new Set(m.references.map(reference => reference.document_name)).size}</button>}

                        {!m.isStreaming &&
                          m.suggestedTheme &&
                          m.suggestedTheme !== currentTheme && (
                            <div>
                              <button
                                type="button"
                                onClick={() =>
                                  switchAndRetryQuestion(
                                    m.suggestedTheme!,
                                    m.originalQuestion
                                  )
                                }
                                className="cross-theme-btn"
                              >
                                <ThemeIcon
                                  code={m.suggestedTheme}
                                  color={
                                    DKI_TAX_THEMES[m.suggestedTheme].iconColor
                                  }
                                />
                                <span>
                                  Pindah ke{" "}
                                  {DKI_TAX_THEMES[m.suggestedTheme].shortLabel} &
                                  Tanya Ulang
                                </span>
                                <ArrowRightIcon size={14} color="var(--text-muted)" aria-hidden="true" />
                              </button>
                            </div>
                          )}

                        {!m.isStreaming && m.content && (
                          <div
                            style={{
                              display: "flex",
                              alignItems: "center",
                              gap: "4px",
                              marginTop: "8px",
                            }}
                          >
                            <button
                              onClick={() => copyMessage(m)}
                              className="action-bar-btn"
                              title="Salin jawaban"
                            >
                              {copiedId === m.id ? (
                                <><CheckIcon size={14} aria-hidden="true" /><span>Tersalin</span></>
                              ) : (
                                <>
                                  <CopyIcon size={14} weight="regular" aria-hidden="true" />
                                  <span>Salin</span>
                                </>
                              )}
                            </button>

                            {idx === activeSession.messages.length - 1 && (
                              <button
                                onClick={regenerateLastResponse}
                                disabled={isGenerating || chatWaitSeconds > 0}
                                className="action-bar-btn"
                                title="Ulangi jawaban"
                              >
                                <ArrowsClockwiseIcon size={14} weight="regular" aria-hidden="true" />
                                <span>Ulangi</span>
                              </button>
                            )}

                            {typeof m.durationMs === "number" && m.durationMs > 0 && (
                              <span
                                style={{
                                  fontSize: "11.5px",
                                  color: "var(--text-muted)",
                                  marginLeft: "6px",
                                }}
                              >
                                {(m.durationMs / 1000).toFixed(1)} dtk
                              </span>
                            )}
                          </div>
                        )}

                        {!m.isStreaming &&
                          idx === activeSession.messages.length - 1 &&
                          !m.suggestedTheme &&
                          m.followUps &&
                          m.followUps.length > 0 && (
                            <div
                              style={{
                                display: "flex",
                                flexDirection: "column",
                                alignItems: "flex-start",
                                gap: "6px",
                                marginTop: "14px",
                              }}
                            >
                              <span
                                style={{
                                  fontSize: "11.5px",
                                  color: "var(--text-muted)",
                                  fontWeight: 500,
                                }}
                              >
                                Tindak lanjut yang disarankan
                              </span>
                              <div
                                style={{
                                  display: "flex",
                                  flexWrap: "wrap",
                                  gap: "6px",
                                }}
                              >
                                {m.followUps.map((q, fIdx) => (
                                  <button
                                    key={fIdx}
                                    type="button"
                                    onClick={() => sendPrompt(q)}
                                    className="followup-chip"
                                  >
                                    <ArrowBendDownRightIcon size={14} color="var(--text-muted)" aria-hidden="true" />
                                    <span>{q}</span>
                                  </button>
                                ))}
                              </div>
                            </div>
                          )}
                      </div>
                    </div>
                  )}
                </div>
              ))}
              <div ref={chatBottomRef} />
            </div>
          )}
        </div>

        {showScrollBottom && !isChatEmpty && (
          <button
            type="button"
            onClick={scrollToBottomNow}
            className="scroll-bottom-btn"
            title="Gulir ke bawah"
          >
            <ArrowDownIcon size={16} weight="regular" aria-hidden="true" />
          </button>
        )}

        {/* Bottom Composer */}
        <div className="composer-wrapper">
          {chatWaitSeconds > 0 && !isGenerating && <p className="jst-chat-cooldown" role="status">Pesan berikutnya bisa dikirim dalam {chatWaitSeconds} detik.</p>}
          <div className="composer-shell">
            <textarea
              ref={textareaRef}
              rows={1}
              value={input}
              onChange={(e) => {
                setInput(e.target.value);
                e.target.style.height = "auto";
                e.target.style.height = `${Math.min(e.target.scrollHeight, 160)}px`;
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  if (!isGenerating) {
                    sendPrompt();
                  }
                }
              }}
              disabled={isGenerating || activeSession.messagesLoaded === false}
              placeholder={
                isGenerating
                  ? "Jakarta SmartTax sedang menelaah & merumuskan jawaban..."
                  : themeConfig.placeholder
              }
              style={{
                width: "100%",
                background: "transparent",
                border: "none",
                outline: "none",
                resize: "none",
                color: "var(--text-primary)",
                fontSize: "15px",
                lineHeight: "1.5",
                padding: "2px 2px",
                maxHeight: "160px",
              }}
            />

            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                gap: "8px",
                flexWrap: "wrap",
              }}
            >
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "6px",
                  flexWrap: "wrap",
                }}
              >
                <div ref={themeDropdownRef} style={{ position: "relative" }}>
                  <button
                    type="button"
                    onClick={() => setThemeMenuOpen((v) => !v)}
                    className={`composer-pill-btn ${themeMenuOpen ? "open" : ""}`}
                    title="Ganti Jenis Pajak DKI Jakarta"
                  >
                    <ThemeIcon
                      code={currentTheme}
                      color={themeConfig.iconColor}
                    />
                    <span>{themeConfig.shortLabel}</span>
                    <span
                      className="composer-pill-scope"
                      style={{ color: "rgba(var(--chat-ink), 0.2)" }}
                    >
                      |
                    </span>
                    <span
                      className="composer-pill-scope"
                      style={{ color: "var(--text-muted)", fontWeight: 400 }}
                    >
                      DKI Jakarta
                    </span>
                    <CaretUpIcon size={12} weight="regular" aria-hidden="true" color="var(--text-muted)" style={{
                        transform: themeMenuOpen
                          ? "rotate(180deg)"
                          : "rotate(0deg)",
                        transition: "transform 0.2s ease",
                      }} />
                  </button>

                  {themeMenuOpen && (
                    <div className="theme-up-dropdown">
                      <div
                        style={{
                          fontSize: "11px",
                          fontWeight: 600,
                          color: "var(--text-muted)",
                          padding: "6px 11px 4px",
                        }}
                      >
                        Jenis Pajak Daerah • DKI Jakarta
                      </div>
                      {(Object.keys(DKI_TAX_THEMES) as TaxThemeCode[]).map(
                        (code) => {
                          const item = DKI_TAX_THEMES[code];
                          const isSelected = currentTheme === code;
                          return (
                            <button
                              key={code}
                              type="button"
                              onClick={() => switchTheme(code)}
                              className={`model-option ${
                                isSelected ? "selected" : ""
                              }`}
                            >
                              <div
                                style={{
                                  display: "flex",
                                  alignItems: "flex-start",
                                  gap: "10px",
                                }}
                              >
                                <div style={{ marginTop: "3px" }}>
                                  <ThemeIcon
                                    code={code}
                                    color={item.iconColor}
                                  />
                                </div>
                                <div>
                                  <div
                                    style={{
                                      fontSize: "13px",
                                      fontWeight: 500,
                                      color: "var(--text-primary)",
                                    }}
                                  >
                                    {item.label}
                                  </div>
                                  <div
                                    style={{
                                      fontSize: "11.5px",
                                      color: "var(--text-muted)",
                                    }}
                                  >
                                    {item.desc}
                                  </div>
                                </div>
                              </div>
                              {isSelected && (
                                <span
                                  style={{
                                    color: "var(--text-primary)",
                                    fontSize: "13px",
                                  }}
                                >
                                  <CheckIcon size={13} aria-hidden="true" />
                                </span>
                              )}
                            </button>
                          );
                        }
                      )}
                    </div>
                  )}
                </div>

              </div>

              {isGenerating ? (
                <button
                  type="button"
                  onClick={stopGeneration}
                  className="send-btn ready"
                  title="Hentikan respons (Esc)"
                >
                  <StopIcon size={14} weight="fill" aria-hidden="true" />
                </button>
              ) : (
                <button
                  type="button"
                  disabled={!input.trim() || chatWaitSeconds > 0 || activeSession.messagesLoaded === false}
                  onClick={() => sendPrompt()}
                  className={`send-btn ${input.trim() ? "ready" : "disabled"}`}
                  title={chatWaitSeconds > 0 ? `Tunggu ${chatWaitSeconds} detik` : "Kirim pesan (Enter)"}
                >
                  <ArrowUpIcon size={18} weight="bold" aria-hidden="true" />
                </button>
              )}
            </div>
          </div>

          <div className="jst-chat-disclaimer">
            AI dapat membuat kesalahan. Periksa kembali informasi penting dan sumbernya.
          </div>
        </div>
        </div>
      </div>

      {sourceSelection && !historyView && <SourcePanel key={`${activeSessionId}-${sourceSelection.messageId}`} message={activeSession.messages.find(message => message.id === sourceSelection.messageId)} selectedNumber={sourceSelection.number} onClose={() => setSourceSelection(null)}/>}

      {/* Quick Search & Theme Switcher Dialog (Cmd+K) */}
      {cmdOpen && (
        <div className="cmd-backdrop" onClick={() => setCmdOpen(false)}>
          <div className="cmd-dialog" onClick={(e) => e.stopPropagation()}>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "10px",
                padding: "14px 16px",
                borderBottom: "1px solid rgba(var(--chat-ink), 0.08)",
              }}
            >
              <MagnifyingGlassIcon size={17} weight="regular" aria-hidden="true" color="var(--text-muted)" />
              <input
                type="text"
                value={cmdQuery}
                onChange={(e) => setCmdQuery(e.target.value)}
                placeholder="Cari percakapan atau jenis pajak…"
                style={{
                  flex: 1,
                  background: "transparent",
                  border: "none",
                  color: "var(--text-primary)",
                  fontSize: "14.5px",
                }}
                autoFocus
              />
              <button
                type="button"
                onClick={() => setCmdOpen(false)}
                style={{
                  background: "rgba(var(--chat-ink), 0.07)",
                  border: "none",
                  borderRadius: "6px",
                  padding: "2px 7px",
                  fontSize: "11px",
                  color: "var(--text-secondary)",
                  cursor: "pointer",
                }}
              >
                Esc
              </button>
            </div>

            <div
              style={{
                maxHeight: "340px",
                overflowY: "auto",
                padding: "8px",
              }}
            >
              <div
                style={{
                  fontSize: "11px",
                  fontWeight: 600,
                  color: "var(--text-muted)",
                  padding: "4px 10px 6px",
                }}
              >
                Pindah Fokus Pajak DKI Jakarta
              </div>
              {(Object.keys(DKI_TAX_THEMES) as TaxThemeCode[])
                .filter((code) => {
                  const t = DKI_TAX_THEMES[code];
                  const q = cmdQuery.toLowerCase();
                  return (
                    !q ||
                    t.label.toLowerCase().includes(q) ||
                    t.desc.toLowerCase().includes(q)
                  );
                })
                .map((code) => {
                  const t = DKI_TAX_THEMES[code];
                  return (
                    <button
                      key={code}
                      type="button"
                      onClick={() => {
                        switchTheme(code);
                        setCmdOpen(false);
                      }}
                      className={`model-option ${
                        currentTheme === code ? "selected" : ""
                      }`}
                    >
                      <div
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: "10px",
                        }}
                      >
                        <ThemeIcon code={code} color={t.iconColor} />
                        <div>
                          <div
                            style={{
                              fontSize: "13px",
                              fontWeight: 500,
                              color: "var(--text-primary)",
                            }}
                          >
                            {t.label}
                          </div>
                          <div style={{ fontSize: "11.5px", color: "var(--text-muted)" }}>
                            {t.desc}
                          </div>
                        </div>
                      </div>
                      {currentTheme === code && (
                        <span style={{ fontSize: "12px", color: "var(--text-secondary)" }}>
                          Aktif
                        </span>
                      )}
                    </button>
                  );
                })}

              <div
                style={{
                  fontSize: "11px",
                  fontWeight: 600,
                  color: "var(--text-muted)",
                  padding: "10px 10px 6px",
                }}
              >
                Riwayat Percakapan
              </div>
              {sortedSessions
                .filter(
                  (s) =>
                    !cmdQuery ||
                    s.title.toLowerCase().includes(cmdQuery.toLowerCase())
                )
                .map((s) => (
                  <button
                    key={s.id}
                    type="button"
                    onClick={() => {
                      openConversation(s.id);
                      setCmdOpen(false);
                    }}
                    className="model-option"
                  >
                    <span
                      style={{
                        fontSize: "13px",
                        color: "var(--text-primary)",
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                      }}
                    >
                      {s.title}
                    </span>
                    <span style={{ fontSize: "11.5px", color: "var(--text-muted)" }}>
                      {s.theme}
                    </span>
                  </button>
                ))}
            </div>
          </div>
        </div>
      )}

      {toast && (
        <div className="ux-toast">
          <span>{toast.message}</span>
          {toast.undoSession && (
            <button
              type="button"
              onClick={undoDeleteSession}
              style={{
                background: "rgba(var(--chat-ink), 0.1)",
                border: "1px solid rgba(var(--chat-ink), 0.18)",
                borderRadius: "6px",
                padding: "3px 9px",
                fontSize: "12px",
                fontWeight: 500,
                color: "var(--text-primary)",
                cursor: "pointer",
              }}
            >
              Urungkan
            </button>
          )}
        </div>
      )}
    </div>
  );
}
