"use client";

import { useEffect, useRef, useState } from "react";

export default function RenameChatDialog({ title, onSave, onCancel }: {
  title: string; onSave: (name: string) => void; onCancel: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const input = useRef<HTMLInputElement>(null);
  const [name, setName] = useState(title);
  const cleaned = name.replace(/\s+/g, " ").trim();
  useEffect(() => { dialog.current?.showModal(); input.current?.focus(); input.current?.select(); }, []);
  return <dialog ref={dialog} className="rename-chat-dialog" aria-labelledby="rename-chat-title"
    aria-describedby="rename-chat-description" onCancel={onCancel} onClose={onCancel}>
    <form onSubmit={event => { event.preventDefault(); if (cleaned) onSave(cleaned); }}>
      <h2 id="rename-chat-title">Ganti nama percakapan</h2>
      <p id="rename-chat-description">Gunakan nama yang mudah kamu temukan kembali.</p>
      <label htmlFor="rename-chat-input">Nama percakapan</label>
      <input ref={input} id="rename-chat-input" autoFocus value={name} maxLength={100}
        onChange={event => setName(event.target.value)} required aria-describedby="rename-chat-limit" />
      <div id="rename-chat-limit" className="rename-chat-limit">Maksimal 100 karakter. Nama tidak boleh kosong.</div>
      <div className="rename-chat-actions"><button type="button" onClick={onCancel}>Batal</button>
        <button type="submit" disabled={!cleaned} className="rename-chat-save">Simpan</button></div>
    </form>
  </dialog>;
}
