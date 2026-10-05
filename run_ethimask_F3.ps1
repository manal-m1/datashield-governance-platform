$baseline = @{
    ws=0.4; wr=0.5; wc=0.1; wp=0.1
    whc=0.1; whf=-0.1; whv=-0.2
    bias=0.2; alpha=0.5
}

$minus10 = @{
    ws=0.36; wr=0.45; wc=0.09; wp=0.09
    whc=0.09; whf=-0.09; whv=-0.18
    bias=0.2; alpha=0.5
}

$plus10 = @{
    ws=0.44; wr=0.55; wc=0.11; wp=0.11
    whc=0.11; whf=-0.11; whv=-0.22
    bias=0.2; alpha=0.5
}

$sensitivities = @("low", "medium", "high", "critical")
$roles = @("admin", "steward", "annotator", "labeler")

function Set-Config($config) {

    $json = $config | ConvertTo-Json -Compress

    return Invoke-RestMethod `
        -Uri "http://localhost:8009/config" `
        -Method POST `
        -ContentType "application/json" `
        -Body $json
}

function Get-Results {

    $results = @()

    foreach ($sensitivity in $sensitivities) {
        foreach ($role in $roles) {

            $url = "http://localhost:8009/decide?sensitivity=$sensitivity&role=$role&context=default&purpose=general"

            $r = Invoke-RestMethod `
                -Uri $url `
                -Method POST

            $results += [PSCustomObject]@{
                Sensitivity = $sensitivity
                Role        = $role
                Score       = [double]$r.score
                Decision    = $r.decision
            }
        }
    }

    return $results
}

Write-Host "========================================"
Write-Host "F.3 - WEIGHT PERTURBATION EXPERIMENT"
Write-Host "========================================"

# -------------------------
# BASELINE
# -------------------------

Write-Host ""
Write-Host "Testing BASELINE..."

Set-Config $baseline | Out-Null
$baseResults = Get-Results

# -------------------------
# -10%
# -------------------------

Write-Host ""
Write-Host "Testing -10%..."

Set-Config $minus10 | Out-Null
$minusResults = Get-Results

# -------------------------
# +10%
# -------------------------

Write-Host ""
Write-Host "Testing +10%..."

Set-Config $plus10 | Out-Null
$plusResults = Get-Results

# -------------------------
# Restore BASELINE
# -------------------------

Write-Host ""
Write-Host "Restoring BASELINE..."

Set-Config $baseline | Out-Null

# -------------------------
# Comparison
# -------------------------

$comparison = @()

for ($i = 0; $i -lt $baseResults.Count; $i++) {

    $b = $baseResults[$i]
    $m = $minusResults[$i]
    $p = $plusResults[$i]

    $comparison += [PSCustomObject]@{
        Sensitivity = $b.Sensitivity
        Role        = $b.Role

        BaselineScore = $b.Score
        Minus10Score  = $m.Score
        Plus10Score   = $p.Score

        Minus10Delta = [math]::Round($m.Score - $b.Score, 4)
        Plus10Delta  = [math]::Round($p.Score - $b.Score, 4)

        BaselineDecision = $b.Decision
        Minus10Decision  = $m.Decision
        Plus10Decision   = $p.Decision

        Minus10Changed = ($b.Decision -ne $m.Decision)
        Plus10Changed  = ($b.Decision -ne $p.Decision)
    }
}

Write-Host ""
Write-Host "========================================"
Write-Host "RESULTS"
Write-Host "========================================"

$comparison | Format-Table -AutoSize

# -------------------------
# Stability
# -------------------------

$minusChanged = ($comparison | Where-Object {$_.Minus10Changed}).Count
$plusChanged  = ($comparison | Where-Object {$_.Plus10Changed}).Count

$minusStable = 16 - $minusChanged
$plusStable  = 16 - $plusChanged

$minusStability = ($minusStable / 16) * 100
$plusStability  = ($plusStable / 16) * 100

Write-Host ""
Write-Host "========================================"
Write-Host "STABILITY"
Write-Host "========================================"

Write-Host ("-10% : {0}/16 unchanged = {1}%" -f $minusStable, $minusStability)
Write-Host ("+10% : {0}/16 unchanged = {1}%" -f $plusStable, $plusStability)

# -------------------------
# Mean absolute score delta
# -------------------------

$minusMeanDelta = (
    $comparison |
    ForEach-Object { [math]::Abs($_.Minus10Delta) } |
    Measure-Object -Average
).Average

$plusMeanDelta = (
    $comparison |
    ForEach-Object { [math]::Abs($_.Plus10Delta) } |
    Measure-Object -Average
).Average

Write-Host ""
Write-Host "Mean absolute score variation:"
Write-Host ("-10% : {0}" -f ([math]::Round($minusMeanDelta,4)))
Write-Host ("+10% : {0}" -f ([math]::Round($plusMeanDelta,4)))

# -------------------------
# Save
# -------------------------

$comparison | Export-Csv `
    -Path ".\ethimask_F3_weight_stability.csv" `
    -NoTypeInformation `
    -Encoding UTF8

Write-Host ""
Write-Host "CSV saved to:"
Write-Host ".\ethimask_F3_weight_stability.csv"

Write-Host ""
Write-Host "Current configuration restored to BASELINE."
