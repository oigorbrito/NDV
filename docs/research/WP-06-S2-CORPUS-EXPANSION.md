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

## Source-field quarantine

SWE-rebench V2 contains both executor-appropriate task text and fields that can leak gold-solution or grader information. Before any candidate can be admitted, the full row must be fetched from a pinned dataset revision and preserved as an admission-only artifact. The executor-visible projection must exclude at least:

- `patch`,
- `test_patch`,
- `FAIL_TO_PASS`,
- `PASS_TO_PASS`,
- `interface`,
- `meta`,
- `install_config`,
- `pr_description`.

These fields may be consumed by admission/verifier tooling when required, but are not automatically valid executor context. Any exception must be preregistered and justified as non-leaking.

Dataset preview snippets are discovery aids only. They are not sufficient for row integrity because previews can be truncated. Admission requires a full selected-row hash and a separate hash of the executor-visible projection.

## First prospective wave

`experiments/p1/s2-candidate-wave-01.json` freezes the first NDV-native discovery wave from SWE-rebench V2. It contains six candidates from six repositories and six languages (`ts`, `js`, `java`, `go`, `python`, `rust`).

The wave deliberately starts at `SCREENING`, not `ADMITTED`. Source metadata was discovered from a separately published pinned smoke manifest; that manifest is a discovery donor, not admission authority. NDV must independently acquire the full rows from the pinned dataset revision, verify source hashes/provenance, resolve image digests, audit verifier independence, and execute base/preservation checks.

Run the deterministic governance validator with:

```bash
python tools/ndv_validate_corpus_intake.py experiments/p1/s2-candidate-wave-01.json
```

The validator checks pinned revision format, candidate/base/hash structure, quarantine coverage, disposition validity, diversity summary consistency, holdout isolation, and stricter requirements for any future `ADMITTED` disposition. It does not execute models or tests.

## Task profiling

After admission criteria are satisfied, record structural profile features such as spread, novelty, centrality, tool intensity, sequential depth, parallelizability, specification ambiguity, verification strength, and context footprint. These profiles are descriptive inputs for later analysis; they must not be post-hoc labels derived from which executor won.

## Current gate

The current gate for Wave 01 is:

`FULL_PINNED_ROW_ACQUISITION_AND_QUARANTINE`

No candidate in Wave 01 is currently admitted. No treatment execution is authorized on these candidates.

## Stop conditions

Corpus acquisition may pause when the operational diversity target is met or when the marginal cost of finding another admissible task becomes high enough that the next scientific decision can already be made with the current development set. Rejections are first-class outputs.

## Claims

WP-06 can support claims about corpus admissibility, diversity, source integrity, quarantine, and reproducibility. It cannot support executor rankings, routing benefits, architecture superiority, or NDV product claims.
