# NDV Experimental Program

## Active research-path amendment — Luna-only composition

The current active path fixes one qualified executor/model surface: Codex + `gpt-5.6-luna` v4. Multi-model routing is no longer a prerequisite for the current research question.

The earlier P1 multi-model/routing program remains preserved and may be revisited, but it is not on the critical path. The active question is whether explicit decomposition/composition with the same Luna model improves the verified-success / total-cost frontier over direct Luna execution.

This is a controlled scope change, not evidence that composition works. The prospective protocol is `experiments/luna-only/luna-composition-protocol-v1.json` and the research note is `docs/research/LUNA-ONLY-COMPOSITION-TRACK.md`.

Because model selection is held constant, the active track may study composition headroom without first establishing multi-model routing headroom. It still must satisfy corpus, verifier, accounting, and holdout-isolation gates before treatment execution.

## P1 — Executor and routing economics

Question: which executor/policy treatment minimizes complete system resource cost per verified solved task while preserving success and reproducibility?

P1 must establish routing headroom before any router is implemented. Compare fixed strategies first, then measure retrospective oracle headroom. If the best fixed strategy is approximately as good as oracle selection, do not build a routing layer.

Current operational split:

- `PIPELINE_SMOKE_READY`: validates harness mechanics only.
- `P1_COMPARATIVE_READY`: requires enough admitted tasks and qualified treatment surfaces for the intended comparison.

## P2 — Continuity and handoff

Open only if recovery/restart/handoff cost is materially relevant after P1.

Compare workspace-only, full trajectory, generic compression, structured state, and structured state plus recent context. If workspace-only or an existing context method is equivalent, reject a custom NDV state layer.

## P3 — Composition

Open only if direct execution leaves measurable family-dependent composition headroom.

Compare direct, executor+verifier, planner+executor, planner+executor+verifier, parallel composition, and external orchestration where practical. Measure oracle composition before building selection logic.

## P4 — Sequential control

Open only if sequential decisions materially affect outcome and fixed cascades leave measurable regret.

Order of complexity:

`fixed -> fixed cascade -> deterministic rules -> LLM controller -> learned controller -> oracle comparison`

If deterministic rules are close to oracle or learned control, do not build a sophisticated controller.

## P5 — Integrated validation

Integrate only capabilities that survived prior gates. Compare strong/simple baselines, thin NDV, any justified fuller NDV, and maximal agentic composition where relevant. Include total overhead, ablations, distribution shift, and ecosystem change.

## Program-wide outcomes

Valid outcomes include `NO_BUILD`, `REUSE_ONLY`, `THIN_NDV`, `FULL_NDV_JUSTIFIED`, and `INCONCLUSIVE`.

Later phases are not milestones that must be reached; they are conditional experiments that may never need to run.