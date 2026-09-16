# WP-06 — P1-S2 Corpus Expansion

## Purpose

Expand the comparative development corpus under the historical verifier-first admissibility contract without exposing candidates to treatment execution during discovery.

## Historical continuity

The authoritative historical admission contract remains in `oigorbrito/dv` at commit `66f3a218fba800daed5d86fdfce386491b8ab0e8`, path `experiments/p1/task-admissibility-contract-v1.json`. Historical admitted tasks `D-F5-01` and `D-F6-01` retain their original provenance and are not rewritten as NDV-native discoveries.

The previous W8 screening found only those two tasks admissible; rejected candidates remain rejected for their recorded reasons unless genuinely new independent evidence changes the admissibility facts. Rejection history is not overwritten.

## Prospective intake

The machine-readable intake contract is `experiments/p1/s2-corpus-intake-v1.json`.

Operational target:

- about 9 admitted development tasks,
- at least 3 task families,
- at least 3 repositories,
- at least 2 languages.

This target is for useful comparative diversity. It is not itself a statistical power claim.

## Source priority

1. SWE-rebench V2 — primary development acquisition source.
2. OmniCode — secondary source for task-type diversity.
3. SWE-Bench Pro Verified — preserve where possible for later confirmation rather than tune on it immediately.
4. Terminal-Bench 2.0 — later heterogeneity/generalization source, not the primary P1-S2 SWE corpus.

A source being high priority does not admit any instance automatically.

## Candidate funnel

Every instance must pass, in order:

1. discovery and source metadata freeze,
2. exact pre-solution base identification,
3. task-statement freeze and hash,
4. focal verifier identification,
5. verifier provenance and independence proof,
6. reproducible environment materialization,
7. base verifier execution,
8. preservation/regression baseline execution,
9. environment classification,
10. solution-isolation check,
11. exactly-one-family assignment,
12. explicit admission or rejection.

## Selection firewall

Treatment/model performance must not influence candidate selection. No admitted or prospective candidate should be run through Luna, a local model, a hosted-free model, or a strong executor until its admission disposition is frozen.

## Task profiling

After admission criteria are satisfied, record structural profile features such as spread, novelty, centrality, tool intensity, sequential depth, parallelizability, specification ambiguity, verification strength, and context footprint. These profiles are descriptive inputs for later analysis; they must not be post-hoc labels derived from which executor won.

## Stop conditions

Corpus acquisition may pause when the operational diversity target is met or when the marginal cost of finding another admissible task becomes high enough that the next scientific decision can already be made with the current development set. Rejections are first-class outputs.

## Claims

WP-06 can support claims about corpus admissibility, diversity, and reproducibility. It cannot support executor rankings, routing benefits, architecture superiority, or NDV product claims.
