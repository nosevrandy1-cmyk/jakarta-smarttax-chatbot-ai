const test=require('node:test');const assert=require('node:assert/strict');
const fs=require('node:fs');const path=require('node:path');const vm=require('node:vm');const ts=require('typescript');
const code=ts.transpileModule(fs.readFileSync(path.join(__dirname,'../src/lib/titleLayout.ts'),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;
const scope={exports:{}};vm.runInNewContext(code,scope);const {fitTitleToWidth}=scope.exports;
const measure=text=>Array.from(text).length;
test('narrow titles end at the last whole word',()=>{assert.equal(fitTitleToWidth('Perhitungan pajak rumah warisan',19,measure),'Perhitungan pajak…')});
test('widening restores the full title without changing its source',()=>{const title='Denda Keterlambatan PBB';assert.equal(fitTitleToWidth(title,12,measure),'Denda…');assert.equal(fitTitleToWidth(title,50,measure),title)});
test('one word wider than its container is never cut mid-word',()=>{assert.equal(fitTitleToWidth('Keterlambatan',5,measure),'…');assert.equal(fitTitleToWidth('PBB',0,measure),'')});
test('word boundaries work with punctuation unicode and variable glyph widths',()=>{assert.equal(fitTitleToWidth('Pajak café Jakarta',12,measure),'Pajak café…');const wide=text=>Array.from(text).reduce((s,c)=>s+(c==='W'?3:1),0);assert.equal(fitTitleToWidth('WWW pajak',10,wide),'WWW…')});
