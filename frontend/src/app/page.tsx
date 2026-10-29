"use client";

import { AccountMenu } from "@/components/AuthProvider";
import { apiFetch } from "@/lib/api";
import { useServerHistory } from "@/lib/useServerHistory";

import { SunIcon } from "@phosphor-icons/react/dist/csr/Sun";
import { MoonIcon } from "@phosphor-icons/react/dist/csr/Moon";
import RenameChatDialog from "@/components/RenameChatDialog";
import AnswerReferences, { type AnswerReference } from "@/components/AnswerReferences";
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
    iconColor: "#60a5fa",
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
    iconColor: "#f59e0b",
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
    iconColor: "#a78bfa",
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
    iconColor: "#f472b6",
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
    iconColor: "#38bdf8",
    greeting: "Apa yang ingin kamu bahas?",
    subtitle: "Tanyakan informasi dari dokumen proyek yang tersedia.",
    placeholder: "Tulis pertanyaan tentang dokumen atau topik ini...",
    suggestions: [],
  },
};

interface ChatMessage {
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
  const parts = text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g);
  return parts.map((part, i) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return (
        <strong key={i} style={{ color: "var(--text-primary)", fontWeight: 600 }}>
          {part.slice(2, -2)}
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

  const [capabilityMode, setCapabilityMode] =
    useState<CapabilityModeCode>("konsultasi");
  const [themeMenuOpen, setThemeMenuOpen] = useState<boolean>(false);
  const [cmdOpen, setCmdOpen] = useState<boolean>(false);
  const [cmdQuery, setCmdQuery] = useState<string>("");

  const [renamingChat, setRenamingChat] = useState<{ id: string; title: string } | null>(null);
  const { sessions, setSessions, activeSessionId, setActiveSessionId, hydrated, loadError, syncStatus, flush } = useServerHistory<ChatSession>([
    { id: 'default-session', title: 'Percakapan Baru', theme: 'PBB-P2', updatedAt: Date.now(), messages: [] },
  ]);
  const [input, setInput] = useState<string>("");
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
        else if (isGenerating) stopGeneration();
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [cmdOpen, themeMenuOpen, editingMsgId, isGenerating]);

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

  function createNewChat(themeOverride?: TaxThemeCode) {
    if (isGenerating) stopGeneration();

    const now = Date.now();
    if (now - lastNewChatAtRef.current < 400) {
      return;
    }
    lastNewChatAtRef.current = now;

    const targetTheme = themeOverride || currentTheme;

    if (activeSession.messages.length === 0) {
      if (themeOverride && activeSession.theme !== themeOverride) {
        switchTheme(themeOverride);
      }
      setInput("");
      closeSidebarOnMobile();
      setTimeout(() => textareaRef.current?.focus(), 50);
      return;
    }

    const existingEmpty = sessions.find((s) => s.messages.length === 0);
    if (existingEmpty) {
      setActiveSessionId(existingEmpty.id);
      if (themeOverride && existingEmpty.theme !== themeOverride) {
        switchTheme(themeOverride);
      }
      setInput("");
      closeSidebarOnMobile();
      setTimeout(() => textareaRef.current?.focus(), 50);
      return;
    }

    const newId = `session-${now}`;
    const newSession: ChatSession = {
      id: newId,
      title: "Percakapan Baru",
      theme: targetTheme,
      updatedAt: now,
      messages: [],
    };
    setSessions((prev) => [newSession, ...prev]);
    setActiveSessionId(newId);
    setInput("");
    closeSidebarOnMobile();
    setTimeout(() => textareaRef.current?.focus(), 60);
  }

  function deleteSession(id: string, e: React.MouseEvent) {
    e.stopPropagation();
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
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setIsGenerating(false);
    setSessions((prev) =>
      prev.map((s) =>
        s.id === activeSessionId
          ? {
              ...s,
              messages: s.messages.map((m) =>
                m.isStreaming
                  ? { ...m, isStreaming: false, statusText: undefined }
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
    if (!query || isGenerating) return;

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
        throw new Error(`HTTP ${response.status}`);
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
          setSessions((prev) =>
            prev.map((s) => {
              if (s.id !== activeSessionId) return s;
              return {
                ...s,
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
                          isStreaming: false,
                          statusText: undefined,
                          content:
                            m.content ||
                            `Koneksi ke layanan AI lokal sedang terputus (${err?.message || err}). Pastikan server backend aktif lalu klik Ulangi.`,
                        }
                      : m
                  ),
                }
              : s
          )
        );
      }
    } finally {
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

  const isChatEmpty = activeSession.messages.length === 0;

  if (!hydrated) return <main className="auth-screen"><section className="auth-card">
    <h1>{loadError ? 'Riwayat belum dapat dimuat' : 'Memuat percakapan…'}</h1>
    {loadError && <><p>Periksa koneksi lalu muat ulang. Riwayat di server tidak akan ditimpa.</p><button className="auth-google-button" onClick={() => window.location.reload()}>Muat ulang</button></>}
  </section></main>;


  return (
    <div className="app-layout" data-chat-theme={appearance}>
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
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            marginBottom: "10px",
            minWidth: "240px",
          }}
        >
          <button
            onClick={() => setSidebarOpen(false)}
            className="icon-btn"
            title="Tutup Sidebar (⌘B)"
          >
            <SidebarSimpleIcon size={19} weight="regular" aria-hidden="true" />
          </button>

          <div style={{ display: "flex", alignItems: "center", gap: "2px" }}>
            <button
              onClick={() => {
                setCmdOpen(true);
                setCmdQuery("");
              }}
              className="icon-btn"
              title="Cari Percakapan & Tema Pajak (⌘K)"
            >
              <MagnifyingGlassIcon size={18} weight="regular" aria-hidden="true" />
            </button>

            <button
              onClick={() => createNewChat()}
              className="icon-btn"
              title="Percakapan Baru"
            >
              <NotePencilIcon size={19} weight="regular" aria-hidden="true" />
            </button>
          </div>
        </div>

        <div
          onClick={() => {
            closeSidebarOnMobile();
            setTimeout(() => textareaRef.current?.focus(), 40);
          }}
          className="session-item active"
          style={{
            marginBottom: "14px",
            minWidth: "240px",
            fontWeight: 500,
            color: "var(--text-primary)",
            cursor: "pointer",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <div
              style={{
                width: "26px",
                height: "26px",
                borderRadius: "999px",
                background: "var(--bg-raised)",
                border: "1px solid rgba(var(--chat-ink), 0.12)",
                color: "var(--text-primary)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <ThemeIcon code={currentTheme} color={themeConfig.iconColor} />
            </div>
            <span>Pajak Daerah DKI Jakarta</span>
          </div>
        </div>

        <div
          style={{
            fontSize: "11.5px",
            fontWeight: 600,
            color: "var(--text-muted)",
            padding: "4px 10px 6px",
            minWidth: "240px",
          }}
        >
          Riwayat Percakapan
        </div>

        <div
          style={{
            flex: 1,
            overflowY: "auto",
            display: "flex",
            flexDirection: "column",
            gap: "2px",
            minWidth: "240px",
          }}
        >
          {sessions.map((s) => {
            const active = s.id === activeSessionId;
            return (
              <div
                key={s.id}
                onClick={() => {
                  setActiveSessionId(s.id);
                  closeSidebarOnMobile();
                }}
                className={`session-item ${active ? "active" : ""}`}
              >
                <span
                  style={{
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                    flex: 1,
                  }}
                >
                  {s.title}
                </span>
                <span
                  style={{
                    fontSize: "11px",
                    color: "var(--text-muted)",
                    fontWeight: 500,
                  }}
                >
                  {s.theme}
                </span>
                <button type="button" className="rename-session-btn"
                  title="Ganti nama percakapan" aria-label={`Ganti nama percakapan: ${s.title}`}
                  onClick={event => { event.stopPropagation(); setRenamingChat({ id: s.id, title: s.title }); }}>
                  <PencilSimpleIcon size={14} aria-hidden="true" />
                </button>
                {sessions.length > 1 && (
                  <button
                    onClick={(e) => deleteSession(s.id, e)}
                    className="delete-btn"
                    title="Hapus percakapan"
                  >
                    <XIcon size={12} aria-hidden="true" />
                  </button>
                )}
              </div>
            );
          })}
        </div>

        <div
          style={{
            borderTop: "1px solid rgba(var(--chat-ink), 0.06)",
            paddingTop: "10px",
            marginTop: "8px",
            minWidth: "240px",
          }}
        >
          <AccountMenu />
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
                  <SidebarSimpleIcon size={19} weight="regular" aria-hidden="true" />
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

          <button type="button" className="chat-appearance-toggle" onClick={toggleAppearance}
            aria-label={appearance === "dark" ? "Aktifkan mode terang" : "Aktifkan mode gelap"}
            title={appearance === "dark" ? "Aktifkan mode terang" : "Aktifkan mode gelap"}>
            {appearance === "dark" ? <SunIcon size={17} aria-hidden="true" /> : <MoonIcon size={17} aria-hidden="true" />}
          </button>
        </header>

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
          {isChatEmpty ? (
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

              <div
                style={{
                  display: "inline-flex",
                  flexWrap: "wrap",
                  justifyContent: "center",
                  gap: "6px",
                  padding: "4px",
                  borderRadius: "999px",
                  background: "rgba(var(--chat-ink), 0.04)",
                  border: "1px solid rgba(var(--chat-ink), 0.08)",
                  marginBottom: "18px",
                }}
              >
                {CAPABILITY_MODES.map((mode) => {
                  const isActive = capabilityMode === mode.code;
                  return (
                    <button
                      key={mode.code}
                      type="button"
                      onClick={() => {
                        setCapabilityMode(mode.code);
                      }}
                      style={{
                        border: "none",
                        borderRadius: "999px",
                        padding: "6px 13px",
                        fontSize: "12.5px",
                        fontWeight: isActive ? 600 : 400,
                        background: isActive
                          ? "rgba(var(--chat-ink), 0.13)"
                          : "transparent",
                        color: isActive ? "var(--text-primary)" : "var(--text-secondary)",
                        cursor: "pointer",
                        transition: "all 0.16s ease",
                      }}
                    >
                      {mode.shortLabel}
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

                        <FormattedMarkdown
                          content={m.content}
                          isStreaming={m.isStreaming}
                          onCopyCode={handleCopyInlineCode}
                        />

                        {!m.isStreaming && <AnswerReferences references={m.references} />}

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
                                className="action-bar-btn"
                                title="Ulangi jawaban"
                              >
                                <ArrowsClockwiseIcon size={14} weight="regular" aria-hidden="true" />
                                <span>Ulangi</span>
                              </button>
                            )}

                            {m.durationMs && (
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
              disabled={isGenerating}
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
                  disabled={!input.trim()}
                  onClick={() => sendPrompt()}
                  className={`send-btn ${input.trim() ? "ready" : "disabled"}`}
                  title="Kirim pesan (Enter)"
                >
                  <ArrowUpIcon size={18} weight="bold" aria-hidden="true" />
                </button>
              )}
            </div>
          </div>

          <div
            style={{
              textAlign: "center",
              fontSize: "11px",
              color: "var(--text-muted)",
              marginTop: "7px",
            }}
          >
            Jawaban mengacu pada dokumen proyek yang tersedia. Periksa sumber sebelum menggunakan informasinya.
          </div>
        </div>
      </div>

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
                placeholder="Cari riwayat percakapan atau pilih jenis pajak DKI..."
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
              {sessions
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
                      setActiveSessionId(s.id);
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
