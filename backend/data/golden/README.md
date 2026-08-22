# Golden Evaluation Set — Review Status

This directory contains the versioned, maintainer-reviewed golden evaluation set
for the MVP safety milestone.

## Status

- **Review status:** `maintainer_reviewed`
- **Reviewer role:** solo maintainer
- **Effective date:** 2026-08-22
- **Legal review:** NOT independently or professionally reviewed. These cases
  and the underlying rules are experimental and informational only.
- **Verified against:** SPDX 3.24.0 catalog and the MIT / Apache-2.0 rule set
  in `data/rules/`.

## Composition (minimum 60)

| Category | Cases |
|---|---|
| `mit_supported` | 10 |
| `apache_supported` | 15 |
| `or_branch` | 5 |
| `missing_facts` | 8 |
| `unsupported` | 6 |
| `invalid` | 6 |
| `conflicting_or_missing_evidence` | 4 |
| `adversarial` | 6 |
| **Total** | **60** |

## Acceptance targets (Milestone 7)

- Severe unsafe answers: **0**
- Material-claim citation coverage: **>= 99%**
- Citation entailment accuracy: **>= 98%**
- Required-context detection recall: **>= 95%**
- Unsupported-case abstention recall: **>= 98%**

These targets are asserted by `tests/integration/test_golden.py`, which runs
every case through the public analysis workflow. The measured report (including
test-set composition and confidence intervals) is produced by
`tests/integration/golden_eval.py`.
