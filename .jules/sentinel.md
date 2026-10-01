# Sentinel Security Journal

## 2026-03-30 - Subprocess Target File Validation
**Vulnerability:** External script execution (`args.quarantine_tool`) via `subprocess.run` did not verify the target path's existence or file status prior to process invocation.
**Learning:** Invoking child process tools with CLI-supplied paths without verifying `.is_file()` can lead to unexpected unhandled exceptions or execution of non-existent/improper filesystem targets.
**Prevention:** Always validate that executable script arguments exist and are regular files (`is_file()`) before passing them to `subprocess.run`.
