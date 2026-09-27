"""Persist ordered note and diary records in Redis."""

import json
import os

from redis import Redis, WatchError

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
    if entry_id < 1:
        return None
    value = redis_client.lindex(collection, entry_id - 1)
    if value is None:
        return None
    entry = json.loads(value)
    return entry if entry.get("id") == entry_id else None


def update_entry(collection: str, entry_id: int, changes: dict) -> dict | None:
    if entry_id < 1:
        return None
    with redis_client.pipeline() as pipe:
        while True:
            try:
                pipe.watch(collection)
                value = pipe.lindex(collection, entry_id - 1)
                if value is None:
                    return None
                entry = json.loads(value)
                if entry.get("id") != entry_id:
                    return None
                entry.update(changes)
                pipe.multi()
                pipe.lset(collection, entry_id - 1, json.dumps(entry, ensure_ascii=False))
                pipe.execute()
                return entry
            except WatchError:
                continue

