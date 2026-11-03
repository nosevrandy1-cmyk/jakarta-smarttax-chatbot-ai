const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');const path=require('node:path');const vm=require('node:vm');const ts=require('typescript');
const code=ts.transpileModule(fs.readFileSync(path.join(__dirname,'../src/lib/chatContext.ts'),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;
const scope={exports:{},TextEncoder};vm.runInNewContext(code,scope);
const {suggestChatTitle,analyzeChatTitle,resolveChatTitle,getLocalChatCommand,estimateTextTokens,roomContext}=scope.exports;
const policy={limit:4096,systemReserve:1000,sourceReserve:1024,replyReserve:512,roomBudget:1560,estimated:true};
test('first substantive question replaces a greeting or numeric title',()=>{
 assert.equal(suggestChatTitle(['halo','2222','tolong jelaskan pajak air tanah']),'Pajak Air Tanah');
 assert.equal(suggestChatTitle(['tes','halo']),'Uji percakapan');
});
test('titles retain subject and numbers rather than fixed character slicing',()=>{
 assert.equal(suggestChatTitle(['coba hitung PBB untuk NJOP 2 miliar']),'Perhitungan PBB');
 const title=suggestChatTitle(['jelaskan '+Array(20).fill('perhitungan').join(' ')]);assert.ok(title.length<=64);assert.ok(!title.endsWith('perhitung'));
});
test('later questions do not replace the first substantive topic',()=>{
 assert.equal(suggestChatTitle(['jelaskan BPHTB','jelaskan PAT']),'BPHTB');
});
test('empty rooms reserve instructions sources and output',()=>{const state=roomContext([],policy);assert.equal(state.remaining,1560);assert.equal(state.percent,0);assert.equal(state.exhausted,false)});
test('full transcript counts include assistant text and utf8 unicode',()=>{
 const text='税'.repeat(12);assert.equal(estimateTextTokens(text),12);
 const state=roomContext([{content:'a'.repeat(300)},{content:'b'.repeat(300)}],policy);assert.equal(state.used,216);
});
test('pending input blocks oversize sends without reducing stored remaining',()=>{
 const state=roomContext([],policy,'a'.repeat(5000));assert.equal(state.exhausted,true);assert.equal(state.remaining,1560);
});
test('full room stays full after refresh recomputation and zero budget is blocked',()=>{
 const messages=[{content:'a'.repeat(5000)}];assert.equal(roomContext(messages,policy).exhausted,true);assert.equal(roomContext(messages,policy).remaining,0);
 assert.equal(roomContext([],{...policy,roomBudget:0}).exhausted,true);
});

const titleCases=[
 ['halo','Sapaan awal'],['halooooooo!!!','Sapaan awal'],['halo, selamat sore','Sapaan awal'],
 ['assalamu’alaikum','Sapaan awal'],['tes 123','Uji percakapan'],['2222','Uji percakapan'],
 ['berapa denda kalau telat bayar PBB?','Denda Keterlambatan PBB'],
 ['brp denda klo telat bayar pbb?','Denda Keterlambatan PBB'],
 ['tolong itungin bphtb dong','Perhitungan BPHTB'],['berapa tarip pajak air tanah','Tarif Pajak Air Tanah'],
 ['apa beda PBB dan BPHTB?','Perbandingan PBB dan BPHTB'],
 ['gimana cara bayar pajak reklame?','Pembayaran Pajak Reklame'],
 ['apa dasar hukum PBJT?','Dasar Hukum PBJT'],
];
for(const [question,title] of titleCases)test(`title intent: ${question}`,()=>assert.equal(suggestChatTitle([question]),title));
test('unknown topics keep original wording and are explicitly fallback',()=>{
 const result=analyzeChatTitle('bagaimana mengurus rumah warisan keluarga?');
 assert.equal(result.confidence,'fallback');assert.equal(result.title,'Bagaimana mengurus rumah warisan keluarga');
 assert.ok(!result.title.includes('BPHTB'));
});
test('negations and ambiguous multiple subjects do not force an inferred intent',()=>{
 for(const question of ['bukan PBB, saya menanyakan organisasi bangsa','PBB dan BPHTB itu saya punya dokumennya','tanpa denda PBB']){
  const result=analyzeChatTitle(question);assert.equal(result.confidence,'fallback');
 }
});
test('greeting turns can be followed by a real topic while manual titles stay intact',()=>{
 assert.equal(suggestChatTitle(['halo','tes','berapa denda kalau telat bayar PBB?']),'Denda Keterlambatan PBB');
 assert.equal(resolveChatTitle({title:'Catatan rumah saya',titleEdited:true},['halo','jelaskan BPHTB']),'Catatan rumah saya');
 assert.equal(resolveChatTitle({title:'Chat baru'},['halo']),'Sapaan awal');
});
test('long unknown text truncates at word boundaries and preserves numerals',()=>{
 const result=analyzeChatTitle('Apakah objek berkode 98765 dengan nilai 2 miliar ini bisa diproses besok jika arsip belum lengkap?');
 assert.equal(result.confidence,'fallback');assert.ok(result.title.includes('98765'));assert.ok(result.title.length<=64);
 assert.ok(!result.title.endsWith('diprose'));
});
test('unicode emoji and empty drafts are safe and deterministic',()=>{
 assert.equal(suggestChatTitle([]),'Chat baru');
 assert.equal(suggestChatTitle(['税金を相談したい']), '税金を相談したい');
 assert.notEqual(suggestChatTitle(['👋']),'Chat baru');
 const before=JSON.stringify(titleCases);for(const [q] of titleCases)assert.equal(suggestChatTitle([q]),suggestChatTitle([q]));assert.equal(JSON.stringify(titleCases),before);
});

test('unknown personal requests keep the request rather than losing its meaning',()=>{
 assert.equal(suggestChatTitle(['jelasin tentang aku dong']),'Jelasin tentang aku dong');
 assert.equal(analyzeChatTitle('jelasin tentang aku dong').confidence,'fallback');
});

test('context is a local command only for the exact command, with whitespace or case',()=>{
 assert.equal(getLocalChatCommand(' /context '),'context');assert.equal(getLocalChatCommand('/CONTEXT'),'context');
 assert.equal(getLocalChatCommand('jelaskan /context'),null);assert.equal(getLocalChatCommand('/contextual'),null);
});
