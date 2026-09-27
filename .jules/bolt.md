## 2025-05-20 - Hoist File Hashing out of Dataset Loops
**Learning:** In NDV Python tools processing candidate datasets, helper functions like `sha256_file` re-read entire files from disk on every iteration if called inside a loop.
**Action:** Always pre-compute and store file SHA-256 digests in local variables before looping over candidates or items.
