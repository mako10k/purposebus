#!/usr/bin/env python3
"""R: Verify the September 30 release against its additive frozen contract."""

from pathlib import Path

import verify_v1_candidate as verifier


if __name__ == "__main__":
    verifier.CONTRACT_PATH = Path(__file__).resolve().parents[1] / "release/v1-20260930-contract.json"
    raise SystemExit(verifier.main())
