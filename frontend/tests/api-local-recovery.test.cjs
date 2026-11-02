const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const ts=require('typescript');
const code=ts.transpileModule(fs.readFileSync(path.join(__dirname,'../src/lib/api.ts'),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;
function setup(session, detail='Permintaan tidak valid. Muat ulang halaman.') {
  const calls=[];
  const scope={exports:{},process:{env:{}},Headers,fetch:async(url,options)=>{
    calls.push({url,headers:new Headers(options.headers)});
    if(calls.length===1)return new Response(JSON.stringify({detail}),{status:403});
    if(url.endsWith('/api/auth/session'))return new Response(JSON.stringify(session));
    return new Response('{}');
  }};
  vm.runInNewContext(code,scope);
  scope.exports.setCsrfToken('old-test-token');
  return {api:scope.exports,calls};
}
test('local restart recovery retries once with refreshed CSRF and same account',async()=>{
  const {api,calls}=setup({user:{id:'local',local:true},csrf_token:'new-test-token'});
  const response=await api.apiFetch('/api/history',{method:'PATCH',headers:{'X-JST-Account-ID':'local'},body:'{}'});
  assert.equal(response.status,200);assert.equal(calls.length,3);
  assert.equal(calls[2].headers.get('X-CSRF-Token'),'new-test-token');
  assert.equal(calls[2].headers.get('X-JST-Account-ID'),'local');
});
test('different accounts and Google sessions are not automatically retried',async()=>{
  for(const user of [{id:'other',local:true},{id:'local',local:false}]){
    const {api,calls}=setup({user,csrf_token:'new-test-token'});
    const response=await api.apiFetch('/api/history',{method:'PATCH',headers:{'X-JST-Account-ID':'local'},body:'{}'});
    assert.equal(response.status,403);assert.equal(calls.length,2);
  }
});
test('developer authorization failures never trigger retry or refresh',async()=>{
  const {api,calls}=setup({user:{id:'local',local:true},csrf_token:'new-test-token'},'Hanya akun developer yang dapat mengakses fitur ini.');
  const response=await api.apiFetch('/api/rag/ingest-pdf',{method:'POST',body:'{}'});
  assert.equal(response.status,403);assert.equal(calls.length,1);
});
