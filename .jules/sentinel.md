## 2026-03-30 - Option Injection via Unvalidated Commit Hashes in Git Subprocess Invocations

**Vulnerability:** Passing unvalidated `base_sha` revision parameters directly to `git diff` or `git reset` allowed potential command option injection if a input parameter started with `-` (e.g. `--output=path`).
**Learning:** Even when using `subprocess` list argument forms (`["git", "diff", "--binary", base_sha]`), arguments starting with `-` placed before positional separators like `--` are still parsed as CLI flags by git.
**Prevention:** Validate that revision inputs are non-empty strings and do not start with `-` before constructing subprocess git argument lists.
