# Install mm on Windows. Points %USERPROFILE%\bin\mm.cmd at this clone.
# From this folder:  install.cmd
# Or:                powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1
# Fresh machine:     irm https://raw.githubusercontent.com/Toseef-Ahmad/mm/master/install.ps1 | iex
$ErrorActionPreference = "Stop"
$script:InvokedAsFile = [bool]($PSScriptRoot -and (Test-Path (Join-Path $PSScriptRoot "mm\cli.py")))

function Test-ExplorerLaunch {
    if ($env:CI -or $env:GITHUB_ACTIONS) { return $false }
    try {
        $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$PID"
        $parent = Get-CimInstance Win32_Process -Filter "ProcessId=$($proc.ParentProcessId)"
        if (-not $parent -or $parent.Name -ne "cmd.exe") { return $false }
        $grand = Get-CimInstance Win32_Process -Filter "ProcessId=$($parent.ParentProcessId)"
        return ($grand -and $grand.Name -eq "explorer.exe")
    } catch {
        return $false
    }
}

$script:HoldWindow = Test-ExplorerLaunch

function Hold-IfExplorer {
    if ($script:HoldWindow) {
        Write-Host ""
        Read-Host "Press Enter to close"
    }
}

function Die([string]$Message) {
    Write-Host ""
    Write-Host $Message
    Hold-IfExplorer
    if ($script:InvokedAsFile) { exit 1 }
    throw $Message
}

function Refresh-ProcessPath {
    $machine = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $user = [Environment]::GetEnvironmentVariable("Path", "User")
    if (-not $machine) { $machine = "" }
    if (-not $user) { $user = "" }
    $env:Path = "$user;$machine"
}

function Test-StoreStub([string]$Path) {
    if (-not $Path) { return $false }
    return ($Path -like "*\WindowsApps\*")
}

function Get-PythonCandidate {
    param([string]$Exe, [string[]]$PrefixArgs)
    if (Test-StoreStub $Exe) { return $null }
    if (-not (Test-Path -LiteralPath $Exe)) { return $null }
    $code = "import sys; print(sys.version_info[0]); print(sys.version_info[1]); print(sys.executable)"
    try {
        $raw = & $Exe @PrefixArgs -c $code 2>$null
    } catch {
        return $null
    }
    if ($LASTEXITCODE -ne 0 -or -not $raw) { return $null }
    $lines = @(
        $raw | ForEach-Object { "$_".Trim() } | Where-Object { $_ -ne "" }
    )
    if ($lines.Count -lt 3) { return $null }
    $major = 0
    $minor = 0
    if (-not [int]::TryParse($lines[0], [ref]$major)) { return $null }
    if (-not [int]::TryParse($lines[1], [ref]$minor)) { return $null }
    if ($major -lt 3 -or ($major -eq 3 -and $minor -lt 11)) { return $null }
    $real = $lines[2]
    if (Test-StoreStub $real) { return $null }
    return @{ Exe = $real; Version = "$major.$minor" }
}

function Find-Python {
    $found = New-Object System.Collections.Generic.List[object]
    foreach ($name in @("py", "python", "python3")) {
        $cmd = Get-Command $name -ErrorAction SilentlyContinue
        if (-not $cmd) { continue }
        $prefix = @()
        if ($name -eq "py") { $prefix = @("-3") }
        $info = Get-PythonCandidate -Exe $cmd.Source -PrefixArgs $prefix
        if ($info) { $found.Add($info) | Out-Null }
    }
    $patterns = @(
        (Join-Path $env:LOCALAPPDATA "Programs\Python\Python*\python.exe"),
        (Join-Path $env:ProgramFiles "Python*\python.exe")
    )
    if (${env:ProgramFiles(x86)}) {
        $patterns += (Join-Path ${env:ProgramFiles(x86)} "Python*\python.exe")
    }
    foreach ($pattern in $patterns) {
        foreach ($exe in @(Get-Item -Path $pattern -ErrorAction SilentlyContinue)) {
            $info = Get-PythonCandidate -Exe $exe.FullName -PrefixArgs @()
            if ($info) { $found.Add($info) | Out-Null }
        }
    }
    if ($found.Count -eq 0) { return $null }
    return ($found | Sort-Object { [version]$_.Version } -Descending | Select-Object -First 1)
}

function Install-PythonWithWinget {
    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if (-not $winget) {
        Die @"
Python 3.11+ was not found, and winget is not available.
Install Python from https://www.python.org/downloads/
On the installer, check "Add python.exe to PATH", then run install.cmd again.
"@
    }
    Write-Host "Python 3.11+ was not found. Installing it for your user account..."
    foreach ($id in @("Python.Python.3.14", "Python.Python.3.13", "Python.Python.3.12")) {
        Write-Host "Trying $id"
        & winget install --id $id -e --scope user --disable-interactivity --accept-package-agreements --accept-source-agreements
        Refresh-ProcessPath
        $info = Find-Python
        if ($info) { return $info }
    }
    Die @"
Python could not be installed automatically.
Install Python 3.11 or newer from https://www.python.org/downloads/
On the installer, check "Add python.exe to PATH", then run install.cmd again.
"@
}

function Ensure-Git {
    $git = Get-Command git -ErrorAction SilentlyContinue
    if ($git -and -not (Test-StoreStub $git.Source)) { return $git.Source }
    $candidates = @(
        (Join-Path $env:ProgramFiles "Git\cmd\git.exe"),
        (Join-Path $env:LOCALAPPDATA "Programs\Git\cmd\git.exe")
    )
    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate) { return $candidate }
    }
    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if (-not $winget) {
        Die "Git is required to download mm. Install it from https://git-scm.com/download/win and run this again."
    }
    Write-Host "Git was not found. Installing Git for your user account..."
    & winget install --id Git.Git -e --scope user --disable-interactivity --accept-package-agreements --accept-source-agreements
    Refresh-ProcessPath
    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate) { return $candidate }
    }
    $git = Get-Command git -ErrorAction SilentlyContinue
    if ($git -and -not (Test-StoreStub $git.Source)) { return $git.Source }
    Die "Git was installed, but this window cannot see it yet. Open a new terminal and run the install again."
}

function Broadcast-EnvironmentChange {
    try {
        if (-not ("MM.Win32.Native" -as [type])) {
            Add-Type -Namespace MM.Win32 -Name Native -MemberDefinition @'
[System.Runtime.InteropServices.DllImport("user32.dll", SetLastError = true, CharSet = System.Runtime.InteropServices.CharSet.Auto)]
public static extern System.IntPtr SendMessageTimeout(System.IntPtr hWnd, uint Msg, System.UIntPtr wParam, string lParam, uint fuFlags, uint uTimeout, out System.UIntPtr lpdwResult);
'@
        }
        $result = [System.UIntPtr]::Zero
        [MM.Win32.Native]::SendMessageTimeout(
            [System.IntPtr]0xffff, 0x001A, [System.UIntPtr]::Zero, "Environment", 2, 1000, [ref]$result
        ) | Out-Null
    } catch {
        # A new terminal still reads PATH from the registry.
    }
}

if ($PSScriptRoot -and (Test-Path (Join-Path $PSScriptRoot "mm\cli.py"))) {
    $Root = (Resolve-Path -LiteralPath $PSScriptRoot).Path
} else {
    $dest = Join-Path $env:USERPROFILE "mm"
    if ((Test-Path (Join-Path $dest "mm\cli.py")) -and (Test-Path (Join-Path $dest ".git"))) {
        $git = Ensure-Git
        Write-Host "Updating $dest"
        & $git -C $dest pull --ff-only
        if ($LASTEXITCODE -ne 0) {
            Die "Could not update $dest. Open that folder and run install.cmd there."
        }
    } elseif (Test-Path -LiteralPath $dest) {
        Die "$dest already exists and is not an mm checkout. Move that folder aside, or clone the repo yourself and run install.cmd inside it."
    } else {
        $git = Ensure-Git
        Write-Host "Cloning mm into $dest"
        & $git clone "https://github.com/Toseef-Ahmad/mm.git" $dest
        if ($LASTEXITCODE -ne 0) { Die "git clone failed." }
    }
    $Root = (Resolve-Path -LiteralPath $dest).Path
}

$py = Find-Python
if (-not $py) { $py = Install-PythonWithWinget }
Write-Host "Using Python $($py.Version) ($($py.Exe))"

$Bin = Join-Path $env:USERPROFILE "bin"
New-Item -ItemType Directory -Force -Path $Bin | Out-Null

$env:MM_ROOT = $Root
$env:MM_OUT = Join-Path $Bin "mm-launch.py"
& $py.Exe -c @'
import os
from pathlib import Path
root = os.environ["MM_ROOT"]
out = os.environ["MM_OUT"]
Path(out).write_text(
    "import sys\n"
    "sys.path.insert(0, %r)\n"
    "from mm.cli import main\n"
    "if __name__ == '__main__':\n"
    "    main()\n" % root,
    encoding="utf-8",
    newline="\n",
)
'@
if ($LASTEXITCODE -ne 0) { Die "Could not write the mm launcher." }

$pyForward = ($py.Exe -replace '\\', '/')
$launchForward = ($env:MM_OUT -replace '\\', '/')
$shLine = 'exec "' + $pyForward + '" "' + $launchForward + '" "$@"'
$sh = "#!/bin/sh`nexport PYTHONUTF8=1`nexport PYTHONIOENCODING=utf-8`n$shLine`n"
$utf8 = New-Object System.Text.UTF8Encoding $false
[System.IO.File]::WriteAllText((Join-Path $Bin "mm"), $sh, $utf8)

$cmd = "@echo off`r`nsetlocal`r`nset `"PYTHONUTF8=1`"`r`nset `"PYTHONIOENCODING=utf-8`"`r`n`"$($py.Exe)`" `"%~dp0mm-launch.py`" %*`r`nexit /b %ERRORLEVEL%`r`n"
$cmdEncoding = $utf8
if ($py.Exe -match '[^\u0000-\u007F]') {
    $cmdEncoding = [System.Text.Encoding]::Default
}
[System.IO.File]::WriteAllText((Join-Path $Bin "mm.cmd"), $cmd, $cmdEncoding)

Remove-Item Env:MM_ROOT -ErrorAction SilentlyContinue
Remove-Item Env:MM_OUT -ErrorAction SilentlyContinue

$manDir = Join-Path $env:USERPROFILE ".local\share\man\man1"
New-Item -ItemType Directory -Force -Path $manDir | Out-Null
Copy-Item -LiteralPath (Join-Path $Root "mm\data\mm.1") -Destination (Join-Path $manDir "mm.1") -Force

$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if (-not $userPath) { $userPath = "" }
$norm = $Bin.TrimEnd('\')
$has = $false
foreach ($piece in ($userPath -split ';')) {
    if ($piece.Trim().TrimEnd('\') -ieq $norm) { $has = $true }
}
if (-not $has) {
    if ($userPath.Trim() -eq "") { $updated = $Bin } else { $updated = $userPath.TrimEnd(';') + ';' + $Bin }
    try {
        [Environment]::SetEnvironmentVariable("Path", $updated, "User")
    } catch {
        Die "mm is installed in $Bin, but your user PATH could not be updated. Add that folder to PATH, then open a new terminal."
    }
    Write-Host "Added $Bin to your user PATH."
    Broadcast-EnvironmentChange
} else {
    Write-Host "$Bin is already on your user PATH."
}
if ($env:Path -notlike "*$norm*") {
    $env:Path = "$Bin;$env:Path"
}

$mmCmd = Join-Path $Bin "mm.cmd"
$version = & $mmCmd --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Die "mm was installed but failed to start:`n$version"
}

Write-Host ""
Write-Host "installed $mmCmd -> $Root"
Write-Host $version
Write-Host ""
Write-Host "Open a new terminal, then:"
Write-Host "  mm add `"CS302`""
Write-Host "  mm"
Write-Host "  mm help"
Hold-IfExplorer
