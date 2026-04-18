#!/usr/bin/env python3
"""Simple async HTTP load tester for /api/letters endpoint.
Usage: adjust CONCURRENCY and TOTAL_REQUESTS constants or pass via env vars.
"""
import os
import asyncio
import time
import statistics
from datetime import date
import httpx

BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:8000")
CONCURRENCY = int(os.getenv("LT_CONCURRENCY", "10"))
TOTAL_REQUESTS = int(os.getenv("LT_TOTAL", "100"))
STUDENT_USERNAME = os.getenv("LT_STUDENT_USER", "student_test")
STUDENT_PASSWORD = os.getenv("LT_STUDENT_PASS", "changeme")
TARGET_ROLL = os.getenv("LT_TARGET_ROLL", "24071A6601")


async def login(client: httpx.AsyncClient, username: str, password: str):
    r = await client.post(f"{BASE_URL}/api/auth/login", json={"username": username, "password": password})
    r.raise_for_status()
    return r.json()["access_token"]


async def post_letter(client: httpx.AsyncClient, token: str, idx: int):
    today = date.today().isoformat()
    payload = {
        "student_roll": TARGET_ROLL,
        "student_name": "Load Test Student",
        "event_name": f"LoadTest-{idx}",
        "start_datetime": f"{today}T12:00:00",
        "end_datetime": f"{today}T13:00:00",
        "body": "Load test"
    }
    headers = {"Authorization": f"Bearer {token}"}
    start = time.monotonic()
    r = await client.post(f"{BASE_URL}/api/letters", json=payload, headers=headers)
    elapsed = time.monotonic() - start
    return r.status_code, elapsed


async def worker(queue: asyncio.Queue, results: list, token: str):
    async with httpx.AsyncClient() as client:
        while True:
            try:
                idx = queue.get_nowait()
            except asyncio.QueueEmpty:
                return
            try:
                status, elapsed = await post_letter(client, token, idx)
                results.append(elapsed)
            except Exception as e:
                results.append(None)


async def main():
    async with httpx.AsyncClient() as client:
        token = await login(client, STUDENT_USERNAME, STUDENT_PASSWORD)
    queue = asyncio.Queue()
    for i in range(TOTAL_REQUESTS):
        queue.put_nowait(i)
    results = []
    tasks = [asyncio.create_task(worker(queue, results, token)) for _ in range(CONCURRENCY)]
    await asyncio.gather(*tasks)

    latencies = [r for r in results if r is not None]
    failures = len([r for r in results if r is None])
    if latencies:
        print(f"Requests: {TOTAL_REQUESTS}, Concurrency: {CONCURRENCY}, Failures: {failures}")
        print(f"Min: {min(latencies):.3f}s, Max: {max(latencies):.3f}s, Mean: {statistics.mean(latencies):.3f}s")
        print(f"Median: {statistics.median(latencies):.3f}s, 95th: {statistics.quantiles(latencies, n=100)[94]:.3f}s")
    else:
        print("All requests failed")


if __name__ == '__main__':
    asyncio.run(main())
