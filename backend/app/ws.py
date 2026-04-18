from typing import Dict
import asyncio
import uuid
import os
from fastapi import WebSocket, WebSocketDisconnect


class ConnectionManager:
    def __init__(self):
        # role -> user_id -> websocket
        self.active: Dict[str, Dict[str, WebSocket]] = {}
        self.lock = asyncio.Lock()
        self.acks = {}  # event_id -> set(user_id)
        self.ack_expected = {}  # event_id -> set(user_id expected)
        self.retry_tasks = {}  # event_id -> asyncio.Task

        # retry config
        self.ack_ttl_seconds = int(os.getenv("ACK_TTL_SECONDS", "20"))
        self.max_retries = int(os.getenv("ACK_MAX_RETRIES", "3"))

    async def connect(self, websocket: WebSocket, user_id: str, role: str):
        await websocket.accept()
        async with self.lock:
            self.active.setdefault(role, {})[user_id] = websocket

    async def disconnect(self, websocket: WebSocket):
        async with self.lock:
            for role, mapping in list(self.active.items()):
                for uid, ws in list(mapping.items()):
                    if ws is websocket:
                        del mapping[uid]
                        break

    async def send_event_to_role(self, role: str, event: dict):
        async with self.lock:
            mapping = dict(self.active.get(role, {}))
        for uid, ws in mapping.items():
            try:
                await ws.send_json(event)
            except Exception:
                # ignore send errors; client may have disconnected
                pass

    async def broadcast(self, event: dict, roles: list[str]):
        # record ack expectation
        event_id = event.get("id")
        expected = set()
        async with self.lock:
            for role in roles:
                mapping = self.active.get(role, {})
                expected.update(mapping.keys())
        if event.get("requires_ack"):
            self.acks[event_id] = set()
            self.ack_expected[event_id] = set(expected)
            # start retry waiter
            task = asyncio.create_task(self._await_acks(event, roles))
            self.retry_tasks[event_id] = task
        for role in roles:
            await self.send_event_to_role(role, event)

    async def _await_acks(self, event: dict, roles: list[str]):
        event_id = event.get("id")
        retries = 0
        while retries < self.max_retries:
            await asyncio.sleep(self.ack_ttl_seconds)
            expected = self.ack_expected.get(event_id, set())
            got = self.acks.get(event_id, set())
            missing = expected - got
            if not missing:
                # all acks received
                self.acks.pop(event_id, None)
                self.ack_expected.pop(event_id, None)
                self.retry_tasks.pop(event_id, None)
                return
            # resend to roles (best-effort delivery)
            for role in roles:
                await self.send_event_to_role(role, event)
            retries += 1
        # After retries exhausted, record final state and cleanup
        self.retry_tasks.pop(event_id, None)

    async def handle_ack(self, event_id: str, user_id: str):
        if event_id in self.acks:
            self.acks[event_id].add(user_id)


manager = ConnectionManager()
