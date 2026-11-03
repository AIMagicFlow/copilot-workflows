# Environment variables

## Short answer

They are worth it, and they need no designer UI. An environment variable is a solution component with a **definition** (schema name, type, default) and a per-environment **current value**. When you import the solution, the import wizard asks for every variable that has no value. Flows read the variables as workflow parameters.

The Trend Researcher solution exported from the UI already defined five variables (`tr_SiteURL`, `tr_DailyClassificationLimit`, …), but **no flow used them**: every action hardcoded the site URL and list GUIDs. Version 1.1.0.0 wires them in.

## Why you couldn't find them in the Copilot Studio designer

Microsoft documents the environment-variable picker for the **Power Automate** cloud-flow designer: in a SharePoint *Site address* or *List name* field, choose **Enter custom value** and the variables appear in dynamic content. No equivalent picker is documented for the Copilot Studio **agent-flow** designer. Editing flows as code here avoids the question entirely.

## How a flow uses one

Two pieces in the flow JSON (`verticals/*/solution/Workflows/*.json`):

```json
"definition": {
  "parameters": {
    "Site URL (tr_SiteURL)": {
      "defaultValue": "",
      "type": "String",
      "metadata": { "schemaName": "tr_SiteURL" }
    }
  },
  "actions": {
    "Get_RSS_Sources": {
      "inputs": { "parameters": {
        "dataset": "@parameters('Site URL (tr_SiteURL)')",
        "table":   "@parameters('Sources list (tr_SourcesList)')"
      } }
    }
  }
}
```

- The parameter key is `"<Display name> (<schema name>)"` by convention. Only `metadata.schemaName` binds it to the variable, so the key stays in English even when the label is translated.
- Types: `String`, `Int` (Number variable), `Float`, `Bool` (Boolean variable). This matches Microsoft's CoE Starter Kit.
- Every variable needs a definition in `solution/environmentvariabledefinitions/<schema>/environmentvariabledefinition.xml`. The build fails if a flow references a parameter without one.

## Variables in Trend Researcher 1.1.0.0

| Schema name | Type | Default | Used by |
|---|---|---|---|
| `tr_SiteURL` | Text | (required at import) | all flows: `dataset` |
| `tr_ResearchBriefsList` | Text | localized list title (`ResearchBriefs` / `Briefs`) | Classify, Digest |
| `tr_SourcesList` | Text | `Sources` / `Fuentes` | Collect |
| `tr_SourceItemsList` | Text | `SourceItems` / `ElementosFuente` | all flows |
| `tr_SignalsList` | Text | `Signals` / `Señales` | Classify, Digest |
| `tr_PublicationsList` | Text | `Publications` / `Publicaciones` | Digest |
| `tr_DailyClassificationLimit` | Number | 50 | Classify: `$top` of ready items |
| `tr_NotificationAudience` | Text | empty | Business Case: Teams channel (`teamId\|channelId`) that receives approved-case links; empty posts to the flow owner |
| `tr_RetentionDays` | Number | 90 | Clean Up Signals: Rejected and Monitor signals older than this many days are deleted; `0` turns the cleanup off |
| `tr_DailyResearchLimit`, `tr_PublishingEnabled` | — | — | reserved, unused |

The SharePoint connector's list parameter accepts either the list **title** or its **GUID**, but the Business Case claim calls the list by its title (`GetByTitle`), so the title is the preferred value for the list variables (`tr_BusinessCaseRequestsList` requires it). Defaulting to the title also lets a standard install work without anyone looking up GUIDs. If a customer renames a list, they put the new title in the variable.

The connector also has a dedicated *Data source* variable type (site + list picker). It was not used: plain text variables behave the same at runtime and are easier to set from an import wizard or a settings file.

## Caveats

- **Cached values.** If you change a current value directly in the environment, a running flow keeps the old value until you turn it off and on. Propagation can take up to an hour. Values set during import apply immediately.
- **2,000-character limit** per value.
- **Never put secrets in text variables.** Use the *Secret* type (Azure Key Vault) or connection references.
- Flows must belong to a solution for variables to work. All flows here do.

## Automated imports

For `pac solution import --settings-file`, copy `verticals/<v>/settings/deployment-settings.example.json`, fill in values and connection IDs, and keep the filled file **out of git**. `*.local.json` and `settings/*.json` other than the example are ignored.
