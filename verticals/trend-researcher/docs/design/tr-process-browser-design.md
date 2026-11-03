----------------
# TR Collect Authenticated Browser Tabs

Another source we need to check how to do with cheap/ compliant (all data uploaded to company's sharepoint) form, would be how to process websites that require some authentication and don't provide an API, i.e. the session lives on the user's comupetr. I presume we could find a cheap way to do computer use (https://learn.microsoft.com/en-us/training/modules/automate-desktop-web-tasks-computer-use-copilot-studio/) maybe power automate already has something? where the user logs into their tabs, and the session is shared with copilot, the data scrapped and uploaded automatically to the Evidence+SourceItems of our system.
------

Yes. This is the main missing ingestion layer.

Our original design already anticipated approved file submissions alongside RSS/API collection, and explicitly treated browser automation and difficult document extraction as separate source adapters. The important architectural property is that every adapter converges onto the same Evidence → SourceItems → TR Classify Items contract.

I would add two adapters, but keep them independent:

                    SOURCE ADAPTERS

RSS feeds ─────────► TR Collect RSS ───────────┐
                                               │
Uploaded files ────► TR Process Documents ─────┼──► Evidence
                                               │       +
Authenticated ─────► TR Collect Browser ───────┘    SourceItems
websites                                             │
                                                    ▼
                                           TR Classify Items
                                                    │
                                                    ▼
                                                 Signals




-------


Executive conclusion

Yes, there is a relatively cheap and compliant pattern for this:

Use Power Automate for desktop on the employee’s Windows computer in attended mode. The user signs into the website normally, Power Automate attaches to that browser session, extracts the permitted data, and uploads only the resulting structured file to the company’s SharePoint. A SharePoint-triggered cloud flow can then continue the Copilot workflow.

The important distinction is that the browser session is not exported or shared with Copilot. The automation runs locally under the same Windows user and controls the already-authenticated browser. Cookies, MFA tokens, and session state remain on the user’s machine.

I would use Power Automate for desktop, rather than Copilot Studio Computer Use, for the initial implementation. It is cheaper, more deterministic, and better suited to extracting structured information from a known website.

1. Recommended architecture
User's managed Windows computer
┌─────────────────────────────────────────────────────────────┐
│ 1. User opens Edge/Chrome and authenticates normally        │
│    - Password manager / SSO / MFA                            │
│    - Website session remains local                           │
│                                                             │
│ 2. User starts an attended Power Automate desktop flow       │
│                                                             │
│ 3. Desktop flow attaches to the running browser              │
│    - Navigates permitted pages                               │
│    - Extracts approved fields                                │
│    - Validates required data                                 │
│    - Creates JSON/CSV/XLSX and optional evidence             │
│                                                             │
│ 4. Desktop flow uploads the output to SharePoint             │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
Company SharePoint library
┌─────────────────────────────────────────────────────────────┐
│ Structured result + metadata + processing status            │
│ SharePoint permissions, retention, sensitivity label        │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
Power Automate cloud flow
┌─────────────────────────────────────────────────────────────┐
│ Trigger: file created in SharePoint                          │
│ - Validate/schema-check data                                 │
│ - Apply classification or approval                           │
│ - Update SharePoint List                                     │
│ - Invoke an approved Copilot/agent workflow                  │
│ - Notify user or downstream team                             │
└─────────────────────────────────────────────────────────────┘


Power Automate for desktop supports Edge, Chrome and Firefox, can attach to supported browser instances, and provides browser actions for extracting tables, page fields, text, links and other web elements. The browser must run under the same Windows user as Power Automate, which is exactly what preserves the user-owned authenticated session.

Power Automate desktop flows can also call the SharePoint connector directly. Microsoft specifically documents SharePoint actions inside desktop flows, although these require attended RPA entitlement.

2. How session sharing would actually work
Option A: Attach to the user’s existing authenticated browser

This is the closest match to your idea.

The employee opens an approved Edge browser profile.
The employee signs into the external website.
MFA, CAPTCHA, consent screens, or other interactive authentication are completed manually.
The employee launches a desktop flow.
The desktop flow uses Attach to running instance.
The flow finds the expected tab by URL or title.
It extracts the required data.
It uploads only the output to SharePoint.

Power Automate can attach to an existing supported browser using its browser extension. It cannot attach to a browser opened under a different Windows identity, and WebDriver mode generally only attaches to browser instances launched by the flow. Therefore, for the existing-session pattern, use the Power Automate browser extension, not WebDriver mode.

What remains local
Session cookies
Refresh tokens
Browser profile
Password-manager contents
Authenticator interaction
Existing tabs
Website credentials
What leaves the machine

Ideally, only:

Extracted business fields
Source URL
Extraction timestamp
User identity
Record count
Run ID
Validation status
Optional approved screenshot or source document

This is substantially safer than trying to copy cookies, browser profiles, session-storage values, or authentication headers into a cloud service.

Option B: Let the flow launch the browser, then have the user authenticate

This may be more reliable than attaching to an arbitrary tab.

Desktop flow launches Edge using an approved work profile.
It navigates to the website.
If authentication is needed, the flow pauses.
The user signs in and completes MFA.
The user selects Continue.
Automation resumes and extracts the data.

This gives the automation a known browser instance while still avoiding storage of external-site credentials.

It is a good fallback if attaching to an already-running browser produces problems because of multiple browser profiles, incompatible extension policies, or ambiguous tabs. Microsoft documents browser-extension troubleshooting considerations including multiple browser profiles and enterprise browser policies.

3. Why I would not start with Copilot Studio Computer Use

Copilot Studio Computer Use can operate websites and Windows applications without an API, using visual interpretation, mouse actions and keyboard input. It supports machine selection, end-user versus maker credentials, stored credentials, access-control allowlists, human supervision and structured JSON output.

However, it is not the best first choice for this requirement.

Main concerns
1. It is model-driven rather than deterministic

Computer Use reads screenshots and reasons about what to click. Microsoft states that its reliability can vary by task, and it can be sensitive to layout changes, timing, custom controls and unexpected dialogs. It can also repeat actions or become stuck.

For structured scraping from known pages, DOM-based Power Automate web actions are generally more predictable.

2. It normally targets a configured machine

Copilot Studio Computer Use asks the maker to select a target machine and connection. It can use end-user credentials for that machine, but this is different from transparently borrowing an arbitrary browser tab already open on the employee’s laptop.

3. Screenshots become part of the agent execution context

Computer Use processes screen pixels and exposes execution screenshots and reasoning information in its activity experience. This requires greater scrutiny if authenticated pages contain PII, confidential data, or unrelated information.

4. It adds Copilot Studio consumption and governance

Computer Use requires a Copilot Studio environment with the feature enabled, generative orchestration, machine configuration, connections and applicable Copilot consumption/licensing. Administrators can disable Computer Use or its hosted browser at the environment or tenant level.

Where Computer Use does fit

Use it later for websites where:

DOM/UI-element selectors do not work.
The interface changes frequently.
Content is rendered in canvas or remote desktop.
Navigation requires visual reasoning.
The task contains several variable paths.
The workflow needs the agent to interpret the page, not merely extract known fields.

Even then, Microsoft recommends isolated machines, least-privilege accounts, domain allowlists and restricted applications.

4. Cost comparison
Model	Best use	Approximate public list price	Authentication modelLocal attended Power Automate desktop flow	User signs in and initiates extraction	$15/user/month, annually	Uses user’s local interactive session
Unattended Power Automate Process	Scheduled automation without employee present	$150/bot/month, annually	Dedicated automation account/session
Microsoft-hosted unattended machine	No local VM or computer management	$215/bot/month, annually	Dedicated hosted Windows machine
Copilot Studio Computer Use	Agentic visual interaction	Consumption/Copilot Credits plus applicable environment and machine requirements	Configured machine and credentials

The current public pricing page lists Power Automate Premium at USD $15 per user/month for cloud flows and attended desktop flows, Power Automate Process at USD $150 per bot/month for unattended RPA, and Hosted Process at USD $215 per bot/month with a Microsoft-hosted VM. Pricing excludes tax and is subject to commercial agreements.

Power Automate Premium includes attended RPA, cloud integration, premium connectors, centralized monitoring and credential features. Unattended runs require Process capacity.

Cheapest practical path

For a pilot involving a small number of employees:

Power Automate Premium for each pilot user
Company-managed Windows computer
Edge work profile
Power Automate browser extension
SharePoint standard connector
No unattended bot
No hosted VM
No Copilot Studio Computer Use initially

If the employee can run the extraction manually and upload to SharePoint directly, the organization avoids the $150 or $215 monthly bot capacity.

5. Compliance controls required

“Everything goes to SharePoint” helps, but it does not by itself make the process compliant. Data is visible in the browser, processed in memory, potentially written to temporary storage, and represented in automation logs before it reaches SharePoint.

Minimum recommended controls
Managed endpoint
Intune-enrolled Windows device
BitLocker enabled
Microsoft Defender for Endpoint
Approved Edge work profile
Power Automate extension deployed through enterprise policy
No personal browser profile during automation
Dedicated browser profile

Use a separate organizational Edge profile for these automations. This reduces the chance that the flow attaches to personal tabs or exposes unrelated browsing data.

Domain allowlist

Permit the flow to visit only:

The approved external website
The company SharePoint tenant
Required Microsoft sign-in endpoints

Copilot Studio Computer Use has a tool-level website and application allowlist, although Microsoft notes that it prevents interaction rather than fully preventing navigation. For Power Automate desktop, endpoint filtering, browser policies, firewall controls and DLP should be combined.

DLP policy

Put these in the Business data group:

SharePoint
Microsoft 365 Users, if needed
Office 365 Outlook, if needed
Dataverse, if used
Desktop-flow actions required by the solution

Block or separate:

Personal cloud storage
Consumer email
Social media connectors
Unapproved HTTP endpoints
Clipboard or scripting actions if not needed

Power Platform DLP policies can classify connectors and desktop-flow action groups as Business, Non-business or Blocked. A desktop flow that violates the policy can be suspended and prevented from running.

No transferred website credentials

Do not:

Save passwords inside the flow.
Export browser cookies.
Copy session tokens to SharePoint.
Pass session headers into a cloud flow.
Reuse a personal automation account among employees.

If credentials must eventually be automated, use Power Automate credentials backed by Azure Key Vault or CyberArk and mark relevant variables as sensitive so values are not written to run logs.

Minimize local persistence

Prefer:

Extract into variables.
Serialize directly to JSON or CSV.
Upload immediately.
Remove temporary files.
Record only non-sensitive operational logs.

If local staging is unavoidable, use an encrypted controlled folder and delete files after SharePoint confirms creation.

SharePoint controls

Use a dedicated document library with:

Restricted Microsoft Entra group
Versioning
Retention policy
Sensitivity label
Audit logging
No anonymous sharing
Separate raw and processed folders
Metadata indicating source, user, time and status
Human confirmation before consequential actions

Collection can be automated, but updates, submissions, purchases, acknowledgments, or contractual actions should require explicit user review.

Microsoft warns that Computer Use can take unintended actions and that human-supervision prompts are not a guaranteed safety mechanism.

Website authorization

Before scraping a third-party website, verify:

Terms of service
Account agreement
Permitted use of the information
Rate limits
Restrictions on automated access
Data ownership
Relevant privacy obligations

Using a valid human account does not automatically authorize automation.

6. Suggested workflow implementation
Desktop flow
1. Display instructions:
   "Open the approved website and sign in. Then select Continue."

2. Attach to running Edge instance:
   Match by URL: https://approved-site.example/*

3. Verify:
   - Expected hostname
   - Logged-in indicator is present
   - Correct account/organization is shown

4. Navigate to required section.

5. Extract required table or data fields.

6. Validate:
   - Required columns present
   - Record count is within expected range
   - No password/token fields
   - No unexpected page or error message

7. Construct structured output:
   {
     "schemaVersion": "1.0",
     "sourceSystem": "...",
     "sourceUrl": "...",
     "extractedAtUtc": "...",
     "extractedBy": "...",
     "recordCount": 25,
     "records": [...]
   }

8. Upload to:
   SharePoint/AutomationIntake/<source>/<year>/<month>/

9. Write a small manifest:
   - Run ID
   - File hash
   - Status
   - Validation result

10. Close only the tabs opened by the automation.
    Do not close the user's original authenticated tab.

SharePoint-triggered cloud flow
Trigger:
When a file is created in AutomationIntake/Raw

Steps:
1. Reject unsupported file types.
2. Validate JSON schema or CSV columns.
3. Check duplicate Run ID/file hash.
4. Move invalid files to Quarantine.
5. Apply metadata and sensitivity classification.
6. Copy normalized data to Processed or a SharePoint List.
7. Invoke the downstream Copilot/agent workflow.
8. Store the agent result in SharePoint.
9. Notify the submitting user.


This creates a clean security boundary:

Local attended automation owns the authenticated session; SharePoint owns persisted data; the cloud/Copilot workflow starts only after the approved artifact reaches SharePoint.

7. Final recommendation
Phase 1: inexpensive proof of concept

Build one attended Power Automate desktop flow for a single approved website:

User authenticates manually.
Flow attaches to Edge.
Flow makes no external-site changes.
Flow extracts only a predefined set of fields.
Output is JSON.
Output goes directly to a restricted SharePoint library.
SharePoint triggers the downstream cloud flow.
No screenshots unless required.
No credentials or cookies leave the computer.
Phase 2: production hardening

Add:

Power Platform solution packaging
Environment-specific connections
DLP and endpoint filtering
Edge profile and extension deployment through Intune
JSON schema validation
SharePoint retention and sensitivity labels
Run monitoring and failure alerts
Formal approval of the target website and fields
Test cases for session expiration, MFA, CAPTCHA and layout changes
Phase 3: selective Computer Use

Evaluate Copilot Studio Computer Use only for target sites that cannot be automated reliably through standard browser elements. Run it on an isolated machine with restricted domains and least-privilege access, rather than giving a general-purpose agent control over each employee’s normal desktop.

Bottom line: your assumption is directionally correct, but the cheapest and safest version is not “share the session with Copilot.” It is“run attended Power Automate locally inside the user’s existing authenticated Windows/browser context, publish sanitized output to SharePoint, and let the Copilot workflow continue from SharePoint.”
