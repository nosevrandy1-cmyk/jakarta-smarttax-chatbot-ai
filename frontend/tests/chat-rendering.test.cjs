const test=require('node:test');const assert=require('node:assert/strict');
const fs=require('node:fs');const path=require('node:path');const vm=require('node:vm');const ts=require('typescript');
const code=ts.transpileModule(fs.readFileSync(path.join(__dirname,'../src/lib/chatRendering.ts'),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;
const scope={exports:{}};vm.runInNewContext(code,scope);const {CHAT_RENDERING,shouldVirtualizeChat,selectVirtualMessages}=scope.exports;
test('short rooms retain normal rendering; long rooms enable virtualization',()=>{
 assert.equal(shouldVirtualizeChat(0),false);assert.equal(shouldVirtualizeChat(40),false);assert.equal(shouldVirtualizeChat(41),true);assert.equal(CHAT_RENDERING.overscan,6);
});
test('a 400-message transcript renders only selected rows without truncating history',()=>{
 const messages=Array.from({length:400},(_,id)=>({id,content:`message ${id}`}));
 const rows=selectVirtualMessages(messages,[{index:120,start:14000},{index:121,start:14200},{index:399,start:45000}]);
 assert.equal(rows.length,3);assert.equal(messages.length,400);
 assert.equal(rows[0].index,120);assert.equal(rows[0].message,messages[120]);assert.equal(rows[2].message,messages[399]);
 assert.equal(rows[0].offset,14000);
});
test('scrolling to older rows preserves source indices and leaves newer content intact',()=>{
 const messages=Array.from({length:100},(_,id)=>({id,content:`message ${id}`}));
 const previous=JSON.stringify(messages);
 const older=selectVirtualMessages(messages,[{index:0,start:18},{index:1,start:100},{index:101,start:99999}]);
 assert.equal(older.length,2);assert.equal(older[0].message.id,0);assert.equal(JSON.stringify(messages),previous);
 assert.equal(selectVirtualMessages(messages,[]).length,0);
});
