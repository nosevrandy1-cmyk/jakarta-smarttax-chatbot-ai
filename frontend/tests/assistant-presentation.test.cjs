const test=require('node:test');const assert=require('node:assert/strict');const fs=require('node:fs');const path=require('node:path');const vm=require('node:vm');const ts=require('typescript');
const code=ts.transpileModule(fs.readFileSync(path.join(__dirname,'../src/lib/assistantPresentation.ts'),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;
const scope={exports:{}};vm.runInNewContext(code,scope);const {presentAssistantMessage}=scope.exports;
test('malformed saved metadata is hidden and its suggestions recovered',()=>{
 const raw={role:'assistant',content:'Rumus nilai awal.\n<JST_FOLLOW_UPS["Apa saja kategori yang tersedia dalam simulasi ini?","Bagaimana contoh perhitungan untuk objek tertentu?"]</JST_FOLLOW_UPS>'};
 const shown=presentAssistantMessage(raw);assert.equal(shown.content,'Rumus nilai awal.');assert.equal(shown.followUps.length,2);assert.ok(raw.content.includes('<JST_FOLLOW_UPS'));
});
test('bad optional metadata cannot hide the answer or become suggested markup',()=>{
 const shown=presentAssistantMessage({role:'assistant',content:'Jawaban utama.<JST_FOLLOW_UPS[broken</JST_FOLLOW_UPS>'});assert.equal(shown.content,'Jawaban utama.');assert.equal(shown.followUps.length,0);
});
test('ordinary answer code and user messages remain unchanged',()=>{
 for(const raw of [{role:'assistant',content:'Nilai < 100; [1] tetap ada.'},{role:'user',content:'Apa itu <JST_FOLLOW_UPS>?'}])assert.equal(presentAssistantMessage(raw),raw);
});
test('legacy followups reject echoes links and file operations',()=>{
 const shown=presentAssistantMessage({role:'assistant',originalQuestion:'Apa rumusnya?',content:'Rumus.<JST_FOLLOW_UPS>["Apa rumusnya?","Upload dokumen berikut?","Buka https://example.test","Apa dasar perhitungannya?"]</JST_FOLLOW_UPS>'});assert.equal(shown.followUps.length,1);assert.equal(shown.followUps[0],'Apa dasar perhitungannya?');
});
