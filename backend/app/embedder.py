import hashlib
import re
from typing import List
import httpx
import numpy as np

from .config import (
    OLLAMA_EMBED_MODEL,
    OLLAMA_LOCAL_URL,
    TRANSFORMERS_MODEL_NAME,
    VECTOR_DIM,
)


class SmartTaxEmbedder:
    """Local vector embedding service for Jakarta SmartTax Chatbot AI."""

    def __init__(self) -> None:
        self.dim = VECTOR_DIM
        self.engine_name = "transformers-local-multilingual"
        self._hf_tokenizer = None
        self._init_tokenizer()

    def _init_tokenizer(self) -> None:
        try:
            from transformers import AutoTokenizer

            self._hf_tokenizer = AutoTokenizer.from_pretrained(
                TRANSFORMERS_MODEL_NAME,
                local_files_only=True,
            )
            self.engine_name = f"transformers ({TRANSFORMERS_MODEL_NAME})"
        except Exception:
            try:
                import transformers

                self.engine_name = f"transformers-subword-v{transformers.__version__}"
            except Exception:
                self.engine_name = "local-subword-embedder"

    def _tokenize(self, text: str) -> List[str]:
        cleaned = text.lower().strip()
        if self._hf_tokenizer is not None:
            try:
                return self._hf_tokenizer.tokenize(cleaned)
            except Exception:
                pass

        words = re.findall(r"[a-z0-9]+(?:\.[0-9]+)*", cleaned)
        tokens: List[str] = []
        for idx, w in enumerate(words):
            tokens.append(f"w:{w}")
            if re.match(r"^\d{2}\.\d{2}", w) or len(w) >= 4:
                tokens.append(f"kw:{w}")
            if idx + 1 < len(words):
                tokens.append(f"bg:{w}_{words[idx + 1]}")
            if len(w) >= 4:
                for i in range(len(w) - 2):
                    tokens.append(f"tri:{w[i:i+3]}")
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
            weight = 2.2 if tok.startswith("kw:") else (1.5 if tok.startswith("w:") else 0.7)
            vec[idx1] += sign1 * weight
            vec[idx2] += sign2 * (weight * 0.5)

        norm = float(np.linalg.norm(vec))
        if norm > 1e-8:
            vec = vec / norm
        return vec.tolist()

    def embed_texts(self, texts: List[str], use_ollama_embed: bool = False) -> List[List[float]]:
        if use_ollama_embed:
            try:
                with httpx.Client(timeout=5.0) as client:
                    resp = client.post(
                        f"{OLLAMA_LOCAL_URL}/api/embed",
                        json={"model": OLLAMA_EMBED_MODEL, "input": texts},
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        embeddings = data.get("embeddings")
                        if embeddings and len(embeddings[0]) == self.dim:
                            return embeddings
            except Exception:
                pass

        return [self._project_tokens(self._tokenize(t)) for t in texts]

    def embed_query(self, query: str) -> List[float]:
        return self.embed_texts([query])[0]


embedder = SmartTaxEmbedder()
