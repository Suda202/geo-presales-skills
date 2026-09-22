# After-Sales Output Contract

This is the practical after-sales extension contract. It is intentionally
separate from the presales v8 fixed-quota validator.

## JSON

Recommended root fields:

```json
{
  "schema_version": "overseas-geo-question-bank/v8",
  "mode": "after-sales-strategic-topics",
  "config": {
    "brand_name": "Example",
    "official_domain": "https://example.com",
    "generation_stage": "discovery",
    "lifecycle_status": "hypothesis",
    "evidence_status": "hypothesis",
    "customer_confirmation": {"status": "pending"},
    "topics": [],
    "attribute_plan": [],
    "expected_total": 0,
    "competitor_selection": {}
  },
  "questions": []
}
```

`generation_stage` is optional for historical full v8 banks. When present, use
`discovery` or `diagnostic` for the dynamic handoff contract. The parent
presales builder may set `generation_stage: discovery` for new work while
leaving it absent for legacy full diagnostic banks. The extra fields in this
after-sales extension do not change the closed presales v8 schema. When a v8
uploader cannot accept them, emit them in sidecar schedule/evidence files
through an explicit adapter; never claim silent v8 compatibility.

Each question should contain:

- `question_id`
- `topic_id`
- `user_question`
- `zh_translation`
- `monitoring_prompt` equal to `user_question`
- `tags`
- `analysis_type`
- `formal_visibility_eligible`
- `intent_key`
- `quality_checks`

Recommended additional per-question metadata when useful:

- `region`
- `cadence`
- `evidence_refs`
- `evidence_status`
- `change_reason`
- `version`
- `lineage_id`
- `status` (`hypothesis`, `customer_confirmed`, `locked`, `retired`)

If the downstream uploader cannot accept these extra fields, keep them in a separate schedule or evidence file rather than dropping the information.

## CSV

The project-compatible baseline is:

`query,question_zh,topic,diagnosis_intent,tags,question_types,purchase_intent,persona_name,scene_name`

For a new after-sales consumer, prefer an explicit adapter with:

`query,question_zh,topic,region,intent,tags,cadence`

Do not silently mix the two column contracts. State which adapter is being delivered.

## Trial and Baseline Metadata

When collection is ready, retain the following in `config` or a separate
schedule/evidence artifact:

- `prompt_version`: immutable version or snapshot hash after customer lock;
- `customer_confirmation`: scope, product line, market/language, and evidence
  gaps;
- `baseline`: `status`, `window_days` (default `7`), `calendar_days: true`,
  `conditions_key`, `valid_samples_only`, and explicit failure handling;
- `collection_config`: market, language, platforms, model/mode, cadence, and
  other conditions required for comparability.

`formal_baseline`/`active` requires customer confirmation and a locked Prompt
version. `hypothesis` or `after_sales_signal` evidence cannot be formal-ready.
Semantically changed or new Prompts start new lineage/version and baseline;
retain history but do not concatenate it.

Use `window_days: 14` only after an anomaly diagnosis, recorded as
`baseline.anomaly_diagnosis`; it is not a default longer baseline.
Compute only from observed valid samples. Do not impute failures, fill missing
days, or concatenate non-consecutive valid days.

## Cadence

Cadence belongs in a separate schedule file or an explicit CSV column:

- Discovery: daily during a formal seven-calendar-day baseline, then weekly or
  otherwise as agreed.
- Evaluation and Competitor: as agreed or event-triggered; no fixed default
  quota or cadence is implied.
- Category Awareness: one-time baseline or occasional refresh.
- Baseline Discovery observation: the same cadence as the comparable Discovery
  set.

These are defaults, not hardcoded quotas. Record any client-specific cadence decision.

## Deterministic Quality Gates

Before delivery:

1. The chosen scope and stage are explicit. The recommended first-stage shape is one category observation Topic plus two same-product buying-scenario Topics; two Topics can be justified.
2. Topic names are short and each Prompt maps to exactly one Topic.
3. A customer-confirmed, locked, or formal Topic has at least five Prompts. A shorter hypothesis Topic is marked for merge, Tag treatment, or evidence completion rather than padded with rewrites. Topic counts may differ; no equalization is required.
4. Every Prompt has Topic, Region, Intent, Tags, English query, and Chinese translation.
5. Intent and Region are not duplicated inside Tags.
6. Competitor Prompts are one-to-one, use only frozen applicable competitors, and do not enter the natural Discovery count.
7. Category Awareness is low-frequency and not duplicated across every Topic without a reason; it is not the category observation Topic.
8. Prompt text is unique after normalization and semantically reviewed for duplicates.
9. New Prompts have evidence or are clearly marked as hypotheses requiring confirmation. Each new Prompt also records why a recognizable buyer would ask it and what independent decision, risk, candidate set, or applicability judgment it adds.
10. No cross-topic competitor, product-line, or category leakage.
11. CSV rows match JSON rows and all upload length limits.
12. Discovery Prompts contain no brand names, ask a commercial recommendation/selection question, and test one primary intent.
13. Trial review checks category/task fit, ambiguity, leading language, and duplication; target-brand mention is not a trial pass/fail criterion.
14. Formal baseline uses seven consecutive calendar days by default, observed
valid samples only; failures are not zeroes, missing days are not glued
together, and old/new Prompt versions are not concatenated.
15. Each Topic records a parent Search-Demand anchor or an explicit reason why no reliable Search-Demand signal is available.
16. A `discovery` generation stage contains Discovery Prompts only. Other
    intents are added later under their own evidence-backed purpose, not a fixed
    quota.
17. Attribute and Tag review covers scenarios, pains, procurement constraints,
    supply/service risks, and applicability boundaries when they affect buyer
    decisions; it is not limited to product features or technical parameters.
18. Attributes were derived in the rule document's four steps — twelve-category
    gap sweep, category-specific attributes from the three sources, one B2B/B2C
    line or an explicit split — and ranked by demand × standing to win ×
    deliverable before Topics were named. The delivery states the resulting
    Attribute order.
19. Prompt generation varied **region and language only**. Platform differences
    are handled in collection and reporting configuration, never as Prompt
    variants.
20. Any prompt-count claim cites the source of demand. No Prompt is described as
    high-frequency without frequency evidence.
21. The intent pass and the Prompt set reconcile **in both directions**: every
    P1/P2 intent is carried by at least one Prompt, and every Prompt's intent
    exists as a row in the client's intent table. The master table's intent
    column quotes the intent table verbatim. Run this as an explicit step — the
    two are drafted from different inputs and drift silently.
22. The evidence layer was checked for existence before being read as a finding.
    Two common cases both leave it unusable: a rough presales pass ran visibility
    only and produced no sentiment layer at all, and a run that marked only the
    branded evaluation questions yields a brand self-portrait rather than a
    competitor matrix. In either case the emptiness is not reported as evidence
    that competitors are clean; the standing-to-win judgement is marked
    provisional, the next evidence layer is used instead, and the gap is recorded
    as a process fix for the next presales run.
23. Where no theme shows a competitor negative, the optimisation labels are held
    as provisional and the deliverable states that no theme has a demonstrated
    opening yet, together with the counter-explanation that roundup-style answers
    rarely criticise. A second run of the same matrix is planned after the
    baseline so the judgement is longitudinal.
24. Before a Topic is reported as short of the five-Prompt floor, attribution was
    re-checked: Prompts filed under the wrong Topic were moved to where their
    actual purchase decision belongs and the counts recomputed. A shortfall
    resolved this way is a correction, not padding.
25. Every table in a client-facing confirmation document carries a 客户确认
    column on the write-what-to-change convention, and question numbering stays
    out of the document.

## Review Summary

The final delivery should state:

- active Topic count and Prompt count per Topic;
- the derived Attribute list and its ranking order;
- Prompt role counts, split so that Discovery (natural visibility) is
  distinguishable from named-brand Evaluation, Comparison, and Verification;
- additions, revisions, merges, and retirements;
- evidence source and confidence gaps, marked against the customer-input tiers
  (must-have / best-to-have / collected by us);
- cadence decisions;
- validator/test result and any intentional incompatibility with presales fixed-quota tooling.
