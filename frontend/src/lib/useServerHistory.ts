"use client";
import { useCallback, useEffect, useRef, useState } from 'react';
import { useAuth } from '@/components/AuthProvider';
import { apiFetch, setHistoryFlusher } from '@/lib/api';

type SessionShape = { id: string; messages: { isStreaming?: boolean; statusText?: string }[] };

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
          method: 'PUT', headers: { 'Content-Type': 'application/json', 'X-JST-Account-ID': user.id },
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
        const response = await apiFetch('/api/history', { signal: controller.signal, headers: { 'X-JST-Account-ID': user.id } });
        if (!response.ok) throw new Error('History unavailable');
        const history = await response.json();
        if (controller.signal.aborted) return;
        revision.current = history.revision;
        if (history.sessions.length) {
          acknowledged.current = JSON.stringify({ activeSessionId: history.activeSessionId || history.sessions[0].id, sessions: history.sessions });
          setSessions(history.sessions);
          setActiveSessionId(history.activeSessionId || history.sessions[0].id);
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

  useEffect(() => {
    if (!hydrated) return;
    latest.current = JSON.stringify({ activeSessionId, sessions: sessions.map(session => ({
      ...session, messages: session.messages.map(({ isStreaming: _streaming, statusText: _status, ...message }) => message),
    })) });
    // Stream tokens stay in memory; save the completed/stopped response once.
    if (sessions.some(session => session.messages.some(message => message.isStreaming))) {
      setSyncStatus('Jawaban sedang dibuat; riwayat disimpan setelah selesai.');
      return;
    }
    if (latest.current !== acknowledged.current) setSyncStatus('Perubahan belum tersimpan…');
    const timer = setTimeout(() => { void flush().catch(() => {}); }, 500);
    return () => clearTimeout(timer);
  }, [sessions, activeSessionId, hydrated, flush]);

  return { sessions, setSessions, activeSessionId, setActiveSessionId, hydrated, loadError, syncStatus, flush };
}
