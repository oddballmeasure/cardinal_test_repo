"""Persist ordered note and diary records in Redis."""

import json
import os

from redis import Redis

redis_client = Redis.from_url(
    os.getenv("REDIS_URL", "redis://redis:6379/0"),
    decode_responses=True,
)


def create_entry(collection: str, values: dict) -> dict:
    entry_id = redis_client.incr(f"{collection}:next_id")
    entry = {"id": entry_id, **values}
    redis_client.rpush(collection, json.dumps(entry, ensure_ascii=False))
    return entry


def list_entries(collection: str) -> list[dict]:
    return [json.loads(value) for value in redis_client.lrange(collection, 0, -1)]


def get_entry(collection: str, entry_id: int) -> dict | None:
    # Entries are appended in ID order, so reading their list index does not
    # disturb the ordered collection.
    if entry_id < 1 or entry_id > redis_client.llen(collection):
        return None
    value = redis_client.lindex(collection, entry_id - 1)
    entry = json.loads(value) if value is not None else None
    return entry if entry is not None and entry["id"] == entry_id else None

