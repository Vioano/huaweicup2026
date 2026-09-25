# Stopped at first script exception

The first launch with `python` did not create a script process (`zsh: command not found: python`); the single actual script process used `/opt/homebrew/bin/python3`. It exited before either graph decomposition or subset DP. `stderr.txt` preserves the traceback and `stdout.txt` is empty.

Cause: the frozen script used standard `configparser` for the official space-delimited `config.txt`; it raised `configparser.ParsingError` on the L1/UB entries. The script and its frozen SHA remain untouched. Per the frozen zero-retry rule, no corrected script or second run was attempted. No certificate, five-core conclusion, official plan, or official score was produced. Official Task, Step, solver, pipe_bound, construct, E0/E1/E2 call counts remain zero.
