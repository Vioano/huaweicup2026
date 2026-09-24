"""Fixed band-DP plus one-leaf lookahead candidate; no candidate sweep."""
from __future__ import annotations

from .forest_band_dp import construct as construct_band
from .leaf_lookahead import transform as leaf_lookahead


def construct(index, cores):
    """Build exactly one pair-cache band owner/order and apply one leaf shift."""
    band_plan, band_metadata = construct_band(
        index, cores, order_mode='pair_cache_model')
    plan, lookahead_metadata = leaf_lookahead(index, band_plan)
    metadata = {
        'strategy': 'band_pair_one_leaf_lookahead',
        'band_dp': band_metadata,
        'leaf_lookahead': lookahead_metadata,
        'official_evaluations': 0,
        'scope': 'fixed composition only; mechanism candidate, not full-500 evidence',
    }
    return plan, metadata
