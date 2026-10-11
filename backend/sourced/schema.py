"""Data contracts for Sourced. The ledger speaks Fact; readers speak DocExtraction; forms speak FormDef and FilledField."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

Category = Literal["vital", "lab", "medication", "condition", "adverse_event", "allergy", "immunization", "demographic", "other"]


class DocFact(BaseModel):
    """One fact as a reader finds it in a document. Every field required so the schema is strict; use null when absent."""
    concept_label: str = Field(description="The measurement, test, medication, condition, vaccine, or demographic item exactly as written.")
    category: Category
    value: str = Field(description="The value exactly as written: '92.4', '158', 'Lisinopril', 'DTaP', 'Asthma'.")
    unit: str | None = Field(description="Unit exactly as written, else null.")
    observed_date: str | None = Field(description="ISO 8601 date the value was measured or the event started, else null.")
    quote: str = Field(description="Verbatim substring of the document, 3 to 160 characters, containing the value. Never paraphrase.")
    dose: str | None
    frequency: str | None
    route: str | None
    start_date: str | None
    end_date: str | None
    severity: str | None
    serious: bool | None
    indication: str | None


class DocExtraction(BaseModel):
    document_kind: str = Field(description="lab report, clinic note, discharge summary, pharmacy list, immunization record, other.")
    document_date: str | None
    patient_name: str | None
    patient_identifiers: list[str] = Field(description="MRNs or record numbers exactly as written.")
    facts: list[DocFact]


class Suggestion(BaseModel):
    """What the model may say about a flagged field. It reasons only from the receipts it is given."""
    likely_cause: str = Field(description="One or two sentences on the most likely reason the sources disagree, using only the receipts.")
    confidence: Literal["likely", "possible", "unclear"]
    suggested_decision: str = Field(description="What the coordinator should record and why, one sentence. Write 'no suggestion' if the evidence does not favor a value.")
    verify_with: str = Field(description="Who or what to check before signing: a role, a document, or the patient.")


class Fact(BaseModel):
    id: int | None = None
    patient_id: str
    concept: str
    display: str
    value_num: float | None = None
    value_text: str | None = None
    unit: str | None = None
    observed_at: date
    end_at: date | None = None
    attrs: dict[str, Any] = {}
    source_org: str
    document_id: str | None = None
    page: int | None = None
    span_start: int | None = None
    span_end: int | None = None
    quote: str | None = None
    resource_ref: str | None = None
    extractor: str
    confidence: float
    status: str = "extracted"


class Document(BaseModel):
    id: str
    patient_id: str | None
    source_org: str
    kind: str
    received_at: datetime
    document_date: date | None = None
    text: str
    n_pages: int = 1


class FieldDef(BaseModel):
    key: str
    label: str
    concept: str
    vtype: Literal["number", "text", "date", "list"]
    unit: str | None = None
    window_before: int = 3          # days before the visit a value may come from
    window_after: int = 1
    required: bool = True
    columns: list[str] = []         # for list fields: which attrs to show


class FormDef(BaseModel):
    id: str
    name: str
    domain: str
    description: str
    fields: list[FieldDef]


class FilledField(BaseModel):
    key: str
    label: str
    vtype: str
    unit: str | None = None
    value: Any = None
    fact_id: int | None = None
    confidence: float = 0.0
    receipt: dict | None = None
    alternatives: list[dict] = []
    rows: list[dict] | None = None
    verifier: dict | None = None
    decision: dict | None = None


class FormInstance(BaseModel):
    id: int | None = None
    form_id: str
    patient_id: str
    visit_date: date
    status: str = "draft"
    fields: list[FilledField]
    filled_ms: int | None = None
    n_fields: int = 0
    n_filled: int = 0
    n_flagged: int = 0
    signed_by: str | None = None
    signed_at: datetime | None = None
