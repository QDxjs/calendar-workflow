param(
    [Parameter(Mandatory=$true)][string]$Uri,
    [Parameter(Mandatory=$true)][string]$DestinationPath,
    [Parameter(Mandatory=$true)][long]$MaximumBytes,
    [Parameter(Mandatory=$true)][int]$TimeoutSeconds,
    [Parameter(Mandatory=$true)][string]$Accept,
    [switch]$ReportProgress
)

$ErrorActionPreference = 'Stop'
$response = $null
$source = $null
$target = $null

try {
    $request = [System.Net.HttpWebRequest]::Create($Uri)
    $request.Method = 'GET'
    $request.UserAgent = 'CalendarWorkflow-Updater'
    $request.Accept = $Accept
    $request.AllowAutoRedirect = $true
    $request.MaximumAutomaticRedirections = 5
    $request.Timeout = $TimeoutSeconds * 1000
    $request.ReadWriteTimeout = 30000

    $proxyAddress = $env:HTTPS_PROXY
    if ([string]::IsNullOrWhiteSpace($proxyAddress)) { $proxyAddress = $env:ALL_PROXY }
    if (-not [string]::IsNullOrWhiteSpace($proxyAddress)) {
        if ($proxyAddress -notmatch '^[a-zA-Z][a-zA-Z0-9+.-]*://') {
            $proxyAddress = 'http://' + $proxyAddress
        }
        $targetHost = $request.RequestUri.Host
        $bypassProxy = $false
        foreach ($entry in ($env:NO_PROXY -split ',')) {
            $entry = $entry.Trim()
            if ($entry -eq '*') {
                $bypassProxy = $true
                break
            }
            if ($entry -match '^\[([^\]]+)\](?::[0-9]+)?$') {
                $entryHost = $Matches[1]
            }
            elseif ($entry -match '^([^:]+):[0-9]+$') {
                $entryHost = $Matches[1]
            }
            else {
                $entryHost = $entry.TrimStart('.')
            }
            if ($entryHost -and ($targetHost -eq $entryHost -or $targetHost.EndsWith('.' + $entryHost, [System.StringComparison]::OrdinalIgnoreCase))) {
                $bypassProxy = $true
                break
            }
        }
        if ($bypassProxy) {
            $request.Proxy = $null
        }
        else {
            $proxyUri = [Uri]$proxyAddress
            $proxy = [System.Net.WebProxy]::new($proxyUri)
            if ($proxyUri.UserInfo) {
                $userInfo = [Uri]::UnescapeDataString($proxyUri.UserInfo)
                $separator = $userInfo.IndexOf(':')
                if ($separator -ge 0) {
                    $username = $userInfo.Substring(0, $separator)
                    $password = $userInfo.Substring($separator + 1)
                    $proxy.Credentials = [System.Net.NetworkCredential]::new($username, $password)
                }
            }
            $request.Proxy = $proxy
        }
    }

    $response = $request.GetResponse()
    $length = $response.ContentLength
    if ($length -gt $MaximumBytes) {
        throw [System.IO.InvalidDataException]::new('SIZE')
    }

    $source = $response.GetResponseStream()
    $target = [System.IO.File]::Open(
        $DestinationPath,
        [System.IO.FileMode]::CreateNew,
        [System.IO.FileAccess]::Write,
        [System.IO.FileShare]::None
    )
    $buffer = New-Object byte[] 65536
    [long]$received = 0
    while (($count = $source.Read($buffer, 0, $buffer.Length)) -gt 0) {
        $received += $count
        if ($received -gt $MaximumBytes -or ($length -ge 0 -and $received -gt $length)) {
            throw [System.IO.InvalidDataException]::new('SIZE')
        }
        $target.Write($buffer, 0, $count)
        if ($ReportProgress) {
            [Console]::Out.WriteLine('PROGRESS|{0}|{1}' -f $received, $length)
            [Console]::Out.Flush()
        }
    }
    $target.Flush()
    $target.Dispose()
    $target = $null

    [Console]::Out.WriteLine('COMPLETE|{0}|{1}|{2}' -f $received, $length, $response.ResponseUri.AbsoluteUri)
    [Console]::Out.Flush()
}
catch [System.Net.WebException] {
    $exception = $_.Exception
    if ($exception.Response -is [System.Net.HttpWebResponse]) {
        [Console]::Out.WriteLine('ERROR|HTTP:{0}|' -f [int]$exception.Response.StatusCode)
    }
    elseif ($exception.Status -eq [System.Net.WebExceptionStatus]::TrustFailure -or
            $exception.Status -eq [System.Net.WebExceptionStatus]::SecureChannelFailure) {
        [Console]::Out.WriteLine('ERROR|TLS|')
    }
    elseif ($exception.Status -eq [System.Net.WebExceptionStatus]::Timeout) {
        [Console]::Out.WriteLine('ERROR|TIMEOUT|')
    }
    else {
        [Console]::Out.WriteLine('ERROR|NETWORK|{0}' -f $exception.Status)
    }
    [Console]::Out.Flush()
    exit 2
}
catch [System.IO.InvalidDataException] {
    if ($_.Exception.Message -eq 'SIZE') {
        [Console]::Out.WriteLine('ERROR|SIZE|')
    }
    else {
        [Console]::Out.WriteLine('ERROR|NETWORK|IOError')
    }
    [Console]::Out.Flush()
    exit 2
}
catch {
    [Console]::Out.WriteLine('ERROR|NETWORK|RequestFailed')
    [Console]::Out.Flush()
    exit 2
}
finally {
    if ($null -ne $target) { $target.Dispose() }
    if ($null -ne $source) { $source.Dispose() }
    if ($null -ne $response) { $response.Dispose() }
}
