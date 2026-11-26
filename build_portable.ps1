param([switch]$FullAcceptance)

$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot
$env:PYTHONUTF8 = "1"
$env:PYTHONDONTWRITEBYTECODE = "1"

python -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)"
if ($LASTEXITCODE -ne 0) {
    throw "Python 3.9 or newer is required to build this application."
}

$installerCheck = @'
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
import sys

try:
    for filename in ('requirements.txt', 'requirements-build.txt'):
        for line in Path(filename).read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if not line or line.startswith(('#', '-r ')):
                continue
            name, pinned = line.split('==', 1)
            if version(name) != pinned:
                sys.exit(1)
except (PackageNotFoundError, ValueError):
    sys.exit(1)
'@
python -c $installerCheck
if ($LASTEXITCODE -ne 0) {
    Write-Host "Compatible PyInstaller or PySide6 is missing; installing the build requirements for this Python environment."
    $previousPipNoIndex = $env:PIP_NO_INDEX
    $previousPipIndexUrl = $env:PIP_INDEX_URL
    try {
        Remove-Item Env:PIP_NO_INDEX -ErrorAction SilentlyContinue
        if ([string]::IsNullOrWhiteSpace($env:PIP_INDEX_URL)) {
            $env:PIP_INDEX_URL = "https://pypi.org/simple"
        }
        python -m pip install --disable-pip-version-check -r requirements-build.txt
        if ($LASTEXITCODE -ne 0) {
            throw "Could not install build requirements. Check Python pip, network access, and the configured package index."
        }
    }
    finally {
        if ($null -eq $previousPipNoIndex) {
            Remove-Item Env:PIP_NO_INDEX -ErrorAction SilentlyContinue
        }
        else {
            $env:PIP_NO_INDEX = $previousPipNoIndex
        }
        if ($null -eq $previousPipIndexUrl) {
            Remove-Item Env:PIP_INDEX_URL -ErrorAction SilentlyContinue
        }
        else {
            $env:PIP_INDEX_URL = $previousPipIndexUrl
        }
    }
    python -c $installerCheck
    if ($LASTEXITCODE -ne 0) {
        throw "Installation did not provide compatible PyInstaller and PySide6 versions in this Python environment."
    }
}

foreach ($example in @('content.csv', 'examples/template_gallery.csv', 'examples/template_gallery_F-I.csv')) {
    python generate.py --input $example --check
    if ($LASTEXITCODE -ne 0) {
        throw "CSV example validation failed: $example."
    }
}

$buildRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("calendar-build-" + [guid]::NewGuid().ToString("N"))
$buildRootFull = [System.IO.Path]::GetFullPath($buildRoot)
$tempRoot = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath()).TrimEnd([System.IO.Path]::DirectorySeparatorChar) + [System.IO.Path]::DirectorySeparatorChar
if (-not $buildRootFull.StartsWith($tempRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing to build outside the temp directory."
}
New-Item -ItemType Directory -Path $buildRootFull | Out-Null

try {
$arguments = @(
    "-m", "PyInstaller", "--noconfirm", "--clean", "--onedir",
    "--name", "CalendarWorkflow",
    "--windowed",
    "--icon", (Join-Path $PSScriptRoot "assets/calendar.ico"),
    "--hidden-import", "desktop",
    "--distpath", (Join-Path $buildRoot "dist"),
    "--workpath", (Join-Path $buildRoot "work"),
    "--specpath", (Join-Path $buildRoot "spec"),
    "--add-data", ((Join-Path $PSScriptRoot "tools/resvg/resvg.exe") + ";tools/resvg"),
    "--add-data", ((Join-Path $PSScriptRoot "data/hitokoto") + ";data/hitokoto"),
    "--add-data", ((Join-Path $PSScriptRoot "assets/calendar.ico") + ";assets")
)
python @arguments launcher.py
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller build failed."
}

$stagedApp = Join-Path $buildRootFull "dist/CalendarWorkflow"
if (-not (Test-Path -LiteralPath (Join-Path $stagedApp "CalendarWorkflow.exe") -PathType Leaf)) {
    throw "Build finished without producing CalendarWorkflow.exe."
}

$documentationRoot = Join-Path $stagedApp "Documentation"
New-Item -ItemType Directory -Path $documentationRoot -Force | Out-Null
Copy-Item -LiteralPath "PORTABLE_README.md" -Destination (Join-Path $stagedApp "README.md") -Force
foreach ($document in 'USER_GUIDE.md','CHANGELOG.md','RELEASE_HANDOFF.md','HITOKOTO_SOURCE.md','QUOTE_SOURCES.md') {
    Copy-Item -LiteralPath $document -Destination $documentationRoot -Force
}
python tools/collect_licenses.py $documentationRoot
if ($LASTEXITCODE -ne 0) {
    throw "Could not collect required project and third-party licenses."
}
$noticesRoot = Join-Path $documentationRoot "THIRD_PARTY_NOTICES"
New-Item -ItemType Directory -Path $noticesRoot -Force | Out-Null
Copy-Item -LiteralPath "tools/resvg/NOTICE.md" -Destination (Join-Path $noticesRoot "resvg-NOTICE.md") -Force
Copy-Item -LiteralPath "tools/resvg/LICENSE-APACHE" -Destination (Join-Path $noticesRoot "resvg-LICENSE-APACHE") -Force
Copy-Item -LiteralPath "tools/resvg/LICENSE-MIT" -Destination (Join-Path $noticesRoot "resvg-LICENSE-MIT") -Force
$hitokotoNotice = Join-Path $noticesRoot "hitokoto"
New-Item -ItemType Directory -Path $hitokotoNotice -Force | Out-Null
Copy-Item -LiteralPath "data/hitokoto/AGPL-3.0.txt" -Destination (Join-Path $hitokotoNotice "AGPL-3.0.txt") -Force
Copy-Item -LiteralPath "HITOKOTO_SOURCE.md" -Destination (Join-Path $hitokotoNotice "SOURCE.md") -Force

$requiredPackageFiles = @(
    "CalendarWorkflow.exe",
    "_internal/assets/calendar.ico",
    "_internal/tools/resvg/resvg.exe",
    "README.md",
    "Documentation/USER_GUIDE.md",
    "Documentation/CHANGELOG.md",
    "Documentation/RELEASE_HANDOFF.md",
    "Documentation/HITOKOTO_SOURCE.md",
    "Documentation/QUOTE_SOURCES.md",
    "Documentation/LICENSE",
    "Documentation/THIRD_PARTY_NOTICES.md",
    "Documentation/BUILD_DEPENDENCIES.json",
    "Documentation/THIRD_PARTY_NOTICES/PYTHON-LICENSE.txt",
    "Documentation/THIRD_PARTY_NOTICES/qt/LGPL-3.0-only.txt",
    "Documentation/THIRD_PARTY_NOTICES/qt/GPL-3.0-only.txt",
    "_internal/data/hitokoto/b.json",
    "_internal/data/hitokoto/d.json",
    "_internal/data/hitokoto/h.json",
    "_internal/data/hitokoto/k.json",
    "Documentation/THIRD_PARTY_NOTICES/hitokoto/AGPL-3.0.txt",
    "Documentation/THIRD_PARTY_NOTICES/hitokoto/SOURCE.md",
    "Documentation/THIRD_PARTY_NOTICES/resvg-NOTICE.md",
    "Documentation/THIRD_PARTY_NOTICES/resvg-LICENSE-APACHE",
    "Documentation/THIRD_PARTY_NOTICES/resvg-LICENSE-MIT"
)
if (Test-Path -LiteralPath (Join-Path $stagedApp '_internal/data/chinese-gushiwen-sentences.json')) {
    throw "The portable package must not include the retired Chinese Gushiwen corpus."
}
foreach ($relativePath in $requiredPackageFiles) {
    if (-not (Test-Path -LiteralPath (Join-Path $stagedApp $relativePath) -PathType Leaf)) {
        throw "Required distribution file is missing: $relativePath"
    }
}
$allowedRootEntries = @("CalendarWorkflow.exe", "README.md", "_internal", "Documentation")
$unexpectedRootEntries = @(Get-ChildItem -LiteralPath $stagedApp -Force | Where-Object { $_.Name -notin $allowedRootEntries })
if ($unexpectedRootEntries.Count -gt 0) {
    throw "Unexpected files in the portable package root: $($unexpectedRootEntries.Name -join ', ')"
}

python package_integrity.py $stagedApp
if ($LASTEXITCODE -ne 0) {
    throw "Could not create the portable package inventory."
}

$smokeRoot = Join-Path $tempRoot ("calendar-smoke-" + [guid]::NewGuid().ToString("N"))
$smokeRootFull = [System.IO.Path]::GetFullPath($smokeRoot)
if (-not $smokeRootFull.StartsWith($tempRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing to create a smoke-test copy outside the temp directory."
}

try {
    $smokeApp = Join-Path $smokeRootFull "CalendarWorkflow"
    New-Item -ItemType Directory -Path $smokeApp | Out-Null
    Get-ChildItem -LiteralPath $stagedApp -Force | Copy-Item -Destination $smokeApp -Recurse -Force

    $process = New-Object System.Diagnostics.Process
    $process.StartInfo.FileName = Join-Path $smokeApp "CalendarWorkflow.exe"
    $timeoutSeconds = if ($FullAcceptance) { 600 } else { 180 }
    $process.StartInfo.Arguments = if ($FullAcceptance) { "--verify-portable --full-year" } else { "--verify-portable" }
    $process.StartInfo.WorkingDirectory = $smokeApp
    $process.StartInfo.UseShellExecute = $false
    $process.StartInfo.CreateNoWindow = $true
    $process.StartInfo.EnvironmentVariables['PATH'] = "$env:SystemRoot\System32;$env:SystemRoot"
    $process.StartInfo.EnvironmentVariables['TEMP'] = $smokeRootFull
    $process.StartInfo.EnvironmentVariables['TMP'] = $smokeRootFull
    $process.StartInfo.EnvironmentVariables.Remove('PYTHONHOME')
    $process.StartInfo.EnvironmentVariables.Remove('PYTHONPATH')
    $process.StartInfo.RedirectStandardOutput = $true
    $process.StartInfo.RedirectStandardError = $true
    $process.StartInfo.StandardOutputEncoding = [System.Text.Encoding]::UTF8
    $process.StartInfo.StandardErrorEncoding = [System.Text.Encoding]::UTF8
    if (-not $process.Start()) {
        throw "Could not start CalendarWorkflow.exe."
    }

    $stdoutTask = $process.StandardOutput.ReadToEndAsync()
    $stderrTask = $process.StandardError.ReadToEndAsync()
    if (-not $process.WaitForExit($timeoutSeconds * 1000)) {
        $process.Kill()
        $process.WaitForExit()
        throw "Portable application smoke test timed out."
    }
    $standardOutput = $stdoutTask.GetAwaiter().GetResult()
    $standardError = $stderrTask.GetAwaiter().GetResult()
    if ($process.ExitCode -ne 0) {
        throw "Portable desktop acceptance failed; release was not published: $standardError`n$standardOutput"
    }

    Write-Host ($standardOutput.TrimEnd())
}
finally {
    if (Test-Path -LiteralPath $smokeRootFull) {
        $resolvedSmokeRoot = [System.IO.Path]::GetFullPath($smokeRootFull)
        if ($resolvedSmokeRoot.StartsWith($tempRoot, [System.StringComparison]::OrdinalIgnoreCase) -and
            $resolvedSmokeRoot -eq $smokeRootFull) {
            for ($cleanupAttempt = 0; $cleanupAttempt -lt 5 -and (Test-Path -LiteralPath $resolvedSmokeRoot); $cleanupAttempt++) {
                try {
                    Remove-Item -LiteralPath $resolvedSmokeRoot -Recurse -Force -ErrorAction Stop
                }
                catch {
                    if ($cleanupAttempt -eq 4) {
                        throw
                    }
                    Start-Sleep -Milliseconds 500
                }
            }
        }
    }
}

$releaseRoot = Join-Path $PSScriptRoot "dist"
$releaseName = if ([string]::IsNullOrWhiteSpace($env:CALENDAR_RELEASE_DIR)) { "CalendarWorkflow" } else { $env:CALENDAR_RELEASE_DIR }
if ($releaseName -notmatch '^[A-Za-z0-9][A-Za-z0-9._-]*$' -or $releaseName.EndsWith('.')) {
    throw "CALENDAR_RELEASE_DIR must be a single directory name."
}
$releaseApp = Join-Path $releaseRoot $releaseName
New-Item -ItemType Directory -Path $releaseRoot -Force | Out-Null
$releaseLock = Join-Path $releaseRoot ".$releaseName.publish-lock"
$releaseLockStream = $null
$ownsReleaseLock = $false
try {
    $releaseLockStream = [System.IO.File]::Open(
        $releaseLock,
        [System.IO.FileMode]::CreateNew,
        [System.IO.FileAccess]::Write,
        [System.IO.FileShare]::None
    )
    $ownsReleaseLock = $true
    $lockContents = "pid=$PID`ntimestamp=$([DateTime]::UtcNow.ToString('o'))`n"
    $lockBytes = [System.Text.Encoding]::UTF8.GetBytes($lockContents)
    $releaseLockStream.Write($lockBytes, 0, $lockBytes.Length)
    $releaseLockStream.Close()
    if (Test-Path -LiteralPath $releaseApp) {
        throw "Release directory already exists; move it aside before building: $releaseApp"
    }
    Move-Item -LiteralPath $stagedApp -Destination $releaseApp
}
finally {
    if ($null -ne $releaseLockStream) {
        $releaseLockStream.Dispose()
    }
    if ($ownsReleaseLock -and (Test-Path -LiteralPath $releaseLock)) {
        Remove-Item -LiteralPath $releaseLock -Force
    }
}
if ($buildRootFull.StartsWith($tempRoot, [System.StringComparison]::OrdinalIgnoreCase) -and
    $buildRootFull -eq [System.IO.Path]::GetFullPath($buildRootFull)) {
    Remove-Item -LiteralPath $buildRootFull -Recurse -Force
}
Write-Host "Portable application built: $releaseApp"
}
finally {
    if (Test-Path -LiteralPath $buildRootFull) {
        $resolvedBuildRoot = [System.IO.Path]::GetFullPath($buildRootFull)
        if ($resolvedBuildRoot.StartsWith($tempRoot, [System.StringComparison]::OrdinalIgnoreCase) -and
            $resolvedBuildRoot -eq $buildRootFull) {
            Remove-Item -LiteralPath $resolvedBuildRoot -Recurse -Force
        }
    }
}
