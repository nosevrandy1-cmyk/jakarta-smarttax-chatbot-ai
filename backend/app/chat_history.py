"""Account-owned chat snapshots. History is never inserted into the RAG corpus."""
import json
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, model_validator


class Message(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: str = Field(min_length=1, max_length=120)
    role: Literal['user', 'assistant']
    content: str = Field(max_length=100000)
    references: list[dict] | None = Field(default=None, max_length=50)
    failed: bool | None = None
    thinking: str | None = Field(default=None, max_length=100000)
    modelUsed: str | None = Field(default=None, max_length=120)
    durationMs: float | None = Field(default=None, ge=0)
    suggestedTheme: str | None = Field(default=None, max_length=30)
    followUps: list[str] | None = Field(default=None, max_length=20)
    originalQuestion: str | None = Field(default=None, max_length=10000)
    theme: Literal['PBB-P2', 'JPB', 'PBJT', 'BPHTB', 'REKLAME', 'PAT'] | None = None


class Conversation(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=200)
    theme: Literal['PBB-P2', 'JPB', 'PBJT', 'BPHTB', 'REKLAME', 'PAT']
    updatedAt: int = Field(ge=0)
    saved: bool | None = None
    pinned: bool | None = None
    unread: bool | None = None
    titleEdited: bool | None = None
    contextLimitReached: int | None = Field(default=None, ge=0)
    continuedFrom: str | None = Field(default=None, min_length=1, max_length=120)
    messages: list[Message] = Field(max_length=500)


class History(BaseModel):
    model_config = ConfigDict(extra='forbid')
    revision: int = Field(ge=0)
    sessions: list[Conversation] = Field(max_length=200)
    activeSessionId: str | None = Field(default=None, max_length=120)

    @model_validator(mode='after')
    def unique_identifiers(self):
        try:
            json.dumps(self.model_dump(), ensure_ascii=False).encode('utf-8')
        except UnicodeError:
            raise ValueError('Teks percakapan tidak valid.')
        ids = [s.id for s in self.sessions]
        if len(ids) != len(set(ids)):
            raise ValueError('Duplicate conversation ID')
        if self.activeSessionId is not None and self.activeSessionId not in ids:
            raise ValueError('Active conversation not found')
        for session in self.sessions:
            message_ids = [m.id for m in (session.messages or [])]
            if len(message_ids) != len(set(message_ids)):
                raise ValueError('Duplicate message ID')
        return self


class ConversationPatch(Conversation):
    # Omitted messages preserve the server copy of an unopened conversation.
    messages: list[Message] | None = Field(default=None, max_length=500)


class HistoryPatch(History):
    sessions: list[ConversationPatch] = Field(max_length=200)


def install_history(app, store):
    from .conversation_store import RevisionConflict
    from .split_storage import invalidate_memory
    router = APIRouter(prefix='/api/history')

    @router.get('')
    async def read_history(request: Request):
        user_id = request.state.auth_user['id']
        expected_account = request.headers.get('x-jst-account-id')
        if expected_account is not None and expected_account != user_id:
            raise HTTPException(409, 'Akun browser berubah. Muat ulang halaman.')
        return store.history.load(user_id)

    @router.get('/search')
    async def search_history(request: Request, q: str = ''):
        user_id = request.state.auth_user['id']
        if len(q) > 300 or any(0xD800 <= ord(c) <= 0xDFFF for c in q):
            raise HTTPException(422, 'Pencarian terlalu panjang.')
        expected = request.headers.get('x-jst-account-id')
        if expected is not None and expected != user_id:
            raise HTTPException(409, 'Akun browser berubah. Muat ulang halaman.')
        return {'items': store.history.search(user_id, q)}

    @router.get('/rooms/{room_id}/messages')
    async def read_messages(room_id: str, request: Request, before: int | None = None, limit: int = 30):
        expected = request.headers.get('x-jst-account-id')
        user_id = request.state.auth_user['id']
        if expected is not None and expected != user_id:
            raise HTTPException(409, 'Akun browser berubah. Muat ulang halaman.')
        result = store.history.page(user_id, room_id, before, limit)
        if result is None:
            raise HTTPException(404, 'Percakapan tidak ditemukan.')
        return result

    @router.get('/index')
    async def read_index(request: Request):
        user_id = request.state.auth_user['id']
        expected = request.headers.get('x-jst-account-id')
        if expected is not None and expected != user_id:
            raise HTTPException(409, 'Akun browser berubah. Muat ulang halaman.')
        return store.history.index(user_id)

    @router.get('/rooms/{room_id}')
    async def read_room(room_id: str, request: Request):
        user_id = request.state.auth_user['id']
        expected = request.headers.get('x-jst-account-id')
        if expected is not None and expected != user_id:
            raise HTTPException(409, 'Akun browser berubah. Muat ulang halaman.')
        history = store.history.load(user_id, room_id=room_id)
        if not history['sessions']:
            raise HTTPException(404, 'Percakapan tidak ditemukan.')
        return {'revision': history['revision'], 'session': history['sessions'][0]}

    @router.patch('')
    async def patch_history(body: HistoryPatch, request: Request):
        if not request.headers.get('x-jst-account-id'):
            raise HTTPException(400, 'Identitas akun pada request diperlukan.')
        user_id = request.state.auth_user['id']
        if request.headers.get('x-jst-account-id') != user_id:
            raise HTTPException(409, 'Akun browser berubah. Muat ulang halaman.')
        with store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            current = store.history.load(user_id, db)
            revision = current['revision']
            if body.revision != revision:
                raise HTTPException(409, 'Riwayat berubah di tab atau perangkat lain. Muat ulang sebelum melanjutkan.')
            if not db.execute('SELECT 1 FROM auth_users WHERE id=?', (user_id,)).fetchone():
                raise HTTPException(401, 'Sesi sudah tidak berlaku.')
            previous = {s['id']: s for s in current['sessions']}
            sessions = []
            for room in body.sessions:
                value = room.model_dump(exclude_none=True)
                if room.messages is None:
                    if room.id not in previous:
                        raise HTTPException(422, 'Isi percakapan baru diperlukan.')
                    value['messages'] = previous[room.id]['messages']
                sessions.append(value)
            # Validate the complete snapshot after restoring unloaded messages.
            payload = History(revision=revision, activeSessionId=body.activeSessionId, sessions=sessions).model_dump(exclude={'revision'}, exclude_none=True)
            encoded = json.dumps(payload, ensure_ascii=False)
            if len(encoded.encode('utf-8')) > 900000:
                raise HTTPException(413, 'Riwayat terlalu besar. Hapus percakapan yang tidak diperlukan.')
            try:
                store.history.save(user_id, payload, revision, db)
                invalidate_memory(db)
            except RevisionConflict as error:
                raise HTTPException(409, str(error))
        return {'revision': revision + 1}

    @router.put('')
    async def save_history(body: History, request: Request):
        if not request.headers.get('x-jst-account-id'):
            raise HTTPException(400, 'Identitas akun pada request diperlukan.')
        user_id = request.state.auth_user['id']
        expected_account = request.headers.get('x-jst-account-id')
        if expected_account is not None and expected_account != user_id:
            raise HTTPException(409, 'Akun browser berubah. Muat ulang halaman.')
        payload = body.model_dump(exclude={'revision'}, exclude_none=True)
        encoded = json.dumps(payload, ensure_ascii=False)
        if len(encoded.encode('utf-8')) > 900000:
            raise HTTPException(413, 'Riwayat terlalu besar. Hapus percakapan yang tidak diperlukan.')
        with store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            current = store.history.load(user_id, db)
            revision = current['revision']
            if body.revision != revision:
                raise HTTPException(409, 'Riwayat berubah di tab atau perangkat lain. Muat ulang sebelum melanjutkan.')
            # Ownership comes exclusively from the authenticated session.
            if not db.execute('SELECT 1 FROM auth_users WHERE id=?', (user_id,)).fetchone():
                raise HTTPException(401, 'Sesi sudah tidak berlaku.')
            try:
                store.history.save(user_id, payload, revision, db)
                invalidate_memory(db)
            except RevisionConflict as error:
                raise HTTPException(409, str(error))
        return {'revision': revision + 1}

    app.include_router(router)
