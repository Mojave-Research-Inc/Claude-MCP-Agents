#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

#===============================================================================
# MCP Rollback & Recovery System
# Provides backup, restore, and rollback capabilities with integrity validation
# Addresses CVSS 7.5 vulnerability - No Rollback Mechanism
#===============================================================================

# Configuration
CLAUDE_DIR="${HOME}/.claude"
BACKUP_ROOT="${CLAUDE_DIR}/backups"
STATE_FILE="${CLAUDE_DIR}/.system_state.json"
CHECKSUM_FILE="${CLAUDE_DIR}/.system_checksums.sha256"
LOCK_FILE="${CLAUDE_DIR}/.rollback.lock"
LOG_FILE="${CLAUDE_DIR}/logs/rollback.log"

# Retention settings
MAX_BACKUPS=10
MAX_BACKUP_AGE_DAYS=30

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

#===============================================================================
# Logging Functions
#===============================================================================

log() {
    local level="${1}"
    shift
    local message="${*}"
    local timestamp
    timestamp="$(date '+%Y-%m-%d %H:%M:%S')"

    echo "[${timestamp}] [${level}] ${message}" | tee -a "${LOG_FILE}"
}

log_info() {
    log "INFO" "${@}"
    echo -e "${BLUE}ℹ ${*}${NC}"
}

log_success() {
    log "SUCCESS" "${@}"
    echo -e "${GREEN}✅ ${*}${NC}"
}

log_warn() {
    log "WARN" "${@}"
    echo -e "${YELLOW}⚠️  ${*}${NC}"
}

log_error() {
    log "ERROR" "${@}"
    echo -e "${RED}❌ ${*}${NC}" >&2
}

#===============================================================================
# Lock Management
#===============================================================================

acquire_lock() {
    local max_wait=30
    local waited=0

    while [ -f "${LOCK_FILE}" ]; do
        if [ ${waited} -ge ${max_wait} ]; then
            log_error "Could not acquire lock after ${max_wait} seconds"
            return 1
        fi

        log_warn "Waiting for lock... (${waited}s)"
        sleep 1
        waited=$((waited + 1))
    done

    echo $$ > "${LOCK_FILE}"
    log_info "Lock acquired (PID: $$)"
}

release_lock() {
    if [ -f "${LOCK_FILE}" ]; then
        rm -f "${LOCK_FILE}"
        log_info "Lock released"
    fi
}

# Ensure lock is released on exit
trap release_lock EXIT INT TERM

#===============================================================================
# Checksum Functions
#===============================================================================

generate_checksums() {
    local target_dir="${1}"
    local output_file="${2}"

    log_info "Generating checksums for ${target_dir}..."

    # Generate checksums for all files
    find "${target_dir}" -type f -exec sha256sum {} \; > "${output_file}" 2>/dev/null || true

    local file_count
    file_count=$(wc -l < "${output_file}")
    log_info "Generated checksums for ${file_count} files"
}

verify_checksums() {
    local checksum_file="${1}"
    local base_dir="${2:-/}"

    log_info "Verifying checksums..."

    if [ ! -f "${checksum_file}" ]; then
        log_error "Checksum file not found: ${checksum_file}"
        return 1
    fi

    local failed=0
    local total=0

    while IFS= read -r line; do
        total=$((total + 1))

        # Parse checksum line
        local expected_hash file_path
        expected_hash=$(echo "${line}" | awk '{print $1}')
        file_path=$(echo "${line}" | awk '{$1=""; print $0}' | sed 's/^ *//')

        # Adjust path if base_dir provided
        if [ "${base_dir}" != "/" ]; then
            file_path="${base_dir}/${file_path##*/}"
        fi

        # Verify file exists
        if [ ! -f "${file_path}" ]; then
            log_warn "File missing: ${file_path}"
            failed=$((failed + 1))
            continue
        fi

        # Calculate current hash
        local current_hash
        current_hash=$(sha256sum "${file_path}" | awk '{print $1}')

        # Compare hashes
        if [ "${current_hash}" != "${expected_hash}" ]; then
            log_warn "Checksum mismatch: ${file_path}"
            failed=$((failed + 1))
        fi
    done < "${checksum_file}"

    if [ ${failed} -eq 0 ]; then
        log_success "All ${total} checksums verified successfully"
        return 0
    else
        log_error "${failed} of ${total} checksums failed verification"
        return 1
    fi
}

#===============================================================================
# Backup Functions
#===============================================================================

create_backup() {
    local backup_name="${1:-auto_$(date '+%Y%m%d_%H%M%S')}"
    local backup_dir="${BACKUP_ROOT}/${backup_name}"

    log_info "Creating backup: ${backup_name}"

    # Create backup directory
    mkdir -p "${backup_dir}"

    # Backup critical directories and files
    local items_to_backup=(
        ".mcp.json"
        ".env"
        "agents"
        "mcp-servers"
        "scripts"
        "services"
        "data"
        "pids"
        ".secrets_index.json"
    )

    for item in "${items_to_backup[@]}"; do
        local source="${CLAUDE_DIR}/${item}"

        if [ -e "${source}" ]; then
            log_info "Backing up: ${item}"

            if [ -d "${source}" ]; then
                cp -r "${source}" "${backup_dir}/"
            else
                cp "${source}" "${backup_dir}/"
            fi
        else
            log_warn "Item not found, skipping: ${item}"
        fi
    done

    # Generate checksums
    generate_checksums "${backup_dir}" "${backup_dir}/.checksums.sha256"

    # Create metadata
    cat > "${backup_dir}/.metadata.json" << EOF
{
  "backup_name": "${backup_name}",
  "created_at": "$(date -Iseconds)",
  "hostname": "$(hostname)",
  "user": "${USER}",
  "claude_dir": "${CLAUDE_DIR}",
  "items_backed_up": $(printf '%s\n' "${items_to_backup[@]}" | jq -R . | jq -s .),
  "backup_size_mb": $(du -sm "${backup_dir}" | cut -f1)
}
EOF

    # Create symlink to latest
    rm -f "${BACKUP_ROOT}/LATEST"
    ln -s "${backup_dir}" "${BACKUP_ROOT}/LATEST"

    log_success "Backup created successfully: ${backup_dir}"
    log_info "Backup size: $(du -sh "${backup_dir}" | cut -f1)"

    # Cleanup old backups
    cleanup_old_backups

    return 0
}

list_backups() {
    log_info "Available backups:"
    echo ""
    printf "%-30s %-20s %-15s %s\n" "NAME" "CREATED" "SIZE" "CHECKSUMS"
    printf "%s\n" "$(printf '=%.0s' {1..80})"

    if [ ! -d "${BACKUP_ROOT}" ]; then
        log_warn "No backups found"
        return 0
    fi

    local count=0

    for backup_dir in "${BACKUP_ROOT}"/*; do
        if [ ! -d "${backup_dir}" ] || [ -L "${backup_dir}" ]; then
            continue
        fi

        local name
        name=$(basename "${backup_dir}")

        if [ -f "${backup_dir}/.metadata.json" ]; then
            local created size checksum_status

            created=$(jq -r '.created_at' "${backup_dir}/.metadata.json" 2>/dev/null || echo "Unknown")
            size=$(jq -r '.backup_size_mb' "${backup_dir}/.metadata.json" 2>/dev/null || echo "?")

            # Verify checksums
            if [ -f "${backup_dir}/.checksums.sha256" ]; then
                if verify_checksums "${backup_dir}/.checksums.sha256" "${backup_dir}" >/dev/null 2>&1; then
                    checksum_status="${GREEN}✅ Valid${NC}"
                else
                    checksum_status="${RED}❌ Invalid${NC}"
                fi
            else
                checksum_status="${YELLOW}⚠️  Missing${NC}"
            fi

            printf "%-30s %-20s %-15s %b\n" "${name}" "${created:0:19}" "${size}MB" "${checksum_status}"
            count=$((count + 1))
        fi
    done

    echo ""
    log_info "Total backups: ${count}"
}

cleanup_old_backups() {
    log_info "Cleaning up old backups..."

    local backup_count
    backup_count=$(find "${BACKUP_ROOT}" -maxdepth 1 -type d -name "*_*" | wc -l)

    if [ ${backup_count} -le ${MAX_BACKUPS} ]; then
        log_info "Backup count (${backup_count}) within limit (${MAX_BACKUPS})"
        return 0
    fi

    # Remove oldest backups beyond the limit
    local to_remove=$((backup_count - MAX_BACKUPS))

    log_info "Removing ${to_remove} oldest backups..."

    find "${BACKUP_ROOT}" -maxdepth 1 -type d -name "*_*" -printf '%T+ %p\n' \
        | sort \
        | head -n ${to_remove} \
        | cut -d' ' -f2- \
        | while read -r backup_dir; do
            log_info "Removing old backup: $(basename "${backup_dir}")"
            rm -rf "${backup_dir}"
        done

    # Also remove backups older than MAX_BACKUP_AGE_DAYS
    find "${BACKUP_ROOT}" -maxdepth 1 -type d -name "*_*" -mtime +${MAX_BACKUP_AGE_DAYS} -exec rm -rf {} \;

    log_success "Cleanup completed"
}

#===============================================================================
# Restore Functions
#===============================================================================

restore_backup() {
    local backup_name="${1}"
    local backup_dir="${BACKUP_ROOT}/${backup_name}"

    if [ ! -d "${backup_dir}" ]; then
        log_error "Backup not found: ${backup_name}"
        return 1
    fi

    log_info "Restoring from backup: ${backup_name}"

    # Verify checksums before restore
    if [ -f "${backup_dir}/.checksums.sha256" ]; then
        log_info "Verifying backup integrity..."

        if ! verify_checksums "${backup_dir}/.checksums.sha256" "${backup_dir}"; then
            log_error "Backup integrity check failed"

            read -p "Continue anyway? (y/N): " -n 1 -r
            echo

            if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                return 1
            fi
        fi
    else
        log_warn "No checksums found for backup"
    fi

    # Create pre-restore backup
    log_info "Creating pre-restore backup..."
    create_backup "pre_restore_$(date '+%Y%m%d_%H%M%S')"

    # Stop all services
    log_info "Stopping MCP services..."
    if command -v claude-control &> /dev/null; then
        claude-control stop || true
    fi

    # Restore files
    log_info "Restoring files..."

    for item in "${backup_dir}"/*; do
        local item_name
        item_name=$(basename "${item}")

        # Skip metadata files
        if [[ "${item_name}" == .* ]]; then
            continue
        fi

        local target="${CLAUDE_DIR}/${item_name}"

        log_info "Restoring: ${item_name}"

        # Remove existing
        rm -rf "${target}"

        # Restore
        if [ -d "${item}" ]; then
            cp -r "${item}" "${target}"
        else
            cp "${item}" "${target}"
        fi
    done

    # Restore permissions
    chmod 600 "${CLAUDE_DIR}/.env" 2>/dev/null || true
    chmod 600 "${CLAUDE_DIR}/.secrets_index.json" 2>/dev/null || true
    chmod +x "${CLAUDE_DIR}"/scripts/*.sh 2>/dev/null || true
    chmod +x "${CLAUDE_DIR}"/scripts/*.py 2>/dev/null || true
    chmod +x "${CLAUDE_DIR}"/services/*.sh 2>/dev/null || true

    # Restart services
    log_info "Restarting MCP services..."
    if command -v claude-control &> /dev/null; then
        claude-control start || true
    fi

    log_success "Restore completed successfully"
    log_info "Restored from: ${backup_dir}"

    return 0
}

#===============================================================================
# Rollback Functions
#===============================================================================

rollback_last_change() {
    log_info "Rolling back to last known good state..."

    # Find latest backup (excluding pre_restore)
    local latest_backup
    latest_backup=$(find "${BACKUP_ROOT}" -maxdepth 1 -type d -name "*_*" ! -name "pre_restore_*" -printf '%T+ %p\n' \
        | sort -r \
        | head -1 \
        | cut -d' ' -f2-)

    if [ -z "${latest_backup}" ]; then
        log_error "No backup found for rollback"
        return 1
    fi

    local backup_name
    backup_name=$(basename "${latest_backup}")

    log_info "Rolling back to: ${backup_name}"

    restore_backup "${backup_name}"
}

#===============================================================================
# Health Check Functions
#===============================================================================

health_check() {
    log_info "Performing system health check..."

    local issues=0

    # Check critical files exist
    local critical_files=(
        ".mcp.json"
        "claude-control"
    )

    for file in "${critical_files[@]}"; do
        if [ ! -e "${CLAUDE_DIR}/${file}" ]; then
            log_error "Critical file missing: ${file}"
            issues=$((issues + 1))
        fi
    done

    # Check critical directories exist
    local critical_dirs=(
        "agents"
        "mcp-servers"
        "scripts"
        "services"
        "logs"
        "pids"
        "data"
    )

    for dir in "${critical_dirs[@]}"; do
        if [ ! -d "${CLAUDE_DIR}/${dir}" ]; then
            log_error "Critical directory missing: ${dir}"
            issues=$((issues + 1))
        fi
    done

    # Check database files
    for db in "${CLAUDE_DIR}"/data/*.db; do
        if [ -f "${db}" ]; then
            if ! sqlite3 "${db}" "PRAGMA integrity_check;" >/dev/null 2>&1; then
                log_error "Database corruption detected: $(basename "${db}")"
                issues=$((issues + 1))
            fi
        fi
    done

    # Check service status
    if command -v claude-control &> /dev/null; then
        if ! claude-control health >/dev/null 2>&1; then
            log_warn "MCP health check returned warnings"
            issues=$((issues + 1))
        fi
    fi

    if [ ${issues} -eq 0 ]; then
        log_success "System health check passed"
        return 0
    else
        log_error "Health check found ${issues} issue(s)"
        return 1
    fi
}

#===============================================================================
# Main Command Handler
#===============================================================================

show_usage() {
    cat << EOF
MCP Rollback & Recovery System

Usage: $(basename "${0}") <command> [options]

Commands:
    backup [name]           Create a new backup (optional custom name)
    list                    List all available backups
    restore <name>          Restore from specific backup
    rollback                Rollback to last known good state
    verify <name>           Verify backup integrity
    cleanup                 Remove old backups
    health                  Perform system health check

Examples:
    $(basename "${0}") backup
    $(basename "${0}") backup my_custom_backup
    $(basename "${0}") list
    $(basename "${0}") restore auto_20251002_120000
    $(basename "${0}") rollback
    $(basename "${0}") verify auto_20251002_120000
    $(basename "${0}") health

EOF
}

main() {
    # Create necessary directories
    mkdir -p "${BACKUP_ROOT}" "${CLAUDE_DIR}/logs"

    # Acquire lock
    acquire_lock || exit 1

    local command="${1:-}"

    case "${command}" in
        backup)
            create_backup "${2:-}"
            ;;

        list)
            list_backups
            ;;

        restore)
            if [ -z "${2:-}" ]; then
                log_error "Backup name required"
                show_usage
                exit 1
            fi
            restore_backup "${2}"
            ;;

        rollback)
            rollback_last_change
            ;;

        verify)
            if [ -z "${2:-}" ]; then
                log_error "Backup name required"
                show_usage
                exit 1
            fi

            local backup_dir="${BACKUP_ROOT}/${2}"
            if [ -f "${backup_dir}/.checksums.sha256" ]; then
                verify_checksums "${backup_dir}/.checksums.sha256" "${backup_dir}"
            else
                log_error "No checksums found for backup: ${2}"
                exit 1
            fi
            ;;

        cleanup)
            cleanup_old_backups
            ;;

        health)
            health_check
            ;;

        *)
            log_error "Unknown command: ${command}"
            show_usage
            exit 1
            ;;
    esac
}

main "${@}"
