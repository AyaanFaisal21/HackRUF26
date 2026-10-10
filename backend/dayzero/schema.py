"""Shared data contracts. Every module speaks these types, so a teammate can replace any single module
without touching the others. Extraction is what the LLM returns; CaseState/Assessment are what the rules produce."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

Channel = Literal["email", "call_note", "patient_portal", "fax_pdf", "site_report"]
Sex = Literal["M", "F", "unknown"]
Qualification = Literal["physician", "pharmacist", "other_health_professional", "lawyer", "consumer", "unknown"]
Outcome = Literal["recovered", "recovering", "not_recovered", "fatal", "unknown"]
DrugRole = Literal["suspect", "concomitant", "interacting"]
MISSING_LABELS = ("identifiable_patient", "identifiable_reporter", "suspect_drug", "adverse_event")


class Evidence(BaseModel):
    quote: str = Field(description="Verbatim substring copied from the message, 3 to 200 characters. Never paraphrase.")
    start: int | None = None
    end: int | None = None


class Patient(BaseModel):
    identifiable: bool = Field(description="True only if the message gives at least one of: initials, a name, age, sex, date of birth, or a patient identifier.")
    initials: str | None
    age: int | None = Field(description="Age in years if stated, else null.")
    sex: Sex
    evidence: list[Evidence]


class Reporter(BaseModel):
    identifiable: bool = Field(description="True only if a reporter name, signature, or direct contact detail (email, phone) is present.")
    name: str | None
    qualification: Qualification
    contact: str | None
    evidence: list[Evidence]


class Drug(BaseModel):
    name: str
    role: DrugRole
    dose: str | None
    start_date: str | None = Field(description="ISO 8601 date if stated, else null.")
    evidence: list[Evidence]


class Reaction(BaseModel):
    term: str = Field(description="The reporter's own words for the event, not a coded term.")
    onset_date: str | None = Field(description="ISO 8601 date if stated, else null.")
    outcome: Outcome
    evidence: list[Evidence]


class Seriousness(BaseModel):
    death: bool
    life_threatening: bool
    hospitalization: bool = Field(description="Hospitalization or prolongation of an existing hospitalization.")
    disability: bool
    congenital_anomaly: bool
    other_medically_important: bool
    evidence: list[Evidence]


class Extraction(BaseModel):
    """What the extractor returns for one message. Every field is required so the JSON schema is strict."""
    language: str = Field(description="ISO 639-1 code of the message language.")
    is_followup: bool = Field(description="True if the message refers to a case the sender already reported.")
    followup_reference: str | None = Field(description="Verbatim phrase the sender uses to refer to the earlier report, else null.")
    patient: Patient
    reporter: Reporter
    drugs: list[Drug]
    reactions: list[Reaction]
    seriousness: Seriousness
    event_date: str | None = Field(description="ISO 8601 date the event started, if stated.")
    summary: str = Field(description="One neutral sentence: who, which product, what happened. No speculation about causality.")
    missing_information: list[str] = Field(description="Facts a case processor would still need, in plain words.")


class Message(BaseModel):
    id: str
    received_at: datetime
    channel: Channel
    sender: str | None = None
    subject: str | None = None
    body: str


class CodedReaction(BaseModel):
    term: str
    pt: str | None            # mock MedDRA preferred term, or None if no confident match
    score: float
    outcome: Outcome
    onset_date: str | None


class Snapshot(BaseModel):
    """One message's contribution to a case. A case is the ordered list of its snapshots."""
    message_id: str
    received_at: datetime
    extraction: Extraction


class CaseState(BaseModel):
    """Merged view of all snapshots. Rebuilt from snapshots, never edited directly, so history is always replayable."""
    case_id: str
    snapshots: list[Snapshot]
    patient: Patient
    reporter: Reporter
    drugs: list[Drug]
    reactions: list[CodedReaction]
    seriousness: Seriousness
    event_date: str | None


class Assessment(BaseModel):
    valid: bool
    missing: list[str]
    serious: bool
    criteria: list[str]
    expectedness: Literal["expected", "unexpected", "unknown"]
    expedited: bool
    day_zero: date | None
    due_date: date | None
    clock_days: int | None
    citations: list[str]
    followup_questions: list[str]


class DuplicateCandidate(BaseModel):
    case_id: str
    other_case_id: str
    score: float
    structured: float
    semantic: float
    evidence: dict[str, float]
    verdict: Literal["likely", "possible"]


class AuditEvent(BaseModel):
    case_id: str
    at: datetime
    actor: str                      # "pipeline", "rules", or a human user id
    action: str                     # created, followup_merged, field_confirmed, field_edited, merged, reassessed
    field: str | None = None
    old: Any = None
    new: Any = None
    message_id: str | None = None
    reason: str | None = None


class CaseRecord(BaseModel):
    state: CaseState
    assessment: Assessment
    status: Literal["new", "in_review", "confirmed", "merged", "closed"] = "new"
    merged_into: str | None = None
    embedding: list[float] | None = None
