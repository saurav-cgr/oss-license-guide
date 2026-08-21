import type { AnalysisResponse, ClaimDto, CitationDto } from "../api/types";

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
        </li>
      ))}
    </ul>
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
          </li>
        ))}
      </ul>
    </section>
  );
}

/** Renders the structured analysis result, including abstention and fallback states. */
export function AnalysisResult({ result }: AnalysisResultProps) {
  const tone = toneFor(result.outcome);

  return (
    <section className={`analysis-result ${tone}`} aria-live="polite">
      <header className="result-header">
        <h2>
          <span className="outcome-badge">{result.outcome}</span>
        </h2>
        {result.canonical && <p className="canonical">Expression: {result.canonical}</p>}
        <p className="short-answer">{result.short_answer}</p>
      </header>

      {result.blocked && (
        <div role="alert" className="blocked">
          <h3>Analysis blocked</h3>
          <p>
            The supporting evidence could not be validated, so no substantive conclusion is
            shown.
          </p>
          <ListSection title="Citation errors" items={result.citation_errors} />
        </div>
      )}

      {!result.blocked && result.missing_facts.length > 0 && (
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
      <ObligationsList obligations={result.obligations} />
      <ListSection title="What could change this" items={result.what_could_change} />
      <Evidence evidence={result.evidence} />
      <Confidence confidence={result.confidence} />

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
