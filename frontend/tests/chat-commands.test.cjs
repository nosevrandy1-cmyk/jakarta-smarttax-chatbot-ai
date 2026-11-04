const test=require('node:test');const assert=require('node:assert/strict');const fs=require('node:fs');const path=require('node:path');const vm=require('node:vm');const ts=require('typescript');
const code=ts.transpileModule(fs.readFileSync(path.join(__dirname,'../src/lib/chatCommands.ts'),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;
const scope={exports:{}};vm.runInNewContext(code,scope);const {getCommandSuggestions,resolveCommandInput}=scope.exports;
test('slash and unfinished command offer the canonical context command',()=>{for(const input of ['/','/c','/cont','/contex','/context'])assert.equal(getCommandSuggestions(input)[0].command,'/context')});
test('completion handles case and surrounding whitespace',()=>assert.equal(resolveCommandInput(' /CONT '),'/context'));
test('ordinary questions and unknown commands are not corrected into context',()=>{for(const input of ['halo','apa /context','/contacts','/context foo','/unknown']){assert.equal(getCommandSuggestions(input).length,0);assert.equal(resolveCommandInput(input),null)}});
