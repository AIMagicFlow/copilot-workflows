# Copilot Workflows

A library of Microsoft Copilot Studio / Power Automate automation workflows, packaged by vertical. Each vertical is one Power Platform solution plus one SharePoint site, kept here as source and built into importable `.zip` files in English and Spanish.

| Vertical | Status | Solution | Spanish name |
|---|---|---|---|
| [Trend Researcher](verticals/trend-researcher/) | 1.5.0.0: RSS and document collection, classification, weekly digest, business cases, monthly signal cleanup, daily classifier stats | `TrendResearcher` | Vigilante de Tendencias |
| Lead generation, content creation, social media research | planned | — | — |

## Repository layout

```text
shared/                     reusable pieces every vertical can use
  i18n/{en,es}.yaml         common strings (impact/horizon labels, output language)
  prompts/                  prompt fragments (e.g. untrusted-evidence guard)
  sharepoint/               SharePoint schema fragments
verticals/<vertical>/
  vertical.yaml             solution name, version, locales, prompt versions
  solution/                 the solution source: same layout as an exported zip, with {{tokens}}
  prompts/                  prompts as reviewable text files
  i18n/{en,es}.yaml         localized names, descriptions and report strings
  sharepoint/lists/*.yaml   list schemas: stable internal names + per-locale display names
  sharepoint/libraries.yaml document libraries
  settings/                 deployment-settings example for pac CLI imports
  docs/                     quickstarts, design history, plans
tools/build.py              renders + validates + zips each vertical per locale
dist/                       local build output and release upload sets (git-ignored)
```

## Build and release

Requires Python 3.10+, PyYAML and lxml (`pip install -r requirements.txt`). No Windows or `pac` CLI needed. If `pwsh` is installed, the tests also run `provision.ps1` against a mock PnP module.

```bash
python3 tools/build.py                          # build every vertical and locale into dist/
python3 tools/build.py trend-researcher --locale es
python3 -m unittest discover -s tools/tests     # tests
python3 tools/build.py trend-researcher --release # write the upload set to dist/release/ (bump the version first)
```

Release zips are not stored in git. Each version is a GitHub Release, tagged `<vertical>-<version>` (for example `trend-researcher-1.4.0.0`), with the zips and `SHA256SUMS` attached. To publish a version, after merging to `main`:

```bash
gh release create trend-researcher-1.4.0.0 --title "Trend Researcher 1.4.0.0" --notes-file notes.md \
  dist/release/trend-researcher/1.4.0.0/*
```

The tag is created on the commit you are on, so run it from the commit that contains the release's source.

Each locale produces two files:

- `<Solution>_<version>_<locale>.zip`: import it in **make.powerapps.com → Solutions → Import solution**.
- `<Solution>_<version>_<locale>_sharepoint.zip`: the SharePoint kit, with two ways to create the lists and libraries: `lists/*.csv` (browser, CSV with schema) or `pnp/provision.ps1` + PnP template (IT, guarantees internal column names and verifies them). Also includes the quickstart.

The build fails if a token is unresolved, a flow uses an undeclared environment variable or connection reference, or a flow reads or writes a SharePoint column that the list schema does not define.

## Documentation

- [Architecture and conventions](docs/architecture.md): how source becomes a release, and the rules that keep flows portable between tenants.
- [Environment variables](docs/environment-variables.md): how flows use them, and why the designer doesn't show them.
- [Localization](docs/localization.md): what is translated where.
- [Adding a vertical](docs/adding-a-vertical.md).
- [Document Sanitizer add-on](docs/addons/document-sanitizer-design.md) (phase 1 built, hardening and large-file phases not started): customer-hosted Azure Function for document conversion and redaction; [how it ships](docs/addons/adr-001-document-sanitizer-distribution.md).
- Trend Researcher: [quickstart (es)](verticals/trend-researcher/docs/quickstart.es.md), [quickstart (en)](verticals/trend-researcher/docs/quickstart.en.md), [next workflows plan](verticals/trend-researcher/docs/plans/2026-11-02-doc-processing-and-business-case-plan.md).
