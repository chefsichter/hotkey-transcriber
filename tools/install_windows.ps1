param(
    [ValidateSet("ask", "on", "off")]
    [string]$Autostart = "ask"
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptDir "..")).Path

function Invoke-External {
    param([string]$Name, [scriptblock]$Script)
    & $Script | Out-Host
    if ($LASTEXITCODE -ne 0) { throw "$Name failed with exit code $LASTEXITCODE" }
}

function Get-PythonCommand {
    if (Get-Command py -ErrorAction SilentlyContinue) { return "py" }
    if (Get-Command python -ErrorAction SilentlyContinue) { return "python" }
    throw "Python launcher not found. Install Python first."
}

function Get-HotkeyTranscriberExecutable {
    param([string]$VenvDir = "")

    if ($VenvDir -and (Test-Path (Join-Path $VenvDir "Scripts\hotkey-transcriber.exe"))) {
        return (Join-Path $VenvDir "Scripts\hotkey-transcriber.exe")
    }

    $cmd = Get-Command hotkey-transcriber -ErrorAction SilentlyContinue
    if ($cmd -and (Test-Path $cmd.Source)) { return $cmd.Source }

    $candidates = @(
        (Join-Path $env:USERPROFILE ".local\bin\hotkey-transcriber.exe"),
        (Join-Path $env:USERPROFILE ".local\bin\hotkey-transcriber")
    )
    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) { return $candidate }
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
    $pngPath = Join-Path $repoRoot "src\hotkey_transcriber\resources\icon\microphone.png"

    if (Test-Path $pngPath) {
        Add-Type -AssemblyName System.Drawing
        $bitmap = [System.Drawing.Bitmap]::FromFile($pngPath)
        try {
            $icon = [System.Drawing.Icon]::FromHandle($bitmap.GetHicon())
            try {
                $stream = [System.IO.File]::Open($iconPath, [System.IO.FileMode]::Create)
                try { $icon.Save($stream) } finally { $stream.Close() }
            } finally { $icon.Dispose() }
        } finally { $bitmap.Dispose() }
    }

    if (Test-Path $iconPath) { return $iconPath }
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

    Write-Host "Start menu shortcut created: $shortcutPath (without terminal window)"
}

function Require-Command {
    param([string]$Name)
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required command '$Name' not found. Install it and rerun the installer."
    }
}

function Resolve-VulkanSdkRoot {
    if ($env:VULKAN_SDK -and (Test-Path $env:VULKAN_SDK)) {
        return $env:VULKAN_SDK
    }

    $base = "C:\VulkanSDK"
    if (-not (Test-Path $base)) { return $null }

    $latest = Get-ChildItem $base -Directory |
        Sort-Object Name -Descending |
        Select-Object -First 1
    if (-not $latest) { return $null }
    return $latest.FullName
}

function Install-NpuBackend {
    $venvDir = Join-Path $repoRoot ".venv"
    $python = Join-Path $venvDir "Scripts\python.exe"

    if (-not (Test-Path $python)) {
        Write-Host "==> Creating venv in $venvDir"
        Invoke-External "Create venv" { & py -3.12 -m venv $venvDir }
    }

    Write-Host "==> Upgrading packaging tools"
    Invoke-External "Upgrade pip" { & $python -m pip install --upgrade pip "setuptools<82" wheel }

    Write-Host "==> Installing project in editable mode"
    Invoke-External "Install project" { & $python -m pip install -e $repoRoot }

    Write-Host ""
    Write-Host "VORAUSSETZUNGEN fuer AMD NPU-Backend (ONNX/VitisAI):"
    Write-Host "  - AMD Ryzen AI Software >= 1.7.0 mit Conda-Umgebung 'ryzen-ai-1.7.0'"
    Write-Host "    https://ryzenai.docs.amd.com/en/latest/inst.html"
    Write-Host "  - NPU-Treiber Version >= .280"
    Write-Host "  - Nur unterstuetzt: Ryzen AI 300 Series (Strix Point / XDNA2)"
    Write-Host ""
    $confirm = Read-Host "Sind alle Voraussetzungen erfuellt? (j/n)"
    if ($confirm -notmatch "^(j|ja|y|yes)$") {
        Write-Host "Installation abgebrochen. Bitte zuerst AMD Ryzen AI Software installieren."
        exit 1
    }

    # Find ryzen-ai-1.7.0 conda python
    $condaEnvCandidates = @(
        "C:\ProgramData\miniconda3\envs\ryzen-ai-1.7.0",
        "$env:USERPROFILE\.conda\envs\ryzen-ai-1.7.0",
        "$env:LOCALAPPDATA\conda\conda\envs\ryzen-ai-1.7.0",
        "$env:USERPROFILE\AppData\Local\conda\conda\envs\ryzen-ai-1.7.0"
    )
    $condaPython = $null
    foreach ($envPath in $condaEnvCandidates) {
        $candidate = Join-Path $envPath "python.exe"
        if (Test-Path $candidate) {
            $condaPython = $candidate
            Write-Host "==> Conda-Umgebung gefunden: $envPath"
            break
        }
    }
    if (-not $condaPython) {
        throw "Python-Interpreter fuer ryzen-ai-1.7.0 nicht gefunden. Stelle sicher, dass AMD Ryzen AI Software 1.7.0 installiert ist."
    }

    # Verify vaip_config.json
    $vaipConfigCandidates = @(
        "C:\Program Files\RyzenAI\1.7.0\voe-4.0-win_amd64\vaip_config.json",
        "C:\Program Files\RyzenAI\1.6.1\voe-4.0-win_amd64\vaip_config.json",
        "C:\Program Files\RyzenAI\1.5.0\voe-4.0-win_amd64\vaip_config.json"
    )
    $vaipConfig = $null
    foreach ($candidate in $vaipConfigCandidates) {
        if (Test-Path $candidate) {
            $vaipConfig = $candidate
            Write-Host "==> vaip_config.json gefunden: $vaipConfig"
            break
        }
    }
    if (-not $vaipConfig) {
        throw "vaip_config.json nicht gefunden. Stelle sicher, dass AMD Ryzen AI Software korrekt installiert ist."
    }

    # Install transformers in conda env if not present
    Write-Host "==> Pruefe 'transformers' in Conda-Umgebung..."
    $checkResult = & $condaPython -c "import transformers; print('ok')" 2>&1
    if ($checkResult -notmatch "ok") {
        Write-Host "==> Installiere 'transformers' in Conda-Umgebung..."
        Invoke-External "Install transformers" { & $condaPython -m pip install transformers }
    } else {
        Write-Host "==> 'transformers' bereits vorhanden."
    }

    # Set backend env var; clear legacy whisper.cpp CLI var
    [Environment]::SetEnvironmentVariable("HOTKEY_TRANSCRIBER_BACKEND", "whisper_npu", "User")
    $env:HOTKEY_TRANSCRIBER_BACKEND = "whisper_npu"
    [Environment]::SetEnvironmentVariable("HOTKEY_TRANSCRIBER_WHISPER_CPP_CLI", $null, "User")

    Write-Host "==> AMD NPU ONNX/VitisAI-Backend konfiguriert."
    Write-Host "    ONNX-Modelle werden beim ersten Start automatisch heruntergeladen."
    Write-Host "    Die erste NPU-Kompilierung kann mehrere Minuten dauern."
    return $venvDir
}

function Install-VulkanBackend {
    $venvDir = Join-Path $repoRoot ".venv"
    $python = Join-Path $venvDir "Scripts\python.exe"

    if (-not (Test-Path $python)) {
        Write-Host "==> Creating venv in $venvDir"
        Invoke-External "Create venv" { & py -3.12 -m venv $venvDir }
    }

    Write-Host "==> Upgrading packaging tools"
    Invoke-External "Upgrade pip" { & $python -m pip install --upgrade pip "setuptools<82" wheel }

    Write-Host "==> Installing project in editable mode"
    Invoke-External "Install project" { & $python -m pip install -e $repoRoot }

    Require-Command -Name "git"
    Require-Command -Name "cmake"

    $vulkanSdk = Resolve-VulkanSdkRoot
    if (-not $vulkanSdk) {
        throw "Vulkan SDK not found. Install with:`n  winget install --id KhronosGroup.VulkanSDK --exact --silent --accept-package-agreements --accept-source-agreements"
    }
    $glslcPath = Join-Path $vulkanSdk "Bin\glslc.exe"
    $vulkanInclude = Join-Path $vulkanSdk "Include\vulkan\vulkan.h"
    if (-not (Test-Path $glslcPath) -or -not (Test-Path $vulkanInclude)) {
        throw "Vulkan SDK seems incomplete. Missing glslc/include under: $vulkanSdk"
    }
    $env:VULKAN_SDK = $vulkanSdk
    $env:PATH = "$(Join-Path $vulkanSdk 'Bin');$env:PATH"

    $whisperRoot = Join-Path $env:SystemDrive "htwcpp"
    $whisperSrc = Join-Path $whisperRoot "src"
    $whisperBuild = Join-Path $whisperRoot "build"
    New-Item -ItemType Directory -Force -Path $whisperRoot | Out-Null

    if (-not (Test-Path $whisperSrc)) {
        Write-Host "==> Cloning whisper.cpp"
        Invoke-External "Clone whisper.cpp" {
            & git clone --depth 1 https://github.com/ggml-org/whisper.cpp.git $whisperSrc
        }
    } else {
        Write-Host "==> Updating whisper.cpp"
        Invoke-External "Update whisper.cpp" {
            & git -C $whisperSrc pull --ff-only
        }
    }

    Write-Host "==> Configuring whisper.cpp (Vulkan)"
    Invoke-External "CMake configure whisper.cpp" {
        & cmake -S $whisperSrc -B $whisperBuild -DGGML_VULKAN=ON -DWHISPER_BUILD_EXAMPLES=ON
    }

    Write-Host "==> Building whisper-cli (Release)"
    Invoke-External "Build whisper-cli" {
        & cmake --build $whisperBuild --config Release --target whisper-cli
    }

    $candidates = @(
        (Join-Path $whisperBuild "bin\Release\whisper-cli.exe"),
        (Join-Path $whisperBuild "bin\whisper-cli.exe"),
        (Join-Path $whisperRoot "whisper-cli.exe")
    )
    $cliPath = $null
    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) {
            $cliPath = $candidate
            break
        }
    }
    if (-not $cliPath) { throw "whisper-cli.exe not found after build." }

    Write-Host "==> Verifying whisper-cli"
    Invoke-External "Verify whisper-cli" { & $cliPath --help }

    [Environment]::SetEnvironmentVariable(
        "HOTKEY_TRANSCRIBER_WHISPER_CPP_CLI",
        $cliPath,
        "User"
    )
    $env:HOTKEY_TRANSCRIBER_WHISPER_CPP_CLI = $cliPath

    Write-Host "==> whisper.cpp configured: $cliPath"
    return $venvDir
}

function Install-PipxBackend {
    if (-not (Get-Command pipx -ErrorAction SilentlyContinue)) {
        $python = Get-PythonCommand
        Write-Host "pipx not found - installing with $python..."
        & $python -m pip install --user pipx
        & $python -m pipx ensurepath
        Write-Host "pipx installed. Restart PowerShell if command resolution still fails."
    }

    Write-Host "Installing hotkey-transcriber with pipx..."
    pipx install --force $repoRoot
    return ""
}

# ── Backend-Auswahl ───────────────────────────────────────────────────────────

Write-Host ""
Write-Host "Welches Backend soll installiert werden?"
Write-Host "  [1] whisper.cpp + Vulkan  (GPU nativ, empfohlen fuer AMD/NVIDIA)"
Write-Host "      Runtime:      whisper.cpp (ggml-org/whisper.cpp, GGML-Modelle)"
Write-Host "      Inferenz auf: GPU via Vulkan"
Write-Host "      Voraussetzung: Vulkan SDK, git, cmake"
Write-Host "      winget install --id KhronosGroup.VulkanSDK --exact"
Write-Host "  [2] WSL ROCm              (AMD GPU via WSL; WSL-Setup separat via setup_wsl_amd.ps1)"
Write-Host "      Runtime:      faster-whisper (CTranslate2, GGML-kompatible Modelle)"
Write-Host "      Inferenz auf: AMD GPU via ROCm in WSL"
Write-Host "  [3] CPU / Standard        (kein GPU, nur CPU)"
Write-Host "      Runtime:      faster-whisper (CTranslate2)"
Write-Host "      Inferenz auf: CPU"
Write-Host "  [4] AMD NPU ONNX/VitisAI  (Ryzen AI 300 XDNA2-NPU; erfordert Ryzen AI Software >= 1.7)"
Write-Host "      Runtime:      ONNX Runtime + VitisAI Execution Provider (AMD ONNX-Modelle)"
Write-Host "      Inferenz auf: NPU (Encoder + Decoder via VitisAI EP)"
Write-Host "      https://ryzenai.docs.amd.com/en/latest/inst.html"
Write-Host ""

do {
    $backendChoice = Read-Host "Auswahl (1/2/3/4)"
} while ($backendChoice -notin @("1", "2", "3", "4"))

switch ($backendChoice) {
    "1" {
        Write-Host ""
        Write-Host "==> Installiere whisper.cpp + Vulkan-Backend..."
        $venvDir = Install-VulkanBackend
        $exePath = Get-HotkeyTranscriberExecutable -VenvDir $venvDir
        New-StartMenuShortcut -ExePath $exePath
    }
    "2" {
        Write-Host ""
        Write-Host "==> Installiere fuer WSL-ROCm-Backend (App via pipx, WSL-Setup separat)..."
        Install-PipxBackend | Out-Null
        $exePath = Get-HotkeyTranscriberExecutable
        New-StartMenuShortcut -ExePath $exePath
        [Environment]::SetEnvironmentVariable(
            "HOTKEY_TRANSCRIBER_BACKEND",
            "wsl_amd",
            "User"
        )
        $env:HOTKEY_TRANSCRIBER_BACKEND = "wsl_amd"
        Write-Host "==> HOTKEY_TRANSCRIBER_BACKEND=wsl_amd gesetzt."
        Write-Host "    WSL + ROCm separat einrichten: .\tools\setup_wsl_amd.ps1"
    }
    "3" {
        Write-Host ""
        Write-Host "==> Installiere Standard-Backend (CPU, faster-whisper)..."
        Install-PipxBackend | Out-Null
        $exePath = Get-HotkeyTranscriberExecutable
        New-StartMenuShortcut -ExePath $exePath
    }
    "4" {
        Write-Host ""
        Write-Host "==> Installiere AMD NPU ONNX/VitisAI-Backend..."
        $venvDir = Install-NpuBackend
        $exePath = Get-HotkeyTranscriberExecutable -VenvDir $venvDir
        New-StartMenuShortcut -ExePath $exePath
    }
}

# ── Autostart ─────────────────────────────────────────────────────────────────

if ($Autostart -eq "ask") {
    $answer = Read-Host "Enable autostart? (y/n)"
    if ($answer -match "^(j|ja|y|yes)$") { $Autostart = "on" } else { $Autostart = "off" }
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

Write-Host "Installation complete."
