#!/usr/bin/env python3
"""Render a visible ChatGPT project DOM capture into an append-only archive snapshot.

The input is a local capture of public, rendered chat rows. This program does not
fetch ChatGPT state, execute attachments, or infer missing replies.
"""

import argparse
import hashlib
import json
from pathlib import Path

from export_chatgpt_archive import dom_markdown


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def render(capture: dict, snapshot: Path, audit: Path, *, manual_top_note: str = "") -> dict:
    if snapshot.exists() or audit.exists():
        raise FileExistsError("Snapshots are append-only")
    checks = capture["verification"]
    if checks.get("loading_older") or not checks.get("reached_bottom"):
        raise ValueError("History pagination or final scroll remains incomplete")
    if checks.get("top_stable", 0) < 3 and not manual_top_note:
        raise ValueError("First page not verified; supply a documented manual top check")
    turns = capture["turns"]
    if not turns or checks.get("turn_count") != len(turns):
        raise ValueError("Turn count mismatch")
    if turns[0]["user_id"] != checks.get("first_user_id") or turns[-1]["user_id"] != checks.get("last_user_id"):
        raise ValueError("First or last user ID mismatch")
    stamp = capture["captured_at"]
    lines = [f'# {capture["title"]}', '',
             f'- 原会话：{capture["url"]}',
             f'- 浏览器公开页面采集 UTC：{stamp}',
             '- 范围：当前选中分支；公开提问与最终可见回答。隐藏推理、已删内容、未选中的再生成版本不在范围内。',
             '- 核验：网页历史分页触顶、遍历到末尾并累计消息 ID；无独立服务端消息清单，不能证明服务器端绝对完整。',
             '- 研究定位：作者声明与建议保留为原文；定理和成绩仍需结合官方材料及本机复核。', '']
    if manual_top_note:
        lines += [f'- 人工触顶补核：{manual_top_note}', '']
    records = []
    seen = set()
    for ix, turn in enumerate(turns, 1):
        user_id = turn["user_id"]
        agent_ids = [mid for mid in turn.get("assistant_ids", []) if mid != user_id]
        answer_id = agent_ids[-1] if agent_ids else None
        if user_id in seen or (answer_id and answer_id in seen):
            raise ValueError(f"Duplicate user/final ID at turn {ix}")
        seen.add(user_id)
        if answer_id:
            seen.add(answer_id)
        user = turn.get("user_markdown") or dom_markdown(turn.get("user_html") or "") or turn.get("user_text", "")
        user_visible = turn.get("user_text", "")
        if not user_visible or len(user) < max(1, len(user_visible) // 2):
            raise ValueError(f"User message appears truncated at turn {ix}")
        parts = [dom_markdown(html) for html in turn.get("assistant_html", [])]
        answer = turn.get("assistant_markdown") or "\n\n".join(part for part in parts if part)
        answer_visible = turn.get("assistant_text", "")
        if answer_visible and len(answer) < max(1, len(answer_visible) // 2):
            raise ValueError(f"Assistant answer appears truncated at turn {ix}")
        status = turn.get("assistant_status", "unknown")
        if status == "final_visible" and not answer:
            answer = "[此轮公开回答为图像或其他非文本输出；原件取得状态见 manifest。]"
        lines += ['---', '', f'## 第 {ix:02d} 轮 · 用户', '', f'`message_id={user_id}`',
                  f'来源：{turn.get("source", "当前网页公开 DOM")}', '', user, '']
        if turn.get("file_controls"):
            lines += ['页面显示的文件名或预览控件（含用户输入与回答，归属以附件清单为准）：', '']
            lines += [f'- {item}' for item in turn["file_controls"]]
            lines += ['']
        lines += [f'## 第 {ix:02d} 轮 · 助手', '',
                  f'`message_id={answer_id or "未见最终回答 ID"}`  状态：`{status}`', '']
        lines += [answer or '[页面未显示最终回答。]', '']
        if len(agent_ids) > 1:
            lines += ['同一轮 DOM 中另见 agent ID，未把其当作最终答复或隐藏推理导出：'
                      + ', '.join(agent_ids[:-1]), '']
        records.append({
            'round': ix, 'user_id': user_id, 'assistant_final_id': answer_id,
            'source': turn.get('source', 'current_browser_public_dom'),
            'other_agent_ids_observed': agent_ids[:-1], 'assistant_status': status,
            'user_markdown_sha256': digest(user), 'user_visible_text_sha256': digest(user_visible),
            'user_visible_length': len(user_visible), 'assistant_markdown_sha256': digest(answer),
            'assistant_visible_text_sha256': digest(answer_visible),
            'assistant_visible_length': len(answer_visible),
            'file_controls': turn.get('file_controls', []),
        })
    body = '\n'.join(lines)
    summary = {
        'schema': 'project-chat-dom-audit-v2', 'conversation_id': capture['conversation_id'],
        'title': capture['title'], 'url': capture['url'], 'captured_at': stamp,
        'pagination': checks, 'manual_top_note': manual_top_note or None,
        'turns': len(turns), 'public_user_messages': len(turns),
        'final_assistant_ids': sum(bool(r['assistant_final_id']) for r in records),
        'no_final_answer_turns': [r['round'] for r in records if not r['assistant_final_id']],
        'snapshot': snapshot.name, 'snapshot_sha256': digest(body), 'messages': records,
        'validation_boundary': 'Browser visible selected branch only; no independent server inventory available in this task.'
    }
    snapshot.parent.mkdir(parents=True, exist_ok=True)
    snapshot.write_text(body, encoding='utf-8')
    audit.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('capture', type=Path)
    parser.add_argument('snapshot', type=Path)
    parser.add_argument('audit', type=Path)
    parser.add_argument('--manual-top-note', default='')
    args = parser.parse_args()
    result = render(json.loads(args.capture.read_text(encoding='utf-8')), args.snapshot, args.audit,
                    manual_top_note=args.manual_top_note)
    print(json.dumps({'conversation_id': result['conversation_id'], 'turns': result['turns'],
                      'final_assistant_ids': result['final_assistant_ids']}))
