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
    thinking: str | None = Field(default=None, max_length=100000)
    modelUsed: str | None = Field(default=None, max_length=120)
    durationMs: float | None = Field(default=None, ge=0)
    suggestedTheme: str | None = Field(default=None, max_length=30)
    followUps: list[str] | None = Field(default=None, max_length=20)
    originalQuestion: str | None = Field(default=None, max_length=10000)


class Conversation(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=200)
    theme: Literal['PBB-P2', 'JPB', 'PBJT', 'BPHTB', 'REKLAME', 'PAT']
    updatedAt: int = Field(ge=0)
    titleEdited: bool | None = None
    messages: list[Message] = Field(max_length=500)


class History(BaseModel):
    model_config = ConfigDict(extra='forbid')
    revision: int = Field(ge=0)
    sessions: list[Conversation] = Field(max_length=200)
    activeSessionId: str | None = Field(default=None, max_length=120)

    @model_validator(mode='after')
    def unique_identifiers(self):
        ids = [s.id for s in self.sessions]
        if len(ids) != len(set(ids)):
            raise ValueError('Duplicate conversation ID')
        if self.activeSessionId is not None and self.activeSessionId not in ids:
            raise ValueError('Active conversation not found')
        for session in self.sessions:
            message_ids = [m.id for m in session.messages]
            if len(message_ids) != len(set(message_ids)):
                raise ValueError('Duplicate message ID')
        return self


def install_history(app, store):
    with store.connect() as db:
        db.execute('''CREATE TABLE IF NOT EXISTS account_chat_history (
            user_id TEXT PRIMARY KEY, revision INTEGER NOT NULL, payload TEXT NOT NULL)''')
    router = APIRouter(prefix='/api/history')

    @router.get('')
    async def read_history(request: Request):
        user_id = request.state.auth_user['id']
        expected_account = request.headers.get('x-jst-account-id')
        if expected_account is not None and expected_account != user_id:
            raise HTTPException(409, 'Akun browser berubah. Muat ulang halaman.')
        with store.connect() as db:
            row = db.execute('SELECT revision,payload FROM account_chat_history WHERE user_id=?', (user_id,)).fetchone()
        if row is None:
            return {'revision': 0, 'sessions': [], 'activeSessionId': None}
        return {**json.loads(row['payload']), 'revision': row['revision']}

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
            row = db.execute('SELECT revision FROM account_chat_history WHERE user_id=?', (user_id,)).fetchone()
            revision = row['revision'] if row else 0
            if body.revision != revision:
                raise HTTPException(409, 'Riwayat berubah di tab atau perangkat lain. Muat ulang sebelum melanjutkan.')
            # Ownership comes exclusively from the authenticated session.
            if not db.execute('SELECT 1 FROM auth_users WHERE id=?', (user_id,)).fetchone():
                raise HTTPException(401, 'Sesi sudah tidak berlaku.')
            db.execute('''INSERT INTO account_chat_history VALUES (?,?,?)
                ON CONFLICT(user_id) DO UPDATE SET revision=excluded.revision,payload=excluded.payload''',
                (user_id, revision + 1, encoded))
        return {'revision': revision + 1}

    app.include_router(router)
