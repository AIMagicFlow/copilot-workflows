# Document Sanitizer Phase 1 (Synchronous core) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the customer-hosted Document Sanitizer add-on: a Python v2 HTTP-triggered Azure Function that extracts text from uploads, redacts caller terms, email and phone, and returns sanitized text with counts. Package it as a reproducible release folder, with Bicep, a custom connector definition, a deploy script and customer quickstarts.

**Architecture:** One Azure Functions app (`function_app.py` as a thin HTTP shell) over a pure-Python core in `app/`: type detection, then one extractor (direct decoding, HTML parser, or Document Intelligence behind a `DocumentReader` interface), then normalization, then a redaction pipeline with a fixed rule order and a post-redaction check. The core has no Azure SDK import except in `document_intelligence.py`, so unit tests run without a tenant. A stdlib-only packaging script writes the release folder.

**Tech Stack:** Python 3.12 (runtime 3.12 on the Function App), azure-functions, azure-ai-documentintelligence, azure-identity, beautifulsoup4, markdownify, regex (see Decision D3), unittest, Bicep, PowerShell 7 (deploy.ps1), GitHub Actions.

**Spec:** [docs/addons/document-sanitizer-design.md](../document-sanitizer-design.md) (§1 to §8 and §10 phase 1). Distribution: [docs/addons/adr-001-document-sanitizer-distribution.md](../adr-001-document-sanitizer-distribution.md).

## Global Constraints

- Endpoint: `POST /api/v1/documents/sanitize`, function-key auth (`authLevel: function`), connector header `x-functions-key`.
- Synchronous calls must finish in under about 100 s. Document Intelligence polling timeout: 90 s.
- Limits, all configurable: 10 MB per file (decoded), 5 MB of extracted text, 100 PDF pages in synchronous mode.
- Caller terms: at most 500 terms, at most 200 characters each. Escaped, never regex.
- Replacements are bracketed placeholders (`[REDACTED_EMAIL]`) that no later rule can match.
- Logs hold only: correlation ID, detected type, byte count, duration, extractor, status, counts. Never content, never matched values. Request-body logging is off.
- Managed identity for Document Intelligence. No service keys in app settings, repo or release.
- No secrets in any committed file. `local.settings.json` is git-ignored; only `local.settings.example.json` (placeholders) is committed.
- Output: UTF-8, LF line endings.
- Do not edit: `tools/build.py`, `tools/tests/`, `verticals/`, the Trend Research plan, `.github/workflows/build.yml`.

## Review Focus

1. A term containing regex metacharacters (`C++ (Ltd.)`, `A.B.`) must match literally and must not raise. Expected: redacted as typed. → Task 7.
2. Excel-exported CSV with a UTF-8 or UTF-16 BOM must decode without a BOM character in the output. → Task 3.
3. Numbers that are not phones (`2026-11-02`, `2026-11-02 10:30`, `1.2.0.0`, `1,234.56`) must not be redacted as phone. → Task 7.
4. Spanish text with accents and CRLF endings (`Señor Acme`, `Acmé`): output keeps accents and uses LF; `Acme` does not match inside `Acmé`. → Tasks 6 and 7.
5. A scanned PDF or blank file that yields no text must return `422 NOT_EXTRACTABLE`, not `200` with empty content. → Tasks 5 and 8.

Each line gets its pinning test in the owning task (noted above).

---

## Decisions this plan makes (for approval)

- **D1. Dependencies ship as source, not wheels.** The release zip holds function code only. `deploy.ps1` uses `az functionapp deploy --build-remote true`, so the Function App installs `requirements.txt` on its own. Reason: the zip stays small and reproducible, and no platform-specific wheels are bundled.
- **D2. Bicep compiles at packaging time.** `azuredeploy.json` is produced by `az bicep build`. The packaging script fails loudly if the Azure CLI with Bicep is missing; it never skips the file. Bicep is not installed in this environment, so this step is verified only in CI (Task 12).
- **D3. `regex` package for timeouts.** The design requires patterns to run with a timeout. Stdlib `re` has no timeout, so Phase 1 adds the `regex` package (its `timeout=` argument). Patterns are also rejected at load time if they contain a nested unbounded quantifier.
- **D4. Tests live in `addons/document-sanitizer/tests/`** (design §8), not `tools/tests/`, which is out of bounds.
- **D5. Local settings are not ignored yet.** `.gitignore` has `*.local.json`, which does not match `local.settings.json`. Task 0 adds an entry in an add-on `.gitignore`, so the root `.gitignore` stays untouched.
- **D6. Flex Consumption (FC1), identity-based storage.** Classic Consumption needs a storage key in app settings, which the design forbids.
- **D7. Error codes** (the design gives status codes only): `INVALID_REQUEST`, `INVALID_BASE64`, `FILE_TOO_LARGE`, `TEXT_TOO_LARGE`, `PAGE_LIMIT_EXCEEDED`, `UNSUPPORTED_TYPE`, `NOT_EXTRACTABLE`, `REDACTION_INCOMPLETE`, `THROTTLED`, `DEPENDENCY_ERROR`, `DEPENDENCY_UNAVAILABLE`, `DEPENDENCY_TIMEOUT`, `INTERNAL`. 401 and 403 come from the Functions host (`authLevel: function`), not app code.
- **D8. Output of text sources.** `markdown` output of TXT, CSV, MD, JSON, XML and LOG is the decoded text, unchanged. `text` output of HTML uses the parser's text content; `markdown` output of HTML uses markdownify. Document Intelligence returns `content`, which is requested as markdown or text (`output_content_format`, to be verified on the real service).
- **D9. Version.** `addons/document-sanitizer/VERSION` holds `1.0.0`, a semver string separate from the Dataverse four-part version.
- **D10. Connector host is a placeholder.** The swagger uses `your-sanitizer.azurewebsites.net`. Making the host an environment variable is wiring for the vertical, a later task, and ADR-001 lists it as a check before the first release.

---

## File Structure

```text
addons/document-sanitizer/
  .gitignore                     local.settings.json (D5)
  VERSION                        1.0.0
  README.md                      short pointer to the design and quickstarts
  function_app.py                HTTP trigger only; calls app.api
  host.json
  requirements.txt               exact pins
  local.settings.example.json    placeholders only
  package.py                     release builder (stdlib only)
  deploy.ps1                     customer deploy script
  app/
    __init__.py
    errors.py                    SanitizerError(status, code, message) + code table (D7)
    config.py                    Settings from environment variables
    models.py                    request parsing and the response shape
    api.py                       handle_sanitize(): the whole pipeline, no Azure types
    type_detection.py
    telemetry.py                 allowlisted metadata logging
    extraction/
      __init__.py
      router.py                  picks the extractor for a DetectedType
      text_extractor.py          BOM and encoding detection, decoding
      html_extractor.py          drops scripts, styles, comments, hidden elements
      document_intelligence.py   DocumentReader protocol and Azure implementation
    normalization/
      __init__.py
      markdown.py                markdownify for HTML; passthrough otherwise
      plain_text.py              get_text for HTML
    redaction/
      __init__.py
      engine.py                  pipeline order (§6), counts, post-check
      terms.py                   escaped, case-insensitive, word-bounded, longest first
      profiles.py                loads and validates config/redaction-profiles.json
      validators.py              phone digit-count and year guard; pattern checks
  config/redaction-profiles.json default-pii: email and phone rules
  infra/
    main.bicep
    main.parameters.example.json
  connector/
    apiDefinition.swagger.json
  tests/
    __init__.py
    test_type_detection.py  test_text_extractor.py  test_html_extractor.py
    test_document_intelligence_router.py  test_normalization.py
    test_terms.py  test_redaction.py  test_profiles.py
    test_api.py  test_logging_no_content.py  test_package.py  test_connector.py
    fixtures/                    small sample files, no real personal data
  quickstart.en.md
  quickstart.es.md
.github/workflows/document-sanitizer.yml   (outside the add-on, new file)
```

Run tests from the add-on folder: `cd addons/document-sanitizer && python3 -m unittest discover -s tests -v`.

---

### Task 0: Scaffold, ignore rules, pins

**Files:**
- Create: `addons/document-sanitizer/.gitignore`, `VERSION`, `README.md`, `host.json`, `requirements.txt`, `local.settings.example.json`, `app/__init__.py`, `tests/__init__.py`

**Interfaces:**
- Consumes: none
- Produces: package roots `app` and `tests` importable from the add-on folder.

- [ ] **Step 1: Write the ignore file.** `.gitignore` contains `local.settings.json`, `.python_packages/`, `__pycache__/`, `*.pyc`, `.venv/`.
- [ ] **Step 2: Verify the ignore rule.** Run `git check-ignore -v addons/document-sanitizer/local.settings.json`. Expected: the matching line from the add-on `.gitignore`.
- [ ] **Step 3: Write `host.json`.** Extension bundle v4, `functionTimeout` `00:03:50`, Application Insights sampling on, request-body capture not configured.
- [ ] **Step 4: Write `requirements.txt` with exact pins.** Pick the latest stable release of each package at implementation time and pin it with `==`. Packages: `azure-functions`, `azure-ai-documentintelligence`, `azure-identity`, `beautifulsoup4`, `markdownify`, `regex`. Do not add `charset-normalizer` (the Phase 1 fallback is a configured encoding, see Task 3).
- [ ] **Step 5: Write `local.settings.example.json`.** Placeholders only: `DOCUMENT_INTELLIGENCE_ENDPOINT` set to `https://<your-resource>.cognitiveservices.azure.com/`, plus the settings in Task 1. No keys.
- [ ] **Step 6: Commit nothing.** Verify `git status` shows only the new add-on files.

---

### Task 1: Settings, errors, models

**Files:**
- Create: `app/errors.py`, `app/config.py`, `app/models.py`
- Test: `tests/test_config.py` (add to Task 8's list if preferred; the request-validation cases are in Task 8)

**Interfaces:**
- Produces:
  - `errors.SanitizerError(status: int, code: str, message: str, retry_after: int | None = None)`, a `Exception`.
  - `config.Settings` (frozen dataclass): `max_file_bytes=10_485_760`, `max_text_bytes=5_242_880`, `max_sync_pages=100`, `fallback_encoding="cp1252"`, `di_timeout_seconds=90`, `profile_path: Path`, `document_intelligence_endpoint: str | None`. Loaded by `config.load_settings(env: Mapping[str, str])`. Env names: `SANITIZER_MAX_FILE_BYTES`, `SANITIZER_MAX_TEXT_BYTES`, `SANITIZER_MAX_SYNC_PAGES`, `SANITIZER_FALLBACK_ENCODING`, `SANITIZER_DI_TIMEOUT_SECONDS`, `SANITIZER_PROFILE_PATH` (default: the packaged `config/redaction-profiles.json`), `DOCUMENT_INTELLIGENCE_ENDPOINT`.
  - `models.SanitizeRequest` (frozen): `file_name: str`, `content_type: str | None`, `content: bytes`, `output_format: Literal["markdown", "text"]`, `profile: str`, `terms: tuple[TermIn, ...]`, `correlation_id: str`. `TermIn(term: str, replacement: str)`.
  - `models.parse_request(body: bytes) -> SanitizeRequest` raises `SanitizerError` (400).
- Behavior: `load_settings` raises `ValueError` for non-integer or negative numbers; `parse_request` rejects invalid Base64 with `INVALID_BASE64`, a missing `fileName` or `contentBase64`, an `outputFormat` other than `markdown`/`text`, more than 500 terms, or a term over 200 characters, all with `INVALID_REQUEST` except Base64.
- Default `replacement` for a term is `[REDACTED_TERM]`; a replacement over 50 characters is `INVALID_REQUEST`.

- [ ] **Step 1: Write failing tests** in `tests/test_config.py`: defaults when env is empty; an override is parsed as int; `"abc"` raises `ValueError`.
- [ ] **Step 2: Write failing tests** for `parse_request` in `tests/test_models.py`: valid body parses; `"contentBase64": "%%%"` gives `INVALID_BASE64` (400); 501 terms gives `INVALID_REQUEST`; term of 201 characters gives `INVALID_REQUEST`; missing `fileName` gives `INVALID_REQUEST`.
- [ ] **Step 3: Run them.** `python3 -m unittest tests.test_config tests.test_models -v`. Expected: FAIL, modules missing.
- [ ] **Step 4: Implement** the three modules to the interfaces above.
- [ ] **Step 5: Run them.** Expected: PASS.

---

### Task 2: Type detection

**Files:**
- Create: `app/type_detection.py`
- Test: `tests/test_type_detection.py`, fixtures in `tests/fixtures/`

**Interfaces:**
- Produces: `detect(data: bytes, file_name: str, content_type: str | None) -> DetectedType`, where `DetectedType` is a `str` Enum with values `txt, csv, md, json, xml, log, html, pdf, docx, xlsx, pptx, jpeg, png, bmp, tiff, heif`. Raises `SanitizerError(415, "UNSUPPORTED_TYPE")` for unknown, legacy OLE2 (`D0 CF 11 E0`), macro-enabled OOXML (contains `xl/vbaProject.bin`, or a `macroEnabled` content type), and text that contains a NUL byte.
- Rules: magic bytes first (PDF `%PDF-`; PNG `89 50 4E 47 0D 0A 1A 0A`; JPEG `FF D8 FF`; BMP `BM` with `.bmp`; TIFF `II*\0` or `MM\0*`; HEIF `ftyp` at offset 4 with brand `heic`, `heix`, `mif1` or `msf1`; ZIP `PK\x03\x04` with `[Content_Types].xml`, then `word/`, `xl/` or `ppt/` decides docx, xlsx or pptx). For text types there are no magic bytes: use the extension, then the NUL check. `.htm` and `.html`, or content starting with `<!doctype html` or `<html` (case-insensitive, after whitespace), give `html`. A document or image extension with no matching signature gives `UNSUPPORTED_TYPE`.

- [ ] **Step 1: Write failing tests**, one per type: a minimal valid byte header for each (for example `b"%PDF-1.7\n"`, `b"\x89PNG\r\n\x1a\n"`), a `.csv` text, a `.html` file, plus negatives: `.doc` with OLE2 header gives 415; `.xlsm`-style zip with `xl/vbaProject.bin` gives 415; `.txt` with `b"\x00"` gives 415; `.exe` with `MZ` gives 415; `.pdf` extension with text content gives 415.
- [ ] **Step 2: Run** `python3 -m unittest tests.test_type_detection -v`. Expected: FAIL.
- [ ] **Step 3: Implement** `detect` to the rules above.
- [ ] **Step 4: Run.** Expected: PASS.

---

### Task 3: Text extractor

**Files:**
- Create: `app/extraction/text_extractor.py`, `app/extraction/__init__.py`
- Test: `tests/test_text_extractor.py`

**Interfaces:**
- Produces: `decode(data: bytes, fallback_encoding: str) -> str`. Raises `SanitizerError(422, "NOT_EXTRACTABLE")` when the result is empty after `strip()`, or when decoding fails with the fallback too.
- Order: UTF-8 BOM (`EF BB BF`) → strip it. UTF-16 BOM (`FF FE` or `FE FF`) → decode UTF-16 and strip the BOM. Otherwise strict UTF-8. Otherwise the fallback encoding. The BOM is never in the output.

- [ ] **Step 1: Write failing tests:**
  - `decode(b"\xef\xbb\xbfNombre,Empresa\n", "cp1252") == "Nombre,Empresa\n"` (Review Focus 2).
  - UTF-16 LE with BOM `"Acme\n".encode("utf-16")` decodes to `"Acme\n"`.
  - `decode("Señor".encode("cp1252"), "cp1252") == "Señor"`.
  - `decode(b"   \n", "cp1252")` raises `SanitizerError` with status 422 and code `NOT_EXTRACTABLE`.
- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run.** Expected: PASS.

---

### Task 4: HTML extractor

**Files:**
- Create: `app/extraction/html_extractor.py`
- Create: `app/normalization/plain_text.py`, `app/normalization/markdown.py`, `app/normalization/__init__.py` (the parts used here; full normalization is Task 6)
- Test: `tests/test_html_extractor.py`

**Interfaces:**
- Produces: `extract_html(html: str, output_format: Literal["markdown", "text"]) -> str`. Drops `script`, `style`, `noscript`, `template` elements, comments, and elements with the `hidden` attribute, `aria-hidden="true"`, or inline `display:none` / `visibility:hidden`. Markdown uses markdownify with headings kept. Text uses the parser's text, with blank lines collapsed.

- [ ] **Step 1: Write failing tests:**
  - `<script>alert(1)</script><p>Hola Acme</p>` as text gives `"Hola Acme"`.
  - `<style>p{}</style><!-- secret --><h1>Titulo</h1>` as markdown contains `# Titulo` and neither `secret` nor `p{}`.
  - `<div hidden>Oculto</div><div style="display: none">Oculto2</div><p>Visible</p>` gives only `Visible`.
- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run.** Expected: PASS.

---

### Task 5: Document Intelligence reader and router

**Files:**
- Create: `app/extraction/document_intelligence.py`, `app/extraction/router.py`
- Test: `tests/test_document_intelligence_router.py`

**Interfaces:**
- Produces:
  - `AnalyzeResult(content: str, page_count: int)` dataclass.
  - `DocumentReader` Protocol: `analyze(data: bytes, output_format: Literal["markdown", "text"], timeout_seconds: int) -> AnalyzeResult`.
  - `AzureDocumentReader(endpoint: str, credential)` implements the protocol with `prebuilt-read`. Maps SDK errors: HTTP 429 → `SanitizerError(429, "THROTTLED", retry_after=...)`; 503 → `DEPENDENCY_UNAVAILABLE` (503); timeout → `DEPENDENCY_TIMEOUT` (504); other 5xx → `DEPENDENCY_ERROR` (502); HTTP 400 from the service (encrypted, corrupt) → `NOT_EXTRACTABLE` (422). The SDK import happens inside this module only.
  - `router.extract(detected: DetectedType, data: bytes, request: SanitizeRequest, settings: Settings, reader: DocumentReader | None) -> Extraction`, where `Extraction(text: str, extractor: str, page_count: int | None)`. Text types → `text_extractor.decode`; HTML → `html_extractor`; documents and images → `reader.analyze`. If `page_count > settings.max_sync_pages` → `SanitizerError(413, "PAGE_LIMIT_EXCEEDED")`. An empty result → `NOT_EXTRACTABLE`.
- Extractor names in metadata: `direct`, `html-parser`, `document-intelligence-prebuilt-read`.

- [ ] **Step 1: Write failing tests** with a `FakeReader` (returns a fixed `AnalyzeResult`, or raises a given error):
  - PDF with `page_count=3` returns text, extractor `document-intelligence-prebuilt-read`.
  - Scanned PDF where `content=""` gives 422 `NOT_EXTRACTABLE` (Review Focus 5).
  - `page_count=101` gives 413 `PAGE_LIMIT_EXCEEDED`.
  - Reader raising a 429 error passes through as 429 with `retry_after`.
  - Text type never calls the reader (`FakeReader` records calls; assert zero).
  - `AzureDocumentReader` mapping: test the error mapping with an injected `client` object that raises fake exceptions carrying `status_code`; no network.
- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement.** The Azure client is constructed lazily, so importing the module needs no credentials.
- [ ] **Step 4: Run.** Expected: PASS.

---

### Task 6: Normalization

**Files:**
- Modify: `app/normalization/markdown.py`, `app/normalization/plain_text.py`
- Test: `tests/test_normalization.py`

**Interfaces:**
- Produces: `normalize(text: str) -> str`: NFC Unicode normalization, CRLF and bare CR to LF, a leading BOM (`﻿`) removed, trailing whitespace on each line kept (no change to content).

- [ ] **Step 1: Write failing tests:** `"Señor\r\nAcme\r"` → `"Señor\nAcme\n"`; decomposed `"ñ"` → `"ñ"`; `"﻿Hola"` → `"Hola"`.
- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run.** Expected: PASS.

---

### Task 7: Redaction (terms, profiles, validators, engine)

**Files:**
- Create: `app/redaction/terms.py`, `profiles.py`, `validators.py`, `engine.py`, `app/redaction/__init__.py`
- Create: `config/redaction-profiles.json`
- Test: `tests/test_terms.py`, `tests/test_redaction.py`, `tests/test_profiles.py`

**Interfaces:**
- `terms.build_rules(terms: Sequence[TermIn]) -> TermRules`. Terms are stripped and NFC-normalized; empty after strip → `INVALID_REQUEST`. Terms that match case-insensitively (casefold) are merged; conflicting replacements → `INVALID_REQUEST`. One combined pattern: `(?<!\w)(?:t1|t2|…)(?!\w)` with `re.IGNORECASE`, alternatives sorted by length descending, each `re.escape`d. Matches map back to the replacement by casefold key, in one pass.
- `terms.apply(text, rules) -> tuple[str, int]`.
- `profiles.load(path) -> Profile`: `Profile(id, rules: tuple[Rule, ...])`, `Rule(id, pattern, replacement, enabled, validator)`. Rejects at load: a missing or unknown `id`, a pattern that does not compile, a pattern with a nested unbounded quantifier (`(…+)+`, `(…*)*`, `(…+)*`, detected by regex over the pattern source), a replacement not in `[...]` form.
- `profiles.get(profile_id) -> Profile`; unknown → `SanitizerError(400, "INVALID_REQUEST", "unknown profile")`.
- `validators.phone_ok(match_text: str) -> bool`: 9 to 15 digits after removing separators; reject if the text starts with a 4-digit year (`19xx` or `20xx`) and has no leading `+`.
- `engine.redact(text, term_rules, profile) -> RedactionResult(text, counts: dict[str, int])`, in this order: terms; then each enabled profile rule in file order (the email rule and the phone rule use `validators.phone_ok` as the acceptance check); counts keyed `term` and by rule id.
- `engine.still_matches(text, term_rules, profile) -> bool` is the post-check: any accepted match left after redaction → caller returns `422 REDACTION_INCOMPLETE`.
- `config/redaction-profiles.json`: `{"profiles": [{"id": "default-pii", "rules": [{"id": "email", "pattern": "...", "replacement": "[REDACTED_EMAIL]", "enabled": true}, {"id": "phone", "pattern": "...", "replacement": "[REDACTED_PHONE]", "enabled": true, "validator": "phone"}]}]}`. Email pattern: `[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}`. Phone pattern: `(?<![\w+])(?:\+\d{1,3}[ .-]?)?(?:\(\d{2,4}\)[ .-]?)?\d{2,4}(?:[ .-]\d{2,4}){1,4}(?!\w)`. Both are `regex`-package patterns with the 2-second timeout.

- [ ] **Step 1: Write failing `test_terms.py`** using the spec's examples, with `Acme` and `Acme Corp` and the replacement `[CUSTOMER]`:
  - `"Acme Corp signed"` with terms `Acme` and `Acme Corp` → `"[CUSTOMER] signed"`, count 1 (longest first).
  - `"acme and AcMe"` → `"[CUSTOMER] and [CUSTOMER]"`, count 2.
  - `"Acmeville"` → unchanged, count 0.
  - `"Acme's office, Acme-Corp"` → both replaced (apostrophe and hyphen are word boundaries).
  - `"Acmé"` → unchanged (Review Focus 4).
  - term `"C++ (Ltd.)"` on `"Pay C++ (Ltd.) now"` → redacted, no exception (Review Focus 1).
  - `"Señor Acme"` with term `"Señor"` → replaced.
  - two terms `"Acme"` with replacements `[A]` and `[B]` → `INVALID_REQUEST`.
- [ ] **Step 2: Write failing `test_redaction.py`:**
  - Email positives: `juan.perez@acme.es`, `a+b@sub.example.co.uk` → replaced. Negatives: `user@localhost`, `@acme`, `tool@v1` → unchanged.
  - Phone positives: `+34 612 345 678`, `(555) 123-4567`, `612-345-678`, `612.345.678`, `+1 555 123 4567` → replaced. Negatives (Review Focus 3): `2026-11-02`, `2026-11-02 10:30`, `1.2.0.0`, `1,234.56`, `12.50`, `ID 12345`, `20261102` → unchanged.
  - Order: a term `Acme` with the phone number in the same text: both counted under their own keys.
  - Post-check: `still_matches` is False on the output of `redact` for a mixed sample; True when a rule is artificially added whose replacement re-creates a match (test by building a `Profile` in the test).
  - Counts are integers only; the result object has no match strings (assert `not any(isinstance(v, str) for v in counts.values())`).
- [ ] **Step 3: Write failing `test_profiles.py`:** the shipped file loads; a pattern `(a+)+$` is rejected; a bad regex is rejected; a replacement `REDACTED` without brackets is rejected.
- [ ] **Step 4: Run.** Expected: FAIL.
- [ ] **Step 5: Implement.**
- [ ] **Step 6: Run.** Expected: PASS.

---

### Task 8: API pipeline

**Files:**
- Create: `app/api.py`
- Test: `tests/test_api.py`

**Interfaces:**
- Produces: `handle_sanitize(body: bytes, settings: Settings, reader: DocumentReader | None, correlation_id_fallback: str) -> HttpResult`, where `HttpResult(status: int, body: dict, headers: dict[str, str])`. Never raises: a `SanitizerError` becomes the §4 error body `{"status": "failed", "error": {"code", "message"}, "correlationId"}` with `Retry-After` when set; any other exception becomes 500 `INTERNAL` with a fixed message.
- Pipeline: `parse_request` → size check on decoded bytes (413 `FILE_TOO_LARGE`) → `type_detection.detect` → `router.extract` → `normalization.normalize` → text-size check (413 `TEXT_TOO_LARGE`) → `terms.build_rules` → `engine.redact` → `engine.still_matches` (422 `REDACTION_INCOMPLETE`) → 200 body `{"status": "completed", "outputContentType", "sanitizedContentBase64", "metadata": {"detectedType", "extractor", "pageCount", "redactionCounts", "warnings": []}, "correlationId"}`. `outputContentType` is `text/markdown; charset=utf-8` or `text/plain; charset=utf-8`.
- Error ordering: request validation before any Document Intelligence call.

- [ ] **Step 1: Write failing tests:** a text file with terms and an email → 200, decoded `sanitizedContentBase64` matches the expected text, counts correct; invalid JSON → 400; oversize (`max_file_bytes` lowered in the test) → 413 before the reader is called (assert zero calls); `.doc` → 415; empty `.txt` → 422; `FakeReader` raising 429 with `Retry-After: 7` → 429 with the header; an unexpected `RuntimeError` in the router → 500 `INTERNAL` and the body contains no input text.
- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run.** Expected: PASS.

---

### Task 9: Function entry point and telemetry

**Files:**
- Create: `function_app.py`, `app/telemetry.py`
- Test: `tests/test_logging_no_content.py`

**Interfaces:**
- `function_app.py`: `app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)`; one function `sanitize_document` at route `v1/documents/sanitize`, POST only. It reads the body bytes, builds the Settings and the Azure reader once (module-level, lazily), calls `api.handle_sanitize`, and returns `func.HttpResponse` with the JSON body and headers. It contains no logic.
- `telemetry.log_event(logger, *, correlation_id: str, **fields)`: allows only keys `detectedType, extractor, bytes, durationMs, status, pageCount, redactionCounts, errorCode`. Any other key raises `ValueError` (developer error, caught in tests). Values are scalars or the counts dict.
- `api.handle_sanitize` calls `telemetry.log_event` once at the end of each request, with metadata only.

- [ ] **Step 1: Write failing `test_logging_no_content.py`:** run `handle_sanitize` on a text file containing the marker `SECRET-MARKER-7731` and the term `Acme`, with a `logging` handler attached to every logger (root and `app`). Also run the failure path (422 on a blank file, which includes a marker in the name). Assert: no record's `getMessage()`, `args`, or `exc_text` contains the marker, `Acme`, or the email; the records contain only the allowed keys. Also patch `telemetry.log_event` to a spy and assert every kwarg name is in the allowlist.
- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement** `telemetry.py`, then `function_app.py`, then the logging call in `api.py`.
- [ ] **Step 4: Run** the whole suite: `python3 -m unittest discover -s tests -v`. Expected: PASS.
- [ ] **Step 5: Local smoke test (no tenant).** Confirm the module imports: `python3 -c "import function_app"` from the add-on folder. Expected: no error. The Azure runtime itself is not run here (see the checklist).

---

### Task 10: Release packaging

**Files:**
- Create: `addons/document-sanitizer/package.py`
- Test: `tests/test_package.py`

**Interfaces:**
- CLI: `python3 package.py [--out-root <repo>/releases] [--bicep az]`. Output: `<out-root>/addons/document-sanitizer/<version>/` containing `document-sanitizer-<version>.zip`, `azuredeploy.json`, `deploy.ps1`, `quickstart.en.md`, `quickstart.es.md`, `SHA256SUMS`. Refuses to overwrite an existing version folder (like `build.py`).
- Zip: entries are `function_app.py`, `host.json`, `requirements.txt`, `app/**`, `config/**`, sorted; no tests, infra, connector, `local.settings*`, `__pycache__`. Fixed timestamp `(1980, 1, 1, 0, 0, 0)`, `ZIP_DEFLATED`, no extra file attributes beyond the default.
- `azuredeploy.json`: `az bicep build --file infra/main.bicep --outfile <tmp>`. If the command is missing, fail with a clear message; never skip.
- `SHA256SUMS`: `<hex>  <name>` lines, sorted by name.
- Version read from `VERSION`.

- [ ] **Step 1: Write failing `test_package.py`:** call the zip builder function (not the CLI) with a temp output dir; run it twice into two dirs; assert the zips are byte-identical and the `SHA256SUMS` match. Assert zip names exclude `tests/`, `infra/`, `local.settings.json`, and include `function_app.py`. For Bicep, pass a fake bicep command (a small script that writes a file) so the test does not need Azure CLI.
- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement.** Stdlib only.
- [ ] **Step 4: Run.** Expected: PASS.
- [ ] **Step 5: Verification step.** Run `python3 package.py --out-root <scratchpad>` without bicep on PATH. Expected: exits non-zero with the missing-bicep message. (Real output is produced in CI, Task 14.)

---

### Task 11: Custom connector definition

**Files:**
- Create: `addons/document-sanitizer/connector/apiDefinition.swagger.json`
- Test: `tests/test_connector.py`

**Interfaces:**
- Swagger 2.0. `host: "your-sanitizer.azurewebsites.net"` (placeholder, D10). `schemes: ["https"]`. `securityDefinitions.api_key` = `{"type": "apiKey", "in": "header", "name": "x-functions-key"}`, applied globally. One operation `SanitizeDocument`, `POST /api/v1/documents/sanitize`, body schema matching §4 (`fileName`, `contentType`, `contentBase64`, `outputFormat` enum, `profile`, `terms` array max 500 with `term`/`replacement` max 200/50, `correlationId`). Responses: 200 with the §4 success schema; 400, 401, 403, 413, 415, 422, 429, 500, 502, 503, 504 with the error schema. The 200 response carries `x-ms-visibility: "internal"` only if needed; do not add it otherwise.

- [ ] **Step 1: Write failing `test_connector.py`:** the file parses as JSON; `swagger == "2.0"`; the security header is `x-functions-key`; the operation path is `/api/v1/documents/sanitize`; no key-like literal (regex for 32+ character base64 or hex) appears anywhere in the file; `terms` `maxItems` is 500.
- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Write the file.**
- [ ] **Step 4: Run.** Expected: PASS.

---

### Task 12: Bicep template

**Files:**
- Create: `addons/document-sanitizer/infra/main.bicep`, `infra/main.parameters.example.json`

**Interfaces:**
- Parameters: `location` (default `resourceGroup().location`), `namePrefix` (3–12 lower-case letters or digits), `documentIntelligenceSku` (default `S0`).
- Resources:
  - Storage account: `allowSharedKeyAccess: false`, TLS 1.2, HTTPS only, no public blob access. Deployment container for the Flex package.
  - Log Analytics workspace and workspace-based Application Insights.
  - Document Intelligence (`kind: 'FormRecognizer'`, `disableLocalAuth: true`, `customSubDomainName` set).
  - Flex Consumption plan (FC1, Linux, Python 3.12) and Function App with system-assigned identity, `functionAppConfig` using the deployment container with identity auth, `AzureWebJobsStorage__accountName`, `DOCUMENT_INTELLIGENCE_ENDPOINT`, `APPLICATIONINSIGHTS_CONNECTION_STRING`. No key-based values.
  - Role assignments for the function identity: Cognitive Services User on the Document Intelligence account (built-in role `a97b65f3-24c7-4388-baec-2e87445bc073`, to be confirmed in the checklist), Storage Blob Data Owner, Storage Queue Data Contributor, Storage Table Data Contributor on the storage account.
- Outputs: `functionAppName`, `functionAppHostName`. No keys in outputs.

- [ ] **Step 1: Write the template.** Verification here: read it back; no `listKeys` or `listSecrets` calls; no secret parameters.
- [ ] **Step 2: Verification step (CI only).** `az bicep build --file infra/main.bicep` in the workflow (Task 14). Locally the Azure CLI is not installed, so the step is recorded as not run in the final report.

---

### Task 13: Deploy script and quickstarts

**Files:**
- Create: `addons/document-sanitizer/deploy.ps1`, `quickstart.en.md`, `quickstart.es.md`, `README.md`

**Interfaces:**
- `deploy.ps1 -ResourceGroup <name> -Location <region> -NamePrefix <prefix> [-PackagePath <zip>]`: checks `az` and login; creates the resource group; deploys `azuredeploy.json` with the parameters; deploys the zip with `az functionapp deploy --type zip --build-remote true`; prints the host name (`https://<host>`). It never prints or writes a key. It tells IT where to copy the function key (Azure portal: Function App → Functions → sanitize_document → Function Keys).
- Quickstarts: English and Spanish, same structure. Sections: prerequisites, deploy, set `<prefix>_SanitizerHost` and create the connection with the key (the Power Platform steps follow ADR-001), redaction profile, limits, the errors table, and a **Manual acceptance checklist** (see below).

**Manual acceptance checklist** (not verified here; must be run in a real tenant):
- [ ] Document Intelligence `prebuilt-read` on a digital PDF, a scanned PDF, DOCX, XLSX, PPTX, and a JPEG: output shape (`content`, `pages`) matches what the code reads; `output_content_format` is accepted for the API version pinned.
- [ ] Encrypted and corrupt files produce 422 `NOT_EXTRACTABLE` (confirm the service's HTTP status for these).
- [ ] The managed identity can call Document Intelligence with `disableLocalAuth` on; the built-in role ID in Task 12 is correct.
- [ ] Deployment: `azuredeploy.json` deploys in an empty resource group; `az functionapp deploy --build-remote true` installs `requirements.txt` on Flex Consumption.
- [ ] A synchronous request on a 10 MB file finishes under 100 s.
- [ ] Function key auth: a request without `x-functions-key` gets 401.
- [ ] Application Insights contains no request bodies, and no document text, after a test run.
- [ ] Connector: the host placeholder is replaced per environment (ADR-001 check); the custom connector accepts the key in a Spanish environment; a `202` + `Location` pattern is not needed in Phase 1.

- [ ] **Step 1: Write `deploy.ps1`** and both quickstarts.
- [ ] **Step 2: Verification.** Parse check on PowerShell: `pwsh` is not installed here, so it is verified in CI (Task 14) with `pwsh -NoProfile -Command "[System.Management.Automation.Language.Parser]::ParseFile(...)"`. Do not claim it passed locally.
- [ ] **Step 3: Check the quickstarts contain no secrets or tenant values** (manual read).

---

### Task 14: CI workflow

**Files:**
- Create: `.github/workflows/document-sanitizer.yml`

**Interfaces:**
- Triggers: `push` to `main` and `pull_request`, with `paths: addons/document-sanitizer/**`, `releases/addons/document-sanitizer/**`, and the workflow file.
- Jobs (ubuntu-latest, Python 3.12):
  1. `pip install -r addons/document-sanitizer/requirements.txt`, then `python3 -m unittest discover -s addons/document-sanitizer/tests -v`.
  2. Install Azure CLI with Bicep (`az bicep install`), `pwsh` already present; run `az bicep build --file addons/document-sanitizer/infra/main.bicep`; parse `deploy.ps1` with `pwsh`.
  3. Build the release into a temp directory (`package.py --out-root "$RUNNER_TEMP/out"`), build twice, and compare `SHA256SUMS`: they must match.
  4. Fail if the committed release folder for the current VERSION exists and differs from the fresh build (`cmp` on each file); if it does not exist, print a notice and pass.
- The existing `build.yml` is not changed.

- [ ] **Step 1: Write the workflow.**
- [ ] **Step 2: Verification.** `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/document-sanitizer.yml'))"` parses. The workflow itself runs only in GitHub; the result is reported as not run here.

---

## Self-review

**1. Spec coverage** (design §1 to §8, §10 phase 1, the user's list):
- Text, HTML, Document Intelligence extraction → Tasks 3, 4, 5. ✓
- Caller terms, email, phone, post-check → Task 7 (terms, engine, validators); post-check in Task 8. ✓
- Function-key auth → Task 9 (`authLevel`), Task 11 (connector), checklist. ✓
- Bicep with managed identity and DI role → Task 12. ✓
- Connector with x-functions-key and placeholder host → Task 11, D10. ✓
- Packaging, reproducible, SHA256SUMS → Task 10. ✓
- deploy.ps1, quickstarts → Task 13. ✓
- Tests: type detection (Task 2), each extractor (Tasks 3, 4, 5), terms (Task 7 with the Acme cases), email and phone pos/neg (Task 7), no log content (Task 9). ✓
- CI workflow → Task 14. ✓
- Status codes and error bodies of §4 → Tasks 1, 5, 8, D7. ✓
- Logging of metadata only → Task 9. ✓
- Limits 10 MB, 5 MB text, 100 pages → Tasks 1, 5, 8. ✓
- `local.settings.json` git-ignored → Task 0 (D5). ✓
- Not covered (phase 2 or 3, correctly out): Entra ID, rate limits, stricter signature checks, regression corpus, 202 jobs, money rule, personal names.

**2. Step scan:** Tasks 1 to 9 have test names and assertions with exact values. Tasks 10 to 14 specify the signatures, file contents and verification commands. No "TBD". Task 4 and 6 step bodies are describe-level, because the parser behavior is fixed by the test cases.

**3. Type consistency:** `SanitizeRequest`, `TermIn`, `Settings`, `DocumentReader`, `AnalyzeResult`, `Extraction`, `RedactionResult`, `Profile`, `Rule`, `HttpResult` are each defined once in the Interfaces blocks and used by the same names later. `DetectedType` values match the names used in Task 5 and the metadata `detectedType`.

**4. Review Focus:** Five lines; each has a pinning test in its owning task (Tasks 7, 3, 7, 6 and 7, 5 and 8). ✓

**5. Proportion:** The plan is long because there are 14 tasks, but code bodies are kept to signatures, test names and the spec's exact values.

---

## Execution Handoff

Plan complete and saved to `docs/addons/plans/2026-11-02-document-sanitizer-phase1-plan.md`. Please review the plan and the decisions D1 to D10 above. Does it capture what you want, and which execution approach should we use?

- **Subagent-driven**: a fresh subagent per task, with a reviewer after each. Most thorough. Tasks 5 and 7 are the riskiest; they mix interfaces and rule ordering.
- **Native**: I implement every task in this session, then one fresh reviewer checks the whole branch. Cheapest and fastest. Tasks depend on each other's interfaces, which the plan pins down.

I recommend **Native** for this plan, because the interfaces are fixed in the plan, the tasks are sequential and share the same small package, and the expensive mistakes (regex order, log leaks) are covered by named tests. Tell me which you prefer. I will not write any code until you approve.
