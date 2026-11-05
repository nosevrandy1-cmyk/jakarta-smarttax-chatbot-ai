"""Bounded FIFO admission for the single local inference device."""
import asyncio
import json
from contextlib import suppress


class InferenceQueue:
    def __init__(self, max_waiting=4, wait_timeout=180):
        self.max_waiting = max_waiting
        self.wait_timeout = wait_timeout
        self._slots = asyncio.Semaphore(1)
        self._pending = 0
        self._actors = {}
        self._rooms = set()

    @staticmethod
    def event(kind, **values):
        return json.dumps({"type": kind, **values}, ensure_ascii=False) + "\n"

    async def stream(self, factory, actor_id=None, room_id=None):
        key = (actor_id, room_id) if actor_id and room_id else None
        if actor_id and (self._actors.get(actor_id, 0) >= 2 or key in self._rooms):
            yield self.event("error", code="account_inference_limit", text="Masih ada jawaban yang diproses. Tunggu sampai selesai.")
            yield self.event("done", response_source="unavailable", follow_ups=[])
            return
        # No await between checking and reserving admission on the event loop.
        if self._pending >= self.max_waiting + 1:
            yield self.event("error", code="inference_queue_full",
                             text="Antrean jawaban sedang penuh. Coba lagi sebentar.")
            yield self.event("done", response_source="unavailable", follow_ups=[])
            return
        self._pending += 1
        if actor_id:
            self._actors[actor_id] = self._actors.get(actor_id, 0) + 1
        if key:
            self._rooms.add(key)
        acquire = asyncio.create_task(self._slots.acquire())
        source = None
        try:
            if self._slots.locked():
                yield self.event("status", text="Menunggu giliran…")
            try:
                await asyncio.wait_for(asyncio.shield(acquire), self.wait_timeout)
            except TimeoutError:
                yield self.event("error", code="inference_queue_timeout",
                                 text="Antrean masih sibuk. Coba lagi sebentar.")
                yield self.event("done", response_source="unavailable", follow_ups=[])
                return
            source = factory()
            async for item in source:
                yield item
        finally:
            # Disconnect/Stop also closes the upstream HTTP stream and frees the slot.
            try:
                if source is not None:
                    await source.aclose()
            finally:
                if not acquire.done():
                    acquire.cancel()
                with suppress(asyncio.CancelledError):
                    await acquire
                if not acquire.cancelled() and acquire.exception() is None:
                    self._slots.release()
                self._pending -= 1
                if actor_id:
                    self._actors[actor_id] -= 1
                    if not self._actors[actor_id]:
                        del self._actors[actor_id]
                if key:
                    self._rooms.discard(key)
