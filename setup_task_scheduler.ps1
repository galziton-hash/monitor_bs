# HBS Ticket Checker – Windows Task Scheduler Setup
# Run this script ONCE as Administrator to register the scheduled task.
# After that it runs automatically every 3 minutes.

$taskName   = "HBS_Ticket_Checker"
$scriptPath = "C:\Users\galz\source\HBS_Shefa\run_checker.bat"

# Remove existing task if present
Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue

# Build the action
$action  = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$scriptPath`""

# Repeat every 3 minutes, starting now, for 10 years
$trigger = New-ScheduledTaskTrigger -RepetitionInterval (New-TimeSpan -Minutes 3) `
                                     -Once -At (Get-Date) `
                                     -RepetitionDuration (New-TimeSpan -Days 3650)

# Run whether logged on or not, with highest privileges
$settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 7) `
    -MultipleInstances IgnoreNew `
    -StartWhenAvailable

$principal = New-ScheduledTaskPrincipal `
    -UserId "$env:USERDOMAIN\$env:USERNAME" `
    -LogonType Interactive `
    -RunLevel Highest

Register-ScheduledTask `
    -TaskName  $taskName `
    -Action    $action `
    -Trigger   $trigger `
    -Settings  $settings `
    -Principal $principal `
    -Description "Checks HBS vs Juventus ticket availability every 3 minutes" `
    -Force

Write-Host ""
Write-Host "✅  Task '$taskName' registered successfully!" -ForegroundColor Green
Write-Host "    It will run every 3 minutes while your computer is on."
Write-Host ""
Write-Host "To check status:  Get-ScheduledTask -TaskName '$taskName'"
Write-Host "To stop it:       Disable-ScheduledTask -TaskName '$taskName'"
Write-Host "To remove it:     Unregister-ScheduledTask -TaskName '$taskName' -Confirm:`$false"
Write-Host "To view logs:     notepad C:\Users\galz\source\HBS_Shefa\logs\checker.log"
