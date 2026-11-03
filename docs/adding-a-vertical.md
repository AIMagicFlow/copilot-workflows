# Adding a vertical

Example: lead generation (`verticals/lead-generation`).

1. **Prototype in a dev environment.** Create a solution with its own publisher and prefix (for example `lg`), build the flows in the designer, and export the solution as **unmanaged**.
2. **Create the folder** from the Trend Researcher layout:
   ```text
   verticals/lead-generation/
     vertical.yaml  solution/  prompts/  i18n/en.yaml i18n/es.yaml
     sharepoint/lists/  sharepoint/libraries.yaml  settings/  docs/
   ```
3. **Copy the export into `solution/`.** Unzip it there.
4. **Make the flows portable** (see [architecture](architecture.md#portability-rules)):
   - Remove `triggers.*.metadata.associatedData` from each flow.
   - Replace the site URL and list GUIDs with `@parameters('<Name> (<schema>)')`, add the `definition.parameters` entries, and add one `environmentvariabledefinitions/<schema>/` per variable. A list variable's default should be `{{list:<ListKey>}}`.
   - Delete `item/{ContentType}` blocks and other tenant IDs.
   - Move prompts to `prompts/*.md`, reference them as `{{prompt:name}}`, and register them with a version in `vertical.yaml`. Include `shared/prompts/untrusted-evidence.md` in any prompt that reads external content.
   - Replace user-visible strings with `{{t:key}}`, and the names in `solution.xml` and `customizations.xml` with tokens. Remove connection references no flow uses.

   A one-off script is fine for this; the Trend Researcher migration did exactly these steps.
5. **Describe the lists.** For each list, write `sharepoint/lists/NN-<List>.yaml`, taking internal names and field IDs from a SharePoint *Export → CSV with schema*. If two verticals share a list shape, move it to `shared/sharepoint/` instead of copying it.
6. **Build and test**: `python3 tools/build.py lead-generation` and `python3 -m unittest discover -s tools/tests`. Add a test module for the vertical's specifics.
7. **Write the quickstarts** and add the vertical to the root README table.
8. **Release**: set the version, run `python3 tools/build.py lead-generation --release`, and commit `releases/lead-generation/<version>/`. In the same commit, update the vertical's row in the root README (version and summary), so the table never shows an older release than the one in `releases/`.
