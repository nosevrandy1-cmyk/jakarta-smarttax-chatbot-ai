"""Developer-only operational metrics; never persist request payloads or identities."""
import asyncio
import json
import uuid
import logging
from contextlib import contextmanager
import csv
import ctypes
import io
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import threading
import time
from datetime import datetime, timezone
import httpx
from fastapi import Query
from .config import DATA_DIR, OLLAMA_LOCAL_URL, DEFAULT_CHAT_MODEL

class OperationsStore:
    def __init__(self,path):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
        self.lock=threading.Lock()
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY,at REAL NOT NULL,category TEXT NOT NULL,action TEXT NOT NULL,method TEXT NOT NULL,status INTEGER NOT NULL,duration_ms REAL NOT NULL)')
            columns={r[1] for r in db.execute('PRAGMA table_info(events)')}
            for name in ('request_id','error_code','component'):
                if name not in columns:db.execute(f"ALTER TABLE events ADD COLUMN {name} TEXT NOT NULL DEFAULT ''")
    @contextmanager
    def connect(self):
        db=sqlite3.connect(self.path,timeout=1)
        try:
            with db:yield db
        finally:db.close()
    def record(self,category,action,method,status,duration,request_id="",error_code="",component="backend"):
        # Values come from fixed classifications, never from URL parameters or payloads.
        with self.lock,self.connect() as db:
            db.execute('INSERT INTO events(at,category,action,method,status,duration_ms,request_id,error_code,component) VALUES(?,?,?,?,?,?,?,?,?)',(time.time(),category,action,method,int(status),round(duration,1),request_id or uuid.uuid4().hex,error_code,component))
            db.execute('DELETE FROM events WHERE at<? OR id <= COALESCE((SELECT max(id)-10000 FROM events),0)',(time.time()-7*86400,))
    def browse(self,category='',offset=0,limit=20,problems_only=False):
        clauses=[];args=[]
        if category:clauses.append('category=?');args.append(category)
        if problems_only:clauses.append('(status>=400 OR length(error_code)>0)')
        where=' WHERE '+' AND '.join(clauses) if clauses else ''
        with self.connect() as db:
            db.row_factory=sqlite3.Row
            total=db.execute('SELECT count(*) FROM events'+where,args).fetchone()[0]
            rows=db.execute('SELECT * FROM events'+where+' ORDER BY id DESC LIMIT ? OFFSET ?',[*args,limit,offset]).fetchall()
        return {'items':[dict(r) for r in rows],'total':total,'offset':offset,'limit':limit}
    def summary(self):
        now=time.time();start=now-86400
        with self.connect() as db:
            count,errors=db.execute('SELECT count(*),COALESCE(sum(status>=400 OR length(error_code)>0),0) FROM events WHERE at>=?',(start,)).fetchone()
            durations=[r[0] for r in db.execute("SELECT duration_ms FROM events WHERE at>=? AND category='chat' AND status<400 AND length(error_code)=0 ORDER BY duration_ms",(start,))]
            bins=[]
            for i in range(12):
                lo=now-(12-i)*7200;hi=lo+7200
                n,e=db.execute('SELECT count(*),COALESCE(sum(status>=400 OR length(error_code)>0),0) FROM events WHERE at>=? AND at<?',(lo,hi)).fetchone()
                bins.append({'at':lo,'requests':n,'errors':e})
        return {'requests':count,'errors':errors,'median_chat_ms':durations[len(durations)//2] if durations else None,'series':bins}


def classify(path):
    if path.startswith('/api/auth/'):
        return ('auth','Google callback' if path.endswith('/callback') else 'Logout' if path.endswith('/logout') else 'Akses akun')
    if path.startswith('/api/chat'):return ('chat','Permintaan jawaban')
    if path.startswith('/api/rag/ingest') or path.endswith('/process'):return ('document','Pemrosesan sumber')
    if path.startswith('/api/rag/'):return ('document','Akses sumber dan evaluasi')
    return ('system','Permintaan aplikasi')

class OperationsMiddleware:
    def __init__(self,app,store):self.app=app;self.store=store
    async def __call__(self,scope,receive,send):
        path=scope.get('path','')
        if scope['type']!='http' or not path.startswith('/api/') or path.startswith('/api/admin/') or path in {'/api/health','/api/auth/session','/api/rag/import-status'} or scope.get('method')=='OPTIONS':
            return await self.app(scope,receive,send)
        start=time.monotonic();status=500;request_id=uuid.uuid4().hex;error_code=''
        component='auth' if path.startswith('/api/auth/') else 'ollama' if path.startswith('/api/chat') else 'ingestion' if '/ingest' in path or path.endswith('/process') else 'backend'
        async def tracked(message):
            nonlocal status,error_code
            if message['type']=='http.response.start':
                status=message['status']
                if path.endswith('/callback') and any(k.lower()==b'location' and b'auth_error=' in v for k,v in message.get('headers',[])):status=401
            if message['type']=='http.response.start':
                message={**message,'headers':[*message.get('headers',[]),(b'x-request-id',request_id.encode())]}
            if path.startswith('/api/chat') and message['type']=='http.response.body':
                # Only classify error events; no content is retained or logged.
                body=message.get('body',b'')
                if len(body)<=262144:
                    for line in body.splitlines():
                        try:
                            event=json.loads(line)
                            if isinstance(event,dict) and event.get('type')=='error':error_code='model_stream_error'
                        except (ValueError,UnicodeDecodeError):pass
            await send(message)
        try:await self.app(scope,receive,tracked)
        except asyncio.CancelledError:
            status=499;error_code="request_cancelled";raise
        except Exception as exc:
            status=500;error_code="upstream_timeout" if isinstance(exc,(TimeoutError,httpx.TimeoutException)) else "connection_failed" if isinstance(exc,(ConnectionError,httpx.ConnectError)) else "backend_exception"
            logging.getLogger(__name__).error("JST request %s: %s",request_id,error_code)
            raise
        finally:
            try:await asyncio.to_thread(self.store.record,*classify(path),scope.get('method','GET'),status,(time.monotonic()-start)*1000,request_id,error_code or ({401:'authentication_required',403:'access_denied',429:'rate_limited'}.get(status,'request_rejected' if 400<=status<500 else 'server_error' if status>=500 else '')),component)
            except Exception:pass # Monitoring cannot stop chat traffic.

class HardwareSampler:
    def __init__(self):self.previous=None;self.cache=None;self.sampled=0;self.lock=threading.Lock()
    def sample(self):
        with self.lock:
            if self.cache and time.monotonic()-self.sampled<10:return self.cache
            result={'cpu_percent':None,'ram_used_gb':None,'ram_total_gb':None,'gpu':None,'cpu_temperature_c':None}
            if os.name=='nt':
                class Memory(ctypes.Structure):
                    _fields_=[('length',ctypes.c_ulong),('load',ctypes.c_ulong)]+[(key,ctypes.c_ulonglong) for key in ['total','available','page_total','page_available','virtual_total','virtual_available','extended']]
                m=Memory();m.length=ctypes.sizeof(m)
                if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)):
                    result.update(ram_used_gb=round((m.total-m.available)/2**30,2),ram_total_gb=round(m.total/2**30,2))
                times=[ctypes.c_ulonglong() for _ in range(3)]
                if ctypes.windll.kernel32.GetSystemTimes(*[ctypes.byref(t) for t in times]):
                    current=[t.value for t in times]
                    if self.previous:
                        idle,kernel,user=[v-p for v,p in zip(current,self.previous)];total=kernel+user
                        if total>0:result['cpu_percent']=round(max(0,min(100,(total-idle)/total*100)),1)
                    self.previous=current
            disk=shutil.disk_usage(DATA_DIR)
            result['disk_used_gb']=round(disk.used/2**30,1);result['disk_total_gb']=round(disk.total/2**30,1)
            exe=shutil.which('nvidia-smi')
            if exe:
                try:
                    raw=subprocess.run([exe,'--query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=3,check=True,creationflags=0x08000000 if os.name=='nt' else 0)
                    row=next(csv.reader(io.StringIO(raw.stdout)))
                    result['gpu']={'name':row[0].strip(),'percent':float(row[1]),'used_mb':float(row[2]),'total_mb':float(row[3]),'temperature_c':float(row[4])}
                except (OSError,ValueError,StopIteration,subprocess.SubprocessError):pass
            self.cache=result;self.sampled=time.monotonic();return result


def install_operations(app,knowledge_store,queue,settings,store=None):
    store=store or OperationsStore(DATA_DIR/'operations.sqlite');sampler=HardwareSampler();started=time.monotonic()
    app.add_middleware(OperationsMiddleware,store=store)
    cached=None;cached_at=0;lock=asyncio.Lock()
    @app.get('/api/admin/operations')
    async def overview():
        nonlocal cached,cached_at
        async with lock:
            if cached and time.monotonic()-cached_at<10:return cached
            hardware=await asyncio.to_thread(sampler.sample)
            ollama=False
            try:
                async with httpx.AsyncClient(timeout=2) as client:
                    ollama=(await client.get(OLLAMA_LOCAL_URL+'/api/tags')).status_code==200
            except httpx.HTTPError:pass
            try:
                chunks=await asyncio.to_thread(knowledge_store.collection.count);vector=True
            except Exception:chunks=None;vector=False
            cached={'sampled_at':datetime.now(timezone.utc).isoformat(),'uptime_seconds':int(time.monotonic()-started),
                    'services':{'backend':True,'ollama':ollama,'qdrant':vector},'model':DEFAULT_CHAT_MODEL,
                    'auth_enabled':settings.enabled,'hardware':hardware,'chunks':chunks,
                    'queue':{'pending':queue._pending,'capacity':queue.max_waiting+1,'active':int(queue._slots.locked())},
                    'traffic':await asyncio.to_thread(store.summary),'recent':(await asyncio.to_thread(store.browse,'',0,5))['items']}
            cached_at=time.monotonic();return cached
    @app.get('/api/admin/events')
    async def events(category: str=Query('',pattern='^(|auth|chat|document|system)$'),offset:int=Query(0,ge=0),limit:int=Query(20,ge=1,le=50),problems_only:bool=Query(False)):
        return await asyncio.to_thread(store.browse,category,offset,limit,problems_only)
    return store
