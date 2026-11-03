"""Private normalized history, retaining the existing frontend API shape."""
import json
from pathlib import Path
import time
import uuid
from .db_core import connect, initialize


class RevisionConflict(ValueError):
    pass


class ConversationStore:
    def __init__(self, path):
        self.path = Path(path)
        initialize(self.path, 'conversations')

    def connect(self):
        return connect(self.path)

    @staticmethod
    def message(db, m):
        data = json.loads(m['extra_json'])
        data.update(id=m['id'], role=m['role'], content=m['content'])
        key = (m['user_id'], m['conversation_id'], m['id'])
        refs = [json.loads(r[0]) for r in db.execute('SELECT reference_json FROM message_references WHERE user_id=? AND conversation_id=? AND message_id=? ORDER BY position', key)]
        followups = [r[0] for r in db.execute('SELECT prompt FROM message_followups WHERE user_id=? AND conversation_id=? AND message_id=? ORDER BY position', key)]
        if refs or m['has_references']:
            data['references'] = refs
        if followups or m['has_followups']:
            data['followUps'] = followups
        return data

    def load(self, user_id, db=None, room_id=None):
        if db is None:
            with self.connect() as db:
                return self.load(user_id, db, room_id)
        state = db.execute('SELECT revision,active_session_id FROM history_states WHERE user_id=?', (user_id,)).fetchone()
        rooms = []
        for r in db.execute('SELECT * FROM conversations WHERE user_id=? AND deleted_at IS NULL AND (? IS NULL OR id=?) ORDER BY display_order', (user_id, room_id, room_id)):
            room = json.loads(r['extra_json'])
            room.update(id=r['id'], title=r['title'], theme=r['tax_category'], updatedAt=r['updated_at'])
            room['messages'] = [self.message(db, m) for m in db.execute('SELECT * FROM messages WHERE user_id=? AND conversation_id=? AND deleted_at IS NULL ORDER BY sequence_no', (user_id, r['id']))]
            rooms.append(room)
        return {'revision': state['revision'] if state else 0, 'activeSessionId': state['active_session_id'] if state else None, 'sessions': rooms}

    def room(self, user_id, room_id):
        rooms = self.load(user_id, room_id=room_id)['sessions']
        return rooms[0] if rooms else None

    def save(self, user_id, payload, expected_revision, db=None):
        if db is None:
            with self.connect() as db:
                db.execute('BEGIN IMMEDIATE')
                return self.save(user_id, payload, expected_revision, db)
        state = db.execute('SELECT revision FROM history_states WHERE user_id=?', (user_id,)).fetchone()
        revision = state['revision'] if state else 0
        if revision != expected_revision:
            raise RevisionConflict('Riwayat berubah di tab lain. Muat ulang sebelum melanjutkan.')
        wanted = {r['id'] for r in payload['sessions']}
        previous = {r['id'] for r in db.execute('SELECT id FROM conversations WHERE user_id=?', (user_id,))}
        for removed in previous - wanted:
            self.event(db, user_id, removed, 'room_deleted', revision + 1)
            db.execute('DELETE FROM conversations WHERE user_id=? AND id=?', (user_id, removed))
        for position, room in enumerate(payload['sessions']):
            extra = {k: v for k, v in room.items() if k not in {'id','title','theme','updatedAt','messages'}}
            now = int(room.get('updatedAt', time.time() * 1000))
            db.execute('''INSERT INTO conversations(user_id,id,title,tax_category,created_at,updated_at,extra_json,display_order,pinned,saved,title_edited)
                VALUES(?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(user_id,id) DO UPDATE SET title=excluded.title,tax_category=excluded.tax_category,
                updated_at=excluded.updated_at,extra_json=excluded.extra_json,display_order=excluded.display_order,pinned=excluded.pinned,saved=excluded.saved,title_edited=excluded.title_edited''',
                (user_id,room['id'],room['title'],room['theme'],now,now,json.dumps(extra,ensure_ascii=False),position,int(bool(room.get('pinned'))),int(bool(room.get('saved'))),int(bool(room.get('titleEdited')))))
            key = (user_id,room['id'])
            old = {m['id']:dict(m) for m in db.execute('SELECT * FROM messages WHERE user_id=? AND conversation_id=?',key)}
            ids = {m['id'] for m in room['messages']}
            for removed in old.keys() - ids:
                self.event(db,user_id,room['id'],'message_changed',revision+1)
                db.execute('DELETE FROM messages WHERE user_id=? AND conversation_id=? AND id=?',(*key,removed))
            db.execute('UPDATE messages SET sequence_no=sequence_no+1000000 WHERE user_id=? AND conversation_id=?',key)
            for sequence,m in enumerate(room['messages'],1):
                previous_m = old.get(m['id'])
                state = 'failed' if m.get('failed') else 'cancelled' if 'Respons dihentikan oleh pengguna.' in m['content'] else 'completed'
                changed = bool(previous_m and any(previous_m[k]!=v for k,v in [('content',m['content']),('role',m['role']),('state',state)]))
                if changed or previous_m is None and room['id'] in previous:
                    self.event(db,user_id,room['id'],'message_changed',revision+1)
                extra = {k:v for k,v in m.items() if k not in {'id','role','content','references','followUps'}}
                db.execute('''INSERT INTO messages(user_id,conversation_id,id,sequence_no,role,content,state,revision,created_at,updated_at,extra_json,has_references,has_followups)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(user_id,conversation_id,id) DO UPDATE SET sequence_no=excluded.sequence_no,
                    role=excluded.role,content=excluded.content,state=excluded.state,revision=excluded.revision,updated_at=excluded.updated_at,
                    extra_json=excluded.extra_json,has_references=excluded.has_references,has_followups=excluded.has_followups''',
                    (*key,m['id'],sequence,m['role'],m['content'],state,previous_m['revision']+int(changed) if previous_m else 1,
                    previous_m['created_at'] if previous_m else now,now,json.dumps(extra,ensure_ascii=False),int('references' in m),int('followUps' in m)))
                mkey = (*key,m['id'])
                db.execute('DELETE FROM message_references WHERE user_id=? AND conversation_id=? AND message_id=?',mkey)
                for pos,ref in enumerate(m.get('references') or []):
                    db.execute('INSERT INTO message_references VALUES(?,?,?,?,?,?,?,?,?)',(*mkey,pos,ref.get('number',pos+1),ref.get('document_id'),ref.get('chunk_id'),ref.get('document_name'),json.dumps(ref,ensure_ascii=False)))
                db.execute('DELETE FROM message_followups WHERE user_id=? AND conversation_id=? AND message_id=?',mkey)
                for pos,q in enumerate(m.get('followUps') or []):
                    db.execute('INSERT INTO message_followups VALUES(?,?,?,?,?)',(*mkey,pos,q))
        db.execute('INSERT INTO history_states VALUES(?,?,?) ON CONFLICT(user_id) DO UPDATE SET revision=excluded.revision,active_session_id=excluded.active_session_id',(user_id,revision+1,payload.get('activeSessionId')))
        return revision+1

    @staticmethod
    def event(db,user,room,kind,revision):
        now = int(time.time()*1000)
        db.execute('''INSERT OR IGNORE INTO outbox_events(id,event_key,event_type,aggregate_id,owner_user_id,aggregate_revision,available_at,created_at)
            VALUES(?,?,?,?,?,?,?,?)''',(str(uuid.uuid4()),f'{user}:{room}:{kind}:{revision}',kind,room,user,revision,now,now))

    def page(self,user,room,before=None,limit=30):
        limit = max(1,min(50,limit))
        with self.connect() as db:
            if not db.execute('SELECT 1 FROM conversations WHERE user_id=? AND id=? AND deleted_at IS NULL',(user,room)).fetchone():
                return None
            rows = db.execute('''SELECT * FROM messages WHERE user_id=? AND conversation_id=? AND deleted_at IS NULL
                AND (? IS NULL OR sequence_no<?) ORDER BY sequence_no DESC LIMIT ?''',(user,room,before,before,limit+1)).fetchall()
            shown = rows[:limit]
            return {'messages':[self.message(db,m) for m in reversed(shown)],'next_cursor':shown[-1]['sequence_no'] if len(rows)>limit else None}

    def index(self,user):
        with self.connect() as db:
            state = db.execute('SELECT * FROM history_states WHERE user_id=?',(user,)).fetchone()
            active = state['active_session_id'] if state else None
            sessions = []
            for row in db.execute('''SELECT c.*,(SELECT COUNT(*) FROM messages m WHERE m.user_id=c.user_id AND m.conversation_id=c.id) AS message_count,
                    (SELECT content FROM messages m WHERE m.user_id=c.user_id AND m.conversation_id=c.id AND role='user' ORDER BY sequence_no DESC LIMIT 1) AS preview,
                    (SELECT state FROM messages m WHERE m.user_id=c.user_id AND m.conversation_id=c.id ORDER BY sequence_no DESC LIMIT 1) AS last_state
                    FROM conversations c WHERE c.user_id=? AND c.deleted_at IS NULL ORDER BY display_order''',(user,)):
                room = json.loads(row['extra_json'])
                room.update(id=row['id'],title=row['title'],theme=row['tax_category'],updatedAt=row['updated_at'],
                    messageCount=row['message_count'],preview=(row['preview'] or '')[:180],lastFailed=row['last_state']=='failed',
                    messagesLoaded=row['id']==active,messages=[])
                if room['messagesLoaded']:
                    room['messages'] = [self.message(db,m) for m in db.execute('SELECT * FROM messages WHERE user_id=? AND conversation_id=? ORDER BY sequence_no',(user,row['id']))]
                sessions.append(room)
            return {'revision':state['revision'] if state else 0,'activeSessionId':active,'sessions':sessions}

    def search(self,user,query,limit=30):
        terms = query.split()[:12]
        if not terms:
            return []
        expression = ' AND '.join('"'+t.replace('"','""')+'"' for t in terms)
        with self.connect() as db:
            return [dict(r) for r in db.execute('''SELECT m.conversation_id,m.id,m.content FROM messages_fts f
                JOIN messages m ON m.rowid=f.rowid JOIN conversations c ON c.user_id=m.user_id AND c.id=m.conversation_id
                WHERE messages_fts MATCH ? AND m.user_id=? AND m.deleted_at IS NULL AND c.deleted_at IS NULL ORDER BY m.updated_at DESC,m.sequence_no DESC LIMIT ?''',(expression,user,max(1,min(50,limit))))]
