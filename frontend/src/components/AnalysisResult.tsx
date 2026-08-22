import type { AnalysisResponse, ClaimDto, CitationDto, RuleReviewDto } from "../api/types";

interface AnalysisResultProps {
  result: AnalysisResponse;
}

type Tone = "permitted" | "obligations" | "caution" | "abstain";

const PERMITTED = "Likely permitted under stated assumptions";
const OBLIGATIONS = "Permitted with listed obligations";
const NOT_SUPPORTED = "Not supported under stated outbound-license goal";
const INSUFFICIENT = "Insufficient information";

function toneFor(outcome: string): Tone {
  if (outcome === PERMITTED) return "permitted";
  if (outcome === OBLIGATIONS) return "obligations";
  if (outcome === INSUFFICIENT || outcome === NOT_SUPPORTED) return "caution";
  return "abstain";
}

function ListSection(props: { title: string; items: string[] }) {
  if (props.items.length === 0) return null;
  return (
    <section className="result-section">
      <h3>{props.title}</h3>
      <ul>
        {props.items.map((item, index) => (
          <li key={index}>{item}</li>
        ))}
      </ul>
    </section>
  );
}

function CitationList({ citations }: { citations: CitationDto[] }) {
  if (citations.length === 0) return null;
  return (
    <ul className="citation-list">
      {citations.map((citation, index) => (
        <li key={index}>
          <span className="source-ref">
            {citation.source_id} §{citation.span_index}
          </span>
          <blockquote>{citation.text}</blockquote>
          <SourceMeta citation={citation} />
        </li>
      ))}
    </ul>
  );
}

function SourceMeta({ citation }: { citation: CitationDto }) {
  const hasMeta = citation.source_type || citation.version || citation.source_url;
  if (!hasMeta) return null;
  return (
    <p className="source-meta">
      {citation.source_type}
      {citation.version ? ` · v${citation.version}` : ""}
      {citation.source_url ? ` · ${citation.source_url}` : ""}
    </p>
  );
}

function ObligationsList({ obligations }: { obligations: ClaimDto[] }) {
  if (obligations.length === 0) return null;
  return (
    <section className="result-section">
      <h3>Obligations</h3>
      <ul className="obligation-list">
        {obligations.map((claim, index) => (
          <li key={index}>
            <p className="claim-text">{claim.text}</p>
            <CitationList citations={claim.citations} />
          </li>
        ))}
      </ul>
    </section>
  );
}

function Confidence({ confidence }: { confidence: Record<string, string> }) {
  const entries = Object.entries(confidence);
  if (entries.length === 0) return null;
  return (
    <section className="result-section">
      <h3>Confidence</h3>
      <dl className="confidence">
        {entries.map(([key, value]) => (
          <div key={key}>
            <dt>{key}</dt>
            <dd>{value}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

function Evidence({ evidence }: { evidence: CitationDto[] }) {
  if (evidence.length === 0) return null;
  return (
    <section className="result-section">
      <h3>Supporting evidence</h3>
      <ul className="citation-list">
        {evidence.map((entry, index) => (
          <li key={index}>
            <span className="source-ref">
              {entry.source_id} §{entry.span_index}
            </span>
            <blockquote>{entry.text}</blockquote>
            <SourceMeta citation={entry} />
          </li>
        ))}
      </ul>
    </section>
  );
}

function PermissionClaim({ permission }: { permission: ClaimDto | null }) {
  if (!permission) return null;
  return (
    <section className="result-section">
      <h3>Permissions</h3>
      <ul className="obligation-list">
        <li>
          <p className="claim-text">{permission.text}</p>
          <CitationList citations={permission.citations} />
        </li>
      </ul>
    </section>
  );
}

function RuleReview({ rule }: { rule: RuleReviewDto | null }) {
  if (!rule) return null;
  return (
    <section className="result-section">
      <h3>Rule provenance</h3>
      <dl className="rule-review">
        <div>
          <dt>Rule</dt>
          <dd>{rule.rule_id}</dd>
        </div>
        <div>
          <dt>Review status</dt>
          <dd>{rule.review_status}</dd>
        </div>
        <div>
          <dt>Version</dt>
          <dd>{rule.rule_version || "—"}</dd>
        </div>
        <div>
          <dt>Content hash</dt>
          <dd>{rule.content_hash ? rule.content_hash.slice(0, 12) : "—"}</dd>
        </div>
      </dl>
      <p className="hint">Rule provenance is maintainer-reviewed, not independent legal review.</p>
    </section>
  );
}

/** Renders the structured analysis result, including abstention and fallback states. */
export function AnalysisResult({ result }: AnalysisResultProps) {
  const tone = toneFor(result.outcome);

  if (result.blocked) {
    return (
      <section className="analysis-result abstain" aria-live="polite">
        <header className="result-header">
          <h2>
            <span className="outcome-badge">Analysis blocked</span>
          </h2>
          <p className="short-answer">
            Analysis blocked because the supporting evidence could not be validated.
          </p>
        </header>
        <div role="alert" className="blocked">
          <h3>Citation errors</h3>
          <p>
            The supporting evidence could not be validated, so no substantive conclusion is
            shown.
          </p>
          <ListSection title="Citation errors" items={result.citation_errors} />
        </div>
        <p className="disclaimer">{result.disclaimer}</p>
      </section>
    );
  }

  return (
    <section className={`analysis-result ${tone}`} aria-live="polite">
      <header className="result-header">
        <h2>
          <span className="outcome-badge">{result.outcome}</span>
        </h2>
        {result.canonical && <p className="canonical">Expression: {result.canonical}</p>}
        <p className="short-answer">{result.short_answer}</p>
      </header>

      {result.missing_facts.length > 0 && (
        <div role="alert" className="missing">
          <h3>Missing information</h3>
          <p>
            This outcome depends on facts that are not yet specified. Provide a value for:
          </p>
          <ul>
            {result.missing_facts.map((fact, index) => (
              <li key={index}>{fact}</li>
            ))}
          </ul>
        </div>
      )}

      <ListSection title="Assumptions" items={result.assumptions} />
      {result.explanation && (
        <section className="result-section explanation">
          <h3>Model explanation</h3>
          <p>{result.explanation}</p>
        </section>
      )}
      {result.provider_note && (
        <div role="note" className="provider-note">
          {result.provider_note}
        </div>
      )}
      <PermissionClaim permission={result.permission} />
      <ObligationsList obligations={result.obligations} />
      <ListSection title="What could change this" items={result.what_could_change} />
      <Evidence evidence={result.evidence} />
      <Confidence confidence={result.confidence} />
      <RuleReview rule={result.rule} />

      {result.warnings.length > 0 && (
        <section className="result-section">
          <h3>Warnings</h3>
          <ul>
            {result.warnings.map((warning, index) => (
              <li key={index}>{warning}</li>
            ))}
          </ul>
        </section>
      )}

      <section className="result-section">
        <h3>Review guidance</h3>
        <p>{result.escalation}</p>
      </section>

      <p className="disclaimer">{result.disclaimer}</p>
    </section>
  );
}
