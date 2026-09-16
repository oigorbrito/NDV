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
3. source parquet identity freeze,
4. local SHA-256 verification of the parquet resolved at the pinned dataset revision,
5. full selected-row extraction,
6. admission-only / executor-visible quarantine split,
7. task-statement freeze and hash,
8. focal verifier identification,
9. verifier provenance and independence proof,
10. reproducible environment materialization,
11. base verifier execution,
12. preservation/regression baseline execution,
13. environment classification,
14. solution-isolation check,
15. exactly-one-family assignment,
16. explicit admission or rejection.

## Selection firewall

Treatment/model performance must not influence candidate selection. No admitted or prospective candidate should be run through Luna, a local model, a hosted-free model, or a strong executor until its admission disposition is frozen.

## Source snapshot and revision binding

`experiments/p1/s2-source-snapshot-01.json` freezes the source identity used by Wave 01:

- dataset: `nebius/SWE-rebench-V2`,
- split: `train`,
- revision: `475dd5e8703bb5fb22dd3c60b5d038b019eba1e0`,
- parquet: `data/train-00000-of-00001.parquet`,
- frozen parquet SHA-256: `0e0bf9355f892ad74ae98d4e1c404f39fd6654a8e351ee3e6ab162e4a64cd3ad`,
- expected row count: 32079.

The Hugging Face Dataset Viewer `/rows` API is useful for discovery and inspection but is not accepted as proof of pinned-row integrity because the API does not take a dataset revision parameter. Therefore, admission requires extracting rows from a parquet resolved at the pinned revision and verifying its SHA-256 locally before extraction.

## Strong acquisition path

Obtain the parquet from the exact pinned dataset revision, then run:

```bash
python tools/ndv_extract_pinned_swe_rebench_rows.py \
  --parquet path/to/train-00000-of-00001.parquet \
  --snapshot experiments/p1/s2-source-snapshot-01.json \
  --wave experiments/p1/s2-candidate-wave-01.json \
  --out .ndv-corpus/s2-w01/full-rows.jsonl \
  --quarantine-out .ndv-corpus/s2-w01/quarantine
```

The extractor performs four gates before quarantine:

1. recompute the complete parquet SHA-256 and require equality with the frozen source snapshot,
2. require the wave and source snapshot to reference the same dataset revision,
3. extract only the preregistered source row indices,
4. require every extracted row's `instance_id` and `base_commit` to match the frozen candidate record.

A SHA mismatch, row-index mismatch, instance mismatch, or base-commit mismatch is a hard failure. The tool does not execute any model or treatment.

`pyarrow` is required only for the local parquet extraction step; it is not part of NDV runtime architecture.

## Full-row quarantine

SWE-rebench V2 contains both executor-appropriate task text and fields that can leak gold-solution or grader information. Dataset preview snippets are discovery aids only and are insufficient for row integrity because they may be truncated.

The quarantine tool creates, per candidate:

- `admission-only.json` — the complete upstream row for verifier/admission work;
- `executor-visible.json` — a strict allowlist projection;
- `quarantine-manifest.json` — hashes binding the two views to the same pinned source row.

It also creates `quarantine-aggregate.json` for the wave.

The executor-visible projection is allowlist-based, not merely a blacklist. Current allowed fields are:

- `instance_id`,
- `repo`,
- `base_commit`,
- `problem_statement`,
- `language`.

Known gold/grader fields remain admission-only, including at least:

- `patch`,
- `test_patch`,
- `FAIL_TO_PASS`,
- `PASS_TO_PASS`,
- `interface`,
- `meta`,
- `install_config`,
- `pr_description`.

Critically, any future upstream field that NDV does not explicitly allow also remains admission-only by default. This prevents schema drift upstream from silently expanding executor context.

The external discovery donor's record hash is retained as provenance but is not assumed to use the same canonicalization as NDV. NDV computes its own canonical full-row SHA-256, task-statement SHA-256, and executor-visible projection SHA-256.

A candidate cannot become `ADMITTED` until the intake validator sees `quarantine_status=PASS` plus references and hashes for the quarantine artifacts.

Admission tooling may inspect full grader/gold metadata only for oracle validity, provenance, environment setup, and leakage control. That material must never be copied into executor-visible artifacts unless a new field is separately preregistered and demonstrated to be non-leaking.

## First prospective wave

`experiments/p1/s2-candidate-wave-01.json` freezes the first NDV-native discovery wave from SWE-rebench V2. It contains six candidates from six repositories and six languages (`ts`, `js`, `java`, `go`, `python`, `rust`).

The wave deliberately starts at `SCREENING`, not `ADMITTED`. Source metadata was discovered from a separately published pinned smoke manifest; that manifest is a discovery donor, not admission authority. NDV must independently acquire the full rows through the pinned parquet path, resolve image digests, verifier independence, and base/preservation behavior.

## Validation

Run the deterministic governance validator with:

```bash
python tools/ndv_validate_corpus_intake.py experiments/p1/s2-candidate-wave-01.json
```

It checks pinned revision format, candidate/base/hash structure, quarantine coverage, disposition validity, diversity-summary consistency, holdout isolation, and stricter requirements for any future `ADMITTED` disposition. It does not execute models or tests.

Synthetic tests cover both halves of the source-integrity boundary:

- `tools/test_ndv_extract_pinned_swe_rebench_rows.py` — parquet SHA and row identity binding;
- `tools/test_ndv_quarantine_swe_rebench_rows.py` — gold-field and unknown-field containment;
- `tools/test_ndv_validate_corpus_intake.py` — admission cannot bypass quarantine.

## Task profiling

After admission criteria are satisfied, record structural profile features such as spread, novelty, centrality, tool intensity, sequential depth, parallelizability, specification ambiguity, verification strength, and context footprint. These profiles are descriptive inputs for later analysis; they must not be post-hoc labels derived from which executor won.

## Current gate

The current gate for Wave 01 is:

`PINNED_PARQUET_SHA_VERIFICATION_AND_ROW_EXTRACTION`

No candidate in Wave 01 is currently admitted. No treatment execution is authorized on these candidates.

## Stop conditions

Corpus acquisition may pause when the operational diversity target is met or when the marginal cost of finding another admissible task becomes high enough that the next scientific decision can already be made with the current development set. Rejections are first-class outputs.

## Claims

WP-06 can support claims about corpus admissibility, diversity, source integrity, quarantine, leakage controls, and reproducibility. It cannot support executor rankings, routing benefits, architecture superiority, or NDV product claims.
