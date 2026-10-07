## 2025-05-18 - Path Traversal Prevention in Artifact Reference Resolution
**Vulnerability:** Artifact reference paths loaded from JSON specs (e.g. `admission_record_ref`, `executor_visible_ref`) were resolved using `Path.resolve()` without checking if the resolved path stayed within `artifact_root`. This permitted path traversal outside the artifact root directory.
**Learning:** Resolving relative or absolute paths with `Path.resolve()` does not enforce directory boundaries unless explicitly checked against `root.resolve()`.
**Prevention:** Always verify `path.is_relative_to(root.resolve())` when resolving user-supplied or spec-defined file paths against a root directory.
