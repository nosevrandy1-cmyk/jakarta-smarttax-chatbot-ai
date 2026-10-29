import hashlib
import re
from typing import Dict, List
import httpx
import numpy as np

from .config import (
    OLLAMA_EMBED_MODEL,
    OLLAMA_LOCAL_URL,
    TRANSFORMERS_MODEL_NAME,
    VECTOR_DIM,
)

STOPWORDS = {
    "yang",
    "dan",
    "di",
    "ke",
    "dari",
    "untuk",
    "pada",
    "dengan",
    "adalah",
    "atau",
    "dalam",
    "atas",
    "oleh",
    "ini",
    "itu",
    "sebagai",
    "tersebut",
    "dapat",
    "akan",
    "telah",
    "secara",
}

CANONICAL_SYNONYMS: Dict[str, List[str]] = {
    "jpb": ["gedung", "perkantoran", "komersial", "bangunan", "pbb"],
    "pbb": ["pbb-p2", "njop", "njoptkp", "sppt", "nop"],
    "pbjt": ["restoran", "hotel", "parkir", "hiburan", "sptpd", "makanan", "minuman"],
    "bphtb": ["npop", "npoptkp", "sspd", "ajb", "waris", "hibah"],
    "reklame": ["nsr", "videotron", "billboard", "megatron", "protokol"],
    "pat": ["airtanah", "npat", "hda", "sumur", "amr"],
}


class SmartTaxEmbedder:
    # Keep embeddings CPU-bound by default so all 8GB VRAM remains dedicated to gemma4:12b.

    def __init__(self) -> None:
        self.dim = VECTOR_DIM
        self.engine_name = f"cpu-hybrid ({OLLAMA_EMBED_MODEL})"
        self._hf_tokenizer = None
        self._init_tokenizer()

    def _init_tokenizer(self) -> None:
        try:
            from transformers import AutoTokenizer

            self._hf_tokenizer = AutoTokenizer.from_pretrained(
                TRANSFORMERS_MODEL_NAME,
                local_files_only=True,
            )
            self.engine_name = f"cpu-transformers ({TRANSFORMERS_MODEL_NAME})"
        except Exception:
            self.engine_name = f"cpu-lexical-semantic ({OLLAMA_EMBED_MODEL})"

    def _tokenize(self, text: str) -> List[str]:
        cleaned = text.lower().strip()
        cleaned = cleaned.replace("0,5%", "0.5%").replace("1,5%", "1.5%")
        raw_words = re.findall(r"[a-z0-9]+(?:[\.,][0-9]+)*%?", cleaned)
        words = [w.strip(".,") for w in raw_words if w.strip(".,") and w not in STOPWORDS]

        tokens: List[str] = []
        for idx, w in enumerate(words):
            tokens.append(f"w:{w}")
            if w in CANONICAL_SYNONYMS:
                for syn in CANONICAL_SYNONYMS[w]:
                    tokens.append(f"kw:{syn}")
            if re.match(r"^\d", w) or w.endswith("%") or len(w) >= 4:
                tokens.append(f"kw:{w}")
            if idx + 1 < len(words):
                tokens.append(f"bg:{w}_{words[idx + 1]}")
            if len(w) >= 5:
                for i in range(len(w) - 3):
                    tokens.append(f"ng:{w[i:i+4]}")

        if self._hf_tokenizer is not None:
            try:
                hf_toks = self._hf_tokenizer.tokenize(cleaned)[:128]
                tokens.extend(f"hf:{t}" for t in hf_toks)
            except Exception:
                pass

        return tokens or ["empty"]

    def _project_tokens(self, tokens: List[str]) -> List[float]:
        vec = np.zeros(self.dim, dtype=np.float32)
        for tok in tokens:
            h = hashlib.blake2b(tok.encode("utf-8"), digest_size=8).digest()
            val = int.from_bytes(h, "little")
            idx1 = val % self.dim
            idx2 = (val >> 16) % self.dim
            sign1 = 1.0 if ((val >> 32) & 1) == 0 else -1.0
            sign2 = 1.0 if ((val >> 33) & 1) == 0 else -1.0
            if tok.startswith("kw:"):
                weight = 2.4
            elif tok.startswith("w:"):
                weight = 1.6
            elif tok.startswith("bg:"):
                weight = 1.1
            else:
                weight = 0.55
            vec[idx1] += sign1 * weight
            vec[idx2] += sign2 * (weight * 0.5)

        norm = float(np.linalg.norm(vec))
        if norm > 1e-8:
            vec = vec / norm
        return vec.tolist()

    def embed_texts(self, texts: List[str], use_ollama_embed: bool = False) -> List[List[float]]:
        if use_ollama_embed:
            try:
                with httpx.Client(timeout=4.0) as client:
                    resp = client.post(
                        f"{OLLAMA_LOCAL_URL}/api/embed",
                        json={"model": OLLAMA_EMBED_MODEL, "input": texts},
                    )
                    if resp.status_code == 200:
                        embeddings = resp.json().get("embeddings")
                        if embeddings and len(embeddings[0]) == self.dim:
                            return embeddings
            except Exception:
                pass

        return [self._project_tokens(self._tokenize(t)) for t in texts]

    def embed_query(self, query: str) -> List[float]:
        return self.embed_texts([query])[0]

    def cosine_similarity(self, text_a: str, text_b: str) -> float:
        if not text_a.strip() or not text_b.strip():
            return 0.0
        vec_a, vec_b = self.embed_texts([text_a, text_b])
        dot = float(np.dot(np.asarray(vec_a, dtype=np.float32), np.asarray(vec_b, dtype=np.float32)))
        return max(0.0, min(1.0, dot))


embedder = SmartTaxEmbedder()
