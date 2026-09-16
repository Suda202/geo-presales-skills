# Regression History

## 2026-08-25 · v0.5.0

- Allowed zero to three user-provided candidates; zero-input runs now discover all three from scratch.
- Promoted “same purchase set” from a ranking signal to a deterministic eligibility gate with evidence binding.
- User-provided candidates no longer bypass eligibility; rejected inputs are audited and automatically replaced.
- Removed adjacent and fallback candidates from formal-slot filling. Fewer than three eligible candidates now requires more automated research.

## 2026-07-27 · v0.4.0

- Changed automatic fill order to `comparability tier → leader representativeness within tier → total score` while retaining every sales-provided competitor first.
- Verified that a lower-scoring direct leader is selected before a higher-scoring direct peer.
- Verified that direct peers and challengers remain ahead of an adjacent leader, so leadership never overrides comparability tier.
- Added an explicit `selection_strategy` audit object and upgraded the ruleset to `competitor-portfolio-v3`.
- Verified that an unverified or stale self-declared leader does not receive head-brand priority.
- `python3 -m unittest discover -s scripts/tests -v`: 14 tests passed.
- Meta Skill validation, resource boundary, lint, and governance checks passed; the pre-existing empty `assets/` warning remains non-blocking.

## 2026-07-27 · v0.3.0

- Changed the input contract to require one to three sales-provided competitors.
- Verified that source attribution is inferred from frozen input rather than trusted from research output.
- Verified that a sales-provided competitor remains selected when evidence and dimensions are missing.
- Verified automatic `direct` → `adjacent` → `fallback` filling and low-comparability comparison guardrails.
- Verified that an incomplete automatic candidate pool requests more automated research instead of business review.
- `python3 -m unittest discover -s scripts/tests -v`: 11 tests passed.
- Meta Skill package validation and resource-boundary checks passed.
