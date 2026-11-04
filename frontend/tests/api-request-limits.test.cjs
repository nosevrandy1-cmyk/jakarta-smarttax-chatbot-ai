const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const ts=require('typescript');
const code=ts.transpileModule(fs.readFileSync(path.join(__dirname,'../src/lib/api.ts'),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;
function setup(handler=async()=>new Response('{}')){
  let now=100000;const calls=[];
  class Clock extends Date{static now(){return now;}}
  const scope={exports:{},process:{env:{}},Headers,DOMException,Date:Clock,setTimeout,clearTimeout,fetch:async(...args)=>{calls.push(args);return handler(...args);}};
  vm.runInNewContext(code,scope);
  return {api:scope.exports,calls,tick:ms=>{now+=ms;}};
}
test('rapid chat sends are blocked before hitting the server and resume after cooldown',async()=>{
  const {api,calls,tick}=setup();
  await api.apiFetch('/api/chat/stream',{method:'POST',body:'{}'});
  tick(1500);
  await assert.rejects(api.apiFetch('/api/chat/stream',{method:'POST',body:'{}'}),{name:'ApiRequestLimitError'});
  assert.equal(calls.length,1);assert.ok(api.getChatWaitMs()>0);
  tick(5501);await api.apiFetch('/api/chat/stream',{method:'POST',body:'{}'});
  assert.equal(calls.length,2);
});
test('double clicks cannot submit concurrent expensive mutations, even to different source endpoints',async()=>{
  let release;const held=new Promise(resolve=>{release=resolve;});
  const {api,calls}=setup(async()=>{await held;return new Response('{}');});
  const first=api.apiFetch('/api/rag/ingest-pdf',{method:'POST',body:'{}'});
  await assert.rejects(api.apiFetch('/api/rag/evaluate',{method:'POST',body:'{}'}),{name:'ApiRequestLimitError'});
  release();await first;assert.equal(calls.length,1);
});
test('429 honors Retry-After and blocks subsequent network calls without automatic retry',async()=>{
  const {api,calls,tick}=setup(async()=>new Response('{}',{status:429,headers:{'Retry-After':'45'}}));
  await assert.rejects(api.apiFetch('/api/chat',{method:'POST',body:'{}'}),{name:'ApiRequestLimitError'});
  assert.equal(calls.length,1);assert.equal(api.getChatWaitMs(),45000);
  tick(2000);await assert.rejects(api.apiFetch('/api/chat',{method:'POST',body:'{}'}),{name:'ApiRequestLimitError'});
  assert.equal(calls.length,1);
});
test('general API budget stops a request storm before the backend limit',async()=>{
  const {api,calls,tick}=setup();
  for(let i=0;i<80;i++){await api.apiFetch('/api/history/index');tick(250);}
  await assert.rejects(api.apiFetch('/api/history/index'),{name:'ApiRequestLimitError'});
  assert.equal(calls.length,80);
  tick(65001);await api.apiFetch('/api/history/index');assert.equal(calls.length,81);
});
test('aborted requests never consume network calls or clear a mutation lock permanently',async()=>{
  const {api,calls}=setup();const controller=new AbortController();controller.abort();
  await assert.rejects(api.apiFetch('/api/history',{method:'PATCH',body:'{}',signal:controller.signal}));
  assert.equal(calls.length,0);
  await api.apiFetch('/api/history',{method:'PATCH',body:'{}'});assert.equal(calls.length,1);
});

test('repeated read clicks share one network call and each caller gets a readable response',async()=>{
  let release;const held=new Promise(resolve=>{release=resolve;});
  const {api,calls}=setup(async()=>{await held;return new Response('{"ok":true}');});
  const first=api.apiFetch('/api/rag/sources');const second=api.apiFetch('/api/rag/sources');
  release();const [a,b]=await Promise.all([first,second]);
  assert.equal(calls.length,1);assert.deepEqual(await a.json(),{ok:true});assert.deepEqual(await b.json(),{ok:true});
});
