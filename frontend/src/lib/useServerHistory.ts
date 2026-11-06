"use client";
import { useCallback, useEffect, useRef, useState } from 'react';
import { historyTransport } from '@/lib/chatHistoryState';
import { useAuth } from '@/components/AuthProvider';
import { apiFetch, setHistoryFlusher } from '@/lib/api';

type SessionShape = { lastFailed?: boolean; messagesLoaded?: boolean; messageCount?: number; preview?: string; id: string; messages: { isStreaming?: boolean; statusText?: string }[] };

export function useServerHistory<T extends SessionShape>(initial: T[]) {
  const { user } = useAuth();
  const [sessions, setSessions] = useState<T[]>(initial);
  const [activeSessionId, setActiveSessionId] = useState(initial[0].id);
  const [hydrated, setHydrated] = useState(false);
  const [loadError, setLoadError] = useState(false);
  const [syncStatus, setSyncStatus] = useState('');
  const revision = useRef(0);
  const acknowledged = useRef('');
  const latest = useRef('');
  const queue = useRef<Promise<void>>(Promise.resolve());
  const disposed = useRef(false);

  const flush = useCallback(() => {
    const operation = queue.current.catch(() => {}).then(async () => {
      if (disposed.current || !latest.current || latest.current === acknowledged.current) return;
      const payload = latest.current;
      setSyncStatus('Menyimpan riwayat…');
      try {
        const response = await apiFetch('/api/history', {
          method: 'PATCH', headers: { 'Content-Type': 'application/json', 'X-JST-Account-ID': user.id },
          body: JSON.stringify({ ...JSON.parse(payload), revision: revision.current }),
        });
        if (!response.ok) {
          if (response.status === 409) throw new Error('Riwayat berubah di tab lain. Muat ulang sebelum melanjutkan.');
          if (response.status === 413 || response.status === 422) throw new Error('Riwayat melebihi batas penyimpanan. Kurangi percakapan atau panjang pesan.');
          throw new Error('Riwayat belum tersimpan. Periksa koneksi lalu coba lagi.');
        }
        revision.current = (await response.json()).revision;
        acknowledged.current = payload;
        if (!disposed.current) setSyncStatus('Riwayat tersimpan di akun');
      } catch (error) {
        if (!disposed.current) setSyncStatus(error instanceof Error ? error.message : 'Riwayat belum tersimpan.');
        throw error;
      }
    });
    queue.current = operation;
    return operation;
  }, [user.id]);

  useEffect(() => {
    const controller = new AbortController();
    disposed.current = false;
    async function load() {
      try {
        const response = await apiFetch('/api/history/index', { signal: controller.signal, headers: { 'X-JST-Account-ID': user.id } });
        if (!response.ok) throw new Error('History unavailable');
        const history = await response.json();
        if (controller.signal.aborted) return;
        revision.current = history.revision;
        if (history.sessions.length) {
          acknowledged.current = JSON.stringify(historyTransport(history.sessions as T[], history.activeSessionId || history.sessions[0].id));
          // Start with an unsaved draft; the URL decides which room to open.
          const draft = {...initial[0], id: `draft-${crypto.randomUUID()}`};
          setSessions([draft, ...history.sessions]);
          setActiveSessionId(draft.id);
        }
        setHydrated(true);
        setLoadError(false);
      } catch {
        if (!controller.signal.aborted) setLoadError(true);
      }
    }
    void load();
    setHistoryFlusher(flush);
    return () => { disposed.current = true; controller.abort(); setHistoryFlusher(null); };
  }, [flush, user.id]);

  // The transport excludes unfinished assistant messages. Token updates therefore
  // do not restart the debounce for another room that has already completed.
  const pendingSnapshot = JSON.stringify(historyTransport(sessions, activeSessionId));
  useEffect(() => {
    if (!hydrated) return;
    latest.current = pendingSnapshot;
    if (latest.current !== acknowledged.current) setSyncStatus('Perubahan belum tersimpan…');
    const timer = setTimeout(() => { void flush().catch(() => {}); }, 500);
    return () => clearTimeout(timer);
  }, [pendingSnapshot, hydrated, flush]);

  const [roomLoadError, setRoomLoadError] = useState('');
  const [loadAttempt, setLoadAttempt] = useState(0);
  const needsMessages = sessions.find(room => room.id === activeSessionId)?.messagesLoaded === false;
  useEffect(() => {
    if (!hydrated || !needsMessages) {setRoomLoadError('');return;}
    const controller = new AbortController();
    setRoomLoadError('');
    void (async () => {
      try {
        // Wait for pending writes without persisting an unfinished stream.
        await queue.current.catch(() => {});
        const response = await apiFetch(`/api/history/rooms/${encodeURIComponent(activeSessionId)}`, {signal:controller.signal,headers:{'X-JST-Account-ID':user.id}});
        if (!response.ok) throw new Error('Percakapan belum dapat dimuat. Coba lagi.');
        const data = await response.json();
        if (controller.signal.aborted) return;
        // Our queued metadata saves can advance the revision while this read is in flight.
        // They preserve unloaded messages; a newer server revision still signals another writer.
        if (data.revision > revision.current) throw new Error('Riwayat berubah di tab lain. Muat ulang halaman.');
        setSessions(previous => previous.map(room => room.id === activeSessionId && room.messagesLoaded === false
          ? {...room, messages:data.session.messages, messagesLoaded:true} : room));
      } catch (error) {
        if (!controller.signal.aborted) setRoomLoadError(error instanceof Error ? error.message : 'Percakapan belum dapat dimuat.');
      }
    })();
    return () => controller.abort();
  }, [activeSessionId, hydrated, needsMessages, loadAttempt, flush, user.id]);

  const adoptHistory = useCallback((history: {revision:number;sessions:T[];activeSessionId:string}) => {
    const value=JSON.stringify(historyTransport(history.sessions,history.activeSessionId));
    revision.current=history.revision;acknowledged.current=value;latest.current=value;
    setSessions(history.sessions);setActiveSessionId(history.activeSessionId);
    setSyncStatus('Riwayat tersimpan di akun');
  },[]);

  return { adoptHistory, sessions, setSessions, activeSessionId, setActiveSessionId, hydrated, loadError, syncStatus, flush, roomLoadError, retryRoomLoad: () => setLoadAttempt(value => value + 1) };
}
