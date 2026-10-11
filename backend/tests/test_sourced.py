from datetime import date

from sourced.concepts import code_concept, convert, numbers_agree
from sourced.forms import FORMS, fill
from sourced.generate import build_world
from sourced.reader import OracleDocReader, extraction_to_facts, read_fhir_bundle
from sourced.schema import Document, Fact
from sourced.store import MemoryStore
from sourced.verifier import verify


def test_units_and_coding():
    assert round(convert(158, "lb", "kg", "weight"), 2) == 71.67
    assert round(convert(98.6, "F", "Cel", "temp"), 1) == 37.0
    assert convert(1.2, "mg/dL", "umol/L", "bili") > 20
    assert code_concept("Weight") == "weight" and code_concept("BP systolic") == "sbp" and code_concept("Alanine aminotransferase") == "alt"
    assert code_concept("Lisinopril", "medication") == "medication" and code_concept("purple elephant") is None
    assert numbers_agree("weight", 92.4, 92.9) and not numbers_agree("weight", 92.4, 112.4)


def test_fhir_reader_maps_observations_and_meds():
    bundle = {"entry": [
        {"resource": {"resourceType": "Patient", "id": "p1", "birthDate": "1960-05-04", "gender": "female"}},
        {"resource": {"resourceType": "Observation", "id": "o1", "code": {"coding": [{"code": "29463-7"}]}, "effectiveDateTime": "2026-09-01", "valueQuantity": {"value": 158, "unit": "lb"}}},
        {"resource": {"resourceType": "Observation", "id": "o2", "code": {"coding": [{"code": "85354-9"}]}, "effectiveDateTime": "2026-09-01",
                      "component": [{"code": {"coding": [{"code": "8480-6"}]}, "valueQuantity": {"value": 132, "unit": "mmHg"}}, {"code": {"coding": [{"code": "8462-4"}]}, "valueQuantity": {"value": 84, "unit": "mmHg"}}]}},
        {"resource": {"resourceType": "MedicationStatement", "id": "m1", "medicationCodeableConcept": {"text": "Lisinopril"}, "effectivePeriod": {"start": "2026-08-01"}, "dosage": [{"text": "10 mg daily"}]}},
    ]}
    facts = read_fhir_bundle(bundle, "p1", "Test EHR")
    by = {f.concept: f for f in facts}
    assert by["birth_date"].value_text == "1960-05-04" and by["sex"].value_text == "F"
    assert by["weight"].unit == "kg" and round(by["weight"].value_num, 1) == 71.7 and by["weight"].attrs["unit_as_written"] == "lb"
    assert by["sbp"].value_num == 132 and by["dbp"].value_num == 84 and by["sbp"].resource_ref == "Observation/o2"
    assert by["medication"].value_text == "Lisinopril" and by["medication"].attrs["dose"] == "10 mg daily"


def test_world_documents_read_with_located_quotes():
    w = build_world(seed=3, today=date(2026, 10, 11), n_doc_adults=6, n_children=2)
    reader = OracleDocReader(w["truth"]["doc_extractions"])
    assert w["documents"] and w["truth"]["planted"]
    located = total = 0
    for d in w["documents"]:
        doc = Document(id=d["id"], patient_id=d["patient_id"], source_org=d["source_org"], kind=d["kind"], received_at=d["received_at"], document_date=d["document_date"], text=d["text"], n_pages=d["n_pages"])
        facts, skipped = extraction_to_facts(doc, reader.read(doc), "oracle", 0.95)
        assert not skipped, skipped
        for f in facts:
            total += 1; located += f.span_start is not None
            assert f.page is not None and f.page <= d["n_pages"]
    assert located == total


def _fact(pid, concept, v, unit, when, org, quote=None, as_written=None):
    return Fact(patient_id=pid, concept=concept, display=concept, value_num=v, unit=unit, observed_at=when, source_org=org, document_id=None if org == "EHR" else "DOC-1",
                quote=quote, attrs={"as_written": as_written or str(v), "unit_as_written": unit}, extractor="test", confidence=0.95)


def test_filler_and_verifier_conflict_trap_and_gap():
    v = date(2026, 9, 10)
    facts = [
        _fact("p", "weight", 92.4, "kg", v, "EHR"), _fact("p", "weight", 112.4, "kg", v, "Riverside", quote="Weight 112.4 kg", as_written="112.4"),   # conflict
        _fact("p", "sbp", 132, "mmHg", v, "EHR"), _fact("p", "sbp", 132, "mmHg", v, "Riverside", quote="BP 132/84 mmHg", as_written="132"),           # agree
        _fact("p", "hr", 76, "/min", v, "EHR"),                                                                                                       # single source
        _fact("p", "temp", 36.8, "Cel", v, "Riverside", quote="Temp 98.2 F", as_written="98.2"),                                                      # gap, filled from the note
        _fact("p", "dbp", 400, "mmHg", v, "EHR"),                                                                                                     # implausible
    ]
    inst = verify(fill(MemoryStore(facts), "p", FORMS["vs_visit"], v), FORMS["vs_visit"])
    f = {x.key: x for x in inst.fields}
    assert f["weight"].verifier["verdict"] == "disagree" and f["weight"].alternatives
    assert f["sbp"].verifier["verdict"] == "agree"
    assert f["hr"].verifier["verdict"] == "single_source"
    assert f["temp"].value == 36.8 and f["temp"].receipt["document_id"] == "DOC-1"
    assert f["dbp"].verifier["verdict"] == "rule_fail"
    assert f["height"].verifier["verdict"] == "empty"
    assert inst.n_flagged == 2


def test_list_fields_union_sources_and_flag_dose_conflict():
    v = date(2026, 9, 10)
    facts = [
        Fact(patient_id="p", concept="medication", display="Medication", value_text="Aspirin", observed_at=date(2026, 1, 1), attrs={"dose": "81 mg", "start": "2026-01-01"}, source_org="EHR", extractor="fhir", confidence=1.0),
        Fact(patient_id="p", concept="medication", display="Medication", value_text="aspirin", observed_at=date(2026, 1, 1), attrs={"dose": "162 mg", "start": "2026-01-01"}, source_org="Pharmacy", document_id="DOC-2", extractor="oracle", confidence=0.95),
        Fact(patient_id="p", concept="medication", display="Medication", value_text="Lisinopril", observed_at=date(2026, 8, 1), attrs={"dose": "10 mg", "start": "2026-08-01"}, source_org="Pharmacy", document_id="DOC-2", extractor="oracle", confidence=0.95),
    ]
    inst = verify(fill(MemoryStore(facts), "p", FORMS["cm_log"], v), FORMS["cm_log"])
    rows = inst.fields[0].rows
    assert len(rows) == 2
    asp = next(r for r in rows if r["term"].lower() == "aspirin")
    assert asp["n_sources"] == 2 and asp["conflicts"]["dose"] == ["162 mg", "81 mg"]
    assert inst.fields[0].verifier["verdict"] == "disagree"
