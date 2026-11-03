import unittest
from unittest.mock import patch

import test_auth as fixtures
from app.auth import SESSION_COOKIE
from app.chat_history import install_history


class ChatHistoryTests(unittest.TestCase):
    tearDown = fixtures.GoogleAuthTests.tearDown
    run_async = fixtures.GoogleAuthTests.run_async

    def setUp(self):
        fixtures.GoogleAuthTests.setUp(self)
        install_history(self.app, self.store)
        self.a = self.store.create_session(self.claims, intent='register')
        self.b = self.store.create_session({**self.claims, 'sub':'second-account', 'email':'other@example.test'}, intent='register')

    def headers(self, token):
        return {'X-JST-Account-ID':self.store.session(token)['id'], 'Origin':self.settings.public_url, 'X-CSRF-Token':self.store.session(token)['csrf']}

    def body(self, text='Account A private question', revision=0):
        return {'revision':revision, 'activeSessionId':'same-conversation-id', 'sessions':[
            {'id':'same-conversation-id', 'title':'Private conversation', 'theme':'PBB-P2', 'updatedAt':123,
             'messages':[{'id':'m1', 'role':'user', 'content':text},
                         {'id':'m2', 'role':'assistant', 'content':'A referenced answer', 'references':[
                             {'number':1, 'chunk_id':'c1', 'document_name':'Test source', 'text':'Reference text'}]}]}]}

    def test_two_users_cannot_read_or_overwrite_each_other_even_with_same_chat_id(self):
        async def check(c):
            c.cookies.set(SESSION_COOKIE, self.a)
            self.assertEqual((await c.put('/api/history',json=self.body(),headers=self.headers(self.a))).status_code,200)
            c.cookies.set(SESSION_COOKIE,self.b)
            self.assertEqual((await c.get('/api/history')).json()['sessions'],[])
            self.assertEqual((await c.put('/api/history',json=self.body('Account B only'),headers=self.headers(self.b))).status_code,200)
            c.cookies.set(SESSION_COOKIE,self.a)
            history=(await c.get('/api/history',params={'user_id':'second-account'})).json()
            self.assertEqual(history['sessions'][0]['messages'][0]['content'],'Account A private question')
            self.assertNotIn('Account B only', str(history))
        self.run_async(check)

    def test_old_tab_cannot_save_account_a_content_after_browser_switches_to_b(self):
        async def check(c):
            old_headers=self.headers(self.a)
            c.cookies.set(SESSION_COOKIE,self.b)
            current_headers=self.headers(self.b)
            response=await c.put('/api/history',json=self.body(),headers={**current_headers,'X-JST-Account-ID':old_headers['X-JST-Account-ID']})
            self.assertEqual(response.status_code,409)
            self.assertEqual((await c.get('/api/history')).json()['sessions'],[])
            self.assertEqual((await c.get('/api/history',headers={'X-JST-Account-ID':old_headers['X-JST-Account-ID']})).status_code,409)
        self.run_async(check)

    def test_logout_and_login_again_preserve_history(self):
        async def check(c):
            c.cookies.set(SESSION_COOKIE,self.a)
            await c.put('/api/history',json=self.body(),headers=self.headers(self.a))
            self.assertEqual((await c.post('/api/auth/logout',headers=self.headers(self.a))).status_code,200)
            self.assertEqual((await c.get('/api/history')).status_code,401)
            token=self.store.create_session(self.claims)
            c.cookies.set(SESSION_COOKIE,token)
            restored=(await c.get('/api/history')).json()
            self.assertEqual(restored['sessions'][0]['messages'][1]['references'][0]['chunk_id'],'c1')
        self.run_async(check)

    def test_anonymous_cannot_read_or_write(self):
        async def check(c):
            self.assertEqual((await c.get('/api/history')).status_code,401)
            self.assertEqual((await c.put('/api/history',json=self.body())).status_code,401)
        self.run_async(check)

    def test_mutations_require_csrf_and_exact_origin(self):
        async def check(c):
            c.cookies.set(SESSION_COOKIE,self.a)
            self.assertEqual((await c.put('/api/history',json=self.body())).status_code,403)
            self.assertEqual((await c.put('/api/history',json=self.body(),headers={**self.headers(self.a),'Origin':'https://attacker.test'})).status_code,403)
            self.assertEqual((await c.get('/api/history')).json()['sessions'],[])
        self.run_async(check)

    def test_stale_revision_does_not_overwrite_newer_tab(self):
        async def check(c):
            c.cookies.set(SESSION_COOKIE,self.a)
            self.assertEqual((await c.put('/api/history',json=self.body(),headers=self.headers(self.a))).status_code,200)
            response=await c.put('/api/history',json=self.body('stale tab'),headers=self.headers(self.a))
            self.assertEqual(response.status_code,409)
            self.assertEqual((await c.get('/api/history')).json()['sessions'][0]['messages'][0]['content'],'Account A private question')
        self.run_async(check)

    def test_rename_delete_and_restore_persist_with_revisions(self):
        async def check(c):
            c.cookies.set(SESSION_COOKIE,self.a)
            await c.put('/api/history',json=self.body(),headers=self.headers(self.a))
            renamed=self.body(revision=1)
            renamed['sessions'][0].update(title='Renamed conversation',titleEdited=True)
            self.assertEqual((await c.put('/api/history',json=renamed,headers=self.headers(self.a))).status_code,200)
            self.assertEqual((await c.get('/api/history')).json()['sessions'][0]['title'],'Renamed conversation')
            self.assertEqual((await c.put('/api/history',json={'revision':2,'sessions':[],'activeSessionId':None},headers=self.headers(self.a))).status_code,200)
            self.assertEqual((await c.get('/api/history')).json()['sessions'],[])
            renamed['revision']=3
            self.assertEqual((await c.put('/api/history',json=renamed,headers=self.headers(self.a))).status_code,200)
        self.run_async(check)

    def test_invalid_payload_cannot_assign_another_user_or_store_system_messages(self):
        async def check(c):
            c.cookies.set(SESSION_COOKIE,self.a)
            payloads=[]
            payloads.append({**self.body(), 'user_id':'someone-else'})
            system=self.body();system['sessions'][0]['messages'][0]['role']='system';payloads.append(system)
            duplicate=self.body();duplicate['sessions']*=2;payloads.append(duplicate)
            missing=self.body();missing['activeSessionId']='missing';payloads.append(missing)
            for body in payloads:
                self.assertEqual((await c.put('/api/history',json=body,headers=self.headers(self.a))).status_code,422)
            self.assertEqual((await c.get('/api/history')).json()['sessions'],[])
        self.run_async(check)

    def test_expired_session_cannot_read_history(self):
        with self.store.connect() as db:
            db.execute('UPDATE auth_sessions SET expires_at=0')
        async def check(c):
            c.cookies.set(SESSION_COOKIE,self.a)
            self.assertEqual((await c.get('/api/history')).status_code,401)
        self.run_async(check)

    def test_payload_limit_and_no_store_responses(self):
        async def check(c):
            c.cookies.set(SESSION_COOKIE,self.a)
            body=self.body()
            body['sessions'][0]['messages']=[{'id':str(i),'role':'user','content':'x'*95000} for i in range(10)]
            self.assertEqual((await c.put('/api/history',json=body,headers=self.headers(self.a))).status_code,413)
            self.assertEqual((await c.get('/api/history')).headers['cache-control'],'no-store')
        self.run_async(check)

    def test_unread_and_failed_status_survive_reload_and_remain_account_owned(self):
        async def check(c):
            c.cookies.set(SESSION_COOKIE, self.a)
            body = self.body()
            body['sessions'][0]['unread'] = True
            body['sessions'][0]['messages'][-1]['failed'] = True
            self.assertEqual((await c.put('/api/history', json=body, headers=self.headers(self.a))).status_code, 200)
            restored = (await c.get('/api/history')).json()
            self.assertTrue(restored['sessions'][0]['unread'])
            self.assertTrue(restored['sessions'][0]['messages'][-1]['failed'])
            restored['sessions'][0]['unread'] = False
            self.assertEqual((await c.put('/api/history', json=restored, headers=self.headers(self.a))).status_code, 200)
            self.assertFalse((await c.get('/api/history')).json()['sessions'][0]['unread'])
            c.cookies.set(SESSION_COOKIE, self.b)
            self.assertEqual((await c.get('/api/history')).json()['sessions'], [])
        self.run_async(check)

    def test_index_omits_other_room_messages_and_patch_preserves_them(self):
        async def check(c):
            c.cookies.set(SESSION_COOKIE, self.b)
            body = self.body()
            body['sessions'].append({**body['sessions'][0], 'id':'older-room', 'messages':[{'id':'old','role':'user','content':'Retain this unopened message'}]})
            self.assertEqual((await c.put('/api/history', json=body, headers=self.headers(self.b))).status_code, 200)
            index = (await c.get('/api/history/index')).json()
            older = index['sessions'][1]
            self.assertEqual(older['messages'], [])
            self.assertFalse(older['messagesLoaded'])
            self.assertEqual(older['preview'], 'Retain this unopened message')
            self.assertEqual(older['messageCount'], 1)
            self.assertTrue(index['sessions'][0]['messagesLoaded'])
            patch = {'revision':index['revision'], 'activeSessionId':body['activeSessionId'], 'sessions':body['sessions']}
            del patch['sessions'][1]['messages']
            patch['sessions'][1]['title']='Renamed without loading'
            self.assertEqual((await c.patch('/api/history',json=patch,headers=self.headers(self.b))).status_code,200)
            room = await c.get('/api/history/rooms/older-room')
            self.assertEqual(room.status_code,200)
            self.assertEqual(room.json()['session']['messages'][0]['content'],'Retain this unopened message')
            self.assertEqual(room.json()['session']['title'],'Renamed without loading')
            self.assertEqual((await c.patch('/api/history',json=patch,headers=self.headers(self.b))).status_code,409)
            c.cookies.set(SESSION_COOKIE, self.a)
            self.assertEqual((await c.get('/api/history/rooms/older-room')).status_code,404)
            self.assertEqual((await c.get('/api/history/index')).json()['sessions'],[])
        self.run_async(check)

    def test_partial_history_cannot_create_room_without_messages_or_bypass_csrf(self):
        async def check(c):
            c.cookies.set(SESSION_COOKIE,self.b)
            body=self.body()
            del body['sessions'][0]['messages']
            self.assertEqual((await c.patch('/api/history',json=body,headers=self.headers(self.b))).status_code,422)
            headers=self.headers(self.b);headers.pop('X-CSRF-Token')
            self.assertEqual((await c.patch('/api/history',json=self.body(),headers=headers)).status_code,403)
            self.assertEqual((await c.get('/api/history')).json()['sessions'],[])
        self.run_async(check)

    def test_saved_and_pinned_flags_persist_without_loading_messages(self):
        async def check(c):
            c.cookies.set(SESSION_COOKIE,self.b)
            body=self.body()
            self.assertEqual((await c.put('/api/history',json=body,headers=self.headers(self.b))).status_code,200)
            body['revision']=1
            room=body['sessions'][0]
            room['saved']=True;room['pinned']=True
            del room['messages']
            self.assertEqual((await c.patch('/api/history',json=body,headers=self.headers(self.b))).status_code,200)
            index=(await c.get('/api/history/index')).json()
            self.assertTrue(index['sessions'][0]['saved'])
            self.assertTrue(index['sessions'][0]['pinned'])
            detail=(await c.get('/api/history/rooms/same-conversation-id')).json()['session']
            self.assertEqual(len(detail['messages']),2)
            body['revision']=2;room['saved']=False;room['pinned']=False
            self.assertEqual((await c.patch('/api/history',json=body,headers=self.headers(self.b))).status_code,200)
            detail=(await c.get('/api/history')).json()['sessions'][0]
            self.assertFalse(detail['saved']);self.assertFalse(detail['pinned'])
            c.cookies.set(SESSION_COOKIE,self.a)
            self.assertEqual((await c.get('/api/history/index')).json()['sessions'],[])
            self.assertEqual((await c.get('/api/history/rooms/same-conversation-id')).status_code,404)
        self.run_async(check)
