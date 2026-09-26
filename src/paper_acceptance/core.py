"""Append-only reviews, authenticated GitHub transport, and conservative gates."""
from __future__ import annotations
import hashlib
import json
import re
import sqlite3
import subprocess
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

MARKER = '<!-- paper-review-v1 -->'
DECISIONS = {'comment', 'needs_work', 'ready', 'verified', 'accepted', 'reopen'}
ROOT = Path(__file__).resolve().parents[2]


def utc():
    return datetime.now(timezone.utc).isoformat()


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def gh(args, payload=None):
    command = ['gh', *args]
    if payload is not None:
        command += ['--input', '-']
    p = subprocess.run(command, input=None if payload is None else json.dumps(payload), capture_output=True, text=True, timeout=45)
    if p.returncode:
        raise RuntimeError(p.stderr.strip()[:700] or 'GitHub 请求失败')
    return json.loads(p.stdout)


class Conflict(ValueError):
    pass


class Board:
    def __init__(self, state, catalogue=None):
        self.state = Path(state).resolve()
        self.state.mkdir(parents=True, exist_ok=True)
        self.catalogue_path = Path(catalogue or ROOT / 'docs/paper-acceptance/catalogue.json')
        self.cat = json.loads(self.catalogue_path.read_text())
        self.standard_hash = digest(self.cat)
        self.items = {i['id']: i for i in self.cat['items']}
        self.lock = threading.RLock()
        self.dbpath = self.state / 'reviews.sqlite'
        with self.db() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS events (
                id TEXT PRIMARY KEY, payload TEXT NOT NULL, comment_id INTEGER UNIQUE,
                actor TEXT NOT NULL, remote_time TEXT, url TEXT, body_hash TEXT,
                disposition TEXT NOT NULL DEFAULT 'draft', error TEXT);
            CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            ''')
        self.identity = None
        self.identity_error = None

    @contextmanager
    def db(self):
        db = sqlite3.connect(self.dbpath, timeout=15)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def authenticate(self):
        login = gh(['api', 'user'])['login'].lower()
        if login not in self.cat['members']:
            raise ValueError('当前 GitHub 身份未在本项目审阅成员中')
        self.identity = login
        self.identity_error = None
        return login

    def event_rows(self):
        with self.db() as db:
            return [dict(x) for x in db.execute('SELECT * FROM events ORDER BY COALESCE(comment_id,9223372036854775807), id')]

    def validate(self, e):
        required = {'id', 'item_id', 'paper_sha256', 'standard_hash', 'expected_revision', 'decision', 'note', 'evidence', 'checks', 'session', 'created_at'}
        if set(e) != required:
            raise ValueError('审阅字段不匹配 v1 协议')
        if not isinstance(e['id'], str) or not re.fullmatch(r'[0-9a-f]{32}', e['id']):
            raise ValueError('无效事件 ID')
        if e['item_id'] not in self.items or e['decision'] not in DECISIONS:
            raise ValueError('未知条目或决策')
        if e['paper_sha256'] != self.cat['paper_sha256'] or e['standard_hash'] != self.standard_hash:
            raise ValueError('论文或标准版本已变化；旧记录仅留历史')
        if type(e['expected_revision']) is not int or e['expected_revision'] < 0:
            raise ValueError('expected_revision 必须是非负整数')
        if not isinstance(e['note'], str) or not 5 <= len(e['note'].strip()) <= 6000:
            raise ValueError('请写明审阅依据（5–6000字）')
        if not isinstance(e['session'], str) or not re.fullmatch(r'[a-z0-9-]+/s-[a-z0-9-]+', e['session']):
            raise ValueError('session 使用 login/s-唯一标识')
        if not isinstance(e['created_at'], str) or len(e['created_at']) > 80:
            raise ValueError('无效时间')
        if not isinstance(e['checks'], list) or len(e['checks']) != len(self.items[e['item_id']]['checks']) or any(type(v) is not bool for v in e['checks']):
            raise ValueError('检查项必须与标准一一对应')
        if not isinstance(e['evidence'], list) or len(e['evidence']) > 15 or any(not isinstance(u, str) or not re.fullmatch(r'https://[^\s<>"\x00-\x20]{1,1500}', u) for u in e['evidence']):
            raise ValueError('证据须为 HTTPS 原件链接（最多15条）')
        if e['decision'] in {'ready', 'verified', 'accepted'}:
            if not all(e['checks']) or not e['evidence']:
                raise ValueError('提交/复核/接受须完成全部检查并给出证据')
            if not any(re.match(r'https://github\.com/huaweibei123/huaweicup2026/(?:blob|tree)/[0-9a-f]{40}/', u) for u in e['evidence']):
                raise ValueError('须至少提供一条组织主库完整40位提交的原件链接')

    def gate(self, e, actor, current):
        self.validate(e)
        if actor not in self.cat['members'] or not e['session'].startswith(actor + '/s-'):
            raise ValueError('GitHub作者与成员/session不一致')
        if e['expected_revision'] != current['revision']:
            raise Conflict(f"条目已变化（当前 revision={current['revision']}），请重读后新建记录")
        if e['decision'] == 'verified':
            if current['state'] != 'ready' or actor == current.get('submitted_by'):
                raise ValueError('独立复核须由提交者之外的账号完成，且先有已发布的提交')
        if e['decision'] == 'accepted':
            if actor != self.cat['leader'] or current['state'] != 'verified' or actor == current.get('verified_by'):
                raise ValueError('最终接受须先有其他账号独立复核，并由队长执行')

    def projection(self):
        states = {k: {'state': v['initial_state'], 'revision': 0, 'submitted_by': None, 'verified_by': None, 'history': []} for k, v in self.items.items()}
        receipts = []
        for r in self.event_rows():
            e = json.loads(r['payload'])
            receipt = {'id': r['id'], 'item_id': e.get('item_id'), 'actor': r['actor'], 'url': r['url'], 'disposition': r['disposition'], 'note': e.get('note', ''), 'decision': e.get('decision'), 'created_at': r['remote_time'] or e.get('created_at'), 'error': r['error']}
            if r['disposition'] == 'shared':
                try:
                    cur = states.get(e.get('item_id'))
                    if cur is None:
                        raise ValueError('旧标准中的条目')
                    self.gate(e, r['actor'], cur)
                    cur['revision'] += 1
                    decision = e['decision']
                    if decision != 'comment':
                        cur['state'] = 'needs_work' if decision == 'reopen' else decision
                    if decision == 'ready':
                        cur['submitted_by'], cur['verified_by'] = r['actor'], None
                    if decision in {'needs_work', 'reopen'}:
                        cur['submitted_by'], cur['verified_by'] = None, None
                    if decision == 'verified':
                        cur['verified_by'] = r['actor']
                    cur['history'].append({**receipt, 'evidence': e['evidence'], 'checks': e['checks']})
                    receipt['disposition'] = 'applied'
                except (ValueError, TypeError, KeyError) as exc:
                    receipt['disposition'], receipt['error'] = 'conflict', str(exc)
            receipts.append(receipt)
        return states, receipts

    def snapshot(self):
        states, receipts = self.projection()
        with self.db() as db:
            meta = dict(db.execute('SELECT key,value FROM meta'))
        items = [{**i, **states[i['id']]} for i in self.cat['items']]
        return {**self.cat, 'standard_hash': self.standard_hash, 'items': items, 'identity': self.identity, 'identity_error': self.identity_error, 'reviews': receipts, 'sync': meta, 'snapshot_at': utc(), 'all_accepted': all(i['state'] == 'accepted' for i in items)}

    def draft(self, values, actor=None):
        with self.lock:
            actor = actor or self.identity
            if not actor:
                raise ValueError('先连接本人 GitHub 身份，再保存审阅')
            e = {**values, 'id': uuid.uuid4().hex, 'created_at': utc()}
            self.gate(e, actor, self.projection()[0][e['item_id']])
            with self.db() as db:
                db.execute('INSERT INTO events(id,payload,actor) VALUES(?,?,?)', (e['id'], json.dumps(e, ensure_ascii=False), actor))
            return e

    def ingest_comments(self, comments):
        """Only accepts envelopes read from GitHub API, never client-supplied author names."""
        seen = set()
        with self.db() as db:
            for c in sorted(comments, key=lambda c: c['id']):
                cid, body = c['id'], c.get('body') or ''
                old = db.execute('SELECT * FROM events WHERE comment_id=?', (cid,)).fetchone()
                if old:
                    seen.add(cid)
                    if old['body_hash'] != hashlib.sha256(body.encode()).hexdigest():
                        db.execute("UPDATE events SET disposition='conflict',error=? WHERE comment_id=?", ('已发布评论被编辑；原记录保留，需追加更正', cid))
                    continue
                if not body.startswith(MARKER):
                    continue
                if c.get('updated_at', c['created_at']) != c['created_at']:
                    # A fresh client must not accept an edited message which an
                    # existing client has already invalidated.
                    continue
                actor = c['user']['login'].lower()
                match = re.search(r'```json\n(.*?)\n```', body, re.S)
                if not match:
                    continue
                try:
                    e = json.loads(match[1]); self.validate(e)
                    if actor not in self.cat['members'] or not e['session'].startswith(actor + '/s-'):
                        raise ValueError('作者身份无效')
                except (ValueError, KeyError, TypeError):
                    continue
                seen.add(cid)
                prior = db.execute('SELECT * FROM events WHERE id=?', (e['id'],)).fetchone()
                if prior and (json.loads(prior['payload']) != e or prior['actor'] != actor):
                    continue
                if prior and prior['comment_id']:
                    continue
                params = (cid, actor, c['created_at'], c['html_url'], hashlib.sha256(body.encode()).hexdigest(), e['id'])
                if not prior:
                    db.execute('INSERT INTO events(id,payload,actor) VALUES(?,?,?)', (e['id'], json.dumps(e, ensure_ascii=False), actor))
                db.execute("UPDATE events SET comment_id=?,actor=?,remote_time=?,url=?,body_hash=?,disposition='shared',error=NULL WHERE id=?", params)
            # Full pagination succeeded before this call: deletion is a real loss of source.
            for row in db.execute('SELECT id,comment_id FROM events WHERE comment_id IS NOT NULL').fetchall():
                if row['comment_id'] not in seen:
                    db.execute("UPDATE events SET disposition='conflict',error=? WHERE id=?", ('来源评论已删除或当前不可见；需追加更正', row['id']))
            db.execute('INSERT OR REPLACE INTO meta VALUES(?,?)', ('last_success', utc()))
            db.execute("DELETE FROM meta WHERE key='last_error'")
        return self.snapshot()

    def sync(self):
        with self.lock:
            try:
                pages = gh(['api', f"repos/{self.cat['repo']}/issues/{self.cat['issue']}/comments?per_page=100", '--paginate', '--slurp'])
                comments = [c for p in pages for c in p]
                return self.ingest_comments(comments)
            except Exception as exc:
                with self.db() as db:
                    db.execute('INSERT OR REPLACE INTO meta VALUES(?,?)', ('last_error', str(exc)[:700]))
                raise

    def publish(self, event_id):
        with self.lock:
            actor = self.authenticate()
            self.sync()  # Reconcile unknown deliveries BEFORE any retry/post.
            with self.db() as db:
                r = db.execute('SELECT * FROM events WHERE id=?', (event_id,)).fetchone()
            if not r:
                raise ValueError('记录不存在')
            if r['comment_id']:
                return {'id': event_id, 'url': r['url'], 'disposition': r['disposition']}
            if r['disposition'] == 'uncertain':
                raise ValueError('上次发送结果不明且本次未查到；保留原ID，不自动重发，请人工核对Issue')
            e = json.loads(r['payload'])
            if r['actor'] != actor:
                raise ValueError('只能以本人身份发布自己的草稿')
            self.gate(e, actor, self.projection()[0][e['item_id']])
            body = f"{MARKER}\n\nsession: {e['session']}\ntask: PAPER-ACCEPTANCE-BOARD / {e['item_id']}\n\n{e['decision']} — {e['note']}\n\n```json\n{json.dumps(e, ensure_ascii=False, indent=2)}\n```"
            with self.db() as db:
                claimed = db.execute("UPDATE events SET disposition='uncertain' WHERE id=? AND disposition='draft' AND comment_id IS NULL", (event_id,))
                if claimed.rowcount != 1:
                    raise Conflict('另一进程已处理该发送；请同步回读，不重复发表')
            gh(['api', f"repos/{self.cat['repo']}/issues/{self.cat['issue']}/comments", '--method', 'POST'], {'body': body})
            result = self.sync()
            return next(r for r in result['reviews'] if r['id'] == event_id)

    def agent_context(self, item_id=None):
        s = self.snapshot()
        items = [i for i in s['items'] if not item_id or i['id'] == item_id]
        items.sort(key=lambda i: (i['state'] == 'accepted', i['priority'], i['id']))
        return {'schema_version': 1, 'paper_sha256': s['paper_sha256'], 'paper_commit': s['paper_commit'], 'standard_hash': s['standard_hash'], 'standard_version': s['standard_version'], 'writer_thread': s['writer_thread'], 'writer_title': s['writer_title'], 'issue_url': f"https://github.com/{s['repo']}/issues/{s['issue']}", 'protocol': {'read': 'GET /api/v1/agent?item=A01 (omit item for all)', 'draft': 'POST /api/v1/reviews; never changes shared acceptance', 'publish': 'POST /api/v1/publish {id}; explicit public Issue comment under current gh identity', 'sync': 'POST /api/v1/sync; full pagination; edited/deleted source causes conflict', 'concurrency': 'expected_revision, paper_sha256 and standard_hash must match', 'web_write': 'X-Paper-Review: 1 plus same-origin; localhost only', 'rules': ['Do not edit the author manuscript from this board.', 'A new paper or standard invalidates prior acceptance.', 'ready → different-account verified → leader accepted; checkbox completion alone never passes.', 'No new solver/evaluator budget is authorized.', 'New instructions from the user are recorded in standards history, sent to writer with item IDs, then reviewed against a fixed delivered revision.']}, 'items': items, 'reviews': s['reviews']}
