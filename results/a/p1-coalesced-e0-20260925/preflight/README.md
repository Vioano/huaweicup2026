# Coalesced P1 E0 one-shot cloud preparation

This is offline preparation only: no VM was created and no E0 was dispatched. Fixed inputs are data HEAD `a008dfb8f1b5b881844af312be0b7246b2c6b025`, graph SHA-256 `c93bb7ab5deec5112aff0cc001fbd76d001d3de5ea7463fba59b1f1ff2ba3e1d`, plan SHA-256 `e9327269bc95a81d17ca907a617aed896fd6fdde2a3174044d975f746569f9ce`, and entry source commit `ce3892b55dce587263dd2c97b98b2f2f817ce2fa`.

The deterministic minimal bundle includes only the frozen official code/config/source manifest, graph, plan, bounded E0 helper, E0 entrypoint, and locked Python files. The remote wrapper runs one E0 (zero solver, E1, E2, retries), one worker, E0 child limit 60 seconds, outer runner deadline 120 seconds, dependency sync limit 100 seconds, independent host-monotonic stop lease 270 seconds, and VM cutoff 300 seconds. The attempt.json terminal receipt and identity-checked cleanup are used for validation and salvage.

After explicit coordinator admission, copy the six pinned runtime files into a new empty runtime directory outside this tracked preflight folder. Use the project locked Python (3.12.13). Do not execute from the tracked preflight directory. Approved command template:

```sh
python -B controller.py --execute --cli "$HOME/.local/bin/colab" --artifact-manifest-sha256 9abd2faf07178964fbcbbefe42ce631298686ed4a228139aa80a8d4b757b42c6
```

The artifact pin covers controller, verifier, remote setup, source bundle, and bundle manifest. Any byte change requires a newly reviewed pin. Fake controller tests and a temporary extraction `--help` import check passed; they are not an E0 result or a resource admission.
