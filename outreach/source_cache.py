"""Private restart-safe cache/pacing for opted-in community sources, never contact proof."""
import json
import math
import os
import sqlite3
import time
from contextlib import contextmanager

MAX_VALUE_BYTES = 262144


@contextmanager
def database(settings):
    settings.data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = settings.data_dir / 'source-cache.sqlite3'
    fd = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
    os.close(fd)
    con = sqlite3.connect(str(path), timeout=2)
    try:
        con.execute('CREATE TABLE IF NOT EXISTS source_pacing '
                    '(provider TEXT PRIMARY KEY, hold_until REAL NOT NULL, next_at REAL NOT NULL)')
        con.execute('CREATE TABLE IF NOT EXISTS source_cache '
                    '(provider TEXT NOT NULL, cache_key TEXT NOT NULL, expires_at REAL NOT NULL, '
                    'written_at REAL NOT NULL, value TEXT NOT NULL, PRIMARY KEY(provider,cache_key))')
        yield con
        con.commit()
    finally:
        con.close()


def timestamp(value):
    if not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise ValueError('Invalid source-cache timestamp')
    return value


def load(settings, provider, key):
    now = time.time()
    with database(settings) as con:
        con.execute('DELETE FROM source_cache WHERE provider=? AND expires_at<=?', (provider, now))
        pacing = con.execute('SELECT hold_until,next_at FROM source_pacing WHERE provider=?', (provider,)).fetchone()
        row = con.execute('SELECT expires_at,CASE WHEN length(value)<=? THEN value END '
                          'FROM source_cache WHERE provider=? AND cache_key=?',
                          (MAX_VALUE_BYTES, provider, key)).fetchone()
        entry = None
        if row:
            expiry = timestamp(row[0])
            if not isinstance(row[1], str) or len(row[1].encode()) > MAX_VALUE_BYTES:
                raise ValueError('Invalid source-cache body size')
            value = json.loads(row[1])
            if not isinstance(value, dict) or not isinstance(value.get('state'), str):
                raise ValueError('Invalid source-cache contract')
            entry = {'until': expiry, 'value': value}
        return {'entry': entry, 'hold_until': timestamp(pacing[0]) if pacing else 0,
                'next_at': timestamp(pacing[1]) if pacing else 0}


def save(settings, provider, key, entry, hold_until, next_at):
    body = json.dumps(entry['value'], allow_nan=False, separators=(',', ':'))
    if len(body.encode()) > MAX_VALUE_BYTES:
        raise ValueError('Source-cache body exceeds budget')
    with database(settings) as con:
        con.execute('INSERT INTO source_pacing VALUES(?,?,?) ON CONFLICT(provider) DO UPDATE SET '
                    'hold_until=max(hold_until,excluded.hold_until),next_at=max(next_at,excluded.next_at)',
                    (provider, timestamp(hold_until), timestamp(next_at)))
        con.execute('INSERT INTO source_cache VALUES(?,?,?,?,?) ON CONFLICT(provider,cache_key) DO UPDATE SET '
                    'expires_at=excluded.expires_at,written_at=excluded.written_at,value=excluded.value',
                    (provider, key, timestamp(entry['until']), time.time(), body))
        con.execute('DELETE FROM source_cache WHERE provider=? AND expires_at<=?', (provider, time.time()))
        con.execute('DELETE FROM source_cache WHERE provider=? AND cache_key IN '
                    '(SELECT cache_key FROM source_cache WHERE provider=? '
                    'ORDER BY written_at DESC,cache_key DESC LIMIT -1 OFFSET 256)', (provider, provider))
