const test=require('node:test');const assert=require('node:assert/strict');
const fs=require('node:fs');const path=require('node:path');const vm=require('node:vm');const ts=require('typescript');
const code=ts.transpileModule(fs.readFileSync(path.join(__dirname,'../src/lib/taxNavigation.ts'),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;
const scope={exports:{}};vm.runInNewContext(code,scope);const {suggestedTaxTargets,precedingQuestion}=scope.exports;
const plain=value=>JSON.parse(JSON.stringify(value));
test('navigation accepts only a supported different model destination',()=>{
 assert.deepEqual(plain(suggestedTaxTargets('PAT','PBB-P2')),['PAT']);
 for(const value of [undefined,null,'UNKNOWN','PBB-P2',{code:'PAT'}])
   assert.deepEqual(plain(suggestedTaxTargets(value,'PBB-P2')),[]);
});
test('a question naming a tax cannot create a button without model metadata',()=>{
 assert.deepEqual(plain(suggestedTaxTargets('pajak air tanah','PBB-P2')),[]);
});
test('old responses recover only their own preceding user message',()=>{
 const messages=[{role:'user',content:'pajak air tanah'},{role:'assistant',content:'PBB saja'},{role:'user',content:'reklame'},{role:'assistant',content:'Jawaban'}];
 assert.equal(precedingQuestion(messages,1),'pajak air tanah');
 assert.equal(precedingQuestion(messages,3),'reklame');
 assert.equal(precedingQuestion(messages,0),'');
});

test('two model categories survive validation, duplicates and current category are removed',()=>{
 assert.deepEqual(plain(suggestedTaxTargets(['BPHTB','REKLAME'],'PBB-P2')),['BPHTB','REKLAME']);
 assert.deepEqual(plain(suggestedTaxTargets(['PAT','PAT','UNKNOWN','PBB-P2'],'PBB-P2')),['PAT']);
});
