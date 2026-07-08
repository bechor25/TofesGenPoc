from enum import StrEnum


class FieldType(StrEnum):
    hebrew_name = "hebrew_name"
    israeli_id = "israeli_id"
    date = "date"
    gush_helka = "gush_helka"
    assessment_number = "assessment_number"
    bank_branch = "bank_branch"
    address = "address"
    phone = "phone"
    currency = "currency"
    enum = "enum"
    free_text = "free_text"


class TestClass(StrEnum):
    equivalence = "equivalence"
    boundary = "boundary"
    negative = "negative"


class PiiType(StrEnum):
    IL_ID = "IL_ID"
    PERSON = "PERSON"
    DATE = "DATE"
    LOCATION = "LOCATION"
    PHONE = "PHONE"
    OTHER = "OTHER"


class SourceKind(StrEnum):
    image = "image"
    pdf = "pdf"


class RenderStrategy(StrEnum):
    reconstruct = "reconstruct"
    overlay = "overlay"


class ValueKind(StrEnum):
    printed = "printed"
    handwritten = "handwritten"


class RelationOp(StrEnum):
    le = "<="
    lt = "<"
    ge = ">="
    gt = ">"
    eq = "=="
