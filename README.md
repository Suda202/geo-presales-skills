# Overseas GEO Presales Skills

Private, versioned Skill packages for the Overseas GEO presales workflow.

## Included packages

- `skills/yao-overseas-geo-intent-miner/` generates and validates commercial English AI-search monitoring questions. It supports recommendation, comparison, and decision questions only; every question must preserve the category and purchasing object defined by its Topic.
- `skills/overseas-geo-presales-report/` consumes the validated question bank when generating an Overseas GEO presales report.
- `evals/v3/` contains nine validated, non-production evaluation inputs. The BPI set and the Skill fixtures guard against known category-drift and “procurement knowledge only” failures.

## Core rules

1. A question must lead the AI to recommend brands/suppliers or make a clear trade-off. Pure explanatory, checklist, or purchasing-process questions do not qualify.
2. The product category must be visible from the wording, whether through the category term, a natural variant, or a product-specific term.
3. The object being selected must stay in the Topic’s purchasing set. For example, an OEM/ODM battery-manufacturer Topic must not drift to thermal-management suppliers, containerized energy-storage systems, or large-project partners.
4. Each Topic has exactly one branded decision benchmark: `Evaluate the {category} company/product {brand} on {topic}`.

## Validation

```bash
python3 skills/yao-overseas-geo-intent-miner/evals/test_validator.py
python3 -m unittest discover -s skills/overseas-geo-presales-report/scripts/tests -p 'test_*.py'
```

The test suite is self-contained and does not call external AI platforms.
