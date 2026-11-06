const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');
const compiled = ts.transpileModule(fs.readFileSync(path.join(__dirname, '../src/lib/chatHistoryState.ts'), 'utf8'), {
  compilerOptions: {module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022},
}).outputText;
const scope = {exports: {}};
vm.runInNewContext(compiled, scope);
const {
  hasStartedConversation,
  historyTransport,
  isSessionGenerating,
  countGeneratingSessions,
  canStartSessionGeneration,
} = scope.exports;
const plain = value => JSON.parse(JSON.stringify(value));

test('empty drafts never enter persisted history or become its active ID', () => {
  const result = historyTransport([{id:'draft', messages:[]}], 'draft');
  assert.deepEqual(plain(result), {activeSessionId:null,sessions:[]});
  const rooms = [{id:'draft',messages:[]},{id:'started',messages:[{role:'user',content:'Hello'}]}];
  assert.equal(historyTransport(rooms,'draft').activeSessionId,'started');
});

test('first sent message promotes a draft; transient stream fields are omitted', () => {
  const result=historyTransport([{id:'draft',messages:[{role:'user',content:'Hello',statusText:'Working'}],saved:true,pinned:true}],'draft');
  assert.equal(result.activeSessionId,'draft');
  assert.deepEqual(plain(result.sessions[0]),{id:'draft',saved:true,pinned:true,messages:[{role:'user',content:'Hello'}]});
});

test('unloaded rooms remain present but never overwrite stored messages with empty arrays', () => {
  const room={id:'old',messagesLoaded:false,messageCount:12,preview:'Hello',lastFailed:false,messages:[],saved:true,pinned:true};
  assert.equal(hasStartedConversation(room),true);
  assert.deepEqual(plain(historyTransport([room],'old').sessions),[{id:'old',saved:true,pinned:true}]);
});

test('legacy empty metadata is excluded, while loaded messages take precedence over stale counts', () => {
  assert.equal(hasStartedConversation({messagesLoaded:false,messageCount:0,messages:[]}),false);
  assert.equal(hasStartedConversation({messagesLoaded:true,messageCount:12,messages:[]}),false);
  assert.equal(hasStartedConversation({messagesLoaded:true,messageCount:0,messages:[{}]}),true);
});

test('pinned rooms stay above newly created and newly active unpinned rooms',()=>{
  const rooms=[{id:'new-chat',updatedAt:900},{id:'pinned-old',updatedAt:1,pinned:true},{id:'recent',updatedAt:500},{id:'pinned-recent',updatedAt:3,pinned:true}];
  const sorted=scope.exports.orderSidebarConversations(rooms);
  assert.deepEqual(plain(sorted.map(room=>room.id)),['pinned-recent','pinned-old','new-chat','recent']);
  assert.equal(rooms[0].id,'new-chat');
  rooms[2].updatedAt=1000;
  assert.equal(scope.exports.orderSidebarConversations(rooms)[0].id,'pinned-recent');
});

test('per-session generation isolates streaming state to the active room and allows a queued new chat', () => {
  const rooms = [
    {id: 'new-draft', messagesLoaded: true, messages: []},
    {id: 'room-a', messagesLoaded: true, messages: [{role: 'user', content: 'A'}, {role: 'assistant', content: '', isStreaming: true}]},
  ];
  assert.equal(isSessionGenerating(rooms[0]), false);
  assert.equal(isSessionGenerating(rooms[1]), true);
  assert.equal(countGeneratingSessions(rooms), 1);
  assert.deepEqual(plain(canStartSessionGeneration(rooms, 'room-a', 2)), {
    allowed: false,
    reason: 'already_generating',
    queued: false,
  });
  assert.deepEqual(plain(canStartSessionGeneration(rooms, 'new-draft', 2)), {
    allowed: true,
    queued: true,
  });

  const withQueued = [
    {id: 'third-draft', messagesLoaded: true, messages: []},
    {id: 'new-draft', messagesLoaded: true, messages: [{role: 'user', content: 'B'}, {role: 'assistant', content: '', isStreaming: true}]},
    rooms[1],
  ];
  assert.equal(countGeneratingSessions(withQueued), 2);
  assert.deepEqual(plain(canStartSessionGeneration(withQueued, 'third-draft', 2)), {
    allowed: false,
    reason: 'queue_full',
    queued: false,
  });
});


test('completed rooms save while another streams; partial assistant text never persists', () => {
  const rooms = [
    {id:'a',messages:[{id:'u1',role:'user',content:'A'},{id:'a1',role:'assistant',content:'Done',theme:'PAT'}]},
    {id:'b',messages:[{id:'u2',role:'user',content:'B'},{id:'a2',role:'assistant',content:'Partial',isStreaming:true}]},
  ];
  const first=plain(historyTransport(rooms,'b'));
  assert.equal(first.sessions[0].messages[1].theme,'PAT');
  assert.equal(first.sessions[1].messages.length,1);
  rooms[1].messages[1].content+=' more tokens';
  assert.deepEqual(plain(historyTransport(rooms,'b')),first);
  rooms[1].messages[1].isStreaming=false;
  assert.equal(historyTransport(rooms,'b').sessions[1].messages.length,2);
});
