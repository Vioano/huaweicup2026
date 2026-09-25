# Recovery stopped before tests

The one authorized recovery child exited 1 at `verify.py:4`: `ModuleNotFoundError: No module named 'src'`. It was launched as a direct file path, so Python placed the recovery directory on `sys.path` rather than the repository root. Saved `stderr.txt` is the exact traceback; `stdout.txt` is empty. **Zero** synthetic tests, old R9 reads, pure guard calls, and official calls occurred in this recovery child. The first-run failures and original frozen test remain preserved in the parent directory. There was no retry.

The guard cleanup and corrected fixture hashes in `FROZEN.md` remain unvalidated. A future separately authorized window should use package/module execution with the repository root importable, or initialize `sys.path` before the guard import, then freeze its own exact bytes and command. Do not mark the guard accepted or use it for the 194-op candidate on this record.
