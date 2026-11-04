"""Optional model-generated follow-ups, separated from visible answer streaming."""
import json
import re

MARKER = "<JST_FOLLOW_UPS>"
CLOSING = "</JST_FOLLOW_UPS>"
# Recognize the reserved name before its optional bracket. Models can omit >.
MARKER_STEM = "<JST_FOLLOW_UPS"
FOLLOWUP_INSTRUCTIONS = (
    " Setelah jawaban utama selesai, tambahkan satu blok metadata persis berformat "
    '<JST_FOLLOW_UPS>["pertanyaan lanjutan"]</JST_FOLLOW_UPS>. '
    "Isi dengan maksimal dua pertanyaan singkat dari sudut pandang pengguna, berdasarkan "
    "pertanyaan terbaru DAN jawaban yang baru Anda berikan. Jangan menyalin pertanyaan awal. "
    "Pilih kelanjutan yang spesifik dan bisa dibantu oleh konteks sumber yang tersedia, "
    "bukan pertanyaan umum yang sama setiap jawaban. Jangan mengarang data, meminta lampiran, "
    "menawarkan unduhan, atau keluar dari kategori pajak. Jangan menulis label saran dalam "
    "jawaban utama. Jika jawaban hanya penolakan, keterbatasan data, atau tidak ada kelanjutan "
    "yang berguna, isi blok dengan []. Gunakan JSON valid tanpa code fence. "
    "Blok ini adalah metadata aplikasi dan tidak termasuk jawaban utama."
)


def validate_followups(raw, original_question):
    if not isinstance(raw, list):
        return []
    result = []
    seen = {re.sub(r"\W+", "", original_question.casefold())}
    for value in raw[:8]:
        if not isinstance(value, str):
            continue
        text = re.sub(r"\s+", " ", value).strip()
        key = re.sub(r"\W+", "", text.casefold())
        if not 8 <= len(text) <= 160 or key in seen:
            continue
        if re.search(r"https?://|www\.|[<>]|data:|base64|^/|\[\d+\]", text, re.I):
            continue
        if re.search(r"\b(unggah|upload|lampirkan|unduh|download)\b|kirim(?:kan)?\s+(?:file|dokumen)", text, re.I):
            continue
        seen.add(key)
        result.append(text)
        if len(result) == 2:
            break
    return result


class FollowUpStream:
    def __init__(self, question):
        self.question = question
        self.pending = ""
        self.metadata = None

    def feed(self, text):
        if self.metadata is not None:
            self.metadata = (self.metadata + text)[:4096]
            return ""
        self.pending += text
        index = self.pending.upper().find(MARKER_STEM)
        if index >= 0:
            visible = self.pending[:index]
            self.metadata = self.pending[index + len(MARKER_STEM):][:4096]
            self.pending = ""
            return visible
        keep = 0
        for size in range(min(len(MARKER_STEM) - 1, len(self.pending)), 0, -1):
            if self.pending.upper().endswith(MARKER_STEM[:size]):
                keep = size
                break
        visible = self.pending[:-keep] if keep else self.pending
        self.pending = self.pending[-keep:] if keep else ""
        return visible

    def finish(self):
        if self.metadata is None:
            # A truncated metadata opener must not appear in the answer.
            tail = "" if self.pending.upper().startswith("<JST_") else self.pending
            self.pending = ""
            return tail, []
        closing = re.search(r"</JST_FOLLOW_UPS\s*>?", self.metadata, re.I)
        if closing is None:
            return "", []
        try:
            payload = self.metadata[:closing.start()].strip()
            if payload.startswith(">"):
                payload = payload[1:].strip()
            raw = json.loads(payload)
        except (ValueError, TypeError):
            return "", []
        return "", validate_followups(raw, self.question)
