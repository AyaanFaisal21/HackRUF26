"""Extraction: raw message -> Extraction with verbatim evidence. Three implementations behind one interface.

OracleExtractor  returns the answer key (offline demo, tests everything downstream of the model).
ModelExtractor   uses whichever provider llm.provider() finds (Anthropic or OpenAI key).
locate_spans     turns verbatim quotes into character offsets so the UI can highlight them."""
from __future__ import annotations

import os
from typing import Protocol

from .llm import provider
from .schema import Evidence, Extraction, Message

SYSTEM = """You are the intake step of a pharmacovigilance case-processing system. You read one incoming report
(an email, call-center note, patient portal message, site report, or OCR text of a fax) and fill a structured record.

Rules you must follow:
- Extract only what the text states. Never infer a fact that is not written. If a fact is absent, use null or false.
- Every evidence quote must be copied verbatim from the message, 3 to 200 characters. The system locates it by exact match.
- identifiable patient means at least one of: initials, name, age, sex, date of birth, or a patient identifier.
- identifiable reporter means a name, a signature, or a direct contact detail. "A nurse called" is not identifiable.
- suspect drug is the product the reporter associates with the event. Other medications are concomitant.
- Seriousness flags follow ICH E2A: death, life-threatening, hospitalization or prolongation, persistent disability,
  congenital anomaly, other medically important. Set a flag only when the text supports it; quote the support.
- Keep reaction terms in the reporter's words. Do not code to a dictionary; a separate step does that.
- The message may be in any language. Fill the record in English but keep quotes in the original language.
- is_followup is true when the sender refers to a report they already sent. Put their exact phrase in followup_reference.
- missing_information lists what a case processor would still have to ask for.
Do not add commentary. Return only the structured record."""


class Extractor(Protocol):
    def extract(self, message: Message) -> Extraction: ...


def locate_spans(ext: Extraction, body: str) -> Extraction:
    low = body.lower()

    def fix(ev: Evidence) -> Evidence:
        i = body.find(ev.quote)
        if i < 0:
            i = low.find(ev.quote.lower())
        return Evidence(quote=ev.quote, start=i if i >= 0 else None, end=i + len(ev.quote) if i >= 0 else None)

    ext.patient.evidence = [fix(e) for e in ext.patient.evidence]
    ext.reporter.evidence = [fix(e) for e in ext.reporter.evidence]
    ext.seriousness.evidence = [fix(e) for e in ext.seriousness.evidence]
    for d in ext.drugs:
        d.evidence = [fix(e) for e in d.evidence]
    for r in ext.reactions:
        r.evidence = [fix(e) for e in r.evidence]
    return ext


class OracleExtractor:
    def __init__(self, answer_key: dict):
        self.key = answer_key

    def extract(self, message: Message) -> Extraction:
        ext = Extraction.model_validate(self.key[message.id]["extraction"])
        return locate_spans(ext, message.body)


class ModelExtractor:
    def __init__(self, llm=None):
        self.llm = llm or provider()
        if self.llm is None:
            raise SystemExit("no model key found: set ANTHROPIC_API_KEY or OPENAI_API_KEY in .env")

    def extract(self, message: Message) -> Extraction:
        user = (f"<message id=\"{message.id}\" channel=\"{message.channel}\" received=\"{message.received_at.isoformat()}\">\n"
                f"From: {message.sender or '(unknown)'}\nSubject: {message.subject or '(none)'}\n\n{message.body}\n</message>")
        return locate_spans(self.llm.parse(SYSTEM, user, Extraction), message.body)


# kept for callers that imported the old name
ClaudeExtractor = ModelExtractor


def get_extractor(answer_key: dict | None = None) -> Extractor:
    kind = os.environ.get("DAYZERO_EXTRACTOR", "oracle")
    if kind in ("claude", "openai", "model"):
        return ModelExtractor()
    if answer_key is None:
        raise SystemExit("DAYZERO_EXTRACTOR=oracle needs an answer key (pass --answer-key)")
    return OracleExtractor(answer_key)
