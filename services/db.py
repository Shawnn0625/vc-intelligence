import json
import sqlite3
from pathlib import Path
from datetime import datetime, timezone

DB_PATH = Path(__file__).resolve().parent.parent / 'data' / 'vc_intelligence.sqlite3'


def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH, timeout=15)
    con.row_factory = sqlite3.Row
    con.execute('PRAGMA journal_mode=WAL')
    return con


def initialize():
    with connect() as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS news (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          title TEXT NOT NULL,
          summary TEXT NOT NULL DEFAULT '',
          category TEXT NOT NULL,
          company TEXT NOT NULL DEFAULT '',
          source TEXT NOT NULL DEFAULT '',
          url TEXT NOT NULL DEFAULT '',
          published_at TEXT NOT NULL DEFAULT '',
          noteworthy INTEGER NOT NULL DEFAULT 0,
          project_update INTEGER NOT NULL DEFAULT 0,
          demo INTEGER NOT NULL DEFAULT 0,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          UNIQUE(url)
        );
        CREATE TABLE IF NOT EXISTS research (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          company TEXT NOT NULL,
          focus TEXT NOT NULL,
          report TEXT NOT NULL,
          sources_json TEXT NOT NULL DEFAULT '[]',
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS notes (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          company TEXT NOT NULL,
          note TEXT NOT NULL,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        ''')


def save_news(payload, demo=False):
    allowed = {'基模及 Agent', '融资与创业公司', 'AI Infra & Robotics'}
    title = str(payload.get('title', '')).strip()
    category = str(payload.get('category', '')).strip()
    if not title or category not in allowed:
        raise ValueError('title 必填，category 必须是三个指定分类之一')
    url = str(payload.get('url', '') or '').strip()
    if url and not url.startswith(('https://', 'http://')):
        raise ValueError('url 必须是 http(s) 链接')
    with connect() as db:
        db.execute('''INSERT INTO news(title, summary, category, company, source, url, published_at, noteworthy, project_update, demo)
          VALUES(?,?,?,?,?,?,?,?,?,?) ON CONFLICT(url) DO UPDATE SET
          title=excluded.title, summary=excluded.summary, category=excluded.category,
          company=excluded.company, source=excluded.source, published_at=excluded.published_at,
          noteworthy=excluded.noteworthy, project_update=excluded.project_update, demo=excluded.demo''',
          (title, str(payload.get('summary', '')), category, str(payload.get('company', '')),
           str(payload.get('source', '')), url or None, str(payload.get('published_at', '')),
           int(bool(payload.get('noteworthy', False))), int(bool(payload.get('project_update', False))), int(demo)))


def list_news(category=None):
    with connect() as db:
        if category:
            rows = db.execute('SELECT * FROM news WHERE category=? ORDER BY published_at DESC, id DESC', (category,)).fetchall()
        else:
            rows = db.execute('SELECT * FROM news ORDER BY published_at DESC, id DESC').fetchall()
    return [dict(r) for r in rows]


def stats():
    with connect() as db:
        row = db.execute('''SELECT count(*) total, coalesce(sum(noteworthy),0) noteworthy,
            coalesce(sum(project_update),0) projects,
            coalesce(sum(demo),0) demos FROM news''').fetchone()
        return dict(row)


def save_research(company, focus, report, sources):
    with connect() as db:
        db.execute('INSERT INTO research(company,focus,report,sources_json) VALUES (?,?,?,?)',
                   (company, focus, report, json.dumps(sources, ensure_ascii=False)))


def research_history(company=None):
    with connect() as db:
        if company:
            rows = db.execute('SELECT * FROM research WHERE company=? ORDER BY id DESC', (company,)).fetchall()
        else:
            rows = db.execute('SELECT * FROM research ORDER BY id DESC').fetchall()
    return [dict(r) for r in rows]


def save_note(company, note):
    with connect() as db:
        db.execute('INSERT INTO notes(company,note) VALUES(?,?)', (company, note))


def list_notes(company):
    with connect() as db:
        rows = db.execute('SELECT * FROM notes WHERE company=? ORDER BY id DESC', (company,)).fetchall()
    return [dict(r) for r in rows]
