import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session")
def faers():
    recs = []
    for f in sorted((ROOT / "data/raw").glob("faers*.json")):
        recs += json.load(open(f))["results"]
    if not recs:
        pytest.skip("no FAERS sample under data/raw; run `make fetch`")
    return recs


@pytest.fixture(scope="session")
def coder():
    from dayzero.coding import Coder
    return Coder(terms=["Nausea", "Myocardial infarction", "Dyspnoea", "Death", "Septic shock", "Leukaemia", "Rash", "Headache"])
