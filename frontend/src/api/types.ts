// Mirrors src/doc2tests/api/schemas.py 1:1.

export interface DetectedDTO {
  id: string
  label: string
  value: string
  field_type: string
  is_personal: boolean
  slot: string | null
}

export interface ColumnDTO {
  id: string
  label: string
}

export interface VariantDTO {
  index: number
  values: Record<string, string>
  rendered: boolean
}

export interface DiagnosticsRowDTO {
  label: string
  field_type: string
  is_personal: boolean
  slot: string | null
  original: string
  generated: string
}

export interface DocStateDTO {
  doc_id: string
  filename: string
  doc_summary: string
  page_image_url: string | null
  detected: DetectedDTO[]
  columns: ColumnDTO[]
  variants: VariantDTO[]
  diagnostics: DiagnosticsRowDTO[]
}

export interface ReviewedValue {
  label: string
  value: string
  field_type: string
  is_personal: boolean
  slot: string | null
}

export interface JobRef {
  job_id: string
  doc_id?: string | null
}

export interface JobStatus {
  id: string
  status: string
  error: string | null
  result: unknown
}

export interface SourceDTO {
  id: number
  filename: string
  doc_summary: string
  n_generated: number
}

export interface GeneratedDTO {
  id: number
  variant_index: number
  values: Record<string, unknown>
}

export interface BatchItem {
  doc_id: string
  filename: string
  n_variants: number
  error: string | null
}

export const FIELD_TYPES = [
  'hebrew_name', 'israeli_id', 'date', 'gush_helka', 'assessment_number',
  'bank_branch', 'address', 'phone', 'currency', 'enum', 'free_text',
] as const
