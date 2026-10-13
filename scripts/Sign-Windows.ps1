param(
    [Parameter(Mandatory = $true)][string]$CertificateThumbprint,
    [string]$AppDirectory = "dist\MicBoost"
)
$ErrorActionPreference = "Stop"
# Use an existing, trusted code-signing certificate. No certificates or keys
# are generated, imported, exported, or stored by this script.
$certificate = Get-Item "Cert:\CurrentUser\My\$CertificateThumbprint"
if (-not $certificate.HasPrivateKey) { throw "Signing certificate has no accessible private key" }
if ($certificate.NotAfter -le (Get-Date)) { throw "Signing certificate has expired" }
if ($certificate.NotBefore -gt (Get-Date)) { throw "Signing certificate is not valid yet" }
if ($certificate.EnhancedKeyUsageList.ObjectId.Value -notcontains "1.3.6.1.5.5.7.3.3") {
    throw "Certificate is not authorized for code signing"
}
$tool = Get-Command signtool.exe -ErrorAction SilentlyContinue
if ($tool) {
    $signTool = $tool.Source
} else {
    $signTool = Get-ChildItem "${env:ProgramFiles(x86)}\Windows Kits\10\bin\*\x64\signtool.exe" |
        Sort-Object FullName | Select-Object -Last 1 -ExpandProperty FullName
}
if (-not $signTool) { throw "Install the official Windows SDK signing tools first" }
$files = @(Get-ChildItem -LiteralPath $AppDirectory -Recurse -File |
    Where-Object { $_.Extension -in @('.exe', '.dll', '.pyd') })
if ($files.Count -eq 0) { throw "No executable files found; build MicBoost first" }
foreach ($file in $files) {
    $signature = Get-AuthenticodeSignature -LiteralPath $file.FullName
    if ($signature.Status -eq 'Valid') { continue }
    & $signTool sign /sha1 $CertificateThumbprint /fd SHA256 /tr https://timestamp.digicert.com /td SHA256 $file.FullName
    if ($LASTEXITCODE -ne 0) { throw "Signing failed: $($file.Name)" }
    $signature = Get-AuthenticodeSignature -LiteralPath $file.FullName
    if ($signature.Status -ne 'Valid') { throw "Signature trust verification failed: $($file.Name)" }
    & $signTool verify /pa /all $file.FullName
    if ($LASTEXITCODE -ne 0) { throw "Signature verification failed: $($file.Name)" }
}
Write-Host "Signing and trust verification completed. Do not modify binaries after signing."
