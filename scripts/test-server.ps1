$response = Invoke-WebRequest -Uri http://localhost:3002/ -UseBasicParsing
if ($response.Content -match 'theme-toggle') {
    Write-Host "SUCCESS: theme-toggle found in HTML"
    exit 0
} else {
    Write-Host "ERROR: theme-toggle NOT found in HTML"
    exit 1
}

