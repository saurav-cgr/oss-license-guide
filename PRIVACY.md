# Privacy Notice

This notice describes how the Open Source License Information Assistant handles
data in its current implementation. It is an informational tool, not a legal
product, and this notice is not legal advice.

## What the application does not retain

- **No accounts.** The MVP is anonymous and stateless. There is no sign-in, no
  saved history, and no saved analyses.
- **No database.** The request path uses no PostgreSQL, Redis, or other storage.
- **Raw queries and answers** are processed in memory for the duration of a
  request and are **not retained** by the application after the response.
- **User-supplied model-provider keys** are held only in browser memory (React
  component state) and backend request memory. They are never written to
  storage, cookies, URLs, logs, or analytics. The browser copy is retained in
  component state until you edit it or reload the page; the backend copy exists
  only for the duration of the request.

## What is processed by third parties

When you opt into a model explanation by selecting a provider and supplying your
own API key, your key, the structured findings, and the evidence spans are sent
to that provider (Gemini or an OpenAI-compatible service) under **their** terms.
The provider endpoints are server-controlled and allowlisted; the application
never accepts an arbitrary base URL from a request.

## Logging and observability

Operational logs are limited to non-secret measurements (request status,
outcome category, rule/source versions, provider type, token counts). Provider
keys and raw authorization headers are redacted and never logged. If a retention
period is ever published, it is verified against the deployed container host and
selected providers first.

## Data use

Content sent to a model provider is processed under that provider's terms, which
differ by provider and may change over time. This application does not itself
train models on your content, but it cannot guarantee that every configured
compatible provider will not use submitted content for training. Review the
selected provider's data-use and training policies before use, and only submit
content you are comfortable sharing with that provider.

## Before public deployment

Retention and data-handling behavior must be re-verified against the actual
deployment host and the selected model provider. If the deployed infrastructure
cannot enforce the statements above, this notice must be corrected before
launch.

## Status

The project and its rules have **not** been independently or professionally
legally reviewed. All output is informational guidance only and not legal
advice.
