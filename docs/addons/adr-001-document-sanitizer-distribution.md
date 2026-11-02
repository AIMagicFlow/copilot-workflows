# ADR-001: How the Document Sanitizer ships

- **Status:** accepted (2026-11-02)
- **Design:** [document-sanitizer-design.md](document-sanitizer-design.md)

## Context

The verticals ship as Power Platform solution zips that customers import, plus a SharePoint kit. Private document uploads and binary formats (PDF, Office, scanned images) need a converter and a regex redactor that flow expressions can't provide. Flow expressions only replace exact-case text, one action per term.

A Power Platform solution can only carry Power Platform components:
- flows, environment variables and connection references;
- custom connectors;
- Dataverse plug-ins.

It can't carry Azure resources. An Azure Function, its storage, Application Insights, Document Intelligence and the identity between them have to reach the customer some other way.

The redactor exists to keep private documents from spreading, so where it runs is part of the privacy promise.

## Options

| | Where the function runs | Private data leaves the customer's tenant? | Customer effort | Our effort |
|---|---|---|---|---|
| **A. Customer-hosted** | the customer's Azure subscription | no | IT deploys one template and pastes a key | template, release package, quickstart |
| **B. Hosted by us (shared)** | our Azure subscription, all customers | **yes**, every private document | create one connection | run a multi-tenant service: uptime, data-processing agreements, residency, support |
| **C. Azure Marketplace managed app** | the customer's subscription, managed by us | no | one Marketplace purchase | Partner Center listing, managed-app packaging, updates |
| **D. Dataverse plug-in (no Azure)** | inside Dataverse, shipped in the solution zip | no | none beyond import | build and sign a .NET Framework plug-in; sandbox limits |

Notes:
- **B** contradicts the design's own rule against sending raw PII to third-party converters. It would turn this repo into a hosted service with its own compliance obligations.
- **D** can do regex and case-insensitive redaction, and text extraction from DOCX and PPTX (Open XML SDK) and from PDFs that contain real text (for example PdfPig).
  - It can't do OCR, and it is bound by the plug-in sandbox: about 2 minutes per call, and dependent assemblies have to be packaged.
  - It runs on Dataverse capacity and is called through the Dataverse connector.

## Decision

**Option A.** The Document Sanitizer is a separate, customer-hosted add-on, released from this repo next to the verticals.

The add-on package is `releases/addons/document-sanitizer/<version>/`, holding:
- `document-sanitizer-<version>.zip`: the function code, ready for zip deploy or run-from-package;
- `azuredeploy.json`: the Bicep template compiled to ARM, for a "Deploy to Azure" button or `az deployment group create`;
- `deploy.ps1`: deploys the template and the code, then prints the host name to paste into the environment variable;
- `quickstart.<locale>.md`;
- `SHA256SUMS`.

Each vertical's solution zip carries:
- **A custom connector** (`addons/document-sanitizer/connector/apiDefinition.swagger.json`). Its host comes from an environment variable, and its security is API key (`x-functions-key`). The customer enters the key when creating the connection, so it is never stored in the solution, the repo or an environment variable.
- **Environment variables:**
  - `<prefix>_SanitizerHost`: empty means the add-on is off;
  - `<prefix>_SanitizerProfile`: default `default-pii`.
- **A connection reference** for the connector.
- **The flow branches** that call it only when `<prefix>_SanitizerHost` is set.

A customer who never deploys the add-on imports the same solution and keeps the plain-text behavior. Imports never require the add-on.

### Customer setup (IT)

1. Deploy the template into a resource group in the tenant's region: Function App, storage, Application Insights, Document Intelligence, managed identity.
2. Deploy the code package.
3. Copy the function's host name and default function key.
4. In Power Platform:
   - set `<prefix>_SanitizerHost`;
   - create the sanitizer connection with the key;
   - turn on the flow.

This is the same audience and skill level as the PnP provisioning option: someone with rights in the customer's Azure subscription.

## Consequences

- **Good:**
  - Private documents stay in the customer's tenant and region.
  - The customer owns the Azure costs and the data-protection settings.
  - We don't run a production service.
- **Good:** one function serves every vertical. Each vertical only adds its connector copy, environment variables and flow branches.
- **Cost:** the customer needs an Azure subscription and someone who can deploy to it. Option C is the later answer if that friction blocks sales.
- **Cost:** two release artifacts to version. A vertical release lists the add-on versions it supports in its CHANGELOG. The API is versioned in the path (`/api/v1/...`), so a vertical keeps working against any 1.x add-on.
- **Cost:** the custom connector and Dataverse connector are premium. Customers' agent-flow licensing has to cover them; see the design's open questions.
- **Kept open:** option D, as a later "no Azure" tier for redaction plus simple DOCX, PPTX and digital-PDF extraction. If it's built, it implements the same request and response shape as the function, so flows can switch between them through configuration.

## To verify before the first release

- A solution custom connector accepts an environment-variable host, in an agent flow, in a Spanish environment.
- An API-key connection created at import binds correctly through the connection reference.
- A custom-connector action in an agent flow follows `202` + `Location` polling.
- Secure inputs and outputs on the connector action hide the content in the run history.
