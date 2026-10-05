$results = @()

$sensitivities = @("low", "medium", "high", "critical")
$roles = @("admin", "steward", "annotator", "labeler")

foreach ($sensitivity in $sensitivities) {
    foreach ($role in $roles) {

        $url = "http://localhost:8009/decide?sensitivity=$sensitivity&role=$role&context=default&purpose=general"

        try {
            $r = Invoke-RestMethod -Uri $url -Method POST

            $results += [PSCustomObject]@{
                Sensitivity = $sensitivity
                Role        = $role
                Score       = [double]$r.score
                Decision    = $r.decision
            }
        }
        catch {
            Write-Host "ERROR: $sensitivity / $role -> $($_.Exception.Message)"
        }
    }
}

$results | Format-Table -AutoSize

$results | Export-Csv `
    -Path ".\ethimask_F1_F2_baseline.csv" `
    -NoTypeInformation `
    -Encoding UTF8

Write-Host ""
Write-Host "CSV saved to: .\ethimask_F1_F2_baseline.csv"

Write-Host ""
Write-Host "=== Distribution ==="
$results |
    Group-Object Decision |
    Select-Object Name, Count |
    Format-Table -AutoSize

Write-Host ""
Write-Host "=== Statistics ==="

$scores = $results | ForEach-Object { $_.Score }

[PSCustomObject]@{
    Tests       = $results.Count
    MeanScore   = [math]::Round(($scores | Measure-Object -Average).Average, 4)
    MinScore    = [math]::Round(($scores | Measure-Object -Minimum).Minimum, 4)
    MaxScore    = [math]::Round(($scores | Measure-Object -Maximum).Maximum, 4)
} | Format-List
