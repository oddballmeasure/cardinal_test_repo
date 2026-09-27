"""Persist ordered note and diary records in Redis."""

import json
import os

from redis import Redis
from redis.exceptions import WatchError

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
    if entry_id <= 0:
        return None
    value = redis_client.lindex(collection, entry_id - 1)
    if value is None:
        return None
    entry = json.loads(value)
    return entry if entry["id"] == entry_id else None


def update_entry(collection: str, entry_id: int, values: dict) -> dict | None:
    if entry_id <= 0:
        return None
    # IDs correspond to list positions; watch the list so concurrent updates
    # cannot overwrite each other's changes between the read and LSET.
    while True:
        with redis_client.pipeline() as pipe:
            try:
                pipe.watch(collection)
                raw = pipe.lindex(collection, entry_id - 1)
                if raw is None:
                    return None
                entry = json.loads(raw)
                if entry["id"] != entry_id:
                    return None
                entry.update(values)
                pipe.multi()
                pipe.lset(collection, entry_id - 1, json.dumps(entry, ensure_ascii=False))
                pipe.execute()
                return entry
            except WatchError:
                continue

