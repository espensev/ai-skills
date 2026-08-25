@{
    RootModule = 'AiEnvironment.psm1'
    ModuleVersion = '0.1.0'
    GUID = '6c2555e7-40ad-4e73-9058-a6cbeb282890'
    Author = 'Sev'
    Description = 'Read-only cross-provider wanted-state observation and planning for the local AI environment.'
    PowerShellVersion = '7.2'
    FunctionsToExport = @(
        'Get-AiEnvironmentState',
        'New-AiEnvironmentPlan',
        'Test-AiEnvironment'
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
