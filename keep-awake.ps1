param([string]$Flag)
Add-Type -Namespace W -Name K -MemberDefinition '[System.Runtime.InteropServices.DllImport("kernel32.dll")] public static extern uint SetThreadExecutionState(uint f);'
while (-not (Test-Path $Flag)) { [W.K]::SetThreadExecutionState(0x80000001) | Out-Null; Start-Sleep -Seconds 30 }
[W.K]::SetThreadExecutionState(0x80000000) | Out-Null
