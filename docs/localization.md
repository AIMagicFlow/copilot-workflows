# Localization

Each vertical builds one package per locale. A locale is declared in `vertical.yaml` (`es: {lcid: 3082}`) and needs an `i18n/<locale>.yaml` file with every key the English file has. A test enforces key parity.

## What is translated, and where

| Item | Mechanism | Source |
|---|---|---|
| Solution name and description, publisher name | `LocalizedName` / `Description` with `languagecode={{lcid}}` | `solution/solution.xml` + `i18n` `solution.*`, `publisher.*` |
| Flow names and descriptions | `Workflow Name`, `LocalizedName`, `Description` | `solution/customizations.xml` + `flows.*` |
| Connection reference names and descriptions | plain string (Dataverse has no per-language label here) | `customizations.xml` + `connections.*` |
| Environment variable names and descriptions | `displayname` / `description` labels | `environmentvariabledefinitions/*` + `env.*` |
| List environment variable defaults | localized list title | `{{list:Key}}` → `sharepoint/lists/*.yaml: title` |
| Weekly digest HTML, Teams message, publication title | `{{t:digest.*}}` tokens inside flow JSON strings | `Workflows/*.json` + `digest.*` |
| Impact and horizon labels in reports | flow expression that maps codes to `{{t:codes.*}}` | `shared/i18n` `codes.*` |
| AI output language (Summary, Limitations) | `{{t:classifier.outputLanguage}}` in the prompt | `prompts/*.md` + `shared/i18n` |
| SharePoint list titles, column display names, default view name | CSV-with-schema and PnP template per locale | `sharepoint/lists/*.yaml: title, fields[].display` + `shared/i18n` `sharepoint.*` |
| Provisioning script messages and help | `{{t:provision.*}}` in `shared/sharepoint/provision.ps1` | `shared/i18n` `provision.*` (no single or double quotes, `$` or backticks; a test enforces it) |
| Library display titles | set by the PnP template; renamed by hand on the CSV path (URL stays English) | `sharepoint/libraries.yaml` + quickstart |
| Quickstart | one file per locale | `docs/quickstart.<locale>.md` |

## What is deliberately not translated

- **SharePoint internal column names** (`field_1`, `PublishedAt`) and **library URL names** (`/Evidence`): flows depend on them.
- **Stored status codes** (`Ready`, `Classified`, `Digest`, `High`, `Near`): flows filter on them. Reports translate them for display.
- **Prompt instructions.** They stay in English, the language the classifier was validated in. Only the output language changes. Translating the instructions would mean revalidating classification quality.
- **Flow parameter keys** (`Site URL (tr_SiteURL)`): internal identifiers.

## One solution per language, not one multilingual solution

Dataverse can hold labels for several languages in one solution, but importing labels for a language that isn't provisioned in the target environment is undocumented, and the solution's base `languagecode` must be a language the environment has. Per-locale zips avoid both problems. The `uniqueName` and component IDs are identical across locales, so an environment can later switch language by importing the other zip: it updates the same solution in place.

## Adding a language (e.g. Portuguese)

1. `vertical.yaml`: add `pt: {lcid: 1046}`.
2. Copy `shared/i18n/en.yaml` → `pt.yaml` and `verticals/<v>/i18n/en.yaml` → `pt.yaml`, then translate.
3. Add `pt:` entries to every `title`, `description` and `fields[].display` in `sharepoint/lists/*.yaml`, and to `libraries.yaml`. Optionally add `seed.pt`.
4. Write `docs/quickstart.pt.md`.
5. Run `python3 tools/build.py <v> --locale pt` and the tests.
