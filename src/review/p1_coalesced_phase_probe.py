"""Research entry point for the coalesced real-reserve control pair.

Uses the R5 runner's private-chain, plan-validation, full-MEM compilation,
single-pass Task reuse and two bounded response guards. No E0 is called.
The explicit period/work parameters remain current-input hypotheses, not
case-ID routing or fitted historic answers.
"""
from src.review import p1_real_work_phase_probe as probe


def main():
    probe.PROPOSAL = probe.ROOT / 'src/review/p1_coalesced_phase_plan.py'
    probe.main()


if __name__ == '__main__':
    main()
