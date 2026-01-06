from __future__ import annotations

import asyncio
from dataclasses import dataclass


@dataclass
class EditJob:
    request_id: int
    user_tg_id: int
    chat_id: int
    image_file_ids: list[str]
    prompt: str


_QUEUE: asyncio.Queue[EditJob] | None = None


def get_queue() -> asyncio.Queue[EditJob]:
    global _QUEUE
    if _QUEUE is None:
        _QUEUE = asyncio.Queue()
    return _QUEUE


async def enqueue_request(
    request_id: int,
    user_tg_id: int,
    chat_id: int,
    image_file_ids: list[str],
    prompt: str,
) -> None:
    q = get_queue()
    await q.put(
        EditJob(
            request_id=request_id,
            user_tg_id=user_tg_id,
            chat_id=chat_id,
            image_file_ids=image_file_ids,
            prompt=prompt,
        )
    )
