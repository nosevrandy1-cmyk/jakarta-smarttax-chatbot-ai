"""Room-local transcript resolution. Never load another owner or another room."""

def resolve_room_history(incoming, stored_room, current_question):
    stored = [m for m in (stored_room or {}).get('messages', []) if not m.get('failed') and m.get('content','').strip()]
    supplied = [m for m in incoming if m.get('content','').strip()]
    if supplied:
        # Client IDs mark the beginning of the loaded page. Preserve older messages,
        # but let the supplied tail replace edited/retried turns instead of appending stale answers.
        anchor = supplied[0].get('id')
        index = next((i for i,m in enumerate(stored) if anchor and m.get('id') == anchor), None)
        merged = stored[:index] + supplied if index is not None else supplied
    else:
        merged = stored
        # A history autosave may have stored the current user message before generation begins.
        if merged and merged[-1].get('role') == 'user' and merged[-1]['content'].strip() == current_question.strip():
            merged = merged[:-1]
    return [{'role':m.get('role','user'),'content':m['content']} for m in merged]
