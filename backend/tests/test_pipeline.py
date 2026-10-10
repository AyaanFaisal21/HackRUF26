from dayzero.coding import Coder
from dayzero.dedupe import structured_score
from dayzero.embed import HashEmbedder, cosine
from dayzero.evaluate import evaluate
from dayzero.extract import OracleExtractor
from dayzero.generate import build_inbox, build_mock_data
from dayzero.pipeline import MemoryStore, Pipeline
from dayzero.schema import Message


def test_coder_synonyms_and_fuzzy(coder):
    assert coder.code("heart attack") == ("Myocardial infarction", 100.0)
    assert coder.code("nausea")[0] == "Nausea"
    assert coder.code("Myocardial Infarct")[0] == "Myocardial infarction"
    assert coder.code("purple elephant")[0] is None


def test_hash_embedder_is_unit_and_similar_for_similar_text():
    e = HashEmbedder()
    a, b, c = e.embed("patient on venclexta developed septic shock"), e.embed("the patient taking venclexta got septic shock"), e.embed("quarterly budget review meeting")
    assert abs(cosine(a, a) - 1) < 1e-6 and cosine(a, b) > cosine(a, c)


def test_offline_inbox_end_to_end(faers):
    meddra, rsi = build_mock_data(faers)
    msgs, key = build_inbox(faers, n=40, seed=3)
    assert msgs and all(key[m["id"]]["extraction"]["patient"]["identifiable"] in (True, False) for m in msgs)
    store = MemoryStore()
    pipe = Pipeline(store, OracleExtractor(key), HashEmbedder(), Coder(terms=meddra["terms"]), rsi["rsi"])
    pipe.process_many([Message.model_validate(m) for m in msgs])
    m = evaluate(store, key, Coder(terms=meddra["terms"]))
    assert m["validity_accuracy"] == 1.0, m
    assert m["day_zero_accuracy"] == 1.0, m
    assert m["followup_attachment"]["correct"] == m["followup_attachment"]["total"], m
    if m["duplicates"]["planted"]:
        assert m["duplicates"]["recall"] >= 0.8, m
    # every evidence quote the oracle supplies must be locatable in the body (the UI highlights by offset)
    for mid, (msg, _, ext) in store.messages.items():
        for ev in ext.patient.evidence + ext.reporter.evidence + ext.seriousness.evidence:
            assert ev.start is not None, (mid, ev.quote)


def test_structured_score_separates_planted_duplicates(faers):
    msgs, key = build_inbox(faers, n=60, seed=5)
    store = MemoryStore()
    Pipeline(store, OracleExtractor(key), HashEmbedder(), Coder(terms=[]), {}).process_many([Message.model_validate(m) for m in msgs])
    pairs = [(store.msg_case[mid], store.msg_case[k["duplicate_of"]]) for mid, k in key.items() if k["duplicate_of"]]
    for a, b in pairs:
        assert structured_score(store.cases[a].state, store.cases[b].state)[0] >= 0.6
