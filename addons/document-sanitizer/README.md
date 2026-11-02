# Document Sanitizer add-on

A customer-hosted Azure Function that extracts text from uploaded documents and redacts sensitive data.

- Design: [../../docs/addons/document-sanitizer-design.md](../../docs/addons/document-sanitizer-design.md)
- How it ships: [../../docs/addons/adr-001-document-sanitizer-distribution.md](../../docs/addons/adr-001-document-sanitizer-distribution.md)
- Customer quickstarts: [quickstart.en.md](quickstart.en.md), [quickstart.es.md](quickstart.es.md)

## For developers

```bash
pip install -r requirements.txt      # plus the test dependencies listed in the CI workflow
python3 -m unittest discover -s tests -v
python3 package.py                   # writes releases/addons/document-sanitizer/<version>/ (needs Azure CLI with Bicep)
```

`local.settings.json` is git-ignored. Copy `local.settings.example.json` and fill in the endpoint for local runs.
