from math import sqrt
from types import SimpleNamespace

from qdrant_client.http import models


class FakeQdrantClient:
    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs
        self.collections: dict[str, dict] = {}

    def get_collections(self) -> dict:
        return {"collections": [{"name": name} for name in self.collections]}

    def collection_exists(self, collection_name: str, **kwargs) -> bool:
        return collection_name in self.collections

    def create_collection(self, collection_name: str, vectors_config, **kwargs) -> bool:
        self.collections.setdefault(
            collection_name,
            {
                "vectors_config": vectors_config,
                "points": {},
            },
        )
        return True

    def upsert(self, collection_name: str, points, wait: bool = True, **kwargs):
        collection = self.collections.setdefault(collection_name, {"vectors_config": None, "points": {}})
        for point in points:
            collection["points"][str(point.id)] = {
                "vector": list(point.vector),
                "payload": dict(point.payload),
            }
        return SimpleNamespace(status="ok")

    def scroll(
        self,
        collection_name: str,
        scroll_filter=None,
        limit: int = 10,
        with_payload: bool = True,
        with_vectors: bool = False,
        **kwargs,
    ):
        points = list(self.collections.get(collection_name, {}).get("points", {}).values())
        filtered = [point for point in points if self._matches(point["payload"], scroll_filter)]
        records = [
            SimpleNamespace(
                payload=point["payload"] if with_payload else None,
                vector=point["vector"] if with_vectors else None,
            )
            for point in filtered[:limit]
        ]
        return records, None

    def query_points(
        self,
        collection_name: str,
        query,
        query_filter=None,
        limit: int = 10,
        score_threshold: float | None = None,
        with_payload: bool = True,
        with_vectors: bool = False,
        **kwargs,
    ):
        scored = []
        for point in self.collections.get(collection_name, {}).get("points", {}).values():
            if not self._matches(point["payload"], query_filter):
                continue
            score = self._cosine(query, point["vector"])
            if score_threshold is not None and score < score_threshold:
                continue
            scored.append(
                SimpleNamespace(
                    payload=point["payload"] if with_payload else None,
                    vector=point["vector"] if with_vectors else None,
                    score=score,
                )
            )
        scored.sort(key=lambda record: record.score, reverse=True)
        return SimpleNamespace(points=scored[:limit])

    def close(self) -> None:
        return None

    def _matches(self, payload: dict, query_filter) -> bool:
        if query_filter is None:
            return True
        must_conditions = getattr(query_filter, "must", []) or []
        for condition in must_conditions:
            if not isinstance(condition, models.FieldCondition):
                continue
            match = getattr(condition, "match", None)
            expected = getattr(match, "value", None)
            if payload.get(condition.key) != expected:
                return False
        return True

    @staticmethod
    def _cosine(left: list[float], right: list[float]) -> float:
        numerator = sum(a * b for a, b in zip(left, right))
        left_norm = sqrt(sum(a * a for a in left))
        right_norm = sqrt(sum(b * b for b in right))
        if left_norm == 0 or right_norm == 0:
            return 0.0
        return numerator / (left_norm * right_norm)
