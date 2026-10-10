"""Synthetic inbox generator. Structured FAERS case -> messy message + answer key.

FAERS (openFDA) has no names, initials, narratives, or contact details, so those are invented here and the
invented values are the ground truth. Offline rendering uses templates and runs with no model; the Claude
renderer rewrites the same facts into more natural text and other languages. Both keep the answer key."""
from __future__ import annotations

import json
import random
import re
from datetime import datetime, timedelta, timezone

from .schema import Drug, Evidence, Extraction, Message, Patient, Reaction, Reporter, Seriousness

QUAL = {"1": "physician", "2": "pharmacist", "3": "other_health_professional", "4": "lawyer", "5": "consumer"}
OUTCOME = {"1": "recovered", "2": "recovering", "3": "not_recovered", "4": "recovered", "5": "fatal", "6": "unknown"}
FIRST = ["Maria", "James", "Priya", "Wei", "Ahmed", "Elena", "Tom", "Grace", "Luis", "Hana", "Olu", "Sofia", "Daniel", "Amara"]
LAST = ["Okafor", "Nguyen", "Patel", "Lee", "Garcia", "Schmidt", "Rossi", "Khan", "Brown", "Silva", "Haddad", "Novak"]
LAY = {"Myocardial infarction": "heart attack", "Dyspnoea": "shortness of breath", "Nausea": "feeling sick", "Vomiting": "throwing up",
       "Pyrexia": "fever", "Fatigue": "very tired", "Death": "passed away", "Syncope": "fainted", "Urticaria": "hives",
       "Hyperglycaemia": "high blood sugar", "Sepsis": "infection in the blood", "Cerebrovascular accident": "stroke"}


def faers_to_truth(rec: dict) -> dict:
    p = rec.get("patient", {})
    age = p.get("patientonsetage")
    age = int(float(age)) if age and p.get("patientonsetageunit") == "801" else None
    suspects = []
    for d in p.get("drug", []):
        if d.get("drugcharacterization") == "1" and d.get("medicinalproduct"):
            name = d["medicinalproduct"].title()
            if name not in suspects:
                suspects.append(name)
    reactions = [(r["reactionmeddrapt"], OUTCOME.get(r.get("reactionoutcome", "6"), "unknown")) for r in p.get("reaction", [])]
    ev = (p.get("summary", {}).get("narrativeincludeclinical", "") or "").replace("CASE EVENT DATE: ", "")
    return {
        "faers_id": rec["safetyreportid"], "age": age, "sex": {"1": "M", "2": "F"}.get(p.get("patientsex"), "unknown"),
        "suspects": suspects[:3], "reactions": reactions[:3], "event_date": ev if re.fullmatch(r"\d{8}", ev) else None,
        "qualification": QUAL.get(rec.get("primarysource", {}).get("qualification"), "unknown"),
        "death": rec.get("seriousnessdeath") == "1", "life_threatening": rec.get("seriousnesslifethreatening") == "1",
        "hospitalization": rec.get("seriousnesshospitalization") == "1", "disability": rec.get("seriousnessdisabling") == "1",
        "congenital_anomaly": rec.get("seriousnesscongenitalanomali") == "1", "other": rec.get("seriousnessother") == "1",
    }


def _fmt_date(d: datetime, rng: random.Random) -> str:
    return rng.choice([d.strftime("%B %d, %Y"), d.strftime("%m/%d/%Y"), d.strftime("%Y-%m-%d"), d.strftime("%d %b %Y")])


class OfflineRenderer:
    """Templates with controlled messiness. Every fact that ends up in the answer key is inserted as an exact string."""

    def __init__(self, rng: random.Random):
        self.rng = rng

    def render(self, t: dict, identity: dict, variant: str, channel: str, received: datetime) -> tuple[str, str | None, str | None, Extraction]:
        rng = self.rng
        pt_bits, pt_ev = [], []
        if variant != "no_patient":
            if identity["use_name"]:
                pt_bits.append(f"{identity['patient_name']}"); pt_ev.append(identity["patient_name"])
            else:
                pt_bits.append(f"patient {identity['initials']}"); pt_ev.append(f"patient {identity['initials']}")
            if t["age"]:
                pt_bits.append(f"{t['age']}-year-old"); pt_ev.append(f"{t['age']}-year-old")
            if t["sex"] != "unknown":
                w = {"M": "male", "F": "female"}[t["sex"]]; pt_bits.append(w); pt_ev.append(w)
        patient_phrase = (" ".join(pt_bits) if pt_bits else "a patient")
        drug_phrase = ", ".join(t["suspects"]) if t["suspects"] else "one of your products"
        rx_words = []
        for pt, _ in t["reactions"]:
            rx_words.append(LAY.get(pt, pt.lower()) if (channel == "patient_portal" or rng.random() < 0.3) else pt.lower())
        rx_phrase = ", ".join(rx_words) if rx_words else "a reaction"
        ev_date = datetime.strptime(t["event_date"], "%Y%m%d").replace(tzinfo=timezone.utc) if t["event_date"] else received - timedelta(days=rng.randint(2, 40))
        if ev_date > received:
            ev_date = received - timedelta(days=rng.randint(2, 40))
        date_str = _fmt_date(ev_date, rng)
        ser_phrase, ser_ev = "", []
        if t["death"]:
            ser_phrase = rng.choice(["The patient died.", "Unfortunately the patient passed away."]); ser_ev.append(ser_phrase)
        elif t["life_threatening"]:
            ser_phrase = "This was life-threatening and required ICU admission."; ser_ev.append(ser_phrase)
        elif t["hospitalization"]:
            ser_phrase = rng.choice(["The patient was admitted to hospital.", "Hospitalized for observation."]); ser_ev.append(ser_phrase)
        elif t["disability"]:
            ser_phrase = "The patient has not regained function and may have lasting disability."; ser_ev.append(ser_phrase)
        elif t["other"]:
            ser_phrase = "The treating physician considered this medically significant."; ser_ev.append(ser_phrase)
        rep_name, rep_contact = identity["reporter_name"], identity["reporter_contact"]
        signed = variant != "no_reporter"
        if channel == "email":
            subject = rng.choice([f"Adverse event report - {drug_phrase}", f"Fwd: patient reaction to {drug_phrase}", "Possible side effect, please advise", "RE: safety report"])
            body = (f"{rng.choice(['Hello,', 'Dear Safety Team,', 'Hi there,', 'To whom it may concern,'])}\n\n"
                    f"I am writing to report that {patient_phrase} taking {drug_phrase} developed {rx_phrase} on {date_str}. {ser_phrase}\n"
                    f"{rng.choice(['Please let me know if you need anything else.', 'Let me know what additional information you require.', ''])}\n\n"
                    + (f"{rng.choice(['Regards,', 'Best,', 'Thanks,'])}\n{rep_name}\n{identity['reporter_role']}\n{rep_contact}\n" if signed else f"{rng.choice(['Regards', 'Sent from my phone', ''])}\n")
                    + rng.choice(["", "\nThis email may contain confidential information intended only for the recipient."]))
            sender = rep_contact if signed else None
        elif channel == "call_note":
            subject = None
            body = (f"CALL LOG {received.strftime('%m/%d %H:%M')}\n"
                    + (f"Caller: {rep_name} ({identity['reporter_role']}), callback {rep_contact}\n" if signed else "Caller: declined to give name\n")
                    + f"Re: {patient_phrase}, on {drug_phrase}\nReported: {rx_phrase}, onset {date_str}\n{ser_phrase}\n"
                    + rng.choice(["Caller asks whether to stop the medication - advised to contact prescriber.", "No further details available at time of call.", "Will send records."]))
            sender = None
        elif channel == "patient_portal":
            subject = rng.choice(["side effect?", "question about my medication", "something happened after my dose"])
            me = f"I am {patient_phrase}" if variant != "no_patient" else "I"
            body = (f"hi, {me} and I have been on {drug_phrase}. since {date_str} i have had {rx_phrase}. {ser_phrase} "
                    f"{rng.choice(['is this normal??', 'should i stop taking it', 'my doctor is on vacation', ''])}\n"
                    + (f"- {rep_name}, {rep_contact}" if signed else ""))
            sender = rep_contact if signed else None
        else:  # fax_pdf / site_report rendered as OCR-like letter text
            subject = "SERIOUS ADVERSE EVENT NOTIFICATION"
            body = (f"{subject}\nDate: {received.strftime('%Y-%m-%d')}\n"
                    + (f"Reporting physician: {rep_name}\nContact: {rep_contact}\n" if signed else "Reporting physician: ________\n")
                    + f"Subject: {patient_phrase}\nSuspect product: {drug_phrase}\nEvent(s): {rx_phrase}\nOnset: {date_str}\n{ser_phrase}\n"
                    + rng.choice(["[page 1 of 1]", "[OCR confidence 0.91]", ""]))
            sender = None

        ext = Extraction(
            language="en", is_followup=False, followup_reference=None,
            patient=Patient(identifiable=variant != "no_patient",
                            initials=None if variant == "no_patient" else (identity["initials"] if not identity["use_name"] else None),
                            age=t["age"] if variant != "no_patient" else None, sex=t["sex"] if variant != "no_patient" else "unknown",
                            evidence=[Evidence(quote=q) for q in pt_ev]),
            reporter=Reporter(identifiable=signed, name=rep_name if signed else None,
                              qualification=identity["qualification"] if signed else "unknown", contact=rep_contact if signed else None,
                              evidence=[Evidence(quote=rep_name)] if signed else []),
            drugs=[Drug(name=s, role="suspect", dose=None, start_date=None, evidence=[Evidence(quote=s)]) for s in t["suspects"]],
            reactions=[Reaction(term=w, onset_date=ev_date.strftime("%Y-%m-%d"), outcome=o, evidence=[Evidence(quote=w)]) for w, (_, o) in zip(rx_words, t["reactions"])],
            seriousness=Seriousness(death=t["death"], life_threatening=t["life_threatening"], hospitalization=t["hospitalization"],
                                    disability=t["disability"], congenital_anomaly=t["congenital_anomaly"], other_medically_important=t["other"],
                                    evidence=[Evidence(quote=q) for q in ser_ev]),
            event_date=ev_date.strftime("%Y-%m-%d"), summary=f"{patient_phrase} on {drug_phrase} developed {rx_phrase}.",
            missing_information=[m for m, cond in (("reporter identity", not signed), ("patient identifier", variant == "no_patient"), ("dose", True)) if cond])
        return body, subject, sender, ext

    def followup(self, identity: dict, orig_msg_id: str, missing: str, drug_phrase: str, received: datetime) -> tuple[str, Extraction]:
        rng = self.rng
        ref = rng.choice([f"my report from {received.strftime('%A')} about the patient on {drug_phrase}", f"case reference {orig_msg_id}", f"the {drug_phrase} report I sent earlier"])
        if missing == "no_reporter":
            body = f"Following up on {ref}. I forgot to sign it. This is {identity['reporter_name']}, {identity['reporter_role']}, reachable at {identity['reporter_contact']}."
            ext = Extraction(language="en", is_followup=True, followup_reference=ref,
                             patient=Patient(identifiable=False, initials=None, age=None, sex="unknown", evidence=[]),
                             reporter=Reporter(identifiable=True, name=identity["reporter_name"], qualification=identity["qualification"], contact=identity["reporter_contact"], evidence=[Evidence(quote=identity["reporter_name"])]),
                             drugs=[], reactions=[], seriousness=Seriousness(death=False, life_threatening=False, hospitalization=False, disability=False, congenital_anomaly=False, other_medically_important=False, evidence=[]),
                             event_date=None, summary="Reporter supplies their identity for an earlier report.", missing_information=[])
        else:
            body = f"Re: {ref}. You asked who the patient was: initials {identity['initials']}, {identity['age_phrase']}."
            ext = Extraction(language="en", is_followup=True, followup_reference=ref,
                             patient=Patient(identifiable=True, initials=identity["initials"], age=identity["age"], sex=identity["sex"], evidence=[Evidence(quote=f"initials {identity['initials']}")]),
                             reporter=Reporter(identifiable=False, name=None, qualification="unknown", contact=None, evidence=[]),
                             drugs=[], reactions=[], seriousness=Seriousness(death=False, life_threatening=False, hospitalization=False, disability=False, congenital_anomaly=False, other_medically_important=False, evidence=[]),
                             event_date=None, summary="Reporter supplies the patient identifier for an earlier report.", missing_information=[])
        return body, ext


def build_inbox(faers_records: list[dict], n: int = 60, seed: int = 7, now: datetime | None = None, renderer=None) -> tuple[list[dict], dict]:
    """Returns (messages, answer_key). answer_key[message_id] = {extraction, truth_case, variant, duplicate_of, followup_of}."""
    rng = random.Random(seed)
    now = now or datetime.now(timezone.utc)
    renderer = renderer or OfflineRenderer(rng)
    truths = [faers_to_truth(r) for r in faers_records]
    truths = [t for t in truths if t["suspects"] and t["reactions"]][:n]
    messages, key = [], {}
    for i, t in enumerate(truths):
        age = t["age"] or rng.randint(24, 86)
        sex = t["sex"] if t["sex"] != "unknown" else rng.choice(["M", "F"])
        t = {**t, "age": age, "sex": sex}
        qual = t["qualification"] if t["qualification"] != "unknown" else rng.choice(["physician", "consumer", "pharmacist"])
        first, last = rng.choice(FIRST), rng.choice(LAST)
        identity = {
            "initials": f"{rng.choice('ABCDEFGHJKLMNPRST')}.{rng.choice('ABCDEFGHJKLMNPRST')}.", "age": age, "sex": sex,
            "age_phrase": f"{age}-year-old {'male' if sex == 'M' else 'female'}",
            "patient_name": f"{rng.choice(FIRST)} {rng.choice(LAST)}", "use_name": qual == "consumer" and rng.random() < 0.5,
            "reporter_name": (f"Dr. {first} {last}" if qual == "physician" else f"{first} {last}"), "qualification": qual,
            "reporter_role": {"physician": "MD, Internal Medicine", "pharmacist": "PharmD", "consumer": "", "other_health_professional": "RN", "lawyer": "Esq."}.get(qual, ""),
            "reporter_contact": rng.choice([f"{first.lower()}.{last.lower()}@{rng.choice(['clinic', 'hospital', 'gmail', 'health'])}.{rng.choice(['org', 'com', 'net'])}", f"({rng.randint(201, 989)}) 555-{rng.randint(1000, 9999)}"]),
        }
        channel = "patient_portal" if qual == "consumer" else rng.choice(["email", "email", "call_note", "fax_pdf", "site_report"])
        r = rng.random()
        variant = "no_reporter" if r < 0.10 else "no_patient" if r < 0.18 else "complete"
        received = now - timedelta(hours=rng.uniform(1, 24 * 30))
        mid = f"MSG-{i:04d}"
        body, subject, sender, ext = renderer.render(t, identity, variant, channel, received)
        messages.append({"id": mid, "received_at": received.isoformat(), "channel": channel, "sender": sender, "subject": subject, "body": body})
        key[mid] = {"extraction": ext.model_dump(), "truth_case": t["faers_id"], "variant": variant, "duplicate_of": None, "followup_of": None}
        if variant != "complete":
            fu_recv = min(received + timedelta(days=2, hours=rng.uniform(0, 8)), now)
            fbody, fext = renderer.followup(identity, mid, variant, ", ".join(t["suspects"]), received)
            fid = f"{mid}-FU"
            messages.append({"id": fid, "received_at": fu_recv.isoformat(), "channel": "email", "sender": identity["reporter_contact"], "subject": "Follow-up", "body": fbody})
            key[fid] = {"extraction": fext.model_dump(), "truth_case": t["faers_id"], "variant": "followup", "duplicate_of": None, "followup_of": mid}
        elif rng.random() < 0.12:  # a second reporter describes the same case in different words
            q2 = "consumer" if qual != "consumer" else "physician"
            f2, l2 = rng.choice(FIRST), rng.choice(LAST)
            ident2 = {**identity, "use_name": False, "reporter_name": f"Dr. {f2} {l2}" if q2 == "physician" else f"{f2} {l2}", "qualification": q2,
                      "reporter_role": "MD" if q2 == "physician" else "", "reporter_contact": f"{f2.lower()}{l2.lower()}@{rng.choice(['mail', 'clinic'])}.com"}
            t2 = {**t, "age": age + rng.choice([-1, 0, 1])}
            ch2 = "patient_portal" if q2 == "consumer" else rng.choice(["email", "call_note"])
            recv2 = min(received + timedelta(hours=rng.uniform(6, 120)), now)
            body2, subj2, send2, ext2 = renderer.render(t2, ident2, "complete", ch2, recv2)
            did = f"{mid}-DUP"
            messages.append({"id": did, "received_at": recv2.isoformat(), "channel": ch2, "sender": send2, "subject": subj2, "body": body2})
            key[did] = {"extraction": ext2.model_dump(), "truth_case": t["faers_id"], "variant": "duplicate", "duplicate_of": mid, "followup_of": None}
    messages.sort(key=lambda m: m["received_at"])
    return messages, key


def build_mock_data(faers_records: list[dict], rng_seed: int = 1) -> tuple[dict, dict]:
    """mock_meddra: every preferred term seen. mock_rsi: for the most-reported products, the commonest half of their
    reported terms is labelled 'expected'. This is a synthetic stand-in for a product label, not real labeling."""
    from collections import Counter, defaultdict
    terms, per_drug = Counter(), defaultdict(Counter)
    for rec in faers_records:
        t = faers_to_truth(rec)
        for pt, _ in t["reactions"]:
            terms[pt] += 1
            for s in t["suspects"]:
                per_drug[s.lower()][pt] += 1
    rsi = {}
    for drug, c in per_drug.items():
        if sum(c.values()) >= 4:
            common = [pt for pt, _ in c.most_common()]
            rsi[drug] = common[: max(1, len(common) // 2)]
    return {"source": "openFDA FAERS reactionmeddrapt values observed in data/raw/faers.json", "terms": sorted(terms)}, \
           {"note": "SYNTHETIC. Expected terms per product were derived from report frequency, not from the approved label.", "rsi": rsi}
