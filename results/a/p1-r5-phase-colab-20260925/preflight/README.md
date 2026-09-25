# R5 phase controller preparation

Static preparation only: no Colab VM, real Task compilation, Fraction model call, or official E0/E1/E2 call has been made. The frozen source commit is `8e63305f86a3692b9552295c61c4f234a006c105`; input graph SHA-256 is `c93bb7ab5deec5112aff0cc001fbd76d001d3de5ea7463fba59b1f1ff2ba3e1d`.

The frozen artifact-manifest SHA-256 pin is `3ff23e7c05b6f80eb8318f58930be7026d18b296a3fb5185fac50b30f1ddda71`. The manifest pins the controller, verifier, remote setup, transfer bundle, and bundle manifest. Controller and detached watchdog verify every listed byte before VM creation. The watchdog must emit a ready ACK that matches the pin, session, and monotonic lease before `new` is allowed.

After coordinator admission only, copy the six frozen runtime files to a new, empty runtime directory. Do not execute from the tracked `preflight` directory because the controller uses single-use receipts there.

```sh
PROJECT_ROOT=/path/to/huaweicup2026
PREP="$PROJECT_ROOT/results/a/p1-r5-phase-colab-20260925/preflight"
RUNTIME="$PROJECT_ROOT/results/a/p1-r5-phase-colab-20260925/runtime-<unique-id>"
mkdir "$RUNTIME"
cp "$PREP/controller.py" "$PREP/controller_draft.py" "$PREP/remote_setup.py" \
  "$PREP/r5-source-bundle.tar.gz" "$PREP/bundle-manifest.json" "$PREP/artifact-manifest.json" "$RUNTIME/"
cd "$RUNTIME"
"$PROJECT_ROOT/.venv/bin/python" -B controller.py --execute \
  --cli "$HOME/.local/bin/colab" \
  --artifact-manifest-sha256 3ff23e7c05b6f80eb8318f58930be7026d18b296a3fb5185fac50b30f1ddda71
```

Use the project locked Python environment (`.venv` from `uv sync --locked`). The frozen budget is 53 Task compilations in one compiler pass, at most two Fraction calls with a 30 second limit each, one CPU worker, 180 seconds for the runner, and a 570 second monotonic lease within a 600 second VM cutoff. Retries and E0/E1/E2 calls are zero.
