# SPDX-License-Identifier: MIT
# Copyright © 2025 Bijan Mousavi
from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

try:  # pragma: no cover - optional dependency
    import faiss
except Exception:  # pragma: no cover - optional dependency
    faiss = None

import numpy as np

from bijux_vex.infra.adapters.vectorstore import VectorStoreAdapter


class FaissVectorStoreAdapter(VectorStoreAdapter):
    backend = "faiss"
    is_noop = False

    def __init__(
        self, uri: str | None = None, options: Mapping[str, str] | None = None
    ):
        if faiss is None:  # pragma: no cover - handled by registry availability
            raise ImportError("faiss is not available")
        self._options = dict(options or {})
        self._index: Any | None = None
        self._dimension: int | None = None
        self._ids: list[str] = []
        self._deleted: set[str] = set()
        self._index_path = Path(uri) if uri else None
        self._ids_path = (
            self._index_path.with_suffix(".ids.json") if self._index_path else None
        )

    @property
    def index_params(self) -> dict[str, object]:
        return {
            "type": "IndexFlatL2",
            "dimension": self._dimension,
            "ntotal": int(self._index.ntotal) if self._index is not None else 0,
        }

    @property
    def backend_version(self) -> str | None:
        return getattr(faiss, "__version__", None) if faiss is not None else None

    def connect(self) -> None:
        if faiss is None:  # pragma: no cover - defensive
            raise ImportError("faiss is not available")
        if not self._index_path:
            return
        if not self._index_path.exists():
            return
        self._index = faiss.read_index(str(self._index_path))
        self._dimension = int(self._index.d)
        if self._ids_path and self._ids_path.exists():
            import json

            self._ids = json.loads(self._ids_path.read_text(encoding="utf-8"))

    def insert(
        self,
        vectors: Iterable[Sequence[float]],
        metadata: Iterable[dict[str, Any]] | None = None,
    ) -> list[str]:
        vectors_list = [list(vec) for vec in vectors]
        if not vectors_list:
            return []
        meta_list = list(metadata or [])
        if len(meta_list) != len(vectors_list):
            raise ValueError("metadata length must match vectors length for FAISS")
        vector_ids: list[str] = []
        for entry in meta_list:
            vector_id = entry.get("vector_id")
            if vector_id is None:
                raise ValueError("vector_id required in metadata for FAISS inserts")
            vector_ids.append(str(vector_id))
        dim = len(vectors_list[0])
        if self._dimension is None:
            self._dimension = dim
        if dim != self._dimension:
            raise ValueError("Vector dimensionality mismatch for FAISS index")
        if self._index is None:
            self._index = faiss.IndexFlatL2(self._dimension)
        array = np.asarray(vectors_list, dtype="float32")
        self._index.add(array)
        self._ids.extend(vector_ids)
        self._persist()
        return vector_ids

    def query(
        self, vector: Sequence[float], k: int, mode: str
    ) -> list[tuple[str, float]]:
        if self._index is None or self._index.ntotal == 0:
            return []
        k_eff = min(int(k) + len(self._deleted), int(self._index.ntotal))
        array = np.asarray([vector], dtype="float32")
        distances, indices = self._index.search(array, k_eff)
        results: list[tuple[str, float]] = []
        for idx, dist in zip(indices[0], distances[0], strict=False):
            if idx < 0:
                continue
            vector_id = self._ids[idx]
            if vector_id in self._deleted:
                continue
            results.append((vector_id, float(dist)))
            if len(results) >= k:
                break
        return results

    def delete(self, ids: Iterable[str]) -> int:
        removed = 0
        for vector_id in list(ids):
            if vector_id not in self._deleted:
                self._deleted.add(vector_id)
                removed += 1
        return removed

    def status(self) -> dict[str, object]:
        return {
            "reachable": True,
            "backend": self.backend,
            "version": self.backend_version,
            "index": self.index_params,
        }

    def _persist(self) -> None:
        if not self._index_path:
            return
        if self._index is None:
            return
        self._index_path.parent.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self._index, str(self._index_path))
        if self._ids_path:
            import json

            self._ids_path.write_text(json.dumps(self._ids, indent=2), encoding="utf-8")


__all__ = ["FaissVectorStoreAdapter"]
