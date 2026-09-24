from pathlib import Path
import os
import tempfile
import threading
import unittest
from unittest.mock import patch
from src.benchmark_sync.launcher import REPLACE_DELAYS
from src.benchmark_sync.snapshot import atomic_write


class AtomicWriteTests(unittest.TestCase):
    def test_transient_windows_reader_preserves_old_file_until_success(self):
        with tempfile.TemporaryDirectory() as directory:
            target=Path(directory)/'status.json';target.write_bytes(b'old')
            original=os.replace
            failures=0
            def replace(source,destination):
                nonlocal failures
                self.assertEqual(target.read_bytes(),b'old')
                failures+=1
                if failures<3:
                    error=PermissionError('sharing denied');error.winerror=5;raise error
                original(source,destination)
            with patch('src.benchmark_sync.launcher.os.replace',side_effect=replace), patch('src.benchmark_sync.launcher.time.sleep') as sleep:
                atomic_write(target,b'new')
            self.assertEqual(sleep.call_count,2)
            self.assertEqual(target.read_bytes(),b'new')
            self.assertEqual(list(Path(directory).glob('*.tmp')),[])

    def test_persistent_denial_is_bounded_and_unknown_errors_are_not_retried(self):
        for winerror,expected_calls in ((5,len(REPLACE_DELAYS)+1),(32,len(REPLACE_DELAYS)+1),(33,len(REPLACE_DELAYS)+1),(None,1),(112,1)):
            with self.subTest(winerror=winerror),tempfile.TemporaryDirectory() as directory:
                target=Path(directory)/'status.json';target.write_bytes(b'old')
                error=PermissionError('denied');error.winerror=winerror
                with patch('src.benchmark_sync.launcher.os.replace',side_effect=error) as replace,patch('src.benchmark_sync.launcher.time.sleep'):
                    with self.assertRaises(PermissionError):atomic_write(target,b'new')
                self.assertEqual(replace.call_count,expected_calls)
                self.assertEqual(target.read_bytes(),b'old')
                self.assertEqual(list(Path(directory).glob('*.tmp')),[])

    @unittest.skipUnless(os.name=='nt','Actual Windows read-handle sharing semantics')
    def test_actual_windows_read_handle_closes_during_retry(self):
        with tempfile.TemporaryDirectory() as directory:
            target=Path(directory)/'status.json';target.write_bytes(b'old')
            reader=target.open('rb')
            timer=threading.Timer(.15,reader.close);timer.start()
            try:atomic_write(target,b'new')
            finally:timer.join();reader.close()
            self.assertEqual(target.read_bytes(),b'new')

    @unittest.skipUnless(os.name=='nt','Actual Windows read-handle sharing semantics')
    def test_actual_windows_persistent_read_handle_retains_old_file(self):
        with tempfile.TemporaryDirectory() as directory:
            target=Path(directory)/'status.json';target.write_bytes(b'old')
            with target.open('rb') as reader:
                with self.assertRaises(PermissionError):atomic_write(target,b'new')
                self.assertEqual(reader.read(),b'old')
            self.assertEqual(target.read_bytes(),b'old')
