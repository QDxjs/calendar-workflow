param(
    [Parameter(Mandatory = $true)][string]$InstallDirectory,
    [Parameter(Mandatory = $true)][string]$StageDirectory,
    [Parameter(Mandatory = $true)][int]$ProcessId,
    [string]$CleanupScriptPath = '',
    [switch]$NoRestart,
    [switch]$NoUI
)

$ErrorActionPreference = 'Stop'
$install = [IO.Path]::GetFullPath($InstallDirectory).TrimEnd('\')
$stage = [IO.Path]::GetFullPath($StageDirectory).TrimEnd('\')
$parent = [IO.Path]::GetDirectoryName($install)
$prefix = '.' + [IO.Path]::GetFileName($install) + '.update-'
$backup = Join-Path $parent ('.' + [IO.Path]::GetFileName($install) + '.backup-' + [guid]::NewGuid().ToString('N'))
$failed = Join-Path $parent ('.' + [IO.Path]::GetFileName($install) + '.failed-' + [guid]::NewGuid().ToString('N'))
$movedData = $false
$movedOldInstall = $false
$movedNewInstall = $false

function Show-UpdateError([string]$Message) {
    if ($NoUI) {
        [Console]::Error.WriteLine($Message)
        return
    }
    try {
        Add-Type -AssemblyName System.Windows.Forms
        [System.Windows.Forms.MessageBox]::Show(
            $Message,
            '每日文学日历更新失败',
            [System.Windows.Forms.MessageBoxButtons]::OK,
            [System.Windows.Forms.MessageBoxIcon]::Error
        ) | Out-Null
    }
    catch {
        [Console]::Error.WriteLine($Message)
    }
}

function Remove-TemporaryUpdater {
    if ([String]::IsNullOrWhiteSpace($CleanupScriptPath)) { return }
    try {
        $temporaryRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\') + '\'
        $cleanupPath = [IO.Path]::GetFullPath($CleanupScriptPath)
        if ($cleanupPath.StartsWith($temporaryRoot, [StringComparison]::OrdinalIgnoreCase) -and
            [IO.Path]::GetFileName($cleanupPath).StartsWith('calendar-update-', [StringComparison]::OrdinalIgnoreCase) -and
            [IO.Path]::GetExtension($cleanupPath) -eq '.ps1') {
            Remove-Item -LiteralPath $cleanupPath -Force
        }
    }
    catch { }
}

try {
    if (-not [IO.Directory]::Exists($install) -or -not [IO.Directory]::Exists($stage)) {
        throw '安装目录或已校验的更新暂存目录不存在。'
    }
    if ([IO.Path]::GetDirectoryName($stage) -ne $parent -or
        -not [IO.Path]::GetFileName($stage).StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw '更新暂存目录不在当前安装目录旁边，已停止安装。'
    }
    if (-not [IO.File]::Exists((Join-Path $stage 'CalendarWorkflow.exe'))) {
        throw '更新暂存目录缺少程序文件。'
    }
    if ([IO.File]::Exists((Join-Path $stage 'calendar_runs')) -or
        [IO.Directory]::Exists((Join-Path $stage 'calendar_runs'))) {
        throw '更新包意外包含 calendar_runs，已停止以保护用户数据。'
    }

    $running = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
    if ($null -ne $running -and -not $running.WaitForExit(300000)) {
        throw '等待当前程序退出超时，旧版本仍保持完整。'
    }
    foreach ($process in @(Get-Process -Name 'CalendarWorkflow' -ErrorAction SilentlyContinue)) {
        if ($process.Id -eq $ProcessId) { continue }
        try {
            if ([String]::Equals($process.Path, (Join-Path $install 'CalendarWorkflow.exe'), [StringComparison]::OrdinalIgnoreCase) -and
                -not $process.WaitForExit(300000)) {
                throw '另一个程序窗口仍在运行，旧版本保持完整。'
            }
        }
        catch [System.ComponentModel.Win32Exception] {
            throw '无法确认其他程序窗口是否已关闭，旧版本保持完整。'
        }
    }

    $data = Join-Path $install 'calendar_runs'
    $stagedData = Join-Path $stage 'calendar_runs'
    if ([IO.File]::Exists($data)) {
        throw 'calendar_runs 已被同名文件占用，旧版本保持完整。'
    }
    if ([IO.Directory]::Exists($data)) {
        $attributes = [IO.File]::GetAttributes($data)
        if (($attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw 'calendar_runs 是链接目录，无法安全迁移；旧版本保持完整。'
        }
        [IO.Directory]::Move($data, $stagedData)
        $movedData = $true
    }

    [IO.Directory]::Move($install, $backup)
    $movedOldInstall = $true
    [IO.Directory]::Move($stage, $install)
    $movedNewInstall = $true

    if (-not [IO.File]::Exists((Join-Path $install 'CalendarWorkflow.exe'))) {
        throw '安装后未找到程序文件。'
    }
    if (-not $NoRestart) {
        Start-Process -FilePath (Join-Path $install 'CalendarWorkflow.exe') -WorkingDirectory $install | Out-Null
    }
}
catch {
    $failure = $_.Exception.Message
    $rollbackFailure = $null
    try {
        if ($movedNewInstall -and [IO.Directory]::Exists($install)) {
            $newData = Join-Path $install 'calendar_runs'
            $oldData = Join-Path $backup 'calendar_runs'
            if ([IO.Directory]::Exists($newData) -and -not [IO.Directory]::Exists($oldData)) {
                [IO.Directory]::Move($newData, $oldData)
            }
            [IO.Directory]::Move($install, $failed)
        }
        if ($movedOldInstall -and [IO.Directory]::Exists($backup) -and -not [IO.Directory]::Exists($install)) {
            [IO.Directory]::Move($backup, $install)
        }
        if ($movedData -and [IO.Directory]::Exists($stage) -and
            [IO.Directory]::Exists((Join-Path $stage 'calendar_runs')) -and
            -not [IO.Directory]::Exists((Join-Path $install 'calendar_runs'))) {
            [IO.Directory]::Move((Join-Path $stage 'calendar_runs'), (Join-Path $install 'calendar_runs'))
        }
        if ([IO.Directory]::Exists($failed)) {
            Remove-Item -LiteralPath $failed -Recurse -Force
        }
        if ([IO.Directory]::Exists($stage)) {
            Remove-Item -LiteralPath $stage -Recurse -Force
        }
    }
    catch {
        $rollbackFailure = $_.Exception.Message
    }

    if ($null -ne $rollbackFailure) {
        Show-UpdateError "$failure`n`n自动回滚未能完成：$rollbackFailure`n`n请保留更新暂存目录和备份目录以便恢复。"
    }
    else {
        Show-UpdateError "$failure`n`n已恢复原版本和日历数据。"
    }
    Remove-TemporaryUpdater
    exit 1
}

if ([IO.Directory]::Exists($backup)) {
    try { Remove-Item -LiteralPath $backup -Recurse -Force } catch { }
}
Remove-TemporaryUpdater
