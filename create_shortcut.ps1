$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("$env:USERPROFILE\Desktop\Claude Monitor.lnk")
$Shortcut.TargetPath = "C:\work\aiml\uxn\monitors\dist\ClaudeMonitor.exe"
$Shortcut.WorkingDirectory = "C:\work\aiml\uxn\monitors\dist"
$Shortcut.Description = "Claude Max Usage Monitor"
$Shortcut.Save()
Write-Host "Shortcut created on Desktop"
