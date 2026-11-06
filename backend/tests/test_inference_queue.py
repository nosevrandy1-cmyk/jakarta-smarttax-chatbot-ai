import asyncio
import json
import unittest
from app.inference_queue import InferenceQueue


class InferenceQueueTests(unittest.IsolatedAsyncioTestCase):
    async def test_serializes_and_rejects_overflow(self):
        queue = InferenceQueue(max_waiting=1)
        entered = []
        release = asyncio.Event()
        async def source(name):
            entered.append(name)
            await release.wait()
            yield name
        async def collect(name):
            return [item async for item in queue.stream(lambda: source(name))]
        first = asyncio.create_task(collect('a'))
        await asyncio.sleep(.01)
        second = asyncio.create_task(collect('b'))
        await asyncio.sleep(.01)
        third = await collect('c')
        self.assertEqual(json.loads(third[0])['code'], 'inference_queue_full')
        self.assertEqual(entered, ['a'])
        release.set()
        self.assertIn('a', await first)
        self.assertIn('b', await second)
        self.assertEqual(entered, ['a', 'b'])
        self.assertEqual(queue._pending, 0)

    async def test_cancellation_and_timeout_release_capacity(self):
        queue = InferenceQueue(wait_timeout=.02)
        async def source():
            yield 'started'
            await asyncio.Event().wait()
        first = queue.stream(source)
        self.assertEqual(await anext(first), 'started')
        expired = [item async for item in queue.stream(source)]
        self.assertEqual(json.loads(expired[-2])['code'], 'inference_queue_timeout')
        waiting = queue.stream(source)
        self.assertEqual(json.loads(await anext(waiting))['type'], 'status')
        await waiting.aclose()
        await first.aclose()
        self.assertEqual(queue._pending, 0)
        self.assertFalse(queue._slots.locked())

    async def test_upstream_failure_does_not_lock_next_request(self):
        queue = InferenceQueue()
        async def broken():
            raise RuntimeError('offline')
            yield ''
        with self.assertRaises(RuntimeError):
            _ = [item async for item in queue.stream(broken)]
        self.assertEqual(queue._pending, 0)
        self.assertFalse(queue._slots.locked())

    async def test_cancel_running_request_allows_waiter_to_proceed(self):
        queue = InferenceQueue()
        entered = asyncio.Event()
        closed = asyncio.Event()
        async def active():
            try:
                entered.set()
                await asyncio.Event().wait()
                yield 'never'
            finally:
                closed.set()
        async def next_source():
            yield 'next'
        async def collect(factory):
            return [item async for item in queue.stream(factory)]
        running = asyncio.create_task(collect(active))
        await entered.wait()
        waiting = asyncio.create_task(collect(next_source))
        await asyncio.sleep(0)
        running.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await running
        self.assertTrue(closed.is_set())
        self.assertIn('next', await asyncio.wait_for(waiting, 1))
        self.assertEqual(queue._pending, 0)

    async def test_account_and_duplicate_room_limits_cannot_be_bypassed_by_tabs(self):
        queue = InferenceQueue()
        async def source():
            yield 'started'
            await asyncio.Event().wait()
        first=queue.stream(source, actor_id='a', room_id='one')
        self.assertEqual(await anext(first),'started')
        duplicate=[json.loads(item) async for item in queue.stream(source, actor_id='a', room_id='one')]
        self.assertEqual(duplicate[0]['code'],'account_inference_limit')
        second=queue.stream(source, actor_id='a', room_id='two')
        await anext(second)
        excess=[json.loads(item) async for item in queue.stream(source, actor_id='a', room_id='three')]
        self.assertEqual(excess[0]['code'],'account_inference_limit')
        other=queue.stream(source, actor_id='b', room_id='one')
        self.assertEqual(json.loads(await anext(other))['type'],'status')
        await other.aclose()
        await second.aclose()
        await first.aclose()
        self.assertEqual(queue._actors,{})
        self.assertEqual(queue._rooms,set())
