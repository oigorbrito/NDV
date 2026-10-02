## 2025-10-02 - Path Traversal in Spec Reference Resolution
**Vulnerability:** Reference path resolution in tooling allowed path traversal outside `artifact_root`.
**Learning:** `Path.resolve()` resolves `..` segments, but without validating `p.is_relative_to(root.resolve())`, resolved paths can escape the expected root folder.
**Prevention:** Always validate `p.is_relative_to(root.resolve())` after calling `Path.resolve()` when resolving paths specified in user input or external config files.
