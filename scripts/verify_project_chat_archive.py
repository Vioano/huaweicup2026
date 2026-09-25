#!/usr/bin/env python3
"""Verify the checked-in huaweicup project chat inventory and archived bytes."""

import hashlib
import json
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    root = Path(__file__).resolve().parent.parent / 'AI chats'
    inventory = json.loads((root / 'PROJECT_AUDIT_20260925.json').read_text(encoding='utf-8'))
    entries = inventory['entries']
    assert len(entries) == inventory['visible_chats_checked'] == 15
    assert len({entry['conversation_id'] for entry in entries}) == len(entries)
    assert {path.name for path in root.iterdir() if path.is_dir()} == {entry['directory'] for entry in entries}
    checked = 0
    for entry in entries:
        folder = root / entry['directory']
        manifest = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
        assert (manifest.get('conversation_id') or manifest.get('chat_url', '').split('/')[-1]) == entry['conversation_id']
        assert (folder / 'README.md').is_file()
        files = manifest['files']
        assert len(files) == entry['current_files_sha256_checked']
        assert {record['path'] for record in files} == {
            str(path.relative_to(folder)) for path in folder.rglob('*')
            if path.is_file() and path.name != 'manifest.json'
        }
        missing = manifest.get('missing_attachments_project_reaudit', manifest.get('missing_attachments', []))
        assert len(missing) == entry['missing_original_assets_reported']
        for record in files:
            path = folder / record['path']
            assert path.is_file() and path.stat().st_size == record['bytes'], path
            assert sha256(path) == record['sha256'], path
            checked += 1
        if entry['current_audit']:
            audit = json.loads((folder / entry['current_audit']).read_text(encoding='utf-8'))
            assert audit['conversation_id'] == entry['conversation_id']
            assert audit['public_user_messages'] == entry['current_user_turns']
            assert audit['final_assistant_ids'] == entry['current_final_answers']
            assert audit['messages'][0]['user_id'] == entry['first_user_id']
            assert audit['messages'][-1]['user_id'] == entry['last_user_id']
            assert sha256(folder / audit['snapshot']) == audit['snapshot_sha256']
    print(f'OK: {len(entries)} chats, {checked} archived files verified by SHA-256')


if __name__ == '__main__':
    main()
