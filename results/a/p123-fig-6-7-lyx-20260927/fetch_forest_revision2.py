
"""Retrieve/verify fixed public-team source bytes only; never run solver/E0."""
import argparse,base64,hashlib,json,subprocess
from pathlib import Path
REPO="huaweibei123/huaweicup2026"
COMMIT="19bebf35205d23fdd832781540f8879da52eeb62"
SOLVER="311322b996c0948e8a6a9c7ec6ddfe6ae41fbee1"
SOURCES=[{'name': 'board-feed-s01-revision2.json', 'blob': '540aae8149dd00f28e0a5c9d7944f13978de2658', 'sha256': 'dc65ad8ed72fab830ac14c5c89b7e65aaec4399aed6e8e6b3d5d417dc75c364d', 'size': 549780}, {'name': 'board-feed-s02-revision2.json', 'blob': '5fee8f207d16c0e13e9ebdade1ab05e4858f59d1', 'sha256': '75b5521fc14e12afd78674f2950d141194a47bb365ddfe07bac8a015e500f71e', 'size': 549997}, {'name': 'board-feed-s03-revision2.json', 'blob': '729c064cdadcd5fb4ca584c9e270a4920561b4a9', 'sha256': '78e83e6f5c336873b4bf431d8d498399ec25c4c4f78d3b547d310ba9f03e974d', 'size': 549873}, {'name': 'board-feed-s04-revision2.json', 'blob': '261b2213433b29ecfc6eafafc50a5af8ce243f00', 'sha256': '97ee774b4379f65e88ddce0268050970840f37c5b7a5f37716492b67a6772e67', 'size': 549533}, {'name': 'board-feed-s05-revision2.json', 'blob': 'c8a2d34094c5f6f6271399801a70025ee09abb37', 'sha256': '29aae9bab068d944affea7d508f0e0d4ac45b1bb8af1ec0c62fbf092b079bc45', 'size': 550143}, {'name': 'board-feed-s06-revision2.json', 'blob': 'e5934c9b2b0b20f8083ad8f521c35cc9c6bf93b8', 'sha256': '9b8d9c9ba610adbb846c13970d177aa295c31d80636ac652961ad75e06cd0a9d', 'size': 550142}, {'name': 'board-feed-s07-revision2.json', 'blob': 'bccb1e3dcf508cb8c1b590aa1023de36b163d3a1', 'sha256': 'e6979596c0312acccd928964986e0576012f3f0d0212a9dc0c5c598db934aa54', 'size': 550035}, {'name': 'board-feed-s08-revision2.json', 'blob': 'b35e7c4f2c81bb370166f824591ed86bcdfb17c2', 'sha256': 'ccf259ac3a44c16d2335fc3a7f38094491ddfb65d78b6336c30061b994ea9627', 'size': 550291}, {'name': 'board-feed-s09-revision2.json', 'blob': '75bb6e9648c7a8b30ee9a571c7918f94ee819e57', 'sha256': '5e935f97a541545a4fbd4c7b30e3853d0e71eaea008daa667620d294e0199bb6', 'size': 550107}, {'name': 'board-feed-s10-revision2.json', 'blob': '672b455d6185b589d29d59a4180a0952b00d0606', 'sha256': 'e499ba7a2fb68258438cf1f43b894f9a7fae4ab4a7bcedb6c147e5baacb67149', 'size': 549993}]
def verify(raw,item):
    if len(raw)!=item['size']:raise ValueError('size mismatch: '+item['name'])
    if hashlib.sha256(raw).hexdigest()!=item['sha256']:raise ValueError('SHA256 mismatch: '+item['name'])
    if hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()!=item['blob']:raise ValueError('git blob mismatch: '+item['name'])
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',default='forest-revision2-offline');ap.add_argument('--verify-only',action='store_true');args=ap.parse_args()
    root=Path(args.output).resolve();feeds=root/'feeds';feeds.mkdir(parents=True,exist_ok=True);records=[]
    for item in SOURCES:
        p=feeds/item['name']
        if p.exists():raw=p.read_bytes()
        else:
            if args.verify_only:raise FileNotFoundError(p)
            # gh api uses api.github.com and the user's own login, no git fetch.
            response=json.loads(subprocess.check_output(['gh','api','repos/'+REPO+'/git/blobs/'+item['blob']],encoding='utf-8',timeout=90))
            raw=base64.b64decode(response['content']);verify(raw,item)
            with p.open('xb') as f:f.write(raw)
        verify(raw,item);records.extend(json.loads(raw)['records']);print('verified',item['name'],flush=True)
    expected={(str(c).zfill(3),k) for c in range(1,101) for k in range(1,6)}
    if len(records)!=500 or {(str(r['case_id']),int(r['cores'])) for r in records}!=expected:raise ValueError('coverage mismatch')
    if not all(r['solver_commit']==SOLVER and r['status']=='ok' and r['revision']==2 for r in records):raise ValueError('version/status mismatch')
    # Convenience merge preserves each original record, with no metric changes.
    merged=json.dumps(dict(source_commit=COMMIT,solver_commit=SOLVER,records=records),ensure_ascii=False,indent=2).encode('utf-8')
    p=root/'P3-forest-revision2.json'
    if p.exists():
        if p.read_bytes()!=merged:raise ValueError('existing merged file differs; use another output folder')
    else:
        with p.open('xb') as f:f.write(merged)
    print('OK: 10 original files, 500 unique cells;',p,flush=True)
if __name__=='__main__':main()


