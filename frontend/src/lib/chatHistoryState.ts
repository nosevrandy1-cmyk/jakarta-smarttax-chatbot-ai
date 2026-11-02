/** Drafts are UI state, not persisted conversations. */
export function hasStartedConversation(room: {
  messages: unknown[]; messagesLoaded?: boolean; messageCount?: number;
}): boolean {
  return room.messages.length > 0 || (room.messagesLoaded === false && (room.messageCount || 0) > 0);
}

export function historyTransport<T extends {
  id: string; messages: {isStreaming?: boolean; statusText?: string}[];
  messagesLoaded?: boolean; messageCount?: number; preview?: string; lastFailed?: boolean;
}>(sessions: T[], activeSessionId: string) {
  const started = sessions.filter(hasStartedConversation);
  return {
    activeSessionId: started.some(room => room.id === activeSessionId) ? activeSessionId : started[0]?.id || null,
    sessions: started.map(({messagesLoaded, messageCount: _count, preview: _preview, lastFailed: _failed, messages, ...room}) => ({
      ...room,
      ...(messagesLoaded === false ? {} : {messages: messages.map(({isStreaming: _streaming, statusText: _status, ...message}) => message)}),
    })),
  };
}

/** Pins always precede newer unpinned rooms; timestamp breaks ties within a group. */
export function orderSidebarConversations<T extends {id:string; pinned?:boolean; updatedAt:number}>(rooms:T[]):T[] {
  return [...rooms].sort((a,b)=>Number(!!b.pinned)-Number(!!a.pinned) || b.updatedAt-a.updatedAt || a.id.localeCompare(b.id));
}
