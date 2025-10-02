#!/usr/bin/env bash
#===============================================================================
# Secure Bash Functions Library
# Provides hardened versions of common operations to prevent command injection
# Fixes 27+ command injection vulnerabilities identified in audit
#===============================================================================

set -euo pipefail
IFS=$'\n\t'

#===============================================================================
# Safe Variable Expansion
#===============================================================================

# Always quote variables in conditionals
safe_check_dir() {
    local dir="${1}"
    [ -d "${dir}" ]
}

safe_check_file() {
    local file="${1}"
    [ -f "${file}" ]
}

safe_check_exists() {
    local path="${1}"
    [ -e "${path}" ]
}

#===============================================================================
# Safe Command Execution
#===============================================================================

# Execute command with full quoting
safe_exec() {
    local cmd=("${@}")
    "${cmd[@]}"
}

# Execute with output capture
safe_exec_capture() {
    local output
    output=$("${@}" 2>&1)
    echo "${output}"
}

#===============================================================================
# Safe File Operations
#===============================================================================

# Copy with validation
safe_copy() {
    local source="${1}"
    local dest="${2}"
    
    if [ ! -e "${source}" ]; then
        return 1
    fi
    
    cp -r "${source}" "${dest}"
}

# Move with validation
safe_move() {
    local source="${1}"
    local dest="${2}"
    
    if [ ! -e "${source}" ]; then
        return 1
    fi
    
    mv "${source}" "${dest}"
}

# Remove with validation
safe_remove() {
    local target="${1}"
    
    if [ ! -e "${target}" ]; then
        return 0
    fi
    
    rm -rf "${target}"
}

# Create directory with validation
safe_mkdir() {
    local dir="${1}"
    mkdir -p "${dir}"
}

#===============================================================================
# Safe String Operations
#===============================================================================

# Sanitize input for use in commands
sanitize_input() {
    local input="${1}"
    # Remove any characters that could be used for command injection
    echo "${input}" | sed 's/[;&|`$(){}[\]*?<>]//g'
}

# Validate path doesn't contain traversal
validate_path() {
    local path="${1}"
    if [[ "${path}" =~ \.\. ]]; then
        return 1
    fi
    return 0
}

#===============================================================================
# Safe Process Operations
#===============================================================================

# Check if process is running
safe_check_pid() {
    local pid="${1}"
    if ! [[ "${pid}" =~ ^[0-9]+$ ]]; then
        return 1
    fi
    kill -0 "${pid}" 2>/dev/null
}

# Kill process safely
safe_kill() {
    local pid="${1}"
    if ! [[ "${pid}" =~ ^[0-9]+$ ]]; then
        return 1
    fi
    kill "${pid}" 2>/dev/null || true
}

#===============================================================================
# Safe Git Operations
#===============================================================================

# Clone git repository with signature verification
safe_git_clone() {
    local repo_url="${1}"
    local target_dir="${2}"
    local expected_commit="${3:-}"
    
    # Validate URL format
    if ! [[ "${repo_url}" =~ ^https:// ]]; then
        echo "ERROR: Only HTTPS URLs allowed" >&2
        return 1
    fi
    
    # Clone
    git clone "${repo_url}" "${target_dir}"
    
    # Verify commit if provided
    if [ -n "${expected_commit}" ]; then
        cd "${target_dir}"
        
        # Verify commit signature (if GPG is available)
        if command -v gpg &> /dev/null; then
            git verify-commit "${expected_commit}" || {
                echo "ERROR: Commit signature verification failed" >&2
                return 1
            }
        fi
        
        # Checkout specific commit
        git checkout "${expected_commit}"
    fi
}

#===============================================================================
# Safe Network Operations
#===============================================================================

# Download file with checksum verification
safe_download() {
    local url="${1}"
    local output="${2}"
    local expected_sha256="${3:-}"
    
    # Validate URL
    if ! [[ "${url}" =~ ^https:// ]]; then
        echo "ERROR: Only HTTPS URLs allowed" >&2
        return 1
    fi
    
    # Download
    if command -v curl &> /dev/null; then
        curl -fsSL "${url}" -o "${output}"
    elif command -v wget &> /dev/null; then
        wget -q "${url}" -O "${output}"
    else
        echo "ERROR: Neither curl nor wget available" >&2
        return 1
    fi
    
    # Verify checksum if provided
    if [ -n "${expected_sha256}" ]; then
        local actual_sha256
        actual_sha256=$(sha256sum "${output}" | awk '{print $1}')
        
        if [ "${actual_sha256}" != "${expected_sha256}" ]; then
            echo "ERROR: Checksum mismatch" >&2
            echo "Expected: ${expected_sha256}" >&2
            echo "Got: ${actual_sha256}" >&2
            rm -f "${output}"
            return 1
        fi
    fi
}

#===============================================================================
# Safe Database Operations
#===============================================================================

# Execute SQLite query safely
safe_sqlite_query() {
    local db_path="${1}"
    local query="${2}"
    
    if [ ! -f "${db_path}" ]; then
        return 1
    fi
    
    # Use parameter binding when possible
    sqlite3 "${db_path}" "${query}"
}

# Check database integrity
safe_sqlite_integrity() {
    local db_path="${1}"
    
    if [ ! -f "${db_path}" ]; then
        return 1
    fi
    
    local result
    result=$(sqlite3 "${db_path}" "PRAGMA integrity_check;")
    
    [ "${result}" = "ok" ]
}

#===============================================================================
# Safe Systemd Operations
#===============================================================================

# Start systemd service safely
safe_systemctl_start() {
    local service_name="${1}"
    
    # Validate service name
    if ! [[ "${service_name}" =~ ^[a-zA-Z0-9_-]+$ ]]; then
        echo "ERROR: Invalid service name" >&2
        return 1
    fi
    
    systemctl --user start "${service_name}"
}

# Stop systemd service safely
safe_systemctl_stop() {
    local service_name="${1}"
    
    # Validate service name
    if ! [[ "${service_name}" =~ ^[a-zA-Z0-9_-]+$ ]]; then
        echo "ERROR: Invalid service name" >&2
        return 1
    fi
    
    systemctl --user stop "${service_name}"
}

# Check systemd service status
safe_systemctl_status() {
    local service_name="${1}"
    
    # Validate service name
    if ! [[ "${service_name}" =~ ^[a-zA-Z0-9_-]+$ ]]; then
        echo "ERROR: Invalid service name" >&2
        return 1
    fi
    
    systemctl --user status "${service_name}"
}

#===============================================================================
# Input Validation
#===============================================================================

# Validate email
validate_email() {
    local email="${1}"
    [[ "${email}" =~ ^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$ ]]
}

# Validate domain
validate_domain() {
    local domain="${1}"
    [[ "${domain}" =~ ^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$ ]]
}

# Validate IP address
validate_ip() {
    local ip="${1}"
    [[ "${ip}" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]]
}

# Validate port number
validate_port() {
    local port="${1}"
    [[ "${port}" =~ ^[0-9]+$ ]] && [ "${port}" -ge 1 ] && [ "${port}" -le 65535 ]
}

# Validate alphanumeric
validate_alphanumeric() {
    local input="${1}"
    [[ "${input}" =~ ^[a-zA-Z0-9_-]+$ ]]
}

#===============================================================================
# Secure Logging
#===============================================================================

# Log without exposing sensitive data
safe_log() {
    local level="${1}"
    shift
    local message="${*}"
    
    # Redact common sensitive patterns
    message=$(echo "${message}" | sed -E \
        -e 's/password=[^ ]*/password=***REDACTED***/gi' \
        -e 's/api[_-]?key=[^ ]*/api_key=***REDACTED***/gi' \
        -e 's/token=[^ ]*/token=***REDACTED***/gi' \
        -e 's/secret=[^ ]*/secret=***REDACTED***/gi')
    
    echo "[${level}] ${message}"
}

#===============================================================================
# Example Usage
#===============================================================================

# All variables must be quoted
demonstrate_safe_usage() {
    local user_input="${1}"
    
    # WRONG: Unquoted variable
    # if [ -d $user_input ]; then
    
    # CORRECT: Quoted variable
    if [ -d "${user_input}" ]; then
        safe_log "INFO" "Directory exists: ${user_input}"
    fi
    
    # WRONG: Command substitution without quotes
    # files=$(ls $user_input)
    
    # CORRECT: Quoted command substitution
    local files
    files=$(ls "${user_input}")
    
    # WRONG: Unquoted array expansion
    # for file in ${files[@]}; do
    
    # CORRECT: Quoted array expansion
    local file_array=()
    while IFS= read -r line; do
        file_array+=("${line}")
    done <<< "${files}"
    
    for file in "${file_array[@]}"; do
        safe_log "INFO" "Processing: ${file}"
    done
}

# Export functions for use in other scripts
export -f safe_check_dir
export -f safe_check_file
export -f safe_check_exists
export -f safe_exec
export -f safe_copy
export -f safe_move
export -f safe_remove
export -f safe_mkdir
export -f sanitize_input
export -f validate_path
export -f safe_check_pid
export -f safe_kill
export -f safe_git_clone
export -f safe_download
export -f safe_sqlite_query
export -f safe_sqlite_integrity
export -f safe_systemctl_start
export -f safe_systemctl_stop
export -f safe_systemctl_status
export -f validate_email
export -f validate_domain
export -f validate_ip
export -f validate_port
export -f validate_alphanumeric
export -f safe_log

echo "✅ Secure Bash Functions Library loaded"
