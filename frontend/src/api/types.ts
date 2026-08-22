/** Typed contracts for the versioned analysis API. */

/** Scenario facts. Omitted or undefined facts are treated as unknown by the API. */
export interface FactsInput {
  action?: string;
  distribution?: boolean;
  distribution_form?: string;
  recipient?: string;
  modified?: boolean;
  outbound_license?: string;
  selected_branch?: string;
  license_file_present?: boolean;
  copyright_notice_present?: boolean;
  notice_file_present?: boolean;
}

/** The full analysis request submitted to the API boundary. */
export interface AnalyzeRequest {
  expression: string;
  question?: string;
  facts: FactsInput;
  provider?: string;
  model?: string;
}

export interface CitationDto {
  source_id: string;
  span_index: number;
  text: string;
  hash: string;
  source_type: string;
  source_url: string;
  version: string;
  retrieved_at: string;
}

export interface ClaimDto {
  text: string;
  citations: CitationDto[];
}

/** Rule provenance surfaced to the client, never described as legal review. */
export interface RuleReviewDto {
  rule_id: string;
  review_status: string;
  reviewer: string;
  effective_date: string;
  last_verified_at: string;
  rule_version: string;
  content_hash: string;
}

export interface AnalysisResponse {
  outcome: string;
  canonical: string;
  short_answer: string;
  assumptions: string[];
  obligations: ClaimDto[];
  permission: ClaimDto | null;
  what_could_change: string[];
  evidence: CitationDto[];
  confidence: Record<string, string>;
  escalation: string;
  disclaimer: string;
  missing_facts: string[];
  warnings: string[];
  rule_id: string | null;
  rule: RuleReviewDto | null;
  citation_errors: string[];
  blocked: boolean;
  rendered: string;
  explanation: string;
  provider: string | null;
  model: string | null;
  provider_note: string;
}

/** Stable error payload shape returned by the API error handlers. */
export interface ApiErrorPayload {
  error?: {
    code?: string;
    message?: string;
    details?: { field?: string; message?: string }[];
  };
}
