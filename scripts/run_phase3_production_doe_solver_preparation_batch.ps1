param(
    [int]$MaxWorkers = 2
)

$ErrorActionPreference = "Stop"

if ($MaxWorkers -lt 1) {
    throw "MaxWorkers must be at least 1."
}

$Root = "D:\ThreadROM"

$Python = Join-Path `
    $Root `
    ".venv\Scripts\python.exe"

$Runner = Join-Path `
    $Root `
    "scripts\prepare_phase3_production_doe_solver_case.py"

$CampaignRoot = Join-Path `
    $Root `
    "simulations\staging\phase3_cp8_production_doe\TRM-PDOE-C01"

$ManifestPath = Join-Path `
    $CampaignRoot `
    "production_doe_campaign_manifest.json"

$SolverRoot = Join-Path `
    $CampaignRoot `
    "solver_preparation"

$LogRoot = Join-Path `
    $CampaignRoot `
    "solver_preparation_logs"

New-Item `
    -ItemType Directory `
    -Force `
    -Path $LogRoot |
    Out-Null


if (-not (Test-Path $Python)) {
    throw "ThreadROM Python not found: $Python"
}

if (-not (Test-Path $Runner)) {
    throw "Solver-preparation runner not found: $Runner"
}

if (-not (Test-Path $ManifestPath)) {
    throw "Frozen campaign manifest not found: $ManifestPath"
}


$campaign = Get-Content `
    $ManifestPath `
    -Raw |
    ConvertFrom-Json


$pending = New-Object System.Collections.Queue


foreach ($row in $campaign.design_cases) {

    if ($row.existing_evidence_reuse_planned) {
        Write-Host (
            "SKIP  {0} — certified FEM anchor" -f
            $row.case_id
        )

        continue
    }


    $runId = (
        "trm_fem_" +
        $row.case_hash.Substring(0, 12)
    )

    $trialRunId = (
        $runId +
        "_cal_01"
    )

    $runDir = Join-Path `
        (Join-Path $SolverRoot $runId) `
        $trialRunId

    $record = Join-Path `
        $runDir `
        "production_doe_solver_preparation_record.json"

    $sidecar = Join-Path `
        $runDir `
        "production_doe_solver_preparation_record.sha256"


    if (
        (Test-Path $record) -and
        (Test-Path $sidecar)
    ) {
        try {
            $evidence = Get-Content `
                $record `
                -Raw |
                ConvertFrom-Json

            $valid = (
                $evidence.record_status -eq "FINAL" -and
                $evidence.overall_disposition -eq
                    "PRODUCTION_DOE_TRIAL1_SOLVER_PREPARATION_PASS" -and
                $evidence.solve_authorization.calculix_invoked -eq $false -and
                $evidence.solve_authorization.holdout_accessed -eq $false
            )
        }
        catch {
            $valid = $false
        }

        if ($valid) {
            Write-Host (
                "SKIP  {0} — FINAL solver-preparation evidence exists" -f
                $row.case_id
            )

            continue
        }
    }


    $pending.Enqueue(
        [pscustomobject]@{
            CaseId = $row.case_id
            CaseHash = $row.case_hash
            RunId = $runId
            TrialRunId = $trialRunId
            Record = $record
            Sidecar = $sidecar
        }
    )
}


Write-Host ""
Write-Host ("=" * 72)
Write-Host "THREADROM — PRODUCTION DOE SOLVER-PREPARATION BATCH"
Write-Host ("=" * 72)

Write-Host (
    "Pending cases : {0}" -f
    $pending.Count
)

Write-Host (
    "Max workers   : {0}" -f
    $MaxWorkers
)

Write-Host "CalculiX      : DISABLED"
Write-Host "Holdouts      : NOT INCLUDED"
Write-Host ("=" * 72)
Write-Host ""


$running = @{}

$failureDetected = $false
$failureMessage = $null


while (
    $pending.Count -gt 0 -or
    $running.Count -gt 0
) {

    while (
        -not $failureDetected -and
        $pending.Count -gt 0 -and
        $running.Count -lt $MaxWorkers
    ) {

        $item = $pending.Dequeue()

        $stdout = Join-Path `
            $LogRoot `
            "$($item.CaseId).stdout.log"

        $stderr = Join-Path `
            $LogRoot `
            "$($item.CaseId).stderr.log"

        Remove-Item `
            $stdout `
            -Force `
            -ErrorAction SilentlyContinue

        Remove-Item `
            $stderr `
            -Force `
            -ErrorAction SilentlyContinue


        Write-Host (
            "START {0}" -f
            $item.CaseId
        )


        $process = Start-Process `
            -FilePath $Python `
            -ArgumentList @(
                $Runner,
                "--case-id",
                $item.CaseId
            ) `
            -RedirectStandardOutput $stdout `
            -RedirectStandardError $stderr `
            -NoNewWindow `
            -PassThru


        $running[$process.Id] = (
            [pscustomobject]@{
                Process = $process
                CaseId = $item.CaseId
                Record = $item.Record
                Sidecar = $item.Sidecar
                Stdout = $stdout
                Stderr = $stderr
                StartTime = Get-Date
            }
        )
    }


    foreach (
        $pidValue
        in @($running.Keys)
    ) {

        $entry = $running[$pidValue]

        $entry.Process.Refresh()

        if (-not $entry.Process.HasExited) {
            continue
        }


        $entry.Process.WaitForExit()
        $entry.Process.Refresh()

        $elapsed = (
            (Get-Date) -
            $entry.StartTime
        )

        $exitCode = (
            $entry.Process.ExitCode
        )

        if ($null -eq $exitCode) {
            $exitDisplay = "n/a"
        }
        else {
            $exitDisplay = $exitCode
        }


        $validEvidence = $false


        if (
            (Test-Path $entry.Record) -and
            (Test-Path $entry.Sidecar)
        ) {
            try {

                $evidence = Get-Content `
                    $entry.Record `
                    -Raw |
                    ConvertFrom-Json

                $validEvidence = (
                    $evidence.record_status -eq "FINAL" -and
                    $evidence.overall_disposition -eq
                        "PRODUCTION_DOE_TRIAL1_SOLVER_PREPARATION_PASS" -and
                    $evidence.solve_authorization.calculix_invoked -eq $false -and
                    $evidence.solve_authorization.holdout_accessed -eq $false
                )
            }
            catch {
                $validEvidence = $false
            }
        }


        if ($validEvidence) {

            Write-Host (
                "PASS  {0} — exit {1} — {2:hh\:mm\:ss}" -f
                $entry.CaseId,
                $exitDisplay,
                $elapsed
            )

        }
        else {

            Write-Host (
                "FAIL  {0} — exit {1} — no valid FINAL evidence — {2:hh\:mm\:ss}" -f
                $entry.CaseId,
                $exitDisplay,
                $elapsed
            )

            Write-Host (
                "      stderr: {0}" -f
                $entry.Stderr
            )

            $failureDetected = $true

            if ($null -eq $failureMessage) {
                $failureMessage = (
                    "Solver-preparation batch detected " +
                    "failure of " +
                    $entry.CaseId
                )
            }
        }


        $running.Remove(
            $pidValue
        )
    }


    if (
        $running.Count -gt 0 -or
        (
            -not $failureDetected -and
            $pending.Count -gt 0
        )
    ) {
        Start-Sleep `
            -Seconds 5
    }
}


if ($failureDetected) {
    throw $failureMessage
}


Write-Host ""
Write-Host ("=" * 72)
Write-Host "PRODUCTION DOE SOLVER-PREPARATION BATCH COMPLETE"
Write-Host "CalculiX invoked : NO"
Write-Host "Holdouts accessed: NO"
Write-Host ("=" * 72)
