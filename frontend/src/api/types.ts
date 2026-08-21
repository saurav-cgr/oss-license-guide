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
}

export interface ClaimDto {
  text: string;
  citations: CitationDto[];
}

export interface AnalysisResponse {
  outcome: string;
  canonical: string;
  short_answer: string;
  assumptions: string[];
  obligations: ClaimDto[];
  what_could_change: string[];
  evidence: CitationDto[];
  confidence: Record<string, string>;
  escalation: string;
  disclaimer: string;
  missing_facts: string[];
  warnings: string[];
  rule_id: string | null;
  citation_errors: string[];
  blocked: boolean;
  rendered: string;
}

/** Stable error payload shape returned by the API error handlers. */
export interface ApiErrorPayload {
  error?: {
    code?: string;
    message?: string;
    details?: { field?: string; message?: string }[];
  };
}
