$ErrorActionPreference = 'Stop'
# Keep a Windows-owned WSL session alive while the platform is in use.
$existing = Get-CimInstance Win32_Process -Filter "Name='wsl.exe'" | Where-Object {
    $_.CommandLine -like '*factorforge-keepalive*'
}
if (-not $existing) {
    Start-Process -FilePath 'wsl.exe' -ArgumentList @('-d', 'Ubuntu', '--', 'bash', '-lc', '"systemctl --user start quantaalpha.service && exec -a factorforge-keepalive sleep infinity"') -WindowStyle Hidden
}
for ($attempt = 0; $attempt -lt 30; $attempt++) {
    try {
        $response = Invoke-WebRequest 'http://localhost:3000/api/health' -TimeoutSec 3
        if ($response.StatusCode -eq 200 -and ($response.Content | ConvertFrom-Json).status -eq 'healthy') {
            Write-Output 'FactorForge is ready: http://localhost:3000/'
            exit 0
        }
    } catch { }
    Start-Sleep -Seconds 2
}
throw 'FactorForge did not become ready. Check the quantaalpha user service in Ubuntu.'
