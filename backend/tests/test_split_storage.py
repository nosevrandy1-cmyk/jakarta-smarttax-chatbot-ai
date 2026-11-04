"""Migration, isolation and atomicity tests against real temporary SQLite files."""
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

import test_dashboard_empty
import test_room_memory as fixtures
from app.auth import AuthStore, SESSION_COOKIE, GoogleLoginError
from app.source_review import SourceArchive
from app.split_storage import invalidate_memory
from app.room_memory import inherited_memory


class SplitStorageTests(unittest.TestCase):
    setUp = fixtures.RoomMemoryTests.setUp
    tearDown = fixtures.RoomMemoryTests.tearDown
    run_async = fixtures.RoomMemoryTests.run_async
    headers = fixtures.RoomMemoryTests.headers
    body = fixtures.RoomMemoryTests.body

    def test_history_is_normalized_and_all_metadata_round_trips(self):
        uid = self.store.session(self.a)['id']
        value = self.body()
        value['sessions'][0].update(saved=True,pinned=True,unread=True,titleEdited=True,contextLimitReached=512)
        value['sessions'][0]['messages'][1].update(followUps=['Pertanyaan berikut?'],durationMs=15.2,modelUsed='local-model',failed=False)
        with self.store.connect() as db:
            self.store.history.save(uid,value,0,db)
            databases = {r['name']:Path(r['file']).name for r in db.execute('PRAGMA database_list')}
            self.assertEqual(databases['chat'],'conversations.sqlite')
            self.assertEqual(databases['memory'],'memory.sqlite')
            self.assertIsNone(db.execute("SELECT 1 FROM main.sqlite_master WHERE name='account_chat_history'").fetchone())
            self.assertEqual(db.execute('SELECT COUNT(*) FROM messages').fetchone()[0],2)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM message_references').fetchone()[0],1)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM message_followups').fetchone()[0],1)
        self.assertEqual(self.store.history.load(uid),{**value,'revision':1})

    def test_reused_message_ids_in_multiple_rooms_remain_distinct(self):
        uid = self.store.session(self.a)['id']
        value=self.body();second=json.loads(json.dumps(value['sessions'][0]));second['id']='second'
        second['messages'][0]['content']='Different room'
        value['sessions'].append(second)
        self.store.history.save(uid,value,0)
        result=self.store.history.load(uid)
        self.assertEqual(result['sessions'][0]['messages'][0]['content'],'Account A private question')
        self.assertEqual(result['sessions'][1]['messages'][0]['content'],'Different room')

    def test_search_and_cursor_pages_do_not_leak_accounts(self):
        async def check(client):
            client.cookies.set(SESSION_COOKIE,self.a)
            value=self.body('SECRET_ALPHABET')
            value['sessions'][0]['messages']=[{'id':str(i),'role':'user','content':f'SECRET_ALPHABET {i}'} for i in range(65)]
            self.assertEqual((await client.put('/api/history',json=value,headers=self.headers(self.a))).status_code,200)
            path='/api/history/rooms/same-conversation-id/messages'
            first=(await client.get(path,params={'limit':30})).json()
            self.assertEqual(len(first['messages']),30)
            self.assertEqual(first['messages'][0]['content'],'SECRET_ALPHABET 35')
            second=(await client.get(path,params={'before':first['next_cursor'],'limit':30})).json()
            self.assertEqual(second['messages'][0]['content'],'SECRET_ALPHABET 5')
            self.assertTrue((await client.get('/api/history/search',params={'q':'SECRET_ALPHABET'})).json()['items'])
            client.cookies.set(SESSION_COOKIE,self.b)
            self.assertEqual((await client.get(path)).status_code,404)
            self.assertEqual((await client.get('/api/history/search',params={'q':'SECRET_ALPHABET'})).json()['items'],[])
            # SQL/FTS syntax is treated as literal text, never as an operator.
            self.assertEqual((await client.get('/api/history/search',params={'q':'" OR *'})).status_code,200)
        self.run_async(check)

    def test_deleting_parent_invalidates_all_descendants_and_search(self):
        uid=self.store.session(self.a)['id']
        value=self.body('SECRET_PARENT')
        for name in ['child','grandchild']:
            value['sessions'].append({'id':name,'title':name,'theme':'PAT','updatedAt':1,'messages':[]})
        with self.store.connect() as db:
            self.store.history.save(uid,value,0,db)
            for child,parent in [('child','same-conversation-id'),('grandchild','child')]:
                db.execute('INSERT INTO room_memories VALUES(?,?,?,?,?,?)',(uid,child,parent,'Private continuation','fp',1))
        value['sessions']=value['sessions'][1:];value['activeSessionId']=None
        with self.store.connect() as db:
            self.store.history.save(uid,value,1,db)
            invalidate_memory(db)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM memories WHERE user_id=?',(uid,)).fetchone()[0],0)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM chat.outbox_events WHERE state='pending'").fetchone()[0],0)
        self.assertEqual(self.store.history.search(uid,'SECRET_PARENT'),[])
        self.assertEqual(inherited_memory(self.store,uid,'grandchild'),'')

    def test_attached_write_rolls_back_history_and_memory_together(self):
        uid=self.store.session(self.a)['id']
        with self.assertRaises(RuntimeError):
            with self.store.connect() as db:
                db.execute('BEGIN IMMEDIATE')
                self.store.history.save(uid,self.body(),0,db)
                db.execute('INSERT INTO room_checkpoints VALUES(?,?,?,?,?)',(uid,'same-conversation-id','fp','secret',1))
                raise RuntimeError('simulated failure')
        self.assertEqual(self.store.history.load(uid)['sessions'],[])
        with self.store.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM memory_checkpoints').fetchone()[0],0)

    def test_disabled_identity_cannot_register_again_or_create_orphan_account(self):
        uid=self.store.session(self.a)['id']
        with self.store.connect() as db:
            before=db.execute('SELECT COUNT(*) FROM users').fetchone()[0]
            db.execute("UPDATE users SET status='disabled' WHERE id=?",(uid,))
        self.assertIsNone(self.store.session(self.a))
        for intent in ['login','register']:
            with self.assertRaises(GoogleLoginError):
                self.store.create_session(self.claims,intent=intent)
        with self.store.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM users').fetchone()[0],before)

    def test_account_deletion_cascades_private_data_and_sessions(self):
        uid=self.store.session(self.a)['id']
        with self.store.connect() as db:
            self.store.history.save(uid,self.body(),0,db)
            db.execute('INSERT INTO room_memories VALUES(?,?,?,?,?,?)',(uid,'same-conversation-id','parent','secret','fp',1))
            db.execute('DELETE FROM auth_users WHERE id=?',(uid,))
        self.assertIsNone(self.store.session(self.a))
        self.assertEqual(self.store.history.load(uid)['sessions'],[])
        with self.store.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM memories WHERE user_id=?',(uid,)).fetchone()[0],0)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM user_identities WHERE user_id=?',(uid,)).fetchone()[0],0)
            self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(),[])


class LegacyMigrationTests(unittest.TestCase):
    def legacy(self,root):
        path=root/'auth.sqlite'
        db=sqlite3.connect(path)
        db.executescript('''CREATE TABLE auth_users(id TEXT PRIMARY KEY,provider TEXT,subject TEXT,email TEXT,name TEXT,created_at INTEGER,updated_at INTEGER,google_authoritative INTEGER);
            INSERT INTO auth_users VALUES('old-user','google','subject','test@example.test','Name',1,1,0);
            CREATE TABLE account_chat_history(user_id TEXT PRIMARY KEY,revision INTEGER,payload TEXT);
            CREATE TABLE room_memories(user_id TEXT,room_id TEXT,parent_id TEXT,summary TEXT,fingerprint TEXT,created_at INTEGER,PRIMARY KEY(user_id,room_id));
            CREATE TABLE room_checkpoints(user_id TEXT,room_id TEXT,fingerprint TEXT,summary TEXT,updated_at INTEGER,PRIMARY KEY(user_id,room_id));''')
        value={'sessions':[{'id':'old-room','title':'Old','theme':'PAT','updatedAt':1,'saved':True,'messages':[{'id':'m','role':'user','content':'KEPT_SECRET'}]}],'activeSessionId':'old-room'}
        db.execute('INSERT INTO account_chat_history VALUES(?,?,?)',('old-user',7,json.dumps(value)))
        db.execute('INSERT INTO room_memories VALUES(?,?,?,?,?,?)',('old-user','old-room','earlier','Old summary','fp',1))
        db.execute('INSERT INTO room_checkpoints VALUES(?,?,?,?,?)',('old-user','old-room','fp','Old checkpoint',1))
        db.commit();db.close()
        return path,value

    def test_legacy_migration_preserves_history_memory_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as folder:
            path,value=self.legacy(Path(folder))
            store=AuthStore(path);store.initialize()
            self.assertEqual(store.history.load('old-user'),{**value,'revision':7})
            self.assertEqual(inherited_memory(store,'old-user','old-room'),'Old summary')
            store.initialize()
            self.assertEqual(store.history.load('old-user'),{**value,'revision':7})
            with store.connect() as db:
                self.assertEqual(db.execute("SELECT type FROM main.sqlite_master WHERE name='auth_users'").fetchone()[0],'view')
                self.assertEqual(db.execute('SELECT COUNT(*) FROM users').fetchone()[0],1)
                self.assertEqual(db.execute('PRAGMA chat.foreign_key_check').fetchall(),[])
                self.assertEqual(db.execute('PRAGMA memory.foreign_key_check').fetchall(),[])
            self.assertTrue(list(Path(folder).glob('.migration-backups/*/auth-before-split.sqlite')))

    def test_failed_migration_leaves_legacy_payload_untouched(self):
        with tempfile.TemporaryDirectory() as folder:
            path,value=self.legacy(Path(folder))
            with patch('app.conversation_store.ConversationStore.save',side_effect=RuntimeError('fail')):
                with self.assertRaises(RuntimeError):AuthStore(path).initialize()
            db=sqlite3.connect(path)
            try:
                self.assertEqual(json.loads(db.execute('SELECT payload FROM account_chat_history').fetchone()[0]),value)
            finally:db.close()


class KnowledgeSchemaTests(unittest.TestCase):
    def test_normalized_archive_page_category_and_inactive_filter(self):
        with tempfile.TemporaryDirectory() as folder:
            archive=SourceArchive(folder)
            source=archive.stage(['Pasal satu'],[{'doc_name':'Peraturan.pdf','tema_pajak':'PAT','page_number':3}],b'%PDF','Peraturan.pdf')
            detail=archive.detail(source)
            self.assertEqual(detail['chunks'][0]['page'],3)
            with archive.connect() as db:
                chunk=db.execute('SELECT id FROM document_chunks').fetchone()[0]
                self.assertEqual(db.execute('SELECT tax_code FROM chunk_tax_categories').fetchone()[0],'PAT')
                self.assertEqual(db.execute('SELECT physical_page FROM document_pages').fetchone()[0],3)
                self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(),[])
                self.assertIsNone(db.execute("SELECT 1 FROM sqlite_master WHERE name='sources'").fetchone())
            self.assertEqual(archive.valid_hits([chunk],'PAT'),set())
            self.assertEqual(archive.valid_hits(['orphan'],'PAT'),set())
            with self.assertRaises(ValueError):
                archive.stage(['text'],[{'tema_pajak':'OTHER'}],None,'x.json')

    def test_catalog_denies_wrong_tax_and_rejected_or_orphan_vector(self):
        with tempfile.TemporaryDirectory() as folder:
            archive=SourceArchive(folder)
            source=archive.stage(['Khusus air tanah'],[{'tema_pajak':'PAT','doc_name':'Air tanah'}],None,'source.json')
            class Collection:
                def upsert(self,**kwargs):pass
                def delete(self,**kwargs):pass
            class Embedding:
                def embed_texts(self,texts):return [[0.0]*384 for _ in texts]
            archive.review(source,'approve','developer','ok',Collection(),Embedding())
            chunk=json.loads(archive.get(source)['payload'])['ids'][0]
            self.assertEqual(archive.valid_hits([chunk],'PAT'),{chunk})
            self.assertEqual(archive.valid_hits([chunk],'REKLAME'),set())
            with archive.connect() as db:db.execute("UPDATE document_versions SET state='rejected' WHERE id=?",(source,))
            self.assertEqual(archive.valid_hits([chunk],'PAT'),set())

    def test_legacy_source_import_is_exact_and_does_not_restore_after_clear(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            meta={'id':'source','doc_name':'Old.pdf','tema_pajak':'PAT','stored_name':'source.pdf','has_file':True,'chunk_count':1}
            payload={'ids':['old-chunk'],'documents':['Old text'],'metadatas':[{'tema_pajak':'PAT','page_number':2}]}
            (root/'source.pdf').write_bytes(b'original')
            db=sqlite3.connect(root/'sources.sqlite')
            db.execute('CREATE TABLE sources(id TEXT,status TEXT,metadata TEXT,payload TEXT,reviewed_by TEXT,reviewed_at TEXT,note TEXT)')
            db.execute('INSERT INTO sources VALUES(?,?,?,?,?,?,?)',('source','approved',json.dumps(meta),json.dumps(payload),'dev',None,None));db.commit();db.close()
            archive=SourceArchive(root)
            self.assertEqual(json.loads(archive.get('source')['payload']),payload)
            self.assertEqual(archive.file('source')[0].read_bytes(),b'original')
            archive.clear()
            self.assertEqual(SourceArchive(root).list(),[])
