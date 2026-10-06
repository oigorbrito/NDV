## 2026-03-30 - URL Scheme Validation in Parquet Acquisition Tool
**Vulnerability:** `ndv_acquire_s2_pinned_parquet.py` passed generated URLs directly to `urllib.request.urlopen()` without restricting the URL scheme, allowing potential arbitrary file access (`file://`) or local service exposure.
**Learning:** `urllib.request.urlopen()` supports multiple URL protocols beyond `http`/`https`.
**Prevention:** Always validate URL schemes (requiring `http` or `https`) before opening remote resources with `urllib.request.urlopen()`.
