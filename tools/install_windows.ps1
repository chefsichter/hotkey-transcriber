param(
    [ValidateSet("ask", "on", "off")]
    [string]$Autostart = "ask",
    [switch]$AmdGpu
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptDir "..")).Path

# ── ROCm wheel URLs (Python 3.12 / ROCm 7.2) ────────────────────────
$RocmCoreWheel = "https://repo.radeon.com/rocm/windows/rocm-rel-7.2/rocm_sdk_core-7.2.0.dev0-py3-none-win_amd64.whl"
$RocmDevelWheel = "https://repo.radeon.com/rocm/windows/rocm-rel-7.2/rocm_sdk_devel-7.2.0.dev0-py3-none-win_amd64.whl"
$RocmLibsWheel = "https://repo.radeon.com/rocm/windows/rocm-rel-7.2/rocm_sdk_libraries_custom-7.2.0.dev0-py3-none-win_amd64.whl"
$RocmMetaTar = "https://repo.radeon.com/rocm/windows/rocm-rel-7.2/rocm-7.2.0.dev0.tar.gz"
$TorchWheel = "https://repo.radeon.com/rocm/windows/rocm-rel-7.2/torch-2.9.1%2Brocmsdk20260116-cp312-cp312-win_amd64.whl"
$TorchAudioWheel = "https://repo.radeon.com/rocm/windows/rocm-rel-7.2/torchaudio-2.9.1%2Brocmsdk20260116-cp312-cp312-win_amd64.whl"
$TorchVisionWheel = "https://repo.radeon.com/rocm/windows/rocm-rel-7.2/torchvision-0.24.1%2Brocmsdk20260116-cp312-cp312-win_amd64.whl"

# ── helpers ───────────────────────────────────────────────────────────

function Invoke-External {
    param([string]$Name, [scriptblock]$Script)
    # Prevent native command stdout from leaking into function return values
    # when callers assign function output (e.g. $venvDir = Install-AmdGpuSupport).
    & $Script | Out-Host
    if ($LASTEXITCODE -ne 0) { throw "$Name failed with exit code $LASTEXITCODE" }
}

function Get-PythonCommand {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        return "py"
    }
    if (Get-Command python -ErrorAction SilentlyContinue) {
        return "python"
    }
    throw "Python launcher not found. Install Python first."
}

function Get-HotkeyTranscriberExecutable {
    param([string]$VenvDir = "")

    if ($VenvDir -and (Test-Path (Join-Path $VenvDir "Scripts\hotkey-transcriber.exe"))) {
        return (Join-Path $VenvDir "Scripts\hotkey-transcriber.exe")
    }

    $cmd = Get-Command hotkey-transcriber -ErrorAction SilentlyContinue
    if ($cmd -and (Test-Path $cmd.Source)) {
        return $cmd.Source
    }

    $candidates = @(
        (Join-Path $env:USERPROFILE ".local\\bin\\hotkey-transcriber.exe"),
        (Join-Path $env:USERPROFILE ".local\\bin\\hotkey-transcriber")
    )
    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) {
            return $candidate
        }
    }

    throw "Could not find hotkey-transcriber executable after install."
}

function Get-ShortcutIconPath {
    $iconDir = Join-Path $env:APPDATA "hotkey-transcriber"
    New-Item -ItemType Directory -Force -Path $iconDir | Out-Null
    return Join-Path $iconDir "hotkey-transcriber.ico"
}

function Ensure-ShortcutIcon {
    $iconPath = Get-ShortcutIconPath
    $pngPath = Join-Path $repoRoot "src\\hotkey_transcriber\\resources\\icon\\microphone.png"

    if (Test-Path $pngPath) {
        Add-Type -AssemblyName System.Drawing
        $bitmap = [System.Drawing.Bitmap]::FromFile($pngPath)
        try {
            $icon = [System.Drawing.Icon]::FromHandle($bitmap.GetHicon())
            try {
                $stream = [System.IO.File]::Open($iconPath, [System.IO.FileMode]::Create)
                try {
                    $icon.Save($stream)
                } finally {
                    $stream.Close()
                }
            } finally {
                $icon.Dispose()
            }
        } finally {
            $bitmap.Dispose()
        }
    }

    if (Test-Path $iconPath) {
        return $iconPath
    }

    return (Get-HotkeyTranscriberExecutable)
}

function Get-LauncherScriptPath {
    $launcherDir = Join-Path $env:APPDATA "hotkey-transcriber"
    New-Item -ItemType Directory -Force -Path $launcherDir | Out-Null
    return Join-Path $launcherDir "launch_hotkey_transcriber.vbs"
}

function New-HiddenLauncherScript {
    param([string]$ExePath)
    $launcherPath = Get-LauncherScriptPath
    $escaped = $ExePath.Replace('"', '""')
    $content = @"
Set WshShell = CreateObject("WScript.Shell")
WshShell.Run """$escaped""", 0, False
"@
    Set-Content -Path $launcherPath -Value $content -Encoding UTF8
    return $launcherPath
}

function New-StartMenuShortcut {
    param([string]$ExePath)
    $launcherPath = New-HiddenLauncherScript -ExePath $ExePath
    $iconPath = Ensure-ShortcutIcon
    $programsDir = [Environment]::GetFolderPath("Programs")
    $shortcutPath = Join-Path $programsDir "Hotkey Transcriber.lnk"

    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = "wscript.exe"
    $shortcut.Arguments = "`"$launcherPath`""
    $shortcut.WorkingDirectory = Split-Path -Parent $launcherPath
    $shortcut.Description = "Hotkey Transcriber (tray app)"
    $shortcut.IconLocation = "$iconPath,0"
    $shortcut.Save()

    Write-Host "Startmenü-Verknüpfung erstellt: $shortcutPath (ohne Terminalfenster)"
}

# ── AMD GPU install (venv + ROCm torch + openai-whisper) ─────────────

function Install-AmdGpuSupport {
    $venvDir = Join-Path $repoRoot ".venv"
    $python = Join-Path $venvDir "Scripts\python.exe"

    if (-not (Test-Path $python)) {
        Write-Host "==> Erstelle Python 3.12 venv in $venvDir"
        Invoke-External "Create Python 3.12 venv" { & py -3.12 -m venv $venvDir }
    }

    $pyVer = & $python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
    if ($pyVer -ne "3.12") {
        throw "AMD ROCm wheels erfordern Python 3.12 (gefunden: $pyVer). Bitte Python 3.12 installieren."
    }

    Write-Host "==> Upgrade pip"
    Invoke-External "Upgrade pip" { & $python -m pip install --upgrade pip setuptools wheel }

    Write-Host "==> Installiere ROCm SDK Pakete"
    $env:PIP_PROGRESS_BAR = "off"
    Invoke-External "Install ROCm SDK wheels" {
        & $python -m pip install --no-cache-dir `
            $RocmCoreWheel `
            $RocmDevelWheel `
            $RocmLibsWheel `
            $RocmMetaTar
    }

    Write-Host "==> Installiere ROCm PyTorch"
    Invoke-External "Install ROCm PyTorch wheels" {
        & $python -m pip install --no-cache-dir `
            $TorchWheel `
            $TorchAudioWheel `
            $TorchVisionWheel
    }

    Write-Host "==> Installiere openai-whisper"
    Invoke-External "Install openai-whisper" { & $python -m pip install openai-whisper }

    Write-Host "==> Installiere hotkey-transcriber"
    Invoke-External "Install project" { & $python -m pip install -e $repoRoot }

    Write-Host "==> Verifiziere GPU-Zugriff"
    Invoke-External "Verify torch GPU" {
        & $python -c "import torch; assert torch.cuda.is_available(), 'GPU nicht erkannt'; print(f'GPU: {torch.cuda.get_device_name(0)}')"
    }

    return $venvDir
}

# ── main ──────────────────────────────────────────────────────────────

if ($AmdGpu) {
    Write-Host "Installiere hotkey-transcriber mit AMD GPU Support (ROCm + torch)..."
    $venvDir = Install-AmdGpuSupport
    $exePath = Get-HotkeyTranscriberExecutable -VenvDir $venvDir
    New-StartMenuShortcut -ExePath $exePath
} else {
    if (-not (Get-Command pipx -ErrorAction SilentlyContinue)) {
        $python = Get-PythonCommand
        Write-Host "pipx not found - installing with $python..."
        & $python -m pip install --user pipx
        & $python -m pipx ensurepath
        Write-Host "pipx installed. Restart PowerShell if command resolution still fails."
    }

    Write-Host "Installing hotkey-transcriber with pipx..."
    pipx install --force $repoRoot
    $exePath = Get-HotkeyTranscriberExecutable
    New-StartMenuShortcut -ExePath $exePath
}

if ($Autostart -eq "ask") {
    $answer = Read-Host "Autostart aktivieren? (j/n)"
    if ($answer -match "^(j|ja|y|yes)$") {
        $Autostart = "on"
    } else {
        $Autostart = "off"
    }
}

$python = Get-PythonCommand
$previousPythonPath = $env:PYTHONPATH
try {
    $env:PYTHONPATH = Join-Path $repoRoot "src"
    if ($Autostart -eq "on") {
        & $python -m hotkey_transcriber.autostart --set on --status
    } else {
        & $python -m hotkey_transcriber.autostart --set off --status
    }
} finally {
    if ($null -ne $previousPythonPath) {
        $env:PYTHONPATH = $previousPythonPath
    } else {
        Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
    }
}

Write-Host "Installation abgeschlossen."
