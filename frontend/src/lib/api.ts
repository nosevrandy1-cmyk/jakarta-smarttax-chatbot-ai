export class ApiRequestLimitError extends Error {
  constructor(message: string, public retryAt = 0) { super(message); this.name = 'ApiRequestLimitError'; }
}
type RequestGroup = 'chat' | 'general';
const windows: Record<RequestGroup, number[]> = {chat:[],general:[]};
const blocked: Record<RequestGroup, number> = {chat:0,general:0};
const mutations = new Set<string>();
const lastMutation = new Map<string,number>();
let dispatchQueue: Promise<void> = Promise.resolve();
let queued = 0;
let lastDispatch = 0;
function groupFor(path: string): RequestGroup { return /^\/api\/chat(?:\/stream)?$/.test(path.split('?')[0]) ? 'chat' : 'general'; }
function readWindow(group: RequestGroup) {
  const now=Date.now();
  try {
    if(typeof window !== 'undefined') {
      const stored=JSON.parse(localStorage.getItem(`jst-request-budget-${group}`)||'{}');
      const times=Array.isArray(stored.times)?stored.times.filter((value:unknown)=>typeof value==='number'&&value>now-65000&&value<=now):[];
      windows[group]=[...new Set([...windows[group],...times])].sort((a,b)=>a-b);
      if(typeof stored.blocked==='number')blocked[group]=Math.max(blocked[group],Math.min(stored.blocked,now+300000));
    }
  } catch { /* In-memory limits still apply if storage is unavailable. */ }
  windows[group]=windows[group].filter(time=>time>now-65000);
}
function writeWindow(group: RequestGroup) {
  try {if(typeof window!=='undefined')localStorage.setItem(`jst-request-budget-${group}`,JSON.stringify({times:windows[group],blocked:blocked[group]}));}catch{}
  if(typeof window!=='undefined')window.dispatchEvent(new Event('jst-api-cooldown'));
}
function waitForGroup(group: RequestGroup) {
  readWindow(group);
  const times=windows[group];
  const budget=group==='chat'?9:80;
  return Math.max(0,blocked[group]-Date.now(),times.length>=budget?times[times.length-budget]+65000-Date.now():0,
    group==='chat'&&times.length?times[times.length-1]+7000-Date.now():0);
}
export function getChatWaitMs(){return waitForGroup('chat');}
function limitError(wait:number){return new ApiRequestLimitError(`Permintaan terlalu cepat. Tunggu ${Math.max(1,Math.ceil(wait/1000))} detik lalu coba lagi.`,Date.now()+wait);}
function delay(ms:number,signal?:AbortSignal|null){
  return new Promise<void>((resolve,reject)=>{
    if(signal?.aborted){reject(new DOMException('Dibatalkan','AbortError'));return;}
    const cancel=()=>{clearTimeout(timer);reject(new DOMException('Dibatalkan','AbortError'));};
    const timer=setTimeout(()=>{signal?.removeEventListener('abort',cancel);resolve();},ms);
    signal?.addEventListener('abort',cancel,{once:true});
  });
}
async function reserveRequest(path:string,signal?:AbortSignal|null){
  const group=groupFor(path);
  if(queued>=16)throw new ApiRequestLimitError('Masih ada permintaan yang diproses. Tunggu sebentar.');
  queued++;
  const turn=dispatchQueue.catch(()=>{}).then(async()=>{
    signal?.throwIfAborted();
    const pause=Math.max(0,lastDispatch+200-Date.now());
    if(pause)await delay(pause,signal);
    signal?.throwIfAborted();
    const wait=waitForGroup(group);if(wait>0)throw limitError(wait);
    lastDispatch=Date.now();windows[group].push(lastDispatch);writeWindow(group);
  });
  dispatchQueue=turn.catch(()=>{});
  try{await turn;}finally{queued--;}
}

export const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
let csrfToken: string | null = null;
export function setCsrfToken(token: string | null) { csrfToken = token; }

async function performApiFetch(path: string, options: RequestInit = {}) {
  const headers = new Headers(options.headers);
  if (!['GET', 'HEAD', 'OPTIONS'].includes((options.method || 'GET').toUpperCase()) && csrfToken) {
    headers.set('X-CSRF-Token', csrfToken);
  }
  let response = await fetch(API_BASE + path, { ...options, headers, credentials: 'include', cache: 'no-store' });
  // Local development restarts rotate CSRF tokens. Retry only a rejected
  // local-session request; permissions, Origin checks, and account IDs stay intact.
  if (response.status === 403 && headers.has('X-CSRF-Token') && (options.body == null || typeof options.body === 'string')) {
    const detail = await response.clone().json().catch(() => null);
    if (detail?.detail === 'Permintaan tidak valid. Muat ulang halaman.') {
      const fresh = await fetch(API_BASE + '/api/auth/session', {credentials:'include', cache:'no-store'});
      if (fresh.ok) {
        const session = await fresh.json();
        const account = headers.get('X-JST-Account-ID');
        if (session.user?.local === true && typeof session.csrf_token === 'string' && (!account || account === session.user.id)) {
          setCsrfToken(session.csrf_token); headers.set('X-CSRF-Token', session.csrf_token);
          response = await fetch(API_BASE + path, {...options, headers, credentials:'include',cache:'no-store'});
        }
      }
    }
  }
  if (response.status === 401 && path !== '/api/auth/logout' && typeof window !== 'undefined') {
    window.dispatchEvent(new Event('jst-session-expired'));
  }
  return response;
}

async function limitedApiFetch(path:string,options:RequestInit={}) {
  const method=(options.method||'GET').toUpperCase();
  const mutation=!['GET','HEAD','OPTIONS'].includes(method);
  const key=path.startsWith('/api/rag/')&&mutation?'source-operation':`${method}:${path.split('?')[0]}`;
  if(mutation&&mutations.has(key))throw new ApiRequestLimitError('Proses masih berjalan. Tunggu sampai selesai.');
  if(mutation&&!path.startsWith('/api/history')&&Date.now()-(lastMutation.get(key)||0)<1200)
    throw limitError(1200-(Date.now()-(lastMutation.get(key)||0)));
  if(mutation)mutations.add(key);
  try {
    await reserveRequest(path,options.signal);
    if(mutation)lastMutation.set(key,Date.now());
    const response=await performApiFetch(path,options);
    if(response.status===429){
      const retry=response.headers.get('Retry-After');
      const seconds=retry&&Number.isFinite(Number(retry))?Number(retry):retry?Math.ceil((Date.parse(retry)-Date.now())/1000):60;
      const wait=Math.max(1000,Math.min(300000,(Number.isFinite(seconds)?seconds:60)*1000));
      const group=groupFor(path);blocked[group]=Date.now()+wait;writeWindow(group);
      throw limitError(wait);
    }
    return response;
  } finally {if(mutation)mutations.delete(key);}
}

const pendingReads=new Map<string,Promise<Response>>();
export async function apiFetch(path:string,options:RequestInit={}) {
  // Coalesce repeated read clicks, but keep abortable reads and session checks independent.
  if((options.method||'GET').toUpperCase()!=='GET'||options.signal||path==='/api/auth/session')
    return limitedApiFetch(path,options);
  const key=JSON.stringify([path,csrfToken,new Headers(options.headers).get('X-JST-Account-ID')]);
  const existing=pendingReads.get(key);
  if(existing)return (await existing).clone();
  const request=limitedApiFetch(path,options);pendingReads.set(key,request);
  try{return (await request).clone();}finally{if(pendingReads.get(key)===request)pendingReads.delete(key);}
}

let historyFlusher: (() => Promise<void>) | null = null;
export function setHistoryFlusher(flusher: (() => Promise<void>) | null) { historyFlusher = flusher; }
export async function flushChatHistory() { await historyFlusher?.(); }
