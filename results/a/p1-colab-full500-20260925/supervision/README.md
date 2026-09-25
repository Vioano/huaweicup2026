# Frozen Colab full500 supervision

This dedicated CPU batch runs solver `3a1b82b71ca1ff6689eb8e72f17d26c48b52073c` at runtime checkout `bd6dc85a0b69f30d08714cbb46200f90632bb2d7`, one worker, 100 cases × 1–5 cores, with a new official E0 for every successful cell. Frozen call/time/memory ceilings are in `frozen-manifest.json`.

`supervisor.py` was reviewed by the root agent after Sol implementation. It uses Linux subreaper ownership and process birth identities to sample and clean up its descendants. A terminal receipt records observed resource samples, dispatch counts, and uncertain cleanup; uncertainty requires stopping the dedicated VM externally. Sample maxima are not continuous true peaks. No local duplicate batch is authorized.

The supervisor launched at 2026-09-25T01:11:23.725815Z; batch T0 and terminal state must be read from actual receipts. These files freeze the procedure, not a claim that all 500 cells completed. Accepted full500 quality remains v4 until the new results are downloaded, independently checked and admitted.
