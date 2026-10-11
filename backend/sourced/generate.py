"""Synthetic two-clinic world with an answer key.

Clinic A, "Memorial General" (EHR, FHIR R4): built from the CDISC pilot subjects, labs, vitals, events, medications.
Clinic B, "Riverside" (documents): lab reports, clinic notes, pharmacy faxes generated from the same truth, with planted
gaps (a value that exists only in a document), unit traps (pounds, Fahrenheit) and conflicts (a wrong value).
Ten children at "Sunrise Pediatrics" (FHIR) and "County Urgent Care" (documents) with split immunization records.
Every document's facts and quotes are the answer key. No real people."""
from __future__ import annotations

import hashlib
import json
import random
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from .concepts import CDISC_TO_KEY, CONCEPTS

ROOT = Path(__file__).resolve().parents[2]
EHR_ORG, DOC_ORG, LAB_ORG = "Memorial General Hospital", "Riverside Clinic", "Riverside Diagnostics"
PED_ORG, PED_DOC_ORG = "Sunrise Pediatrics", "County Urgent Care"
FIRST = ["Maria", "James", "Priya", "Wei", "Ahmed", "Elena", "Tom", "Grace", "Luis", "Hana", "Olu", "Sofia", "Daniel", "Amara", "Noah", "Leila", "Ivan", "Rosa"]
LAST = ["Okafor", "Nguyen", "Patel", "Lee", "Garcia", "Schmidt", "Rossi", "Khan", "Brown", "Silva", "Haddad", "Novak", "Reyes", "Kim", "Murphy", "Adeyemi"]
VACCINES = [("Hepatitis B", 0), ("DTaP", 60), ("Hib", 60), ("IPV", 60), ("PCV13", 60), ("MMR", 365), ("Varicella", 365), ("Hepatitis A", 400), ("DTaP", 1500), ("Influenza", 2500)]
NEW_MEDS = [("Lisinopril", "10 mg", "daily", "ORAL", "hypertension"), ("Metformin", "500 mg", "twice daily", "ORAL", "type 2 diabetes"), ("Atorvastatin", "20 mg", "nightly", "ORAL", "hyperlipidemia"),
            ("Amoxicillin", "500 mg", "three times daily", "ORAL", "sinusitis"), ("Omeprazole", "20 mg", "daily", "ORAL", "reflux")]
CONDITIONS = ["Hypertension", "Type 2 diabetes mellitus", "Osteoarthritis", "Hyperlipidemia", "Gastroesophageal reflux", "Chronic kidney disease stage 2"]


def _fmt(d: date, rng: random.Random) -> str:
    return rng.choice([d.strftime("%m/%d/%Y"), d.isoformat(), d.strftime("%d %b %Y"), d.strftime("%B %d, %Y")])


def _kg_to_lb(kg: float) -> float:
    return round(kg / 0.45359237, 1)


def _c_to_f(c: float) -> float:
    return round(c * 1.8 + 32, 1)


class Builder:
    def __init__(self, trial: dict, seed: int = 7, today: date | None = None, n_doc_adults: int = 80, n_children: int = 10):
        self.rng = random.Random(seed)
        self.trial = trial
        self.today = today or date.today()
        self.n_doc_adults, self.n_children = n_doc_adults, n_children
        self.patients, self.identifiers, self.documents, self.bundles = [], [], [], {}
        self.truth = {"doc_extractions": {}, "planted": [], "visit_truth": {}, "children": []}

    # ------------------------------------------------------------ helpers
    def _doc(self, patient_id, org, kind, doc_date: date, text: str, facts: list[dict], received_offset_days=1):
        did = f"DOC-{len(self.documents) + 1:04d}"
        received = datetime.combine(doc_date + timedelta(days=received_offset_days), datetime.min.time(), tzinfo=timezone.utc) + timedelta(hours=self.rng.randint(8, 17))
        self.documents.append({"id": did, "patient_id": patient_id, "source_org": org, "kind": kind, "received_at": received.isoformat(), "document_date": doc_date.isoformat(),
                               "text": text, "n_pages": text.count("\f") + 1, "sha256": hashlib.sha256(text.encode()).hexdigest()})
        for f in facts:
            assert f["quote"] in text, (did, f["quote"])
        self.truth["doc_extractions"][did] = {"document_kind": kind, "document_date": doc_date.isoformat(), "patient_name": None, "patient_identifiers": [], "facts": [
            {"concept_label": f["label"], "category": f["category"], "value": f["value"], "unit": f.get("unit"), "observed_date": f.get("date", doc_date.isoformat()), "quote": f["quote"],
             "dose": f.get("dose"), "frequency": f.get("frequency"), "route": f.get("route"), "start_date": f.get("start"), "end_date": f.get("end"), "severity": f.get("severity"), "serious": f.get("serious"), "indication": f.get("indication")} for f in facts]}
        return did

    def _plant(self, **kw):
        self.truth["planted"].append(kw)

    # ------------------------------------------------------------ adults
    def build_adults(self):
        rng, t = self.rng, self.trial
        first_day = self.today - timedelta(days=240)
        by_lab, by_vs, by_ae, by_cm = defaultdict(list), defaultdict(list), defaultdict(list), defaultdict(list)
        seen_rows = set()
        for r in t["labs"]:
            k = (r["subject"], r["test"], r["day"])
            if k not in seen_rows:
                seen_rows.add(k); by_lab[r["subject"]].append(r)
        for r in t["vitals"]:
            k = (r["subject"], r["test"], r["day"])
            if k not in seen_rows:
                seen_rows.add(k); by_vs[r["subject"]].append(r)
        for r in t["events"]: by_ae[r["subject"]].append(r)
        seen = set()
        for r in t["medications"]:
            k = (r["subject"], r["name"], r.get("dose"), r.get("start_day"))
            if k not in seen:
                seen.add(k); by_cm[r["subject"]].append(r)
        subjects = t["subjects"]
        doc_subjects = set(s["id"] for s in rng.sample(subjects, min(self.n_doc_adults, len(subjects))))
        for s in subjects:
            pid = s["id"]
            ref = first_day + timedelta(days=rng.randint(0, 150))
            d2 = lambda day: ref + timedelta(days=day - 1)
            name = f"{rng.choice(FIRST)} {rng.choice(LAST)}"
            birth = ref - timedelta(days=s["age"] * 365 + rng.randint(0, 364))
            self.patients.append({"id": pid, "display_name": name, "birth_date": birth.isoformat(), "sex": s["sex"], "race": s.get("race"), "kind": "adult", "trial_id": t["trial"]["id"], "site": s["site"], "ref_date": ref.isoformat()})
            mrn = f"MG-{rng.randint(100000, 999999)}"
            self.identifiers.append({"patient_id": pid, "org": EHR_ORG, "local_id": mrn})
            # truth per visit (before any gap is removed)
            vt = defaultdict(dict)
            for r in by_vs[pid]:
                if r["day"] <= self.today.toordinal() - ref.toordinal() + 1:
                    vt[d2(r["day"]).isoformat()][CDISC_TO_KEY[r["test"]]] = r["value"]
            for r in by_lab[pid]:
                if r["day"] <= self.today.toordinal() - ref.toordinal() + 1:
                    vt[d2(r["day"]).isoformat()][CDISC_TO_KEY[r["test"]]] = r["value"]
            self.truth["visit_truth"][pid] = dict(vt)
            # FHIR bundle
            entries = [{"resource": {"resourceType": "Patient", "id": pid, "identifier": [{"system": "urn:memorial-general:mrn", "value": mrn}], "name": [{"text": name}],
                                     "gender": {"M": "male", "F": "female"}.get(s["sex"], "unknown"), "birthDate": birth.isoformat(),
                                     "extension": [{"url": "http://example.org/fhir/StructureDefinition/race", "valueString": s.get("race")}]}}]
            cutoff = self.today
            gap_weight_day = gap_lab_day = None
            if pid in doc_subjects:
                wdays = [r["day"] for r in by_vs[pid] if r["test"] == "WEIGHT" and r["day"] > 1 and d2(r["day"]) <= cutoff]
                ldays = sorted({r["day"] for r in by_lab[pid] if r["day"] > 1 and d2(r["day"]) <= cutoff})
                if wdays and rng.random() < 0.5:
                    gap_weight_day = rng.choice(wdays)
                if ldays and rng.random() < 0.5:
                    gap_lab_day = rng.choice(ldays)
            n = 0
            for r in by_vs[pid]:
                when = d2(r["day"])
                if when > cutoff or (r["test"] == "WEIGHT" and r["day"] == gap_weight_day):
                    continue
                n += 1
                key = CDISC_TO_KEY[r["test"]]
                unit = {"mmHg": "mmHg", "BEATS/MIN": "/min", "C": "Cel", "kg": "kg", "cm": "cm"}.get(r["unit"], r["unit"])
                entries.append({"resource": {"resourceType": "Observation", "id": f"{pid}-vs-{n}", "status": "final", "code": {"coding": [{"system": "http://loinc.org", "code": CONCEPTS[key]["code"], "display": CONCEPTS[key]["display"]}]},
                                             "subject": {"reference": f"Patient/{pid}"}, "effectiveDateTime": when.isoformat(), "valueQuantity": {"value": r["value"], "unit": unit}}})
            for r in by_lab[pid]:
                when = d2(r["day"])
                if when > cutoff or r["day"] == gap_lab_day:
                    continue
                n += 1
                key = CDISC_TO_KEY[r["test"]]
                entries.append({"resource": {"resourceType": "Observation", "id": f"{pid}-lb-{n}", "status": "final", "code": {"coding": [{"system": "http://loinc.org", "code": CONCEPTS[key]["code"], "display": CONCEPTS[key]["display"]}]},
                                             "subject": {"reference": f"Patient/{pid}"}, "effectiveDateTime": when.isoformat(), "valueQuantity": {"value": r["value"], "unit": r["unit"]},
                                             "referenceRange": [{"low": {"value": r["lln"]}, "high": {"value": r["uln"]}}] if r.get("uln") else []}})
            for i, r in enumerate(by_cm[pid]):
                start = d2(r["start_day"]) if r.get("start_day") else None
                if start and start > cutoff:
                    continue
                dose = " ".join(str(x) for x in (r.get("dose"), r.get("dose_unit"), r.get("frequency")) if x)
                entries.append({"resource": {"resourceType": "MedicationStatement", "id": f"{pid}-cm-{i}", "status": "active", "medicationCodeableConcept": {"text": r["name"]}, "subject": {"reference": f"Patient/{pid}"},
                                             "effectivePeriod": {k: v for k, v in {"start": start.isoformat() if start else None, "end": d2(r["end_day"]).isoformat() if r.get("end_day") else None}.items() if v},
                                             "dateAsserted": (start or ref).isoformat(), "dosage": [{"text": dose}] if dose else [], "reasonCode": [{"text": r["indication"]}] if r.get("indication") else []}})
            for i, r in enumerate(by_ae[pid]):
                if not r.get("start_day") or d2(r["start_day"]) > cutoff:
                    continue
                entries.append({"resource": {"resourceType": "AdverseEvent", "id": f"{pid}-ae-{i}", "actuality": "actual", "event": {"text": (r.get("pt") or r["term"]).title()}, "subject": {"reference": f"Patient/{pid}"},
                                             "date": d2(r["start_day"]).isoformat(), "severity": {"text": r.get("severity")}, "seriousness": {"text": "Serious" if r.get("serious") else "Non-serious"},
                                             "extension": [{"url": "http://example.org/fhir/StructureDefinition/end", "valueDate": d2(r["end_day"]).isoformat()}] if r.get("end_day") else []}})
            self.bundles[pid] = {"resourceType": "Bundle", "type": "collection", "timestamp": self.today.isoformat(), "entry": entries}
            if pid in doc_subjects:
                self._adult_documents(pid, name, birth, s, ref, by_vs[pid], by_lab[pid], by_cm[pid], gap_weight_day, gap_lab_day, cutoff)

    def _adult_documents(self, pid, name, birth, s, ref, vs, lb, cm, gap_weight_day, gap_lab_day, cutoff):
        rng = self.rng
        d2 = lambda day: ref + timedelta(days=day - 1)
        rmrn = f"RC-{rng.randint(10000, 99999)}"
        self.identifiers.append({"patient_id": pid, "org": DOC_ORG, "local_id": rmrn})
        # 1. central lab report for the gap visit (or any lab visit)
        ldays = sorted({r["day"] for r in lb if r["day"] > 1 and d2(r["day"]) <= cutoff})
        if ldays:
            day = gap_lab_day or rng.choice(ldays)
            when = d2(day)
            rows = [r for r in lb if r["day"] == day]
            lines, facts = [], []
            for r in rows:
                key = CDISC_TO_KEY[r["test"]]
                label = {"alt": "ALT", "ast": "AST", "bili": "Bilirubin, total", "alp": "Alkaline phosphatase", "creat": "Creatinine", "hgb": "Hemoglobin", "wbc": "WBC", "plat": "Platelets", "glucose": "Glucose"}[key]
                line = f"{label:<24}{r['value']:>8g}  {r['unit']:<8}  ({r.get('lln') or ''}-{r.get('uln') or ''})"
                lines.append(line); facts.append({"label": label, "category": "lab", "value": f"{r['value']:g}", "unit": r["unit"], "date": when.isoformat(), "quote": line.strip()})
            text = (f"{LAB_ORG.upper()}\n1200 River Road, New Brunswick NJ 08901\n\nLABORATORY REPORT\nPatient: {name}    DOB: {birth.strftime('%m/%d/%Y')}    MRN: {rmrn}\n"
                    f"Collected: {_fmt(when, rng)}    Reported: {_fmt(when + timedelta(days=1), rng)}    Ordering: Dr. {rng.choice(LAST)}\n\n"
                    f"{'TEST':<24}{'RESULT':>8}  {'UNITS':<8}  REFERENCE\n" + "\n".join(lines) + "\n\nH = above reference range, L = below. Results verified by automated analyzer.\nPage 1 of 1")
            self._doc(pid, LAB_ORG, "lab_report", when, text, facts)
            if gap_lab_day:
                self._plant(kind="gap_fill", patient_id=pid, concept="lab_panel", visit=when.isoformat(), note="lab panel exists only in the outside lab report")
        # 2. clinic note at a vitals visit (prefer the weight gap visit)
        vdays = sorted({r["day"] for r in vs if r["day"] > 1 and d2(r["day"]) <= cutoff})
        if vdays:
            day = gap_weight_day or rng.choice(vdays)
            when = d2(day)
            at = {CDISC_TO_KEY[r["test"]]: r["value"] for r in vs if r["day"] == day}
            facts, parts = [], []
            if "sbp" in at and "dbp" in at:
                q = f"BP {at['sbp']:g}/{at['dbp']:g} mmHg"; parts.append(q)
                facts += [{"label": "systolic blood pressure", "category": "vital", "value": f"{at['sbp']:g}", "unit": "mmHg", "quote": q}, {"label": "diastolic blood pressure", "category": "vital", "value": f"{at['dbp']:g}", "unit": "mmHg", "quote": q}]
            if "hr" in at:
                q = f"HR {at['hr']:g} bpm"; parts.append(q); facts.append({"label": "heart rate", "category": "vital", "value": f"{at['hr']:g}", "unit": "bpm", "quote": q})
            if "temp" in at:
                if rng.random() < 0.5:
                    q = f"Temp {_c_to_f(at['temp'])} F"; facts.append({"label": "temperature", "category": "vital", "value": f"{_c_to_f(at['temp'])}", "unit": "F", "quote": q})
                else:
                    q = f"Temp {at['temp']:g} C"; facts.append({"label": "temperature", "category": "vital", "value": f"{at['temp']:g}", "unit": "C", "quote": q})
                parts.append(q)
            if "weight" in at:
                w = at["weight"]; roll = rng.random()
                if gap_weight_day == day and roll < 0.25:
                    roll = 0.9    # the note is the only source at a gap visit, so it must carry the true value
                if roll < 0.25:   # conflict: wrong value in the note
                    w2 = round(w + rng.choice([-20, 20, 10, -10]), 1); q = f"Weight {w2:g} kg"
                    facts.append({"label": "weight", "category": "vital", "value": f"{w2:g}", "unit": "kg", "quote": q})
                    self._plant(kind="conflict", patient_id=pid, concept="weight", visit=when.isoformat(), doc_value=w2, truth_value=w, note="clinic note weight disagrees with the EHR")
                elif roll < 0.55:  # unit trap: pounds
                    lb_ = _kg_to_lb(w); q = f"Weight {lb_:g} lb"
                    facts.append({"label": "weight", "category": "vital", "value": f"{lb_:g}", "unit": "lb", "quote": q})
                    self._plant(kind="unit_trap", patient_id=pid, concept="weight", visit=when.isoformat(), doc_value=f"{lb_} lb", truth_value=w, note="weight written in pounds")
                else:
                    q = f"Weight {w:g} kg"; facts.append({"label": "weight", "category": "vital", "value": f"{w:g}", "unit": "kg", "quote": q})
                parts.append(q)
                if gap_weight_day:
                    self._plant(kind="gap_fill", patient_id=pid, concept="weight", visit=when.isoformat(), note="weight exists only in the clinic note")
            med_line = cond_line = ""
            if rng.random() < 0.45:
                m = rng.choice(NEW_MEDS); start = when - timedelta(days=rng.randint(3, 40))
                med_line = f"Started {m[0]} {m[1]} PO {m[2]} on {start.strftime('%m/%d/%Y')} for {m[4]}."
                facts.append({"label": m[0], "category": "medication", "value": m[0], "unit": None, "quote": med_line, "dose": m[1], "frequency": m[2], "route": m[3], "start": start.isoformat(), "indication": m[4], "date": start.isoformat()})
                self._plant(kind="gap_fill", patient_id=pid, concept="medication", visit=when.isoformat(), doc_value=m[0], note="medication exists only in the clinic note")
            if rng.random() < 0.35:
                c = rng.choice(CONDITIONS); cond_line = f"Assessment: {c}, stable."
                facts.append({"label": c, "category": "condition", "value": c, "unit": None, "quote": cond_line, "date": when.isoformat()})
            page1 = (f"{DOC_ORG.upper()} - PROGRESS NOTE\n{'FAX RECEIVED ' + (when + timedelta(days=1)).strftime('%m/%d/%Y %H:%M') + ' FROM 732-555-0199  P.1/2' if rng.random() < 0.5 else ''}\n"
                     f"Patient: {name}   DOB {birth.strftime('%m/%d/%Y')}   MRN {rmrn}\nDate of visit: {_fmt(when, rng)}\n\n"
                     f"S: Patient presents for follow-up. {rng.choice(['Reports feeling well.', 'Mild fatigue over the past week.', 'No new complaints.', 'Sleeping poorly.'])}\n"
                     f"O: Vitals: {', '.join(parts)}. {rng.choice(['Lungs clear.', 'Heart regular rate and rhythm.', 'No edema.'])}\n")
            page2 = f"\fA/P:\n{cond_line}\n{med_line}\n{rng.choice(['Return in 4 weeks.', 'Labs ordered.', 'Continue current regimen.'])}\n\nElectronically signed, Dr. {rng.choice(FIRST)} {rng.choice(LAST)}, MD\nPage 2 of 2"
            self._doc(pid, DOC_ORG, "clinic_note", when, page1 + page2, facts)
        # 3. pharmacy medication list fax
        if cm and rng.random() < 0.5:
            when = ref + timedelta(days=rng.randint(10, max(11, (cutoff - ref).days)))
            lines, facts = [], []
            for r in cm[:6]:
                dose = f"{r['dose']:g} {r['dose_unit']}" if r.get("dose") and r.get("dose_unit") else ""
                if dose and rng.random() < 0.2:
                    wrong = f"{r['dose'] * 2:g} {r['dose_unit']}"
                    self._plant(kind="conflict", patient_id=pid, concept="medication", visit=when.isoformat(), doc_value=f"{r['name']} {wrong}", truth_value=f"{r['name']} {dose}", note="pharmacy list dose differs from the EHR")
                    dose = wrong
                start = d2(r["start_day"]).strftime("%m/%d/%Y") if r.get("start_day") else "on file"
                line = f"{r['name']:<22}{dose:<14}{(r.get('frequency') or ''):<10}{(r.get('route') or ''):<8}started {start}"
                lines.append(line)
                facts.append({"label": r["name"], "category": "medication", "value": r["name"], "unit": None, "quote": line.strip(), "dose": dose or None, "frequency": r.get("frequency"), "route": r.get("route"),
                              "start": d2(r["start_day"]).isoformat() if r.get("start_day") else None, "date": d2(r["start_day"]).isoformat() if r.get("start_day") else when.isoformat()})
            text = (f"FAX  {when.strftime('%m/%d/%Y')} 09:{rng.randint(10, 59)}  FROM RIVERSIDE PHARMACY 732-555-0142  P.1/1\n\nMEDICATION LIST - {name}   DOB {birth.strftime('%m/%d/%Y')}   MRN {rmrn}\nAs of {_fmt(when, rng)}\n\n"
                    + "\n".join(lines) + "\n\nQuestions: call the pharmacy. This list reflects dispensed prescriptions only.")
            self._doc(pid, DOC_ORG, "pharmacy_list", when, text, facts)

    # ------------------------------------------------------------ children
    def build_children(self):
        rng = self.rng
        for i in range(self.n_children):
            pid = f"PED-{i + 1:03d}"
            age_days = rng.randint(5 * 365, 12 * 365)
            birth = self.today - timedelta(days=age_days)
            name = f"{rng.choice(FIRST)} {rng.choice(LAST)}"; sex = rng.choice(["M", "F"])
            self.patients.append({"id": pid, "display_name": name, "birth_date": birth.isoformat(), "sex": sex, "race": None, "kind": "child", "trial_id": None, "site": None, "ref_date": None})
            mrn = f"SP-{rng.randint(1000, 9999)}"; umrn = f"UC-{rng.randint(10000, 99999)}"
            self.identifiers += [{"patient_id": pid, "org": PED_ORG, "local_id": mrn}, {"patient_id": pid, "org": PED_DOC_ORG, "local_id": umrn}]
            years = age_days / 365
            height = round(75 + years * 6.2 + rng.uniform(-6, 6), 1); weight = round(9 + years * 2.6 + rng.uniform(-3, 3), 1)
            v1 = self.today - timedelta(days=rng.randint(60, 300)); v0 = v1 - timedelta(days=365)
            entries = [{"resource": {"resourceType": "Patient", "id": pid, "identifier": [{"system": "urn:sunrise:mrn", "value": mrn}], "name": [{"text": name}], "gender": {"M": "male", "F": "female"}[sex], "birthDate": birth.isoformat()}}]
            for j, (when, h, w) in enumerate(((v0, height - 6, weight - 2.5), (v1, height, weight))):
                for key, val, unit in (("height", h, "cm"), ("weight", w, "kg"), ("sbp", rng.randint(92, 112), "mmHg"), ("dbp", rng.randint(55, 72), "mmHg")):
                    entries.append({"resource": {"resourceType": "Observation", "id": f"{pid}-{key}-{j}", "status": "final", "code": {"coding": [{"system": "http://loinc.org", "code": CONCEPTS[key]["code"]}]},
                                                 "subject": {"reference": f"Patient/{pid}"}, "effectiveDateTime": when.isoformat(), "valueQuantity": {"value": val, "unit": unit}}})
            given = [(v, birth + timedelta(days=off + rng.randint(0, 20))) for v, off in VACCINES if birth + timedelta(days=off) <= self.today]
            rng.shuffle(given)
            half = len(given) // 2
            ehr_vax, doc_vax = given[:half], given[half:]
            for j, (v, when) in enumerate(ehr_vax):
                entries.append({"resource": {"resourceType": "Immunization", "id": f"{pid}-imm-{j}", "status": "completed", "vaccineCode": {"text": v}, "patient": {"reference": f"Patient/{pid}"}, "occurrenceDateTime": when.isoformat()}})
            allergy = rng.choice([None, None, "Penicillin", "Peanut", "Amoxicillin"])
            if allergy:
                entries.append({"resource": {"resourceType": "AllergyIntolerance", "id": f"{pid}-al", "code": {"text": allergy}, "patient": {"reference": f"Patient/{pid}"}, "recordedDate": (birth + timedelta(days=rng.randint(400, 2000))).isoformat(), "reaction": [{"manifestation": [{"text": rng.choice(["hives", "rash", "swelling"])}]}]}})
            asthma = rng.random() < 0.3
            if asthma:
                onset = birth + timedelta(days=rng.randint(700, 2500))
                entries.append({"resource": {"resourceType": "Condition", "id": f"{pid}-cond", "code": {"text": "Asthma"}, "subject": {"reference": f"Patient/{pid}"}, "onsetDateTime": onset.isoformat(), "clinicalStatus": {"text": "active"}}})
                entries.append({"resource": {"resourceType": "MedicationStatement", "id": f"{pid}-med", "status": "active", "medicationCodeableConcept": {"text": "Albuterol inhaler"}, "subject": {"reference": f"Patient/{pid}"}, "effectivePeriod": {"start": onset.isoformat()}, "dosage": [{"text": "2 puffs every 4 to 6 hours as needed"}], "reasonCode": [{"text": "Asthma"}]}})
            self.bundles[pid] = {"resourceType": "Bundle", "type": "collection", "timestamp": self.today.isoformat(), "entry": entries}
            self.truth["children"].append({"patient_id": pid, "immunizations_total": len(given), "in_ehr": len(ehr_vax), "in_document": len(doc_vax), "allergy": allergy, "asthma": asthma, "height": height, "weight": weight})
            # documents from the urgent care: immunization card scan and a visit note
            card_lines = [f"{v:<16}{when.strftime('%m/%d/%Y')}" for v, when in sorted(doc_vax, key=lambda x: x[1])]
            facts = [{"label": v, "category": "immunization", "value": v, "unit": None, "date": when.isoformat(), "quote": f"{v:<16}{when.strftime('%m/%d/%Y')}".strip()} for v, when in doc_vax]
            card = (f"{PED_DOC_ORG.upper()}\nIMMUNIZATION RECORD (copy of card on file)\nChild: {name}   DOB: {birth.strftime('%m/%d/%Y')}   Record #: {umrn}\n\nVACCINE         DATE GIVEN\n" + "\n".join(card_lines)
                    + "\n\n[scanned copy - lower section illegible]\nPage 1 of 1")
            self._doc(pid, PED_DOC_ORG, "immunization_record", self.today - timedelta(days=rng.randint(5, 120)), card, facts)
            # the three planted conflicts happen within two days of the pediatrician's visit, so the disagreement is real, not growth
            uc_day = (v1 + timedelta(days=rng.randint(1, 2))) if i < 3 else self.today - timedelta(days=rng.randint(10, 200))
            w_uc = weight + (6 if i < 3 else 0)
            lb_ = _kg_to_lb(w_uc); tf = _c_to_f(round(rng.uniform(36.6, 38.4), 1)); sbp, dbp = rng.randint(94, 114), rng.randint(56, 74)
            qw, qt, qb = f"Wt {lb_:g} lb", f"Temp {tf:g} F", f"BP {sbp}/{dbp}"
            facts = [{"label": "weight", "category": "vital", "value": f"{lb_:g}", "unit": "lb", "quote": qw}, {"label": "temperature", "category": "vital", "value": f"{tf:g}", "unit": "F", "quote": qt},
                     {"label": "systolic blood pressure", "category": "vital", "value": str(sbp), "unit": "mmHg", "quote": qb}, {"label": "diastolic blood pressure", "category": "vital", "value": str(dbp), "unit": "mmHg", "quote": qb}]
            if i < 3:
                self._plant(kind="conflict", patient_id=pid, concept="weight", visit=uc_day.isoformat(), doc_value=f"{lb_} lb", truth_value=weight, note="urgent care weight disagrees with the pediatrician's record")
            else:
                self._plant(kind="unit_trap", patient_id=pid, concept="weight", visit=uc_day.isoformat(), doc_value=f"{lb_} lb", truth_value=w_uc, note="weight in pounds")
            if allergy:
                qa = f"Allergies: {allergy}"; facts.append({"label": allergy, "category": "allergy", "value": allergy, "unit": None, "quote": qa, "date": uc_day.isoformat()})
            else:
                qa = "Allergies: NKDA"
            note = (f"{PED_DOC_ORG.upper()} - VISIT SUMMARY\nPatient: {name}  DOB {birth.strftime('%m/%d/%Y')}  Record # {umrn}\nDate: {_fmt(uc_day, rng)}\nChief complaint: {rng.choice(['fever and cough', 'ear pain', 'sore throat', 'fall at playground'])}\n"
                    f"Vitals: {qw}, {qt}, {qb}, HR {rng.randint(70, 110)}\n{qa}\nAssessment: {rng.choice(['viral URI', 'otitis media', 'pharyngitis', 'contusion'])}. Plan: supportive care, return if worse.\nSeen by: {rng.choice(FIRST)} {rng.choice(LAST)}, PA-C\n")
            self._doc(pid, PED_DOC_ORG, "urgent_care_note", uc_day, note, facts)

    def build(self) -> dict:
        self.build_adults()
        self.build_children()
        return {"patients": self.patients, "identifiers": self.identifiers, "documents": self.documents, "bundles": self.bundles, "truth": self.truth,
                "orgs": {"ehr": [EHR_ORG, PED_ORG], "documents": [DOC_ORG, LAB_ORG, PED_DOC_ORG]}}


def build_world(seed: int = 7, today: date | None = None, trial_path: Path | None = None, n_doc_adults: int = 80, n_children: int = 10) -> dict:
    trial = json.load(open(trial_path or ROOT / "data/samples/trial_cdiscpilot01.json"))
    return Builder(trial, seed=seed, today=today, n_doc_adults=n_doc_adults, n_children=n_children).build()
