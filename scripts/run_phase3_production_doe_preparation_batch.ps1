param(
    [int]$MaxWorkers = 2
)

$ErrorActionPreference = "Stop"

$Root = "D:\ThreadROM"

$CampaignManifest = Join-Path $Root `
    "simulations\staging\phase3_cp8_production_doe\TRM-PDOE-C01\production_doe_campaign_manifest.json"

$PreparedRoot = Join-Path $Root `
    "simulations\staging\phase3_cp8_production_doe\TRM-PDOE-C01\prepared_cases"

$LogRoot = Join-Path $Root `
    "simulations\staging\phase3_cp8_production_doe\TRM-PDOE-C01\preparation_logs"

$Python = Join-Path $Root ".venv\Scripts\python.exe"
$Runner = Join-Path $Root "scripts\prepare_phase3_production_doe_case.py"

New-Item `
    -ItemType Directory `
    -Force `
    -Path $LogRoot `
    | Out-Null

$campaign = Get-Content `
    $CampaignManifest `
    -Raw `
    | ConvertFrom-Json

$pending = @()

foreach ($row in $campaign.design_cases) {

    if ($row.existing_evidence_reuse_planned) {
        continue
    }

    $runId = "trm_fem_$($row.case_hash.Substring(0,12))"

    $caseRoot = Join-Path `
        $PreparedRoot `
        $runId

    $prepRecord = Join-Path `
        $caseRoot `
        "production_doe_preparation_record.json"

    $reuseRecord = Join-Path `
        $caseRoot `
        "production_doe_geometry_mesh_reuse_record.json"

    if (
        (Test-Path $prepRecord) -or
        (Test-Path $reuseRecord)
    ) {
        Write-Host `
            "SKIP  $($row.case_id) — preparation evidence already exists"
        continue
    }

    $pending += $row
}

Write-Host ""
Write-Host "============================================================"
Write-Host "THREADROM — PRODUCTION DOE PREPARATION BATCH"
Write-Host "============================================================"
Write-Host "Pending cases :" $pending.Count
Write-Host "Max workers   :" $MaxWorkers
Write-Host "CalculiX      : DISABLED"
Write-Host "Holdouts      : NOT INCLUDED"
Write-Host "============================================================"
Write-Host ""

if ($pending.Count -eq 0) {
    Write-Host "Nothing to prepare."
    exit 0
}

$queue = [System.Collections.Queue]::new()

foreach ($row in $pending) {
    $queue.Enqueue($row)
}

$running = @{}

while (
    $queue.Count -gt 0 -or
    $running.Count -gt 0
) {

    while (
        $queue.Count -gt 0 -and
        $running.Count -lt $MaxWorkers
    ) {

        $row = $queue.Dequeue()

        $caseId = $row.case_id

        $stdout = Join-Path `
            $LogRoot `
            "$caseId.stdout.log"

        $stderr = Join-Path `
            $LogRoot `
            "$caseId.stderr.log"

        Write-Host "START $caseId"

        $process = Start-Process `
            -FilePath $Python `
            -ArgumentList @(
                $Runner,
                "--case-id",
                $caseId
            ) `
            -RedirectStandardOutput $stdout `
            -RedirectStandardError $stderr `
            -PassThru `
            -NoNewWindow

        $running[$process.Id] = @{
            Process = $process
            CaseId = $caseId
            Stdout = $stdout
            Stderr = $stderr
            StartTime = Get-Date
        }
    }

    Start-Sleep -Seconds 5

    foreach ($pidValue in @($running.Keys)) {

        $entry = $running[$pidValue]

        $entry.Process.Refresh()

        if (-not $entry.Process.HasExited) {
            continue
        }

        $elapsed = (Get-Date) - $entry.StartTime

        # Ensure Windows has finalized process bookkeeping.
        $entry.Process.WaitForExit()
        $entry.Process.Refresh()

        $exitCode = $entry.Process.ExitCode

        $row = $campaign.design_cases |
            Where-Object {
                $_.case_id -eq $entry.CaseId
            } |
            Select-Object -First 1

        if (-not $row) {
            throw (
                "Completed process has no matching " +
                "frozen DOE design row: " +
                $entry.CaseId
            )
        }

        $runId = "trm_fem_$($row.case_hash.Substring(0,12))"

        $caseRoot = Join-Path `
            $PreparedRoot `
            $runId

        $prepRecord = Join-Path `
            $caseRoot `
            "production_doe_preparation_record.json"

        $reuseRecord = Join-Path `
            $caseRoot `
            "production_doe_geometry_mesh_reuse_record.json"

        $finalEvidenceExists = (
            (Test-Path $prepRecord) -or
            (Test-Path $reuseRecord)
        )

        if ($finalEvidenceExists) {
            Write-Host (
                "PASS  {0} — exit {1} — {2:hh\:mm\:ss}" -f
                $entry.CaseId,
                $exitCode,
                $elapsed
            )
        }
        else {
            Write-Host (
                "FAIL  {0} — exit {1} — no FINAL preparation evidence — {2:hh\:mm\:ss}" -f
                $entry.CaseId,
                $exitCode,
                $elapsed
            )

            Write-Host (
                "      stderr: " +
                $entry.Stderr
            )

            throw (
                "Preparation batch stopped because " +
                "the case process ended without " +
                "immutable preparation evidence: " +
                $entry.CaseId
            )
        }

        $running.Remove(
            $pidValue
        )
    }
}

Write-Host ""
Write-Host "============================================================"
Write-Host "PRODUCTION DOE PREPARATION BATCH COMPLETE"
Write-Host "CalculiX invoked : NO"
Write-Host "Holdouts accessed: NO"
Write-Host "============================================================"
