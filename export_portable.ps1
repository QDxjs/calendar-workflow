param(
    [Parameter(Mandatory = $true)][string]$PackageDirectory,
    [Parameter(Mandatory = $true)][string]$ArchivePath
)

$ErrorActionPreference = 'Stop'
$package = Get-Item -LiteralPath $PackageDirectory
if (-not $package.PSIsContainer -or $package.Attributes -band [IO.FileAttributes]::ReparsePoint) {
    throw 'The package must be a regular directory.'
}
$destination = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($ArchivePath)
$parent = Get-Item -LiteralPath (Split-Path -Parent $destination)
if (-not $parent.PSIsContainer -or [IO.Path]::GetExtension($destination) -ne '.zip') {
    throw 'The destination must be a .zip file in an existing directory.'
}
$destination = Join-Path $parent.FullName (Split-Path -Leaf $destination)
if ($destination.StartsWith($package.FullName.TrimEnd('\') + '\', [StringComparison]::OrdinalIgnoreCase)) {
    throw 'The archive must be outside the package directory.'
}
if (Test-Path -LiteralPath $destination) {
    throw "Archive already exists: $destination"
}
if (Get-ChildItem -LiteralPath $package.FullName -Force -Recurse -Attributes ReparsePoint) {
    throw 'The package contains a link or other reparse point.'
}

$inventoryPath = Join-Path $package.FullName '_internal\PACKAGE_SHA256.json'
$inventoryBytes = [IO.File]::ReadAllBytes($inventoryPath)
$inventory = [Text.Encoding]::UTF8.GetString($inventoryBytes) | ConvertFrom-Json
$expectedFiles = $inventory.sha256
if ([string]::IsNullOrWhiteSpace([string]$inventory.version) -or $null -eq $expectedFiles -or
    $null -eq $expectedFiles.PSObject.Properties['CalendarWorkflow.exe']) {
    throw 'Package inventory is invalid.'
}
$expectedCount = @($expectedFiles.PSObject.Properties).Count
$executable = Join-Path $package.FullName 'CalendarWorkflow.exe'
$verification = [System.Diagnostics.Process]::new()
$verification.StartInfo.FileName = $executable
$verification.StartInfo.Arguments = '--verify-package'
$verification.StartInfo.WorkingDirectory = $package.FullName
$verification.StartInfo.UseShellExecute = $false
$verification.StartInfo.CreateNoWindow = $true
if (-not $verification.Start()) {
    throw 'Could not start package verification.'
}
if (-not $verification.WaitForExit(180000)) {
    $verification.Kill()
    $verification.WaitForExit()
    $verification.Dispose()
    throw 'Package verification timed out.'
}
$verificationExitCode = $verification.ExitCode
$verification.Dispose()
if ($verificationExitCode -ne 0) {
    throw 'Package verification failed; no ZIP was published.'
}

Add-Type -AssemblyName System.IO.Compression.FileSystem
$temporary = Join-Path $parent.FullName ('.calendar-export-' + [guid]::NewGuid().ToString('N') + '.tmp')
$zipFile = $null
try {
    [IO.Compression.ZipFile]::CreateFromDirectory($package.FullName, $temporary, [IO.Compression.CompressionLevel]::Optimal, $true)
    $zipFile = [IO.Compression.ZipFile]::OpenRead($temporary)
    $seen = [System.Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    $sha256 = [Security.Cryptography.SHA256]::Create()
    $prefix = $package.Name + '/'
    try {
        $inventoryHash = [BitConverter]::ToString($sha256.ComputeHash($inventoryBytes)).Replace('-', '')
        foreach ($entry in $zipFile.Entries) {
            $entryPath = $entry.FullName.Replace('\', '/')
            if ($entryPath.EndsWith('/')) { continue }
            if (-not $entryPath.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) {
                throw "Unexpected path in release ZIP: $($entry.FullName)"
            }
            $relativePath = $entryPath.Substring($prefix.Length)
            if (-not $seen.Add($relativePath)) {
                throw "Duplicate path in release ZIP: $relativePath"
            }
            $entryStream = $entry.Open()
            try {
                $hash = [BitConverter]::ToString($sha256.ComputeHash($entryStream)).Replace('-', '')
            }
            finally { $entryStream.Dispose() }
            if ($relativePath -eq '_internal/PACKAGE_SHA256.json') {
                if (-not [String]::Equals($hash, $inventoryHash, [StringComparison]::OrdinalIgnoreCase)) {
                    throw 'Release ZIP contains a changed package inventory.'
                }
                continue
            }
            $expected = $expectedFiles.PSObject.Properties[$relativePath]
            if ($null -eq $expected -or -not [String]::Equals($hash, [string]$expected.Value, [StringComparison]::OrdinalIgnoreCase)) {
                throw "Release ZIP file differs from the package inventory: $relativePath"
            }
        }
        if (-not $seen.Contains('_internal/PACKAGE_SHA256.json') -or $seen.Count -ne ($expectedCount + 1)) {
            throw 'Release ZIP is missing one or more inventoried files.'
        }
    }
    finally { $sha256.Dispose() }
    $zipFile.Dispose()
    $zipFile = $null
    $hash = (Get-FileHash -LiteralPath $temporary -Algorithm SHA256).Hash
    [IO.File]::Move($temporary, $destination)
    Write-Host "Portable archive: $destination"
    Write-Host "SHA-256: $hash"
}
finally {
    if ($null -ne $zipFile) { $zipFile.Dispose() }
    if (Test-Path -LiteralPath $temporary -PathType Leaf) {
        Remove-Item -LiteralPath $temporary -Force
    }
}
