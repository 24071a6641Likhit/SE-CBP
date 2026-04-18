#!/usr/bin/env python3
"""Quick test: open a websocket as coordinator, then submit a letter to trigger letter.created event, and send ack."""
import asyncio
import os
import json
import websockets
import requests
from urllib.parse import urlencode

BASE = os.getenv('BASE_URL', 'http://127.0.0.1:8000')
WS_BASE = BASE.replace('http', 'ws')

MAINTAINER = {'username': 'maintainer', 'password': 'changeme'}
COORDINATOR = {'username': 'coordinator', 'password': 'changeme'}
STUDENT = {'username': 'student_test', 'password': 'changeme'}
TARGET_ROLL = '24071A6601'


def get_token(user):
    r = requests.post(f"{BASE}/api/auth/login", json=user)
    r.raise_for_status()
    return r.json()['access_token']


async def ws_client(token):
    uri = f"{WS_BASE}/ws?token={token}"
    async with websockets.connect(uri) as ws:
        print('Connected WS')
        while True:
            msg = await ws.recv()
            try:
                data = json.loads(msg)
            except Exception:
                print('non-json', msg)
                continue
            print('WS event:', data.get('type'), data.get('id'))
            # send ack
            if data.get('requires_ack'):
                ack = {'type': 'ack', 'id': data.get('id')}
                await ws.send(json.dumps(ack))
                print('Sent ack for', data.get('id'))


def post_letter(token):
    today = date.today().isoformat()


async def main():
    # login and create student if missing
    mtoken = get_token(MAINTAINER)
    requests.post(f"{BASE}/api/import/roster", headers={'Authorization': f'Bearer {mtoken}'}, files={'file': open('samples/roster.csv','rb')})
    requests.post(f"{BASE}/api/import/teachers", headers={'Authorization': f'Bearer {mtoken}'}, files={'file': open('samples/teachers.csv','rb')})

    # ensure student user exists
    # reuse e2e harness direct DB insertion
    import backend.app.database as dbmod
    from backend.app import models, auth
    db = dbmod.SessionLocal()
    try:
        u = db.query(models.User).filter_by(username=STUDENT['username']).first()
        if not u:
            u = models.User(username=STUDENT['username'], password_hash=auth.get_password_hash(STUDENT['password']), role='student')
            db.add(u); db.flush()
        st = db.query(models.Student).filter_by(roll_number=TARGET_ROLL).first()
        if st:
            st.user_id = u.id
        else:
            s = models.Student(roll_number=TARGET_ROLL, name='Test Student', user_id=u.id)
            db.add(s)
        db.commit()
    finally:
        db.close()

    ctoken = get_token(COORDINATOR)
    stoken = get_token(STUDENT)

    # start ws client
    client_task = asyncio.create_task(ws_client(ctoken))
    await asyncio.sleep(1)

    # submit a letter as student
    today = date.today().isoformat()
    payload = {
        'student_roll': TARGET_ROLL,
        'student_name': 'Test Student',
        'event_name': 'WS Ack Test',
        'start_datetime': f"{today}T12:05:00",
        'end_datetime': f"{today}T13:05:00"
    }
    r = requests.post(f"{BASE}/api/letters", headers={'Authorization': f'Bearer {stoken}'}, json=payload)
    print('submit status', r.status_code, r.text)

    # wait for events and ack handling
    await asyncio.sleep(5)
    client_task.cancel()

if __name__ == '__main__':
    import sys
    from datetime import date
    asyncio.run(main())
