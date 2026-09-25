# Coalesced phase controller preparation

Static preparation only. Frozen source commit `77977e3000904a47013458e666fee1ecddefb5de`; input graph SHA-256 `c93bb7ab5deec5112aff0cc001fbd76d001d3de5ea7463fba59b1f1ff2ba3e1d`. The bundle is assembled from that commit and the tracked prior transfer's verified graph bytes.

Artifact-manifest SHA-256 pin: `06246bfb5de5af360d374dfaf765d3454decd346a2b53f923e960b38c0fe3dc4`. Run only after explicit coordinator admission. Copy the six pinned runtime files to a new empty runtime directory; do not execute from this tracked `preflight` directory (single-use receipts).

```sh
PROJECT_ROOT=/path/to/huaweicup2026
PREP="$PROJECT_ROOT/results/a/p1-coalesced-phase-colab-20260925/preflight"
RUNTIME="$PROJECT_ROOT/results/a/p1-coalesced-phase-colab-20260925/runtime-<unique-id>"
mkdir "$RUNTIME"
cp "$PREP/controller.py" "$PREP/controller_draft.py" "$PREP/remote_setup.py" \
  "$PREP/coalesced-source-bundle.tar.gz" "$PREP/bundle-manifest.json" "$PREP/artifact-manifest.json" "$RUNTIME/"
cd "$RUNTIME"
"$PROJECT_ROOT/.venv/bin/python" -B controller.py --execute \
  --cli "$HOME/.local/bin/colab" \
  --artifact-manifest-sha256 06246bfb5de5af360d374dfaf765d3454decd346a2b53f923e960b38c0fe3dc4
```

Use the project locked Python environment from `uv sync --locked`. Frozen limits: one CPU worker; at most 27 Task compiles in one pass; two Fraction calls, each limited to 30s; 180s runner cutoff; 570s host-monotonic lease; 600s VM cutoff; zero retries and zero E0/E1/E2 calls.
