# Reuse repository steward readiness v2

## Contract and evidence boundary

Use the existing GitHub-native observer and five unchanged shell scripts. No LLM, runtime, custom policy engine or external service is needed. The versioned manifest `repository-steward-readiness-reuse-manifest-v1.json` pins qualified source commits, common Git blob identities and the two workflow profiles.

This is a pinned installation contract, not a reusable release or a third-repository PASS. NDV and RJ native execution remains attributable to their own evidence. Closure reporting, Scorecard, labels and stale automation have separate contracts and are not included in this readiness-only bundle. Steward authority remains READ/REPORT.

## Installation profiles

| Profile | Source commit | Automatic invocation |
| --- | --- | --- |
| NDV | ed1698905f04f87c6792baf570544fe714bc059e | completed CI workflows, native current-head association; supports observed pull_request and dynamic CodeQL |
| RJ | 5ae90995d235714d622cbc0f7b81005efc62bb92 | completed `ci` pull_request workflow, native current-head association |

Copy the five manifest `common_files` to their existing paths, plus the selected profile's observer and classifier-test workflows. Obtain files from that exact commit, not a moving `main`. Keep the v1 compatibility classifier because v2 sources it and historical manual reproduction uses it.

Use NDV's profile when workflow names vary; it excludes its own observer to prevent recursion. Use RJ's profile when `ci` is the actual source workflow; adapt that name to the target's native workflow name if necessary and record the resulting deviation. The observer must execute from the default branch, consume no PR code/artifacts and stay outside the PR head rollup.

Bash, jq, gh and Git are the required runner tools. The current native workflows use `ubuntu-latest` and upstream `actions/checkout@v4`, preserving the qualified source configuration. No provider credential or paid model call is required.

Verify files using Git's native `git hash-object -- <path>` against the manifest's `git_blob_sha` before changing a target profile. These are Git blob SHA-1 identities, not raw-file SHA-256 digests. The two profiles must not be described as byte-identical workflows.

## Frozen verification gate

Before implementation acceptance, the hosted reuse-contract workflow must check out the literal candidate head and each fixed source commit independently. It must compare all five common file blobs, each profile's two workflow blobs, check shell syntax, then execute the unchanged v1/v2 and association matrices from each pinned source. Record exact candidate head, source commit, run and jobs.

These checks qualify the pinned common-core identity and synthetic execution only. The manifest is DOCUMENTED/IMPLEMENTED until those commands execute. Workflow presence or successful checkout is not synthetic PASS.

## Target acceptance gate

For a new repository, inspect its native CI and permissions, record the installed head and profile deviations, and execute the existing synthetic matrices on the target. Activate on the default branch only after its implementation checks pass. Then open a minimal non-merged documentation fixture and inspect automatic source association, exact current head and native v2 fields; record runs/jobs and absence from the head check rollup. Close the fixture without merge and retain the branch.

A positive candidate requires OPEN, isDraft=false, CLEAN, MERGEABLE, SUCCESS and an allowed native review decision (APPROVED or an explicit native null normalized to NONE). Missing, malformed, stale or uncertain data stays fail-closed. Never reconstruct branch policies locally or treat unavailable policy reads as PASS.

Do not repeat the entire historical policy suite in every repository. Requalify the installation, target-native observations and actual deviations. Optional uninduced states remain NOT_PROVEN. Unchanged-source synthetic evidence and native target evidence are separate.

No automatic merge, review, issue closure, release, rerun, branch deletion or repository-rule mutation is enabled by installation. An operator's permission to merge implementation PRs is separate from this contract.

## Existing native references

- NDV: `docs/repository-steward-readiness-v2-evidence.md` and `docs/repository-steward-automatic-readiness-ndv.md`.
- RJ: `docs/engineering/repository-steward-readiness-portability-evidence.md` and `docs/engineering/repository-steward-automatic-observation-evidence.md`.

## Execution status

```text
PINNED_REUSE_CONTRACT = DOCUMENTED / IMPLEMENTED
TWO_PROFILE_IDENTITY_AND_MATRICES = NOT_EXECUTED
THIRD_REPOSITORY_INSTALLATION = NOT_PROVEN
```
