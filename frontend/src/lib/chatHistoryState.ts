/** Drafts are UI state, not persisted conversations. */
export function hasStartedConversation(room: {
  messages: unknown[]; messagesLoaded?: boolean; messageCount?: number;
}): boolean {
  return room.messages.length > 0 || (room.messagesLoaded === false && (room.messageCount || 0) > 0);
}

export function historyTransport<T extends {
  id: string; messages: {isStreaming?: boolean; statusText?: string; theme?: unknown}[];
  messagesLoaded?: boolean; messageCount?: number; preview?: string; lastFailed?: boolean;
}>(sessions: T[], activeSessionId: string) {
  const started = sessions.filter(hasStartedConversation);
  return {
    activeSessionId: started.some(room => room.id === activeSessionId) ? activeSessionId : started[0]?.id || null,
    sessions: started.map(({messagesLoaded, messageCount: _count, preview: _preview, lastFailed: _failed, messages, ...room}) => ({
      ...room,
      ...(messagesLoaded === false ? {} : {messages: messages.map(({isStreaming: _streaming, statusText: _status, theme: _theme, ...message}) => message)}),
    })),
  };
}

/** Pins always precede newer unpinned rooms; timestamp breaks ties within a group. */
export function orderSidebarConversations<T extends {id:string; pinned?:boolean; updatedAt:number}>(rooms:T[]):T[] {
  return [...rooms].sort((a,b)=>Number(!!b.pinned)-Number(!!a.pinned) || b.updatedAt-a.updatedAt || a.id.localeCompare(b.id));
}

export function isSessionGenerating(room?: {messages?: readonly {isStreaming?: boolean}[]} | null): boolean {
  return Boolean(room?.messages?.some(message => message.isStreaming));
}

export function countGeneratingSessions(rooms: readonly {messages?: readonly {isStreaming?: boolean}[]}[]): number {
  return rooms.filter(isSessionGenerating).length;
}

export function canStartSessionGeneration(
  rooms: readonly {id: string; messagesLoaded?: boolean; messages?: readonly {isStreaming?: boolean}[]}[],
  sessionId: string,
  maxConcurrent = 2,
): {allowed: boolean; reason?: "unloaded" | "already_generating" | "queue_full"; queued: boolean} {
  const target = rooms.find(room => room.id === sessionId);
  if (!target || target.messagesLoaded === false) return {allowed: false, reason: "unloaded", queued: false};
  if (isSessionGenerating(target)) return {allowed: false, reason: "already_generating", queued: false};
  const activeCount = countGeneratingSessions(rooms);
  if (activeCount >= maxConcurrent) return {allowed: false, reason: "queue_full", queued: false};
  return {allowed: true, queued: activeCount > 0};
}
