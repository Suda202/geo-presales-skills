# GEO Presales Skills

Versioned Skill packages for the GEO presales workflow.

## Included packages

- `skills/geo-presales-prompt-builder/` generates and validates `overseas-geo-question-bank/v8` English AI-search monitoring Prompts. It derives an `Attribute × Topic` plan from the Case, records diagnostic intent, brand scope, Attributes, and custom analysis dimensions as free Tags, and keeps each Prompt within the purchasing object defined by its Topic.
- `skills/geo-presales-report/` turns company-backend statistics into evidence-constrained Chinese analysis conclusions and an upload-ready CSV. It does not recalculate production metrics or render HTML/PDF.
- `evals/v3/` contains nine validated, non-production evaluation inputs. The BPI set and the Skill fixtures guard against known category-drift and “procurement knowledge only” failures.

## Core rules

1. Build an independent P1/P2/P3 Attribute plan for every Topic before writing Prompts. Topic is the primary monitoring unit; the same Attribute may have different priorities across Topics.
2. Allocate Prompt counts from each Topic’s useful Attribute coverage. Topics may have different totals, 10–25 per Topic is a soft planning range, and the complete batch must contain no more than 60 Prompts. Do not create repetitive questions to fill a quota.
3. Discovery must be a strict majority inside every Topic: `Discovery > Competitor + Verification + Accuracy + Evaluation + Category Awareness`. An aggregate majority across the batch cannot compensate for a Topic that fails this rule.
4. Each applicable competitor receives exactly one controlled Competitor Prompt per Topic. Verification, Accuracy, target-brand Evaluation, and Category Awareness use per-Topic counts of `1/0/1/1` by default.
5. Presales Evaluation measures only the target brand. Competitor sentiment matrices are deferred to aftersales monitoring so they do not displace Discovery coverage.
6. Discovery and Category Awareness do not name the target brand or competitors. Competitor Prompts name the target brand and one applicable competitor; Verification and Evaluation name only the target brand.
7. Every Prompt uses free `tags` for its default Intent, actual Branded or Non-Branded scope, and applicable Attributes. Tags do not override `analysis_type` or `formal_visibility_eligible`.
8. The product category and purchasing object must remain clear from the wording. Questions that drift to another supplier set, ask only for generic procurement knowledge, or add facts not supported by the Case are invalid.

## Validation

```bash
python3 -m unittest discover -s skills/geo-presales-prompt-builder/evals -p 'test_*.py'
python3 -m unittest discover -s skills/geo-presales-report/scripts/tests -p 'test_*.py'
```

The test suite is self-contained and does not call external AI platforms.
