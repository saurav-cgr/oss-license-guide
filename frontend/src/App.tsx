import { ApiClient } from "./api/client";
import { AnalysisForm } from "./components/AnalysisForm";
import { AnalysisResult } from "./components/AnalysisResult";
import { HealthStatus } from "./components/HealthStatus";
import { useAnalysis } from "./components/useAnalysis";
import { useHealth } from "./components/useHealth";

const apiClient = new ApiClient({ baseUrl: import.meta.env.VITE_API_BASE_URL ?? "" });

function LogoMark() {
  return (
    <span className="logo-mark" aria-hidden="true">
      <svg viewBox="0 0 32 32" role="img">
        <path d="M7 5.5h11.5A6.5 6.5 0 0 1 25 12v14.5H13.5A6.5 6.5 0 0 0 7 33V5.5Z" />
        <path d="M25 5.5H13.5A6.5 6.5 0 0 0 7 12v14.5h11.5A6.5 6.5 0 0 1 25 33V5.5Z" />
        <path d="M11 11.5h6M11 16h6M15 20.5h4" />
      </svg>
    </span>
  );
}

function ArrowIcon() {
  return (
    <svg className="arrow-icon" viewBox="0 0 18 18" aria-hidden="true">
      <path d="M3 9h11M9.5 4.5 14 9l-4.5 4.5" />
    </svg>
  );
}

function FeatureIcon({ type }: { type: "expression" | "evidence" | "guardrail" }) {
  if (type === "expression") {
    return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m8 5-5 7 5 7M16 5l5 7-5 7M14 3l-4 18" /></svg>;
  }
  if (type === "evidence") {
    return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 3.5h10l4 4V20.5H5zM15 3.5v5h4M8 13h8M8 16.5h5" /></svg>;
  }
  return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3 20 6v5.5c0 4.5-3 7.7-8 9.5-5-1.8-8-5-8-9.5V6zM8.5 12l2.3 2.3 4.8-5" /></svg>;
}

export function App() {
  const health = useHealth(apiClient);
  const analysis = useAnalysis(apiClient);

  return (
    <main className="site-shell">
      <nav className="site-nav" aria-label="Main navigation">
        <a className="brand" href="#top" aria-label="License Lens home">
          <LogoMark />
          <span>license<span className="brand-accent">/</span>lens</span>
        </a>
        <div className="nav-links">
          <a href="#how-it-works">How it works</a>
          <a href="#safety">Safety</a>
          <a className="nav-cta" href="#analyze">Try the analyzer <ArrowIcon /></a>
        </div>
      </nav>

      <section className="hero" id="top">
        <div className="hero-copy">
          <p className="eyebrow"><span className="eyebrow-dot" /> Open source license clarity</p>
          <h1>License answers you can <em>actually trace.</em></h1>
          <p className="hero-lede">Understand likely obligations from the exact SPDX expression and the scenario you actually have — with evidence, assumptions, and a clear line to human review.</p>
          <div className="hero-actions">
            <a className="button button-primary" href="#analyze">Analyze a license <ArrowIcon /></a>
            <a className="text-link" href="#how-it-works">See how it works <ArrowIcon /></a>
          </div>
          <div className="hero-meta">
            <span><span className="meta-check">✓</span> Deterministic first</span>
            <span><span className="meta-check">✓</span> Claim-level citations</span>
            <span><span className="meta-check">✓</span> No account required</span>
          </div>
        </div>

        <div className="hero-visual" aria-label="A preview of a cited license analysis" role="img">
          <div className="visual-grid" />
          <div className="analysis-preview">
            <div className="preview-topline"><span className="preview-dot" /> analysis / apache-2.0</div>
            <div className="preview-expression">MIT <span>OR</span> Apache-2.0</div>
            <div className="preview-divider" />
            <div className="preview-label">LIKELY OUTCOME</div>
            <div className="preview-outcome">Permitted with listed obligations <span>↗</span></div>
            <div className="preview-row"><span>01</span><span>Retain license + attribution notices</span><i>cited</i></div>
            <div className="preview-row"><span>02</span><span>State meaningful changes</span><i>cited</i></div>
            <div className="preview-source">SPDX · Apache-2.0 · §4</div>
          </div>
          <div className="floating-note"><span>↳</span> assumptions included</div>
        </div>
      </section>

      <section className="trust-strip" aria-label="Product principles">
        <span>BUILT FOR THE MOMENT BEFORE YOU SHIP</span>
        <div className="strip-rule" />
        <span>MIT · APACHE-2.0 · SPDX EXPRESSIONS</span>
      </section>

      <section className="feature-section" id="how-it-works">
        <div className="section-heading">
          <p className="eyebrow">A better starting point</p>
          <h2>License names are not scenarios.</h2>
          <p>License Lens keeps the useful parts of automation and makes the uncertain parts visible.</p>
        </div>
        <div className="feature-grid">
          <article className="feature-card">
            <div className="feature-icon"><FeatureIcon type="expression" /></div>
            <p className="feature-number">01 / Exact input</p>
            <h3>Preserve the expression.</h3>
            <p>AND, OR, WITH, parentheses, and version suffixes stay intact. No hand-wavy normalization.</p>
          </article>
          <article className="feature-card featured-card">
            <div className="feature-icon"><FeatureIcon type="evidence" /></div>
            <p className="feature-number">02 / Source-backed</p>
            <h3>Show your work.</h3>
            <p>Material permissions and obligations point back to versioned source spans you can inspect.</p>
          </article>
          <article className="feature-card">
            <div className="feature-icon"><FeatureIcon type="guardrail" /></div>
            <p className="feature-number">03 / Honest output</p>
            <h3>Know when to stop.</h3>
            <p>Missing facts, unsupported rules, and contested questions become clarification or escalation.</p>
          </article>
        </div>
      </section>

      <section className="analyzer-section" id="analyze">
        <div className="analyzer-intro">
          <p className="eyebrow">Start with what you know</p>
          <h2>Run a grounded analysis.</h2>
          <p>Enter an exact expression, describe the scenario, and get a conditional answer you can review.</p>
          <div className="analyzer-status"><HealthStatus state={health} /></div>
        </div>
        <div className="analyzer-panel">
          <div className="panel-header"><span>new analysis</span><span className="panel-status"><span /> stateless session</span></div>
          <AnalysisForm client={apiClient} state={analysis.state} onRun={analysis.run} />
          {analysis.state.status === "success" && <AnalysisResult result={analysis.state.result} />}
        </div>
      </section>

      <section className="safety-section" id="safety">
        <div className="safety-mark"><FeatureIcon type="guardrail" /></div>
        <div>
          <p className="eyebrow">The boundary matters</p>
          <h2>Useful information, not a rubber stamp.</h2>
          <p>Rules are maintainer-reviewed and citations are validated before they reach you. The assistant explains likely outcomes; it does not decide derivative works, certify compliance, or replace qualified counsel.</p>
        </div>
        <a className="text-link" href="#analyze">Try it with MIT <ArrowIcon /></a>
      </section>

      <footer className="site-footer">
        <a className="brand" href="#top"><LogoMark /><span>license<span className="brand-accent">/</span>lens</span></a>
        <p>For context only — not legal advice. Have qualified counsel review decisions with material legal or business impact.</p>
        <span className="footer-note">open source · stateless by design</span>
      </footer>
    </main>
  );
}
