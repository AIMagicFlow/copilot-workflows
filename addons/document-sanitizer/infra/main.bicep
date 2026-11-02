// Document Sanitizer: Function App (Flex Consumption), storage, Application Insights,
// Document Intelligence and the identity that connects them. No keys in app settings or outputs.
// Pattern follows the Microsoft Learn "Create and deploy Azure Functions resources using Bicep"
// quickstart. Not compiled in this repo's sessions: CI runs `az bicep build` (see Task 14).

@description('Short prefix for resource names: 3 to 12 lowercase letters or digits.')
@minLength(3)
@maxLength(12)
param namePrefix string

@description('Azure region. Use the customer region (design §7).')
param location string = resourceGroup().location

@description('Document Intelligence pricing tier.')
@allowed([
  'S0'
])
param documentIntelligenceSku string = 'S0'

@description('Maximum Flex Consumption instances.')
@minValue(1)
@maxValue(1000)
param maximumInstanceCount int = 40

var suffix = take(uniqueString(resourceGroup().id), 8)
var storageName = toLower('${take(namePrefix, 12)}${suffix}')
var baseName = '${namePrefix}-${suffix}'

// Built-in role definition IDs.
var roleStorageBlobDataOwner = 'b7e6dc6d-f1e8-4753-8033-0f276bb0955b'
var roleStorageQueueDataContributor = '974c5e8b-45b9-4653-ba55-5f855dd0fb88'
var roleStorageTableDataContributor = '0a9a7e1f-b9d0-4cc4-a60d-0319b160aaa3'
var roleCognitiveServicesUser = 'a97b65f3-24c7-4388-baec-2e87445bc073'

resource identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: 'id-${baseName}'
  location: location
}

resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: storageName
  location: location
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
    allowBlobPublicAccess: false
    allowSharedKeyAccess: false
  }
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = {
  parent: storage
  name: 'default'
}

resource deploymentContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobService
  name: 'app-package'
}

resource logs 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: 'log-${baseName}'
  location: location
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
  }
}

resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: 'appi-${baseName}'
  location: location
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logs.id
  }
}

resource documentIntelligence 'Microsoft.CognitiveServices/accounts@2023-05-01' = {
  name: 'di-${baseName}'
  location: location
  kind: 'FormRecognizer'
  sku: {
    name: documentIntelligenceSku
  }
  properties: {
    customSubDomainName: 'di-${baseName}'
    publicNetworkAccess: 'Enabled'
    disableLocalAuth: true
  }
}

// Role assignments: the identity reaches storage and Document Intelligence without keys.
resource blobRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storage.id, identity.id, roleStorageBlobDataOwner)
  scope: storage
  properties: {
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleStorageBlobDataOwner)
  }
}

resource queueRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storage.id, identity.id, roleStorageQueueDataContributor)
  scope: storage
  properties: {
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleStorageQueueDataContributor)
  }
}

resource tableRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storage.id, identity.id, roleStorageTableDataContributor)
  scope: storage
  properties: {
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleStorageTableDataContributor)
  }
}

resource documentIntelligenceRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(documentIntelligence.id, identity.id, roleCognitiveServicesUser)
  scope: documentIntelligence
  properties: {
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleCognitiveServicesUser)
  }
}

resource plan 'Microsoft.Web/serverfarms@2024-04-01' = {
  name: 'plan-${baseName}'
  location: location
  kind: 'functionapp'
  sku: {
    tier: 'FlexConsumption'
    name: 'FC1'
  }
  properties: {
    reserved: true
  }
}

resource functionApp 'Microsoft.Web/sites@2024-04-01' = {
  name: 'func-${baseName}'
  location: location
  kind: 'functionapp,linux'
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${identity.id}': {}
    }
  }
  properties: {
    serverFarmId: plan.id
    httpsOnly: true
    functionAppConfig: {
      deployment: {
        storage: {
          type: 'blobContainer'
          value: '${storage.properties.primaryEndpoints.blob}${deploymentContainer.name}'
          authentication: {
            type: 'UserAssignedIdentity'
            userAssignedIdentityResourceId: identity.id
          }
        }
      }
      runtime: {
        name: 'python'
        version: '3.12'
      }
      scaleAndConcurrency: {
        maximumInstanceCount: maximumInstanceCount
        instanceMemoryMB: 2048
      }
    }
    siteConfig: {
      minTlsVersion: '1.2'
      ftpsState: 'Disabled'
      appSettings: [
        {
          name: 'AzureWebJobsStorage__accountName'
          value: storage.name
        }
        {
          name: 'AzureWebJobsStorage__credential'
          value: 'managedidentity'
        }
        {
          name: 'AzureWebJobsStorage__clientId'
          value: identity.properties.clientId
        }
        {
          name: 'AZURE_CLIENT_ID'
          value: identity.properties.clientId
        }
        {
          name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
          value: appInsights.properties.ConnectionString
        }
        {
          name: 'DOCUMENT_INTELLIGENCE_ENDPOINT'
          value: documentIntelligence.properties.endpoint
        }
      ]
    }
  }
  dependsOn: [
    blobRole
    queueRole
    tableRole
    documentIntelligenceRole
  ]
}

output functionAppName string = functionApp.name
output functionAppHostName string = functionApp.properties.defaultHostName
