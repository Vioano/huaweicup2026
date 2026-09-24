import hashlib
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.benchmark_sync.snapshot import digest
from src.benchmark_sync.submission import verify_commit_artifacts


def blob_oid(value):
    return hashlib.sha1(b'blob '+str(len(value)).encode()+b'\0'+value).hexdigest()


class ArtifactBatchTests(unittest.TestCase):
    def test_tree_paths_and_blob_bytes_are_checked_in_batches(self):
        values={f'results/{index:04}.bin':f'fixture-{index}'.encode() for index in range(260)}
        entries=[];response=bytearray()
        for path,value in values.items():
            oid=blob_oid(value)
            entries.append(f'100644 blob {oid} {len(value)}\t{path}'.encode()+b'\0')
            response.extend(f'{oid} blob {len(value)}\n'.encode()+value+b'\n')
        with tempfile.TemporaryDirectory() as tmp:
            with patch('src.benchmark_sync.submission.git',return_value=b''.join(entries)) as git_call, \
                 patch('src.benchmark_sync.submission.subprocess.run',return_value=subprocess.CompletedProcess([],0,bytes(response),b'')) as batch_call:
                verify_commit_artifacts(Path(tmp),'a'*40,{path:digest(value) for path,value in values.items()})
            self.assertEqual(git_call.call_count,3)
            args=batch_call.call_args.args[0]
            self.assertEqual(args[-1],'--batch')
            self.assertEqual(batch_call.call_count,1)
            self.assertEqual(len(batch_call.call_args.kwargs['input'].splitlines()),260)

    def test_mismatched_hash_and_missing_paths_are_rejected(self):
        value=b'right';oid=blob_oid(value)
        entry=f'100644 blob {oid} {len(value)}\tresults/item.bin'.encode()+b'\0'
        response=f'{oid} blob {len(value)}\n'.encode()+value+b'\n'
        with tempfile.TemporaryDirectory() as tmp:
            with patch('src.benchmark_sync.submission.git',return_value=entry), \
                 patch('src.benchmark_sync.submission.subprocess.run',return_value=subprocess.CompletedProcess([],0,response,b'')):
                with self.assertRaisesRegex(ValueError,'bytes/hash'):
                    verify_commit_artifacts(Path(tmp),'b'*40,{'results/item.bin':'0'*64})
            with patch('src.benchmark_sync.submission.git',return_value=b''):
                with self.assertRaisesRegex(ValueError,'Missing artifact'):
                    verify_commit_artifacts(Path(tmp),'b'*40,{'results/item.bin':digest(value)})


if __name__=='__main__': unittest.main()
