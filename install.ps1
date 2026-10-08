# Per-user Windows installer. No preinstalled Python or Git is required.
[CmdletBinding()]
param(
    [Alias('Host')]
    [ValidateSet('codex', 'claude', 'kimi', 'all')]
    [string]$TargetHost,
    [switch]$ForceSkill,
    [string]$Ref = 'main',
    [string]$ArchiveUrl,
    [string]$Source,
    [switch]$Offline,
    [Alias('Uv')]
    [string]$UvPath,
    [string]$PythonVersion = '3.11',
    [switch]$Help
)

$ErrorActionPreference = 'Stop'

function Show-DebateHelp {
    @'
Install Debate Direction for the current user with uv-managed Python.

Usage: .\install.ps1 [OPTIONS]

  -Host codex|claude|kimi|all  Also install the selected host skill explicitly
  -ForceSkill                Allow install-skill to replace a conflicting skill
  -Ref REF                   GitHub branch, tag, or commit (default: main)
  -ArchiveUrl HTTPS_URL       Install a specific HTTPS source archive
  -Source PATH               Install a local project, wheel, or source archive
  -Offline                   Use local source and preinstalled/cached uv resources
  -UvPath PATH               Use this existing uv executable
  -PythonVersion VERSION     Managed Python version, >=3.11 (default: 3.11)
  -Help                      Show this help

Select only one of -Ref, -ArchiveUrl, and -Source. Ref names may contain letters,
digits, dots, underscores, and hyphens; use -ArchiveUrl for other refs.
Rerun this installer to update or reinstall. It does not change execution policy,
user or machine PATH, profiles, provider credentials, or host settings.
No host is installed unless requested. Offline mode requires existing uv,
managed Python, and cached build requirements, or a prepared local wheel.
'@
}

function Format-DebatePsArgument([string]$Value) {
    return "'" + $Value.Replace("'", "''") + "'"
}

function Invoke-DebateUv([string[]]$UvArguments) {
    & $script:DebateUv @UvArguments
    if ($LASTEXITCODE -ne 0) {
        throw "uv failed with exit code $LASTEXITCODE. Review its error above."
    }
}

if ($Help) {
    Show-DebateHelp
    return
}

try {
    if ($PSVersionTable.PSVersion -lt [Version]'5.1') {
        throw 'PowerShell 5.1 or newer is required.'
    }
    if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) {
        throw 'Use install.sh on macOS or Linux. This PowerShell installer supports Windows.'
    }
    $sourceOptionCount = 0
    foreach ($option in @('Ref', 'ArchiveUrl', 'Source')) {
        if ($PSBoundParameters.ContainsKey($option)) { $sourceOptionCount++ }
    }
    if ($sourceOptionCount -gt 1) {
        throw 'Choose only one source option: -Ref, -ArchiveUrl, or -Source.'
    }
    if ($ForceSkill -and -not $TargetHost) {
        throw '-ForceSkill requires -Host.'
    }
    $pythonMatch = [regex]::Match($PythonVersion, '^3\.(\d+)(\.\d+)?$')
    if (-not $pythonMatch.Success -or [int]$pythonMatch.Groups[1].Value -lt 11) {
        throw '-PythonVersion must be Python 3.11 or newer, such as 3.11 or 3.12.4.'
    }
    if ($Source) {
        $sourceItem = Get-Item -LiteralPath $Source -ErrorAction Stop
        if ($sourceItem.PSProvider.Name -ne 'FileSystem') {
            throw '-Source must be a local filesystem path.'
        }
        $packageSource = $sourceItem.FullName
    } elseif ($Offline) {
        throw '-Offline requires -Source with a local project or distribution.'
    } elseif ($ArchiveUrl) {
        $archiveUri = $null
        if (-not [Uri]::TryCreate($ArchiveUrl, [UriKind]::Absolute, [ref]$archiveUri) -or $archiveUri.Scheme -ne 'https') {
            throw '-ArchiveUrl must use HTTPS.'
        }
        $packageSource = 'debate-direction @ ' + $ArchiveUrl
    } else {
        if ($Ref -notmatch '^[A-Za-z0-9][A-Za-z0-9._-]*$') {
            throw 'Invalid -Ref; use a branch, tag, or commit without slashes, or supply -ArchiveUrl.'
        }
        if ($Ref -eq 'main') {
            $ArchiveUrl = 'https://github.com/Afloat16/debate-direction/archive/refs/heads/main.zip'
        } else {
            $ArchiveUrl = "https://github.com/Afloat16/debate-direction/archive/$Ref.zip"
        }
        $packageSource = 'debate-direction @ ' + $ArchiveUrl
    }

    $userDirectory = [Environment]::GetFolderPath('UserProfile')
    $localData = [Environment]::GetFolderPath('LocalApplicationData')
    if (-not $userDirectory -or -not $localData) {
        throw 'The current user profile directories are unavailable.'
    }
    $bootstrapDirectory = Join-Path $localData 'debate-direction\uv'
    $defaultUv = Join-Path $userDirectory '.local\bin\uv.exe'
    $bootstrapUv = Join-Path $bootstrapDirectory 'uv.exe'
    $script:DebateUv = $null
    if ($UvPath) {
        if (Test-Path -LiteralPath $UvPath -PathType Leaf) {
            $script:DebateUv = (Get-Item -LiteralPath $UvPath).FullName
        } else {
            $uvCommand = Get-Command $UvPath -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
            if ($uvCommand) { $script:DebateUv = $uvCommand.Source }
        }
        if (-not $script:DebateUv) { throw 'The -UvPath executable was not found.' }
    } else {
        $uvCommand = Get-Command uv -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($uvCommand) {
            $script:DebateUv = $uvCommand.Source
        } elseif (Test-Path -LiteralPath $defaultUv -PathType Leaf) {
            $script:DebateUv = $defaultUv
        } elseif (Test-Path -LiteralPath $bootstrapUv -PathType Leaf) {
            $script:DebateUv = $bootstrapUv
        }
    }

    if (-not $script:DebateUv) {
        if ($Offline) { throw 'Offline mode requires an existing uv executable; use -UvPath PATH.' }
        # Astral's script installer requires a permissive execution policy.
        # Use its official immutable release binary directly instead.
        $uvBootstrapVersion = '0.12.23'
        try {
            $architecture = [System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture.ToString()
        } catch {
            $architecture = $env:PROCESSOR_ARCHITECTURE
            if ($env:PROCESSOR_ARCHITEW6432) { $architecture = $env:PROCESSOR_ARCHITEW6432 }
        }
        switch ($architecture.ToUpperInvariant()) {
            { $_ -in @('X64', 'AMD64') } {
                $uvTarget = 'x86_64-pc-windows-msvc'
                $uvExpectedHash = '75d05de6762778c31ee183398de7dd15093fad0ed90b1f236d8205ea5ec00c90'
            }
            'ARM64' {
                $uvTarget = 'aarch64-pc-windows-msvc'
                $uvExpectedHash = '13294e232ececbe709c06b74e6ced06f2a225ea5591476685362f22be56a50d5'
            }
            'X86' {
                $uvTarget = 'i686-pc-windows-msvc'
                $uvExpectedHash = '22a92f4374e4716c2848acaa0392f2f8e4a13b0ff65d080e2a5ade167bce96a8'
            }
            default { throw 'No bundled uv bootstrap is available for this Windows architecture. Install uv from its official site and use -UvPath.' }
        }
        $uvArchiveUrl = "https://releases.astral.sh/github/uv/releases/download/$uvBootstrapVersion/uv-$uvTarget.zip"
        Write-Host "Installing uv $uvBootstrapVersion for the current user from $uvArchiveUrl"
        $temporaryDirectory = Join-Path ([IO.Path]::GetTempPath()) ('debate-direction-' + [Guid]::NewGuid().ToString('N'))
        New-Item -ItemType Directory -Path $temporaryDirectory | Out-Null
        $previousTls = [Net.ServicePointManager]::SecurityProtocol
        try {
            if ($PSVersionTable.PSVersion.Major -lt 6) {
                [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
            }
            $uvArchive = Join-Path $temporaryDirectory 'uv.zip'
            Invoke-WebRequest -UseBasicParsing -Uri $uvArchiveUrl -OutFile $uvArchive
            if ((Get-FileHash -LiteralPath $uvArchive -Algorithm SHA256).Hash -ne $uvExpectedHash) {
                throw 'The downloaded uv archive failed SHA256 verification.'
            }
            $expandedDirectory = Join-Path $temporaryDirectory 'expanded'
            Expand-Archive -LiteralPath $uvArchive -DestinationPath $expandedDirectory
            $uvBinaries = @(Get-ChildItem -LiteralPath $expandedDirectory -Filter 'uv.exe' -File -Recurse)
            if ($uvBinaries.Count -ne 1) { throw 'The verified uv archive did not contain exactly one uv.exe.' }
            New-Item -ItemType Directory -Path $bootstrapDirectory -Force | Out-Null
            Copy-Item -LiteralPath $uvBinaries[0].FullName -Destination $bootstrapUv
        } finally {
            [Net.ServicePointManager]::SecurityProtocol = $previousTls
            Remove-Item -LiteralPath $temporaryDirectory -Recurse -Force -ErrorAction SilentlyContinue
        }
        $script:DebateUv = $bootstrapUv
    }
    if (-not (Test-Path -LiteralPath $script:DebateUv -PathType Leaf)) {
        throw 'The uv executable is unavailable. Review the bootstrap output or install uv separately.'
    }

    Write-Host "Installing Debate Direction with managed Python $PythonVersion..."
    $uvInstallArguments = @('tool', 'install', '--no-config', '--managed-python', '--python', $PythonVersion, '--reinstall')
    if ($Offline) { $uvInstallArguments += @('--offline', '--no-python-downloads') }
    $uvInstallArguments += @('--', $packageSource)
    Invoke-DebateUv -UvArguments $uvInstallArguments
    $directoryOutput = @(Invoke-DebateUv -UvArguments @('tool', 'dir', '--bin', '--no-config'))
    if ($directoryOutput.Count -ne 1 -or -not $directoryOutput[0]) {
        throw 'Could not locate the installed command directory.'
    }
    $commandDirectory = ([string]$directoryOutput[0]).Trim()
    $cliPath = Join-Path $commandDirectory 'debate-direction.exe'
    if (-not (Test-Path -LiteralPath $cliPath -PathType Leaf)) {
        throw 'uv completed but debate-direction.exe was not found.'
    }
    & $cliPath --help | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'The installed CLI could not start.' }

    Write-Host "`nInstalled CLI: $cliPath"
    Write-Host ('Run immediately:' + "`n  & " + (Format-DebatePsArgument $cliPath) + ' doctor')
    Write-Host 'For this PowerShell session:'
    Write-Host ('  $env:PATH = ' + (Format-DebatePsArgument ($commandDirectory + ';')) + ' + $env:PATH')
    Write-Host 'For future sessions, add the command directory to your user PATH in Windows environment settings.'
    Write-Host 'Update: rerun this installer with the desired source or -Ref.'
    Write-Host ('Uninstall the CLI:' + "`n  & " + (Format-DebatePsArgument $script:DebateUv) + ' tool uninstall debate-direction')
    Write-Host 'Uninstalling the CLI keeps optional host skills and shared uv/Python data.'

    if ($TargetHost) {
        Write-Host "`nInstalling the explicitly selected host skill: $TargetHost"
        $skillArguments = @('install-skill', '--host', $TargetHost)
        if ($ForceSkill) { $skillArguments += '--force' }
        & $cliPath @skillArguments
        if ($LASTEXITCODE -ne 0) {
            throw 'The CLI is installed, but the requested host skill could not be installed. Resolve the reported conflict before retrying.'
        }
    }
} catch {
    Write-Error -ErrorAction Continue ("Installation failed: " + $_.Exception.Message)
    exit 1
}
