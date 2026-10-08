#!/bin/sh
# Per-user installer for macOS and Linux. No Python or Git prerequisite.
set -eu

debate_ref=main
debate_source=
debate_archive=
debate_source_options=0
debate_host=
debate_force_skill=0
debate_offline=0
debate_python=3.11
debate_uv_requested=
debate_temp=

debate_die() {
    printf 'Error: %s\n' "$*" >&2
    exit 1
}

debate_help() {
    cat <<'HELP'
Install Debate Direction for the current user with uv-managed Python.

Usage: sh install.sh [OPTIONS]

  --host codex|claude|kimi|all  Also install the selected host skill explicitly
  --force-skill                Allow install-skill to replace a conflicting skill
  --ref REF                   GitHub branch, tag, or commit (default: main)
  --archive-url HTTPS_URL      Install a specific HTTPS source archive
  --source PATH               Install a local project, wheel, or source archive
  --offline                   Use local source and preinstalled/cached uv resources
  --uv PATH                   Use this existing uv executable
  --python VERSION            Managed Python version, >=3.11 (default: 3.11)
  -h, --help                  Show this help

Select only one of --ref, --archive-url, and --source. Ref names may contain
letters, digits, dots, underscores, and hyphens; use --archive-url for other refs.
Rerun this installer to update or reinstall. It does not edit shell profiles,
provider credentials, or host settings. No host is installed unless requested.
Offline mode requires an existing uv executable, managed Python, and cached build
requirements; a prepared local wheel avoids source-build requirements.
HELP
}

debate_value() {
    [ "$#" -ge 2 ] && [ -n "$2" ] || debate_die "$1 requires a value."
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --host)
            debate_value "$@"; debate_host=$2; shift 2 ;;
        --force-skill)
            debate_force_skill=1; shift ;;
        --ref)
            debate_value "$@"; debate_ref=$2
            debate_source_options=$((debate_source_options + 1)); shift 2 ;;
        --archive-url)
            debate_value "$@"; debate_archive=$2
            debate_source_options=$((debate_source_options + 1)); shift 2 ;;
        --source)
            debate_value "$@"; debate_source=$2
            debate_source_options=$((debate_source_options + 1)); shift 2 ;;
        --offline)
            debate_offline=1; shift ;;
        --uv)
            debate_value "$@"; debate_uv_requested=$2; shift 2 ;;
        --python)
            debate_value "$@"; debate_python=$2; shift 2 ;;
        -h|--help)
            debate_help; exit 0 ;;
        *) debate_die "Unknown option: $1. Use --help for supported options." ;;
    esac
done

[ "$debate_source_options" -le 1 ] || debate_die 'Choose only one source option: --ref, --archive-url, or --source.'
case "$debate_host" in
    ''|codex|claude|kimi|all) ;;
    *) debate_die '--host must be codex, claude, kimi, or all.' ;;
esac
[ "$debate_force_skill" -eq 0 ] || [ -n "$debate_host" ] || debate_die '--force-skill requires --host.'
case "$debate_python" in
    3.*) ;;
    *) debate_die '--python must be a Python 3 version at least 3.11, such as 3.11 or 3.12.4.' ;;
esac
debate_minor=${debate_python#3.}
debate_minor=${debate_minor%%.*}
case "$debate_python" in
    *[!0-9.]*|*..*|*.) debate_die 'Invalid Python version.' ;;
esac
case "${debate_python#3.}" in
    *.*.*) debate_die 'Use a Python major.minor or major.minor.patch version.' ;;
esac
case "$debate_minor" in
    ''|*[!0-9]*) debate_die 'Invalid Python minor version.' ;;
esac
[ "$debate_minor" -ge 11 ] || debate_die 'Python 3.11 or newer is required.'

if [ -n "$debate_source" ]; then
    [ -e "$debate_source" ] || debate_die 'The --source path does not exist.'
    case "$debate_source" in
        /*) ;;
        *) debate_source="$PWD/$debate_source" ;;
    esac
elif [ "$debate_offline" -eq 1 ]; then
    debate_die '--offline requires --source with a local project or distribution.'
elif [ -n "$debate_archive" ]; then
    case "$debate_archive" in
        https://?*) debate_source="debate-direction @ $debate_archive" ;;
        *) debate_die '--archive-url must use HTTPS.' ;;
    esac
else
    case "$debate_ref" in
        ''|.*|-*|*[!A-Za-z0-9._-]*) debate_die 'Invalid --ref; use a branch, tag, or commit without slashes, or supply --archive-url.' ;;
    esac
    if [ "$debate_ref" = main ]; then
        debate_archive=https://github.com/Afloat16/debate-direction/archive/refs/heads/main.zip
    else
        debate_archive="https://github.com/Afloat16/debate-direction/archive/$debate_ref.zip"
    fi
    debate_source="debate-direction @ $debate_archive"
fi

case "$(uname -s)" in
    Darwin|Linux) ;;
    *) debate_die 'Use install.ps1 on Windows. This shell installer supports macOS and Linux.' ;;
esac
[ -n "${HOME:-}" ] || debate_die 'The current user home directory is unavailable.'
debate_bootstrap="${XDG_DATA_HOME:-$HOME/.local/share}/debate-direction/uv"

if [ -n "$debate_uv_requested" ]; then
    if [ -x "$debate_uv_requested" ]; then
        debate_uv=$debate_uv_requested
        case "$debate_uv" in
            /*) ;;
            *) debate_uv="$PWD/$debate_uv" ;;
        esac
    else
        debate_uv=$(command -v "$debate_uv_requested" 2>/dev/null) || debate_die 'The --uv executable was not found.'
    fi
elif command -v uv >/dev/null 2>&1; then
    debate_uv=$(command -v uv)
elif [ -x "$HOME/.local/bin/uv" ]; then
    debate_uv="$HOME/.local/bin/uv"
elif [ -x "$debate_bootstrap/uv" ]; then
    debate_uv="$debate_bootstrap/uv"
else
    [ "$debate_offline" -eq 0 ] || debate_die 'Offline mode requires an existing uv executable; use --uv PATH.'
    debate_temp=$(mktemp -d "${TMPDIR:-/tmp}/debate-direction.XXXXXXXX") || debate_die 'Could not create a temporary directory.'
    trap 'if [ -n "$debate_temp" ]; then rm -rf "$debate_temp"; fi' EXIT
    trap 'exit 129' HUP
    trap 'exit 130' INT
    trap 'exit 143' TERM
    printf 'Installing uv for the current user from https://astral.sh/uv/0.12.23/install.sh\n'
    if command -v curl >/dev/null 2>&1; then
        curl --proto '=https' --tlsv1.2 -fLsS https://astral.sh/uv/0.12.23/install.sh -o "$debate_temp/uv-install.sh" || debate_die 'Could not download the official uv installer.'
    elif command -v wget >/dev/null 2>&1; then
        wget --https-only -q -O "$debate_temp/uv-install.sh" https://astral.sh/uv/0.12.23/install.sh || debate_die 'Could not download uv; install curl or download uv from its official site.'
    else
        debate_die 'Install curl or wget, or install uv separately and rerun with --uv PATH.'
    fi
    env UV_UNMANAGED_INSTALL="$debate_bootstrap" UV_NO_MODIFY_PATH=1 sh "$debate_temp/uv-install.sh" || debate_die 'The official uv installer failed.'
    debate_uv="$debate_bootstrap/uv"
fi

[ -x "$debate_uv" ] || debate_die 'The uv executable is unavailable.'
printf 'Installing Debate Direction with managed Python %s...\n' "$debate_python"
if [ "$debate_offline" -eq 1 ]; then
    "$debate_uv" tool install --no-config --managed-python --python "$debate_python" --reinstall --offline --no-python-downloads -- "$debate_source" || debate_die 'Offline installation failed. Provide managed Python and cached build requirements, or a prepared local wheel.'
else
    "$debate_uv" tool install --no-config --managed-python --python "$debate_python" --reinstall -- "$debate_source" || debate_die 'Installation failed. Review the uv error above; an existing executable from another installer is not overwritten.'
fi
debate_bin=$("$debate_uv" tool dir --bin --no-config) || debate_die 'Could not locate the installed command directory.'
debate_cli="$debate_bin/debate-direction"
[ -x "$debate_cli" ] || debate_die 'uv completed but the debate-direction executable was not found.'
"$debate_cli" --help >/dev/null || debate_die 'The installed CLI could not start.'

debate_quote() {
    printf "'"
    printf '%s' "$1" | sed "s/'/'\\\\''/g"
    printf "'"
}
debate_cli_quoted=$(debate_quote "$debate_cli")
debate_uv_quoted=$(debate_quote "$debate_uv")
debate_bin_quoted=$(debate_quote "$debate_bin")

printf '\nInstalled CLI: %s\n' "$debate_cli"
printf 'Run immediately:\n  %s doctor\n' "$debate_cli_quoted"
printf 'For this POSIX shell session:\n  export PATH=%s:"$PATH"\n' "$debate_bin_quoted"
printf 'For future sessions, add the command directory to your user PATH or shell profile.\n'
printf 'Update: rerun this installer with the desired source or --ref.\n'
printf 'Uninstall the CLI:\n  %s tool uninstall debate-direction\n' "$debate_uv_quoted"
printf 'Uninstalling the CLI keeps optional host skills and shared uv/Python data.\n'

if [ -n "$debate_host" ]; then
    printf '\nInstalling the explicitly selected host skill: %s\n' "$debate_host"
    if [ "$debate_force_skill" -eq 1 ]; then
        "$debate_cli" install-skill --host "$debate_host" --force || debate_die 'The CLI is installed, but the requested host skill could not be installed.'
    else
        "$debate_cli" install-skill --host "$debate_host" || debate_die 'The CLI is installed, but the requested host skill could not be installed. Resolve the reported conflict before retrying.'
    fi
fi
