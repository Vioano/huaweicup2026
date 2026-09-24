"""Small signed website releases. Safe staged extraction; activation belongs to supervisor."""
from __future__ import annotations
import io
import json
from pathlib import Path
import shutil
import subprocess
import zipfile
from .github import fixed_sha, path_ok
from .snapshot import atomic_write, canonical, digest, now
from .engine import read_json, write_json

MAX_RELEASE=8*1024*1024
DOCS={'docs/a/source-manifest.json',*(f'docs/benchmarks/{name}' for name in (
    'algorithm-registry.json','board-sources.json','board-calibrations.json','board-feed.schema.json',
    'SUBMISSION_PROTOCOL.md','examples/submission-v1.json'))}


def allowed(path):
    path_ok(path)
    return path in DOCS or (path.startswith(('src/benchmark_board/','src/benchmark_sync/'))
                           and Path(path).suffix in ('.py','.mjs','.html','.css','.js'))


def build_release(repo,commit):
    fixed_sha(commit)
    names=subprocess.check_output(['git','-C',str(repo),'ls-tree','-r','--name-only',commit],text=True).splitlines()
    files={}
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w',compression=zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(names):
            if not allowed(name): continue
            data=subprocess.check_output(['git','-C',str(repo),'show',commit+':'+name])
            if len(data)>MAX_RELEASE: raise ValueError('Release file exceeds size limit')
            files[name]={'sha256':digest(data),'size':len(data)}
            info=zipfile.ZipInfo(name); info.compress_type=zipfile.ZIP_DEFLATED; info.external_attr=0o100644<<16
            archive.writestr(info,data)
    data=stream.getvalue()
    if len(data)>MAX_RELEASE: raise ValueError('Release package too large')
    if not DOCS.issubset(files) or 'src/benchmark_board/app.py' not in files: raise ValueError('Incomplete website release')
    manifest={'schema_version':1,'release_id':digest(data),'code_commit':commit,'size':len(data),
              'files':files,'created_at':now(),'python_minimum':'3.12'}
    return manifest,data


def stage_release(state,manifest,data):
    if not isinstance(manifest,dict) or len(data)>MAX_RELEASE or len(data)!=manifest['size'] or digest(data)!=manifest['release_id']:
        raise ValueError('Release bytes/hash mismatch')
    fixed_sha(manifest['code_commit'])
    files=manifest['files']
    if not isinstance(files,dict) or not DOCS.issubset(files) or len(files)>300: raise ValueError('Invalid release file manifest')
    if any(not allowed(p) for p in files): raise ValueError('Unsafe release file manifest')
    dest=Path(state)/'releases'/manifest['release_id']
    completed=dest/'release.json'
    if completed.exists():
        # A local cache hit is not trusted without byte verification.
        if any(not (dest/p).is_file() or digest((dest/p).read_bytes())!=spec['sha256'] for p,spec in files.items()):
            raise ValueError('Installed release cache damaged')
        return dest
    temporary=dest.with_name(dest.name+'.staging')
    if temporary.exists(): shutil.rmtree(temporary)
    temporary.mkdir(parents=True)
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            names=archive.namelist()
            if len(names)!=len(set(names)) or set(names)!=set(files): raise ValueError('Release ZIP entries mismatch')
            total=0
            for item in archive.infolist():
                if not allowed(item.filename) or item.is_dir() or (item.external_attr>>16)&0o170000 not in (0,0o100000):
                    raise ValueError('Unsafe release ZIP entry')
                spec=files[item.filename];total+=item.file_size
                if item.file_size!=spec['size'] or total>MAX_RELEASE*4: raise ValueError('Expanded release size limit')
                value=archive.read(item)
                if digest(value)!=spec['sha256']: raise ValueError('Release file hash mismatch')
                atomic_write(temporary/item.filename,value)
        write_json(temporary/'release.json',manifest)
        if dest.exists(): raise ValueError('Incomplete previous release directory; preserve for diagnosis')
        temporary.rename(dest)
        return dest
    finally:
        if temporary.exists(): shutil.rmtree(temporary)


def publish_release(engine,repo,commit):
    manifest,data=build_release(repo,commit)
    head=engine.remote.head()
    old,previous_envelope=engine.channel(head,'release','release') if head else (None,None)
    if old and old['manifest']['release_id']==manifest['release_id']: return old['manifest']
    path='objects/'+manifest['release_id']
    channel={'generation':old['generation']+1 if old else 1,'manifest':manifest,'object':path}
    engine.remote.update({path:data,'channels/release.json':canonical(engine.sign('release',channel))},
                         expected={'channels/release.json':canonical(previous_envelope) if previous_envelope else None})
    return manifest


def receive_release(engine,head):
    channel,envelope=engine.channel(head,'release','release')
    if not channel: return
    state=engine.state/'software'; pointer=state/'desired.json'
    if pointer.exists():
        previous=engine.verify(read_json(pointer)['_channel'],'release',central=True)
        if channel['generation']<previous['generation']: raise ValueError('Signed release rollback')
        if channel['generation']==previous['generation']:
            if channel!=previous: raise ValueError('Release generation reused')
            return
    m=channel['manifest']; path=channel['object']
    if path!='objects/'+m['release_id']: raise ValueError('Release object identity mismatch')
    dest=stage_release(engine.state,m,engine.remote.read(head,path))
    write_json(pointer,{'release_id':m['release_id'],'code_commit':m['code_commit'],'path':str(dest),'_channel':envelope})
