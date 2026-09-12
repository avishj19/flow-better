"""Multi-desk SQLite store for IROP MVP.

One SQLite file per desk. Default desk keeps the legacy path DATA/irop.db
so existing workspaces keep working. Additional desks live under DATA/desks/<id>/.

Hardening vs the stress findings:
- busy_timeout + WAL so concurrent writers retry instead of failing immediately
- per-path write lock inside one process (API threads)
- lean summary column so /api/runs does not hydrate every full payload
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import threading
from contextvars import ContextVar
from pathlib import Path

DESK_RE = re.compile(r'^[a-z0-9][a-z0-9_-]{0,63}$')
_desk: ContextVar[str] = ContextVar('irop_desk', default='default')
_ready: set[str] = set()
_path_locks: dict[str, threading.RLock] = {}
_path_locks_guard = threading.Lock()
_BUSY_MS = int(os.getenv('IROP_DB_BUSY_MS', '30000'))
_TIMEOUT_S = float(os.getenv('IROP_DB_TIMEOUT_S', '30'))


def normalize_desk(name: str | None) -> str:
    raw = (name or os.getenv('IROP_DESK') or 'default').strip().lower()
    if not DESK_RE.match(raw):
        raise ValueError('Desk id must be 1–64 chars: lowercase letters, digits, _ or -')
    return raw


def get_desk() -> str:
    return _desk.get()


def set_desk(name: str | None) -> str:
    desk = normalize_desk(name)
    _desk.set(desk)
    return desk


def desk_dir(data_root: Path, desk: str | None = None) -> Path:
    desk = normalize_desk(desk if desk is not None else get_desk())
    if desk == 'default':
        return Path(data_root)
    path = Path(data_root) / 'desks' / desk
    path.mkdir(parents=True, exist_ok=True)
    return path


def db_path(data_root: Path, desk: str | None = None) -> Path:
    return desk_dir(data_root, desk) / 'irop.db'


def path_lock(path: Path | str) -> threading.RLock:
    key = str(path)
    with _path_locks_guard:
        lock = _path_locks.get(key)
        if lock is None:
            lock = threading.RLock()
            _path_locks[key] = lock
        return lock


def list_desks(data_root: Path) -> list[dict]:
    root = Path(data_root)
    desks = [{'id': 'default', 'path': str(root / 'irop.db'), 'legacy': True}]
    desks_root = root / 'desks'
    if desks_root.is_dir():
        for child in sorted(desks_root.iterdir()):
            if child.is_dir() and DESK_RE.match(child.name) and child.name != 'default':
                desks.append({'id': child.name, 'path': str(child / 'irop.db'), 'legacy': False})
    return desks


def summarize_run(run: dict) -> dict:
    """Lean list/history projection — keep UI fields, drop bulky arrays."""
    return {k: run.get(k) for k in ('id', 'created', 'seed', 'revision', 'phase', 'name')}


def _migrate(conn: sqlite3.Connection):
    cols = {row[1] for row in conn.execute('PRAGMA table_info(runs)')}
    if not cols:
        conn.execute(
            'CREATE TABLE runs (id TEXT PRIMARY KEY, created TEXT, summary TEXT NOT NULL, payload TEXT NOT NULL)'
        )
    elif 'payload' not in cols:
        raise RuntimeError('irop.db runs table is missing payload column')
    else:
        if 'summary' not in cols:
            conn.execute('ALTER TABLE runs ADD COLUMN summary TEXT')
            conn.execute('ALTER TABLE runs ADD COLUMN created TEXT')
            for rid, payload in conn.execute('SELECT id, payload FROM runs'):
                try:
                    run = json.loads(payload)
                except json.JSONDecodeError:
                    run = {'id': rid}
                summary = summarize_run(run if isinstance(run, dict) else {'id': rid})
                conn.execute(
                    'UPDATE runs SET summary=?, created=? WHERE id=?',
                    (json.dumps(summary), summary.get('created'), rid),
                )
            conn.execute("UPDATE runs SET summary='{}' WHERE summary IS NULL")
    conn.execute('CREATE TABLE IF NOT EXISTS connector_state (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
    conn.execute('CREATE INDEX IF NOT EXISTS runs_created_idx ON runs(created)')


def connect(path: Path | str) -> sqlite3.Connection:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=_TIMEOUT_S, check_same_thread=False)
    conn.execute(f'PRAGMA busy_timeout={_BUSY_MS}')
    key = str(path.resolve()) if path.exists() else str(path)
    if key not in _ready:
        conn.execute('PRAGMA journal_mode=WAL')
        conn.execute('PRAGMA synchronous=NORMAL')
        conn.execute('PRAGMA temp_store=MEMORY')
        _migrate(conn)
        conn.commit()
        _ready.add(key)
    return conn


def connect_data(data_root: Path, desk: str | None = None) -> sqlite3.Connection:
    return connect(db_path(data_root, desk))


def save_run(data_root: Path, run: dict, desk: str | None = None):
    path = db_path(data_root, desk)
    summary = summarize_run(run)
    payload = json.dumps(run)
    summary_json = json.dumps(summary)
    created = run.get('created')
    with path_lock(path):
        with connect(path) as conn:
            conn.execute(
                'INSERT OR REPLACE INTO runs(id, created, summary, payload) VALUES (?,?,?,?)',
                (run['id'], created, summary_json, payload),
            )


def get_run(data_root: Path, run_id: str, desk: str | None = None) -> dict | None:
    with connect_data(data_root, desk) as conn:
        row = conn.execute('SELECT payload FROM runs WHERE id=?', (run_id,)).fetchone()
    if not row:
        return None
    return json.loads(row[0])


def list_run_summaries(data_root: Path, desk: str | None = None, limit: int | None = None) -> list[dict]:
    sql = 'SELECT summary, payload FROM runs ORDER BY COALESCE(created, id) DESC, rowid DESC'
    args: tuple = ()
    if limit is not None:
        sql += ' LIMIT ?'
        args = (int(limit),)
    out = []
    with connect_data(data_root, desk) as conn:
        for summary, payload in conn.execute(sql, args):
            if summary:
                try:
                    item = json.loads(summary)
                    if isinstance(item, dict) and item.get('id'):
                        out.append(item)
                        continue
                except json.JSONDecodeError:
                    pass
            out.append(summarize_run(json.loads(payload)))
    return out
