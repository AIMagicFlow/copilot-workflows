#requires -Version 7.4
<#
.SYNOPSIS
    Deploys the Document Sanitizer into a resource group in your Azure subscription.

.DESCRIPTION
    Runs from the release folder (releases/addons/document-sanitizer/<version>/).
    Creates the resource group, deploys azuredeploy.json, then deploys the function code
    with a remote build. It never reads, prints or stores a function key.

    Requires the Azure CLI (az) and an active login: az login.

.PARAMETER ResourceGroup
    Resource group to create or reuse.

.PARAMETER Location
    Azure region, for example westeurope. Use the region your data policy requires.

.PARAMETER NamePrefix
    3 to 12 lowercase letters or digits. Used in every resource name.

.PARAMETER PackagePath
    Optional. The function zip. Defaults to the document-sanitizer-*.zip next to this script.

.EXAMPLE
    ./deploy.ps1 -ResourceGroup rg-sanitizer -Location westeurope -NamePrefix dsanit01
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)] [string] $ResourceGroup,
    [Parameter(Mandatory)] [string] $Location,
    [Parameter(Mandatory)] [ValidatePattern('^[a-z0-9]{3,12}$')] [string] $NamePrefix,
    [string] $PackagePath
)

$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$template = Join-Path $here 'azuredeploy.json'

function Invoke-Az {
    # Native commands do not throw under $ErrorActionPreference, so check the exit code here.
    & az @args
    if ($LASTEXITCODE -ne 0) { throw "az $($args[0]) $($args[1]) failed with exit code $LASTEXITCODE" }
}

if (-not (Get-Command az -ErrorAction SilentlyContinue)) {
    throw 'The Azure CLI (az) is not installed. Install it from https://learn.microsoft.com/cli/azure/install-azure-cli'
}
& az account show --only-show-errors *> $null
if ($LASTEXITCODE -ne 0) { throw 'Not signed in. Run: az login' }
if (-not (Test-Path $template)) { throw "Missing $template. Run this script from the release folder." }

if (-not $PackagePath) {
    $found = Get-ChildItem -Path $here -Filter 'document-sanitizer-*.zip' | Select-Object -First 1
    if (-not $found) { throw 'No document-sanitizer-*.zip next to this script. Pass -PackagePath.' }
    $PackagePath = $found.FullName
}
if (-not (Test-Path $PackagePath)) { throw "Package not found: $PackagePath" }

Write-Host "Creating or reusing resource group $ResourceGroup in $Location"
Invoke-Az group create --name $ResourceGroup --location $Location --only-show-errors --output none

$deploymentName = "dsanit-$(Get-Date -Format 'yyyyMMddHHmmss')"
Write-Host "Deploying infrastructure ($deploymentName)"
$outputs = & az deployment group create `
    --resource-group $ResourceGroup `
    --name $deploymentName `
    --template-file $template `
    --parameters namePrefix=$NamePrefix location=$Location `
    --only-show-errors `
    --query 'properties.outputs' --output json
if ($LASTEXITCODE -ne 0) { throw 'Infrastructure deployment failed. See the error above.' }
$outputs = $outputs | ConvertFrom-Json
$appName = $outputs.functionAppName.value
$hostName = $outputs.functionAppHostName.value

Write-Host "Deploying function code to $appName (remote build installs requirements.txt)"
Invoke-Az functionapp deployment source config-zip `
    --resource-group $ResourceGroup `
    --name $appName `
    --src $PackagePath `
    --build-remote true `
    --only-show-errors --output none

Write-Host ''
Write-Host "Done. Host name for the environment variable: https://$hostName"
Write-Host 'Next: copy the default function key from the Azure portal'
Write-Host "  Function App $appName > Functions > sanitize_document > Function Keys > default"
Write-Host 'The key is not printed here. See the quickstart for the next steps.'
