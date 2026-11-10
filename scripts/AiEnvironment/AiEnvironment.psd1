@{
    RootModule = 'AiEnvironment.psm1'
    ModuleVersion = '0.2.0'
    GUID = '6c2555e7-40ad-4e73-9058-a6cbeb282890'
    Author = 'Sev'
    Description = 'Cross-provider wanted-state observation, lock capture/promotion, and planning for the local AI environment.'
    PowerShellVersion = '7.2'
    FunctionsToExport = @(
        'Approve-AiEnvironmentLock',
        'Get-AiEnvironmentState',
        'New-AiEnvironmentPlan',
        'Save-AiEnvironmentState',
        'Test-AiEnvironment',
        'Update-AiEnvironmentLock'
    )
    CmdletsToExport = @()
    VariablesToExport = @()
    AliasesToExport = @()
    PrivateData = @{
        PSData = @{
            Tags = @('Codex', 'Claude', 'WantedState', 'DevHome')
        }
    }
}
