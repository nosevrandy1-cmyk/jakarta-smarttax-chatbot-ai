"use client";

import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react';
import { usePathname } from 'next/navigation';
import { SignOutIcon } from '@phosphor-icons/react/dist/csr/SignOut';
import { ArrowLeftIcon } from '@phosphor-icons/react/dist/csr/ArrowLeft';
import { API_BASE, apiFetch, setCsrfToken } from '@/lib/api';

type User = { id: string; email: string; name: string; role: 'user' | 'developer' };
type Session = { configured: boolean; user: User | null; csrf_token: string | null };
type AuthContextValue = { user: User; logout: () => Promise<void> };
const AuthContext = createContext<AuthContextValue | null>(null);
export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error('Authenticated content requires AuthProvider');
  return context;
}
const LOGOUT_KEY = 'jakarta_smarttax_logout_event';

export default function AuthProvider({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [providerError, setProviderError] = useState('');
  const [authMode, setAuthMode] = useState<'login' | 'register'>('login');
  const userRef = useRef<User | null>(null);
  const requestVersion = useRef(0);

  const clearSession = useCallback((removeHistory = false) => {
    requestVersion.current += 1;
    if (removeHistory && userRef.current) {
      try { localStorage.removeItem(`jakarta_smarttax_sessions_v3_user_${userRef.current.id}`); } catch { /* Browser storage may be unavailable. */ }
    }
    userRef.current = null;
    setCsrfToken(null);
    setSession(previous => previous ? { ...previous, user: null, csrf_token: null } : null);
  }, []);

  const refresh = useCallback(async () => {
    const version = ++requestVersion.current;
    try {
      const response = await apiFetch('/api/auth/session');
      if (!response.ok) throw new Error('Sesi tidak dapat diperiksa.');
      const next: Session = await response.json();
      if (version !== requestVersion.current) return;
      userRef.current = next.user;
      setCsrfToken(next.csrf_token);
      setSession(next);
      setError('');
    } catch {
      if (version === requestVersion.current) {
        setError('Belum dapat terhubung. Coba lagi sebentar.');
        clearSession();
        setSession(null);
        setLoading(false);
      }
    } finally {
      if (version === requestVersion.current) setLoading(false);
    }
  }, [clearSession]);

  useEffect(() => {
    void refresh();
    const query = new URLSearchParams(window.location.search);
    const reason = query.get('auth_error');
    if (reason) {
      const messages: Record<string, string> = {
        not_registered: 'Akun ini belum terdaftar. Silakan daftar terlebih dahulu.',
        already_registered: 'Akun ini sudah terdaftar. Silakan masuk.',
        cancelled: 'Login dibatalkan. Kamu bisa mencoba lagi.',
        not_allowed: 'Akun ini belum mendapat akses. Hubungi pengelola JST.',
        invalid_state: 'Proses login sudah kedaluwarsa. Silakan mulai lagi.',
        not_configured: 'Login Google belum tersedia. Hubungi pengelola JST.',
        invalid_client: 'Google menolak konfigurasi aplikasi. Periksa pasangan Client ID dan Client Secret pada backend.',
        invalid_grant: 'Kode login ditolak atau sudah terpakai. Mulai login lagi dari halaman ini.',
        redirect_mismatch: 'Alamat callback aplikasi belum cocok dengan konfigurasi Google.',
        token_exchange_failed: 'Google belum dapat menyelesaikan pertukaran kode login. Coba lagi.',
        missing_id_token: 'Google tidak mengembalikan identitas akun. Periksa scope login aplikasi.',
        invalid_id_token: 'Identitas Google belum dapat diverifikasi oleh server. Hubungi developer JST.',
        server_clock: 'Waktu server tidak sesuai. Developer perlu menyinkronkan jam komputer sebelum login ulang.',
        token_expired: 'Identitas login sudah kedaluwarsa. Silakan mulai login lagi.',
        invalid_audience: 'Identitas login berasal dari aplikasi Google yang berbeda. Periksa Client ID backend.',
        invalid_issuer: 'Penerbit identitas login tidak sesuai dengan Google.',
        invalid_signature: 'Tanda tangan identitas Google belum dapat diverifikasi. Hubungi developer JST.',
        certificate_unavailable: 'Kunci verifikasi Google belum tersedia. Coba lagi sebentar.',

        invalid_identity: 'Identitas login tidak cocok atau email belum terverifikasi. Mulai login lagi.',
        google_unreachable: 'Server belum dapat terhubung ke Google. Coba lagi sebentar.',

      };
      if (reason === 'not_registered') setAuthMode('register');
      if (reason === 'already_registered') setAuthMode('login');
      setProviderError(messages[reason] || 'Login belum berhasil. Silakan coba lagi.');
      query.delete('auth_error');
      const remaining = query.toString();
      window.history.replaceState(null, '', window.location.pathname + (remaining ? '?' + remaining : '') + window.location.hash);
    }
    function storage(event: StorageEvent) { if (event.key === LOGOUT_KEY) { clearSession(true); void refresh(); } }
    function expired() { clearSession(); }
    function visible() { if (document.visibilityState === 'visible') void refresh(); }
    window.addEventListener('storage', storage);
    window.addEventListener('jst-session-expired', expired);
    document.addEventListener('visibilitychange', visible);
    return () => {
      requestVersion.current += 1;
      window.removeEventListener('storage', storage);
      window.removeEventListener('jst-session-expired', expired);
      document.removeEventListener('visibilitychange', visible);
    };
  }, [clearSession, refresh]);

  async function logout() {
    const response = await apiFetch('/api/auth/logout', { method: 'POST' });
    if (!response.ok && response.status !== 401) throw new Error('Belum bisa keluar. Coba lagi.');
    clearSession(true);
    try { localStorage.setItem(LOGOUT_KEY, String(Date.now())); } catch { /* The current tab still logs out. */ }
  }

  if (loading) return <main className="auth-screen"><p role="status">Memeriksa sesi…</p></main>;
  if (!session?.user) return <main className="auth-screen"><section className="auth-card">
    <span className="auth-brand">JST <span>Jakarta SmartTax</span></span>
    <h1>{authMode === 'register' ? 'Daftar Jakarta SmartTax' : 'Masuk ke Jakarta SmartTax'}</h1>
    <p>{authMode === 'register' ? 'Daftarkan akun Google untuk mulai menggunakan chatbot JST. Tidak perlu membuat password baru.' : 'Masuk menggunakan akun Google yang sudah terdaftar di JST.'}</p>
    {(error || providerError) && <p className="auth-feedback" role="alert">{error || providerError}</p>}
    {session && !session.configured && <p className="auth-feedback" role="status">Login Google belum tersedia. Hubungi pengelola JST untuk menyiapkannya.</p>}
    {session?.configured ? <a className="auth-google-button" href={API_BASE + '/api/auth/google/' + authMode}>{authMode === 'register' ? 'Daftar dengan Google' : 'Masuk dengan Google'}</a>
      : <button className="auth-google-button" onClick={() => { setLoading(true); void refresh(); }}>Periksa kembali</button>}
    <p className="auth-switch">{authMode === 'register' ? 'Sudah punya akun? ' : 'Belum punya akun? '}<button type="button" onClick={() => { setAuthMode(authMode === 'login' ? 'register' : 'login'); setProviderError(''); }}>{authMode === 'register' ? 'Masuk' : 'Daftar'}</button></p>
    <p className="auth-privacy">{authMode === 'register' ? 'JST akan menerima nama, email, dan ID akun Google untuk membuat akun. Pertanyaan dan dokumenmu tidak dikirim ke Google untuk pendaftaran.' : 'Google digunakan untuk memverifikasi identitas akun. Pertanyaan dan dokumenmu tidak dikirim ke Google untuk login.'}</p>
  </section></main>;

  const restricted = ['/admin','/audit'].some(route => pathname === route || pathname.startsWith(route + '/'));
  if (restricted && session.user.role !== 'developer') return <main className="auth-screen"><section className="auth-card">
    <span className="auth-brand">Jakarta SmartTax</span><h1>Akses khusus developer</h1>
    <p>Akun ini dapat menggunakan chatbot. Dashboard hanya tersedia untuk developer yang telah diberi akses.</p>
    <a className="auth-google-button" href="/"><ArrowLeftIcon size={17} aria-hidden="true" />Kembali ke chatbot</a>
  </section></main>;
  return <AuthContext.Provider value={{ user: session.user, logout }}><div key={session.user.id} className="auth-content">{children}</div></AuthContext.Provider>;
}

export function AccountMenu() {
  const { user, logout } = useAuth();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  return <div className="auth-account">
    <div className="auth-avatar" aria-hidden="true">{(user.name || user.email).slice(0, 1).toUpperCase()}</div>
    <div className="auth-account-copy"><strong>{user.name || 'Akun Google'}</strong><span>{user.email}</span></div>
    <button type="button" className="icon-btn" disabled={busy} title="Keluar akun" aria-label="Keluar akun" onClick={async () => {
      setBusy(true); setError('');
      try { await logout(); } catch { setError('Belum bisa keluar. Coba lagi.'); setBusy(false); }
    }}><SignOutIcon size={18} aria-hidden="true" /></button>
    {user.role === 'developer' && <a className="auth-dashboard-link" href="/admin">Buka dashboard developer</a>}
    <small>Riwayat di perangkat ini dibersihkan saat keluar. Sinkronisasi akun belum tersedia.</small>
    {error && <small role="alert">{error}</small>}
  </div>;
}
