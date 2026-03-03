param(
    [string]$RocmVenv = "",
    [string]$WorkRoot = "",
    [string]$CTranslate2Version = "4.7.1",
    [string]$RocmMergedRoot = "",
    [string]$HipArch = "gfx1150",
    [bool]$InstallAmdRocmFromGuide = $true,
    [string]$RocmCoreWheel = "https://repo.radeon.com/rocm/windows/rocm-rel-7.2/rocm_sdk_core-7.2.0.dev0-py3-none-win_amd64.whl",
    [string]$RocmDevelWheel = "https://repo.radeon.com/rocm/windows/rocm-rel-7.2/rocm_sdk_devel-7.2.0.dev0-py3-none-win_amd64.whl",
    [string]$RocmLibsWheel = "https://repo.radeon.com/rocm/windows/rocm-rel-7.2/rocm_sdk_libraries_custom-7.2.0.dev0-py3-none-win_amd64.whl",
    [string]$RocmMetaTar = "https://repo.radeon.com/rocm/windows/rocm-rel-7.2/rocm-7.2.0.dev0.tar.gz",
    [string]$TorchWheel = "https://repo.radeon.com/rocm/windows/rocm-rel-7.2/torch-2.9.1%2Brocmsdk20260116-cp312-cp312-win_amd64.whl",
    [string]$TorchAudioWheel = "https://repo.radeon.com/rocm/windows/rocm-rel-7.2/torchaudio-2.9.1%2Brocmsdk20260116-cp312-cp312-win_amd64.whl",
    [string]$TorchVisionWheel = "https://repo.radeon.com/rocm/windows/rocm-rel-7.2/torchvision-0.24.1%2Brocmsdk20260116-cp312-cp312-win_amd64.whl",
    [bool]$InstallProjectIntoRocmVenv = $true
)

$ErrorActionPreference = "Stop"

function Invoke-External {
    param(
        [string]$Name,
        [scriptblock]$Script
    )
    & $Script
    if ($LASTEXITCODE -ne 0) {
        throw "$Name failed with exit code $LASTEXITCODE"
    }
}

$cwd = (Get-Location).Path
if ([string]::IsNullOrWhiteSpace($RocmVenv)) {
    $dotVenv = Join-Path $cwd ".venv"
    $plainVenv = Join-Path $cwd "venv"
    $dotPy = Join-Path $dotVenv "Scripts\python.exe"
    $plainPy = Join-Path $plainVenv "Scripts\python.exe"
    if (Test-Path $dotPy) {
        $RocmVenv = $dotVenv
    } elseif (Test-Path $plainPy) {
        $RocmVenv = $plainVenv
    } else {
        $RocmVenv = $dotVenv
    }
}
if ([string]::IsNullOrWhiteSpace($WorkRoot)) {
    $WorkRoot = Join-Path $cwd "build\rocm-win-ct2"
}
if ([string]::IsNullOrWhiteSpace($RocmMergedRoot)) {
    $RocmMergedRoot = Join-Path $WorkRoot "_rocm_sdk_devel"
}

$python = Join-Path $RocmVenv "Scripts\python.exe"
$cmakeExe = Join-Path $RocmVenv "Scripts\cmake.exe"
$rocmMergedRootPosix = $RocmMergedRoot.Replace("\", "/")
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

if (-not (Test-Path $python)) {
    if (-not $InstallAmdRocmFromGuide) {
        throw "Python not found in ROCm venv: $python"
    }
    Write-Host "==> Create Python 3.12 venv at $RocmVenv"
    Invoke-External "Create Python 3.12 venv" { & py -3.12 -m venv $RocmVenv }
}

$pyVer = & $python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
if ($pyVer -ne "3.12") {
    throw "ROCm Windows wheels currently require Python 3.12 (found: $pyVer)."
}

if ($InstallAmdRocmFromGuide) {
    Write-Host "==> Install ROCm SDK packages (AMD guide, Windows)"
    Invoke-External "Upgrade pip tooling" { & $python -m pip install --upgrade pip setuptools wheel }
    $env:PIP_PROGRESS_BAR = "off"
    Invoke-External "Install ROCm SDK wheels" {
        & $python -m pip install --no-cache-dir `
            $RocmCoreWheel `
            $RocmDevelWheel `
            $RocmLibsWheel `
            $RocmMetaTar
    }

    Write-Host "==> Install ROCm PyTorch wheels (AMD guide, Windows)"
    Invoke-External "Install ROCm PyTorch wheels" {
        & $python -m pip install --no-cache-dir `
            $TorchWheel `
            $TorchAudioWheel `
            $TorchVisionWheel
    }

    Write-Host "==> Verify torch ROCm setup"
    Invoke-External "Verify torch ROCm setup" {
        & $python -c "import torch; print(torch.__version__); print('cuda', torch.cuda.is_available()); print('hip', torch.version.hip); print('gpu', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'none')"
    }
}

$coreRoot = Join-Path $RocmVenv "Lib\site-packages\_rocm_sdk_core"
$libsRoot = Join-Path $RocmVenv "Lib\site-packages\_rocm_sdk_libraries_custom"
$develTar = Join-Path $RocmVenv "Lib\site-packages\rocm_sdk_devel\_devel.tar"

if (-not (Test-Path $coreRoot)) { throw "Missing _rocm_sdk_core in $RocmVenv" }
if (-not (Test-Path $libsRoot)) { throw "Missing _rocm_sdk_libraries_custom in $RocmVenv" }
if (-not (Test-Path $develTar)) { throw "Missing rocm_sdk_devel/_devel.tar in $RocmVenv" }

Write-Host "==> Ensure build tools"
Invoke-External "Install build tools" {
    & $python -m pip install --upgrade pip setuptools wheel cmake ninja packaging
}

Write-Host "==> Extract ROCm devel payload"
New-Item -ItemType Directory -Path $RocmMergedRoot -Force | Out-Null
Invoke-External "Extract ROCm devel payload" { & $python -c @"
import tarfile, pathlib
src = pathlib.Path(r'$develTar')
dst = pathlib.Path(r'$([System.IO.Path]::GetDirectoryName($RocmMergedRoot))')
with tarfile.open(src, 'r') as tf:
    tf.extractall(dst)
print('extracted', src)
"@
}

Write-Host "==> Merge core + libraries into devel root"
Copy-Item -Recurse -Force (Join-Path $coreRoot "bin\*") (Join-Path $RocmMergedRoot "bin\")
Copy-Item -Recurse -Force (Join-Path $coreRoot "lib\*") (Join-Path $RocmMergedRoot "lib\")
Copy-Item -Recurse -Force (Join-Path $coreRoot "include\*") (Join-Path $RocmMergedRoot "include\")
Copy-Item -Recurse -Force (Join-Path $libsRoot "bin\*") (Join-Path $RocmMergedRoot "bin\")

$srcZip = Join-Path $WorkRoot "CTranslate2-$CTranslate2Version.zip"
$srcRoot = Join-Path $WorkRoot "CTranslate2-$CTranslate2Version"
$buildDir = Join-Path $srcRoot "build-hip-win"
$depsDir = Join-Path $WorkRoot "deps"

Write-Host "==> Download CTranslate2 source"
New-Item -ItemType Directory -Path $WorkRoot -Force | Out-Null
$ProgressPreference = "SilentlyContinue"
Invoke-WebRequest -UseBasicParsing "https://github.com/OpenNMT/CTranslate2/archive/refs/tags/v$CTranslate2Version.zip" -OutFile $srcZip
Expand-Archive -Path $srcZip -DestinationPath $WorkRoot -Force

Write-Host "==> Download required submodules (spdlog + cpu_features)"
New-Item -ItemType Directory -Path $depsDir -Force | Out-Null
Invoke-WebRequest -UseBasicParsing "https://github.com/gabime/spdlog/archive/refs/tags/v1.15.3.zip" -OutFile (Join-Path $depsDir "spdlog.zip")
Invoke-WebRequest -UseBasicParsing "https://github.com/google/cpu_features/archive/refs/tags/v0.9.0.zip" -OutFile (Join-Path $depsDir "cpu_features.zip")
Expand-Archive -Path (Join-Path $depsDir "spdlog.zip") -DestinationPath $depsDir -Force
Expand-Archive -Path (Join-Path $depsDir "cpu_features.zip") -DestinationPath $depsDir -Force

New-Item -ItemType Directory -Path (Join-Path $srcRoot "third_party\spdlog") -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $srcRoot "third_party\cpu_features") -Force | Out-Null
Copy-Item -Recurse -Force (Join-Path $depsDir "spdlog-1.15.3\*") (Join-Path $srcRoot "third_party\spdlog\")
Copy-Item -Recurse -Force (Join-Path $depsDir "cpu_features-0.9.0\*") (Join-Path $srcRoot "third_party\cpu_features\")

$env:ROCM_PATH = $rocmMergedRootPosix
$env:HIP_PLATFORM = "amd"
$env:HIP_RUNTIME = "rocclr"
$env:PATH = "$RocmMergedRoot\lib\llvm\bin;$RocmMergedRoot\bin;" + $env:PATH
$hipLangDir = Join-Path $RocmMergedRoot "lib\cmake\hip-lang"
if (-not (Test-Path (Join-Path $hipLangDir "hip-lang-config.cmake"))) {
    throw "Missing hip-lang config in merged ROCm root: $hipLangDir"
}
$cmakePrefix = @(
    $rocmMergedRootPosix,
    (Join-Path $RocmMergedRoot "lib/cmake").Replace("\", "/"),
    $hipLangDir.Replace("\", "/")
) -join ";"

Write-Host "==> Configure CTranslate2 HIP build"
Invoke-External "Configure CTranslate2 HIP build" {
    & $cmakeExe -S $srcRoot -B $buildDir -G Ninja `
        -DCMAKE_BUILD_TYPE=Release `
        -DWITH_HIP=ON `
        -DWITH_CUDA=OFF `
        -DWITH_MKL=OFF `
        -DOPENMP_RUNTIME=NONE `
        -DBUILD_CLI=OFF `
        -DCMAKE_HIP_ARCHITECTURES=$HipArch `
        -DCMAKE_HIP_COMPILER="$rocmMergedRootPosix/lib/llvm/bin/clang++.exe" `
        -DCMAKE_HIP_COMPILER_ROCM_ROOT="$rocmMergedRootPosix" `
        -DCMAKE_PREFIX_PATH="$cmakePrefix" `
        -Dhip-lang_DIR="$($hipLangDir.Replace("\", "/"))" `
        -DCMAKE_HIP_FLAGS="--rocm-path=$rocmMergedRootPosix --rocm-device-lib-path=$rocmMergedRootPosix/lib/llvm/amdgcn/bitcode" `
        -DCMAKE_CXX_FLAGS="--rocm-path=$rocmMergedRootPosix --rocm-device-lib-path=$rocmMergedRootPosix/lib/llvm/amdgcn/bitcode" `
        -DCMAKE_RC_COMPILER="C:/Program Files (x86)/Windows Kits/10/bin/10.0.22621.0/x64/rc.exe" `
        -DCMAKE_MT="C:/Program Files (x86)/Windows Kits/10/bin/10.0.22621.0/x64/mt.exe"
}

Write-Host "==> Build + install native library"
Invoke-External "Build CTranslate2" { & $cmakeExe --build $buildDir --config Release -j 8 }
Invoke-External "Install CTranslate2 native artifacts" { & $cmakeExe --install $buildDir --prefix $RocmVenv }

Write-Host "==> Build + install Python wheel"
Push-Location (Join-Path $srcRoot "python")
try {
    $env:CTRANSLATE2_ROOT = $RocmVenv.Replace("\", "/")
    Invoke-External "Install Python build requirements" { & $python -m pip install -r install_requirements.txt }
    Invoke-External "Build ctranslate2 wheel" { & $python setup.py bdist_wheel }
    $wheel = Get-ChildItem -Path dist -Filter "ctranslate2-$CTranslate2Version-*.whl" | Select-Object -First 1
    if (-not $wheel) { throw "Built wheel not found in dist/." }
    $env:PIP_PROGRESS_BAR = "off"
    Invoke-External "Install ctranslate2 wheel" { & $python -m pip install --force-reinstall $wheel.FullName }
}
finally {
    Pop-Location
}

Write-Host "==> Smoke test"
Invoke-External "Run smoke test" { & $python -c @"
import os
os.add_dll_directory(r'$RocmVenv\\bin')
os.add_dll_directory(r'$RocmMergedRoot\\bin')
import ctranslate2, torch
print('ctranslate2', ctranslate2.__version__)
print('supported cuda compute types', ctranslate2.get_supported_compute_types('cuda'))
print('torch cuda', torch.cuda.is_available())
if torch.cuda.is_available():
    print('gpu', torch.cuda.get_device_name(0))
"@
}

if ($InstallProjectIntoRocmVenv) {
    Write-Host "==> Install hotkey-transcriber into ROCm venv"
    Push-Location $repoRoot
    try {
        Invoke-External "Install project (editable) into ROCm venv" { & $python -m pip install -e . }
    }
    finally {
        Pop-Location
    }
}

Write-Host "Done."
Write-Host "For native Windows ROCm run the app from this ROCm venv (not a global/pipx install):"
Write-Host "  `$env:HOTKEY_TRANSCRIBER_BACKEND='native'"
Write-Host "  `$env:HOTKEY_TRANSCRIBER_ROCM_ROOT='$RocmMergedRoot'"
Write-Host "  & '$RocmVenv\Scripts\hotkey-transcriber.exe'"
Write-Host "If that exe does not exist:"
Write-Host "  & '$python' -m pip install -e '$repoRoot'"
Write-Host "  & '$RocmVenv\Scripts\hotkey-transcriber.exe'"
