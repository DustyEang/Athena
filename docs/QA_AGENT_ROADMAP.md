# QA / Document Review Agent

Purpose: review submitted documents against SOPs, manufacturer charts
(including MC/component charts), and internal quality rules — at analyst
quality, in bulk.

State: **placeholder plugin (`plugins/qa_agent`) + this architecture.** The
"QA Agent" workspace is seeded in Athena.

## Architecture

```
uploads (bulk) ─► intake ─► extract ─► rule engine ─► scoring ─► report
                  queue      text,      SOP rules      0-100,     analyst-
                  (jobs      fields,    chart lookups  missing     friendly,
                  table)     tables     tolerance      info,       export xlsx/
                                        checks         failed      pdf later
                                                       checks
                                     ▲
                     knowledge base: SOP folder + charts folder
                     (folder grants + file index already exist)
```

## Data model (add when implementing)

- `qa_rules`: id, source (SOP doc/section), rule text, machine-checkable
  predicate (structured), severity
- `qa_charts`: manufacturer, component, parameter, expected value/range —
  imported from chart files (xlsx/csv/pdf-table)
- `qa_reviews`: document, timestamp, score, per-check results
  (pass/fail/missing + explanation + rule citation), reviewer overrides
- `qa_audit`: immutable history of reviews and overrides

## Review pipeline detail

1. **Extract**: text + key-value fields from the submitted doc (start with
   text formats; PDF extraction next)
2. **Deterministic checks first**: presence checks, value-vs-chart tolerance
   checks — cheap, explainable, no tokens
3. **Model checks second**: local model for classification/interpretation;
   Fable 5 only for ambiguous judgment calls (batch them)
4. **Score + explain**: every failed check carries the rule citation and a
   human explanation — analysts must be able to trust *why*
5. **Report**: per-document and per-batch; Excel/PDF export later

## Integration points already in place

- Folder grants + FTS indexing for SOP/chart folders (`files` router)
- Job-queue pattern reserved in SERVER_ROADMAP.md for bulk batches
- Flow tab/module via `flow.qa_review_queue`
- Workspace "QA Agent" for memory/goals/roadmap scoping
