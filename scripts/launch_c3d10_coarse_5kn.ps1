$ErrorActionPreference = "Stop"

Set-Location "D:\ThreadROM"

$jobName = "trm_sim_000009_c3d10_5000n_pretension"
$runDirectory = "D:\ThreadROM\simulations\staging\TRM-SIM-000009\physical_pretension\coarse"

$stiffnessThreads = 6
$equationSolverThreads = 4
$resultsThreads = 6

New-Item -ItemType Directory -Force -Path $runDirectory | Out-Null

$existingSolver = Get-CimInstance Win32_Process |
    Where-Object {
        $_.Name -ieq "ccx.exe" -and
        $_.CommandLine -like "*$jobName*"
    } |
    Select-Object -First 1

if ($null -ne $existingSolver) {
    throw "This job is already running as PID $($existingSolver.ProcessId)."
}

$memory = Get-CimInstance Win32_PerfFormattedData_PerfOS_Memory

$commitUsage = 100.0 * (
    $memory.CommittedBytes / $memory.CommitLimit
)

$commitFreeGb = (
    $memory.CommitLimit - $memory.CommittedBytes
) / 1GB

Write-Host "PRE-LAUNCH MEMORY"
Write-Host "-----------------"
Write-Host "Commit usage: $([math]::Round($commitUsage, 1))%"
Write-Host "Commit free: $([math]::Round($commitFreeGb, 2)) GB"
Write-Host ""

if ($commitUsage -gt 85.0) {
    throw "Commit usage is already above 85%. Launch cancelled."
}

$python = (
    Resolve-Path ".\.venv\Scripts\python.exe"
).Path

$launcherStdout = Join-Path $runDirectory "overnight_launcher.stdout.log"
$launcherStderr = Join-Path $runDirectory "overnight_launcher.stderr.log"
$runnerPidPath = Join-Path $runDirectory "runner.pid"
$solverPidPath = Join-Path $runDirectory "solver.pid"

Remove-Item $launcherStdout -Force -ErrorAction SilentlyContinue
Remove-Item $launcherStderr -Force -ErrorAction SilentlyContinue
Remove-Item $runnerPidPath -Force -ErrorAction SilentlyContinue
Remove-Item $solverPidPath -Force -ErrorAction SilentlyContinue

$arguments = @(
    "scripts\run_complete_joint_physical_pretension.py",
    "--transfer-config",
    "complete_joint_pretension_calculix_transfer_c3d10_coarse.toml",
    "--contact-config",
    "complete_joint_pretension_contact_c3d10_coarse.toml",
    "--boundary-config",
    "complete_joint_pretension_boundary_regions_c3d10_coarse.toml",
    "--pretension-config",
    "complete_joint_pretension_c3d10_coarse_5kn.toml",
    "--timeout-seconds",
    "0",
    "--stiffness-threads",
    "$stiffnessThreads",
    "--equation-solver-threads",
    "$equationSolverThreads",
    "--results-threads",
    "$resultsThreads"
)

$runnerProcess = Start-Process `
    -FilePath $python `
    -ArgumentList $arguments `
    -WorkingDirectory "D:\ThreadROM" `
    -RedirectStandardOutput $launcherStdout `
    -RedirectStandardError $launcherStderr `
    -WindowStyle Hidden `
    -PassThru

$runnerProcess.Id | Set-Content $runnerPidPath

Write-Host "Python runner started: PID $($runnerProcess.Id)"
Write-Host "Waiting for the actual CalculiX process..."

$solverInfo = $null

for ($attempt = 1; $attempt -le 90; $attempt++) {
    Start-Sleep -Seconds 2

    $solverInfo = Get-CimInstance Win32_Process |
        Where-Object {
            $_.Name -ieq "ccx.exe" -and
            $_.CommandLine -like "*$jobName*"
        } |
        Select-Object -First 1

    if ($null -ne $solverInfo) {
        break
    }

    $runnerAlive = Get-Process `
        -Id $runnerProcess.Id `
        -ErrorAction SilentlyContinue

    if ($null -eq $runnerAlive) {
        break
    }
}

if ($null -eq $solverInfo) {
    Write-Host ""
    Write-Host "--- LAUNCHER STDOUT ---"

    if (Test-Path $launcherStdout) {
        Get-Content $launcherStdout -Tail 80
    }

    Write-Host ""
    Write-Host "--- LAUNCHER STDERR ---"

    if (Test-Path $launcherStderr) {
        Get-Content $launcherStderr -Tail 120
    }

    throw "CalculiX did not start."
}

$solverProcessId = [int]$solverInfo.ProcessId
$solverProcessId | Set-Content $solverPidPath

$solverBefore = Get-Process -Id $solverProcessId
$cpuBefore = $solverBefore.CPU

Start-Sleep -Seconds 5

$solverAfter = Get-Process `
    -Id $solverProcessId `
    -ErrorAction SilentlyContinue

if ($null -eq $solverAfter) {
    throw "CalculiX exited during startup."
}

$cpuIncrease = $solverAfter.CPU - $cpuBefore

$memoryAfter = Get-CimInstance Win32_PerfFormattedData_PerfOS_Memory

$commitUsageAfter = 100.0 * (
    $memoryAfter.CommittedBytes /
    $memoryAfter.CommitLimit
)

Write-Host ""
Write-Host "COARSE C3D10 5 kN RUN: VERIFIED ACTIVE"
Write-Host "--------------------------------------"
Write-Host "Python runner PID: $($runnerProcess.Id)"
Write-Host "CalculiX PID: $solverProcessId"
Write-Host "Timeout: disabled"
Write-Host "Stiffness threads: $stiffnessThreads"
Write-Host "Equation-solver threads: $equationSolverThreads"
Write-Host "Results threads: $resultsThreads"
Write-Host "CPU increase over 5 s: $([math]::Round($cpuIncrease, 2)) s"
Write-Host "Solver RAM: $([math]::Round($solverAfter.WorkingSet64 / 1GB, 2)) GB"
Write-Host "System commit usage: $([math]::Round($commitUsageAfter, 1))%"
Write-Host "Run directory: $runDirectory"
