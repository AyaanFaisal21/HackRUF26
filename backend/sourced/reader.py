"""Readers turn sources into Facts with receipts.

read_fhir_bundle   structured: FHIR R4 resources -> facts, receipt = resource reference, confidence 1.0
OracleDocReader    documents: returns the answer key (offline demo and tests)
ModelDocReader     documents: the model reads the text (Anthropic or OpenAI key)
extraction_to_facts  codes labels, normalises units, locates every quote to a page and span"""
from __future__ import annotations

import re
from datetime import date, datetime

from .concepts import CONCEPTS, LOINC_TO_KEY, code_concept, convert, normalize_unit, parse_number
from .llm import provider
from .schema import DocExtraction, Document, Fact

SYSTEM = """You read one medical document (a lab report, clinic note, discharge summary, pharmacy list, immunization record, or a scan of one)
and list every clinical fact in it as structured records.

Rules:
- One record per measurement, lab result, medication, diagnosis, adverse event, allergy, vaccine dose, or demographic item.
- Copy values and units exactly as written. Do not convert units. Do not infer values that are not written.
- Every quote must be a verbatim substring of the document, 3 to 160 characters, that contains the value. The system locates it by exact match.
- Blood pressure written as 132/84 is two records: systolic 132 and diastolic 84, same quote.
- Dates in ISO 8601. If a date is only implied by the document date, use the document date.
- For medications fill dose, frequency, route, start_date, end_date, indication when written; otherwise null.
- Ignore boilerplate, headers, signatures, and anything about a different patient.
Return only the structured record."""

_DATE_FORMATS = ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%d %b %Y", "%d %B %Y", "%B %d, %Y", "%b %d, %Y", "%Y%m%d")


def parse_date(s: str | None) -> date | None:
    if not s:
        return None
    s = str(s).strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(s[:10] if fmt == "%Y-%m-%d" else s, fmt).date()
        except ValueError:
            continue
    return None


def locate(text: str, quote: str) -> tuple[int, int] | None:
    i = text.find(quote)
    if i < 0:
        i = text.lower().find(quote.lower())
    if i < 0:
        q = re.sub(r"\s+", r"\\s+", re.escape(quote.strip()))
        m = re.search(q, text, re.I)
        if m:
            return m.start(), m.end()
        return None
    return i, i + len(quote)


def page_of(text: str, offset: int) -> int:
    return text[:offset].count("\f") + 1


# ---------------------------------------------------------------- FHIR
def _q(r):
    vq = r.get("valueQuantity") or {}
    return vq.get("value"), vq.get("unit") or vq.get("code")


def _fact(patient_id, key, source_org, ref, observed, value_num=None, value_text=None, unit=None, attrs=None, end=None):
    c = CONCEPTS[key]
    return Fact(patient_id=patient_id, concept=key, display=c["display"], value_num=value_num, value_text=value_text, unit=unit or c.get("unit"),
                observed_at=observed, end_at=end, attrs=attrs or {}, source_org=source_org, resource_ref=ref, extractor="fhir", confidence=1.0)


def read_fhir_bundle(bundle: dict, patient_id: str, source_org: str) -> list[Fact]:
    facts: list[Fact] = []
    for e in bundle.get("entry", []):
        r = e.get("resource", {})
        rt, ref = r.get("resourceType"), f"{r.get('resourceType')}/{r.get('id')}"
        if rt == "Patient":
            bd = parse_date(r.get("birthDate"))
            recorded = parse_date(bundle.get("timestamp")) or date.today()
            if bd:
                facts.append(_fact(patient_id, "birth_date", source_org, ref, recorded, value_text=bd.isoformat()))
                g = {"male": "M", "female": "F"}.get(r.get("gender"))
                if g:
                    facts.append(_fact(patient_id, "sex", source_org, ref, recorded, value_text=g))
                for ext in r.get("extension", []):
                    if ext.get("url", "").endswith("race") and ext.get("valueString"):
                        facts.append(_fact(patient_id, "race", source_org, ref, recorded, value_text=ext["valueString"]))
        elif rt == "Observation":
            when = parse_date(r.get("effectiveDateTime") or r.get("issued"))
            codes = [c.get("code") for c in r.get("code", {}).get("coding", [])]
            key = next((LOINC_TO_KEY[c] for c in codes if c in LOINC_TO_KEY), None)
            if not when or not key:
                continue
            if key == "bp_panel":
                for comp in r.get("component", []):
                    ck = next((LOINC_TO_KEY[c.get("code")] for c in comp.get("code", {}).get("coding", []) if c.get("code") in LOINC_TO_KEY), None)
                    v, u = _q(comp)
                    if ck and v is not None:
                        facts.append(_fact(patient_id, ck, source_org, ref, when, value_num=float(v), unit=normalize_unit(u)))
                continue
            v, u = _q(r)
            if v is None:
                continue
            u = normalize_unit(u); canon = CONCEPTS[key].get("unit")
            cv = convert(float(v), u, canon, key)
            if cv is None:
                facts.append(_fact(patient_id, key, source_org, ref, when, value_num=float(v), unit=u, attrs={"as_written": v, "unit_as_written": u}))
            else:
                facts.append(_fact(patient_id, key, source_org, ref, when, value_num=round(cv, 3), unit=canon, attrs={"as_written": v, "unit_as_written": u}))
        elif rt in ("MedicationStatement", "MedicationRequest"):
            name = (r.get("medicationCodeableConcept") or {}).get("text")
            if not name:
                continue
            per = r.get("effectivePeriod") or {}
            start = parse_date(per.get("start")) or parse_date(r.get("dateAsserted") or r.get("authoredOn"))
            dosage = (r.get("dosage") or r.get("dosageInstruction") or [{}])[0]
            attrs = {"dose": dosage.get("text"), "start": start.isoformat() if start else None, "end": per.get("end"),
                     "indication": next((rc.get("text") for rc in r.get("reasonCode", [])), None)}
            facts.append(_fact(patient_id, "medication", source_org, ref, start or parse_date(bundle.get("timestamp")) or date.today(), value_text=name, attrs={k: v for k, v in attrs.items() if v}, end=parse_date(per.get("end"))))
        elif rt == "Condition":
            name = (r.get("code") or {}).get("text")
            onset = parse_date(r.get("onsetDateTime")) or parse_date(r.get("recordedDate"))
            if name and onset:
                facts.append(_fact(patient_id, "condition", source_org, ref, onset, value_text=name, attrs={"status": (r.get("clinicalStatus") or {}).get("text")}, end=parse_date(r.get("abatementDateTime"))))
        elif rt == "AllergyIntolerance":
            name = (r.get("code") or {}).get("text"); when = parse_date(r.get("recordedDate"))
            if name and when:
                facts.append(_fact(patient_id, "allergy", source_org, ref, when, value_text=name, attrs={"reaction": next((m.get("text") for rx in r.get("reaction", []) for m in rx.get("manifestation", [])), None)}))
        elif rt == "Immunization":
            name = (r.get("vaccineCode") or {}).get("text"); when = parse_date(r.get("occurrenceDateTime"))
            if name and when:
                dose = next((p.get("doseNumberPositiveInt") for p in r.get("protocolApplied", [])), None)
                facts.append(_fact(patient_id, "immunization", source_org, ref, when, value_text=name, attrs={"dose_number": dose} if dose else {}))
        elif rt == "AdverseEvent":
            name = (r.get("event") or {}).get("text"); when = parse_date(r.get("date") or r.get("detected"))
            if name and when:
                attrs = {"severity": (r.get("severity") or {}).get("text"), "serious": (r.get("seriousness") or {}).get("text") == "Serious", "outcome": (r.get("outcome") or {}).get("text"),
                         "end": next((ext.get("valueDate") for ext in r.get("extension", []) if ext.get("url", "").endswith("end")), None)}
                facts.append(_fact(patient_id, "adverse_event", source_org, ref, when, value_text=name, attrs={k: v for k, v in attrs.items() if v is not None}, end=parse_date(attrs.get("end"))))
    return facts


# ---------------------------------------------------------------- documents
class OracleDocReader:
    name = "oracle"

    def __init__(self, answer_key: dict):
        self.key = answer_key

    def read(self, doc: Document) -> DocExtraction:
        return DocExtraction.model_validate(self.key[doc.id])


class ModelDocReader:
    def __init__(self, llm=None):
        self.llm = llm or provider()
        if self.llm is None:
            raise SystemExit("no model key found: set ANTHROPIC_API_KEY or OPENAI_API_KEY in .env, or use --reader oracle")
        self.name = f"model:{self.llm.name}:{self.llm.model}"

    def read(self, doc: Document) -> DocExtraction:
        user = f"<document id=\"{doc.id}\" source=\"{doc.source_org}\" kind=\"{doc.kind}\" received=\"{doc.received_at.date()}\">\n{doc.text}\n</document>"
        return self.llm.parse(SYSTEM, user, DocExtraction)


def extraction_to_facts(doc: Document, ext: DocExtraction, extractor: str, base_confidence: float = 0.85) -> tuple[list[Fact], list[dict]]:
    """Returns (facts, skipped). A fact whose quote cannot be located keeps a lower confidence and no span."""
    facts, skipped = [], []
    doc_date = parse_date(ext.document_date) or doc.document_date or doc.received_at.date()
    for f in ext.facts:
        key = code_concept(f.concept_label, f.category)
        if key is None:
            skipped.append({"label": f.concept_label, "value": f.value, "reason": "uncoded"})
            continue
        c = CONCEPTS[key]
        loc = locate(doc.text, f.quote)
        conf = base_confidence + (0.1 if loc else -0.35)
        observed = parse_date(f.observed_date) or parse_date(f.start_date) or doc_date
        attrs = {k: v for k, v in dict(dose=f.dose, frequency=f.frequency, route=f.route, start=f.start_date, end=f.end_date, severity=f.severity, serious=f.serious, indication=f.indication).items() if v is not None}
        value_num = value_text = None
        unit = normalize_unit(f.unit)
        if c["vtype"] == "number":
            n = parse_number(f.value)
            if n is None:
                skipped.append({"label": f.concept_label, "value": f.value, "reason": "no number"})
                continue
            attrs.update({"as_written": f.value, "unit_as_written": unit})
            cv = convert(n, unit, c.get("unit"), key) if unit else n
            if cv is None:
                value_num, unit = n, unit
            else:
                value_num, unit = round(cv, 3), c.get("unit")
        elif c["vtype"] == "date":
            d = parse_date(f.value); value_text = d.isoformat() if d else f.value
        else:
            value_text = f.value.strip()
            if key == "sex":
                value_text = {"male": "M", "female": "F", "m": "M", "f": "F"}.get(value_text.lower(), value_text)
        facts.append(Fact(patient_id=doc.patient_id or "", concept=key, display=c["display"], value_num=value_num, value_text=value_text, unit=unit or c.get("unit"),
                          observed_at=observed, end_at=parse_date(f.end_date), attrs=attrs, source_org=doc.source_org, document_id=doc.id,
                          page=page_of(doc.text, loc[0]) if loc else None, span_start=loc[0] if loc else None, span_end=loc[1] if loc else None,
                          quote=f.quote, extractor=extractor, confidence=round(min(0.99, max(0.05, conf)), 2)))
    return facts, skipped
