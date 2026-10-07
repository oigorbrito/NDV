## 2026-03-31 - Unsanitized Attribute Resolution in Log Parser Importer
**Vulnerability:** `import_parser` used `getattr(mod, parser_name, None)` on user/oracle-supplied string inputs, allowing access to internal or private module attributes and returning non-callable objects.
**Learning:** `getattr` on module objects can retrieve docstrings, builtins, and private attributes if input strings are not validated against leading underscores and callability.
**Prevention:** Always validate string attribute names against private/dunder prefixes (`_`) and assert `callable(...)` when dynamically resolving functions from modules.
