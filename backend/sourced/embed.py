"""Text embeddings for semantic duplicate detection, stored in Tiger Data's pgvector column.

HashEmbedder runs offline with no model, so the whole demo works from a clean clone. It is a 384-dim hashed
bag of words and bigrams, L2 normalized. It is deliberately simple. The upgrade path is Tiger's pgai vectorizer
(in-database embeddings) or a hosted embedding model; both are drop-in because every caller only sees embed().
"""
from __future__ import annotations

import hashlib
import math
import re

DIM = 384
_TOKEN = re.compile(r"[a-zà-ÿ0-9]+")


class HashEmbedder:
    dim = DIM

    def embed(self, text: str) -> list[float]:
        toks = _TOKEN.findall(text.lower())
        feats = toks + [a + "_" + b for a, b in zip(toks, toks[1:], strict=True)]
        v = [0.0] * self.dim
        for f in feats:
            h = int.from_bytes(hashlib.blake2b(f.encode(), digest_size=8).digest(), "big")
            v[h % self.dim] += 1.0 if (h >> 63) else -1.0
        n = math.sqrt(sum(x * x for x in v)) or 1.0
        return [x / n for x in v]


def get_embedder():
    return HashEmbedder()
