# Install Agent Work Kit (awkit) on Windows.
#   irm https://raw.githubusercontent.com/min-seokkim/agent-work-kit/dev/install.ps1 | iex
# Installs Git and Python with winget when they are missing, then pipx and awkit, then runs
# `awkit doctor`. $env:AWKIT_SOURCE overrides what pipx installs (default: the dev branch on GitHub).
# The script never calls exit, because under `irm | iex` that would close the user's window, and it
# checks exit codes itself, because Windows PowerShell 5.1 turns native stderr into errors under Stop.

function Update-SessionPath {
    $machine = [Environment]::GetEnvironmentVariable('Path', 'Machine')
    $user = [Environment]::GetEnvironmentVariable('Path', 'User')
    $env:Path = "$env:Path;$machine;$user"
}

function Install-WithWinget($Name, $Id) {
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        Write-Host "Missing: $Name. winget is not available; install $Name from its website, then run this installer again."
        return $false
    }
    Write-Host "Installing $Name with winget..."
    winget install --id $Id -e --source winget --accept-package-agreements --accept-source-agreements | Out-Host
    Update-SessionPath
    return $true
}

function Find-Python {
    # The Microsoft Store alias named python prints nothing useful; check the version, not the name.
    foreach ($candidate in @(@('py', '-3'), @('python'), @('python3'))) {
        $exe = $candidate[0]
        if (-not (Get-Command $exe -ErrorAction SilentlyContinue)) { continue }
        $arguments = @($candidate | Select-Object -Skip 1) + @('-c', 'import sys; print(sys.version_info >= (3, 11))')
        $answer = & $exe @arguments 2>$null
        if ($LASTEXITCODE -eq 0 -and "$answer".Trim() -eq 'True') { return ,$candidate }
    }
    return $null
}

function Install-Awkit {
    $source = if ($env:AWKIT_SOURCE) { $env:AWKIT_SOURCE } else { 'git+https://github.com/min-seokkim/agent-work-kit@dev' }

    if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
        if (-not (Install-WithWinget 'Git' 'Git.Git')) { return }
    }

    $python = Find-Python
    if (-not $python) {
        if (-not (Install-WithWinget 'Python 3.12' 'Python.Python.3.12')) { return }
        $python = Find-Python
        if (-not $python) {
            Write-Host 'Python was installed but is not on PATH yet. Open a new terminal and run this installer again.'
            return
        }
    }
    $pyExe = $python[0]
    $pyArgs = @($python | Select-Object -Skip 1)

    & $pyExe @pyArgs -m pipx --version *> $null
    if ($LASTEXITCODE -ne 0) {
        Write-Host 'Installing pipx...'
        & $pyExe @pyArgs -m pip install --user --upgrade pipx
        if ($LASTEXITCODE -ne 0) { Write-Host 'Installing pipx failed.'; return }
    }

    Write-Host "Installing awkit from $source..."
    & $pyExe @pyArgs -m pipx install --force $source
    if ($LASTEXITCODE -ne 0) { Write-Host 'Installing awkit failed.'; return }
    & $pyExe @pyArgs -m pipx ensurepath *> $null
    Update-SessionPath

    $bin = & $pyExe @pyArgs -m pipx environment --value PIPX_BIN_DIR 2>$null
    $awkit = if ($bin) { Join-Path "$bin".Trim() 'awkit.exe' } else { '' }
    if (-not $awkit -or -not (Test-Path $awkit)) { $awkit = 'awkit' }
    Write-Host ''
    & $awkit --version
    & $awkit doctor
    Write-Host ''
    Write-Host 'Open a new terminal if the awkit command is not found. Fix anything marked missing above, then run'
    Write-Host 'awkit kit init in your project folder.'
}

Install-Awkit
