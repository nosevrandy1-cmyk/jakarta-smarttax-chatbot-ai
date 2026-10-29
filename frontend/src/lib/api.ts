export const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
let csrfToken: string | null = null;
export function setCsrfToken(token: string | null) { csrfToken = token; }

export async function apiFetch(path: string, options: RequestInit = {}) {
  const headers = new Headers(options.headers);
  if (!['GET', 'HEAD', 'OPTIONS'].includes((options.method || 'GET').toUpperCase()) && csrfToken) {
    headers.set('X-CSRF-Token', csrfToken);
  }
  const response = await fetch(API_BASE + path, { ...options, headers, credentials: 'include', cache: 'no-store' });
  if (response.status === 401 && path !== '/api/auth/logout' && typeof window !== 'undefined') {
    window.dispatchEvent(new Event('jst-session-expired'));
  }
  return response;
}
