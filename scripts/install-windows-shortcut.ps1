param(
  [Parameter(Mandatory = $true)][string]$Root,
  [string]$Name = 'Xultron'
)
$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path $Root).Path
$Desktop = [Environment]::GetFolderPath('Desktop')
if ([string]::IsNullOrWhiteSpace($Desktop)) { throw 'Windows masaustu klasoru bulunamadi.' }
$ShortcutPath = Join-Path $Desktop "$Name.lnk"
$Launcher = Join-Path $Root 'scripts\start-windows.bat'
if (-not (Test-Path $Launcher -PathType Leaf)) { throw "Launcher bulunamadi: $Launcher" }
$Shell = New-Object -ComObject WScript.Shell
try {
  if (Test-Path $ShortcutPath) {
    $Existing = $Shell.CreateShortcut($ShortcutPath)
    $ExistingTarget = [IO.Path]::GetFullPath(($Existing.Arguments -replace '.*"([^"]+start-windows\.bat)".*', '$1'))
    if ($Existing.TargetPath -notmatch '(?i)cmd(\.exe)?$' -or $ExistingTarget -ne [IO.Path]::GetFullPath($Launcher)) {
      Write-Host "Mevcut kisayol korunuyor: $ShortcutPath"
      exit 0
    }
  }
  $Shortcut = $Shell.CreateShortcut($ShortcutPath)
  $Shortcut.TargetPath = $env:ComSpec
  $Shortcut.Arguments = "/c `"$Launcher`""
  $Shortcut.WorkingDirectory = $Root
  $Shortcut.Description = 'Xultron AI'
  $Shortcut.IconLocation = "$env:SystemRoot\System32\imageres.dll,13"
  $Shortcut.Save()
  Write-Host "Masaustu kisayolu hazir: $ShortcutPath"
} finally {
  [Runtime.InteropServices.Marshal]::ReleaseComObject($Shell) | Out-Null
}
