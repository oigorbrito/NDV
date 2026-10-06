# NDV automatic readiness observation — prospective portability gate

## Scope and reuse decision

Reuse the GitHub-native `workflow_run` observer and commit-to-PR association wrapper from RJ commit `5ae90995d235714d622cbc0f7b81005efc62bb92`. Keep the NDV v1 and v2 classifier files unchanged. This changes invocation only, not the frozen decision protocol.

NDV has several CI names and dynamic CodeQL runs instead of RJ's single `ci` workflow. Listen for completed workflows using the native name glob, excluding this observer to prevent recursion. Accept only source events `pull_request` or `dynamic`; native association must identify exactly one OPEN PR whose current head equals the source head. Reject pagination, ambiguity, errors and obsolete heads. Recheck the head in the subsequent native readiness query.

The existing lightweight classifier workflow now tests every PR on its exact head, providing an automatic observation source for documentation-only PRs too. The observer checks out the default branch and consumes no PR artifacts or code. Permissions remain READ/REPORT. Manual commands remain available but are not required. Operator merge authorization does not grant merge authority to the steward.

## Frozen gate before activation

1. Inspect the diff: classifier blobs unchanged, read permissions, default-branch checkout, native association, head recheck and self-trigger exclusion.
2. On the exact implementation head, execute shell syntax, the existing v1/v2 matrix and the reused association matrix. Inspect logs and all head checks before operator merge.
3. After activation, open a minimal documentation fixture without posting an observer comment. Record fixture head, implementation commit, source run, observer run/job and actual ASSOCIATION / OBSERVATION lines.
4. Accept automatic invocation only if the native head association and v2 observation execute without adding the observer to the fixture head's check rollup. Accept a positive candidate only if the recorded native fields satisfy v2. Native transient states retain their actual classifications; do not fabricate them.
5. Close the fixture without merge, retain its branch and record evidence. Until gate 3–4 execution, automatic invocation is IMPLEMENTED / NOT_PROVEN, never PASS.

This gate does not reopen existing NDV v2 qualification or optional policy cases, and does not qualify unrelated NDV research PRs.
