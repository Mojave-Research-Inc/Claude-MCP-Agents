#!/usr/bin/env bash
# Claude Code Services Control Script
# Manages background services for knowledge management and orchestration

set -euo pipefail

CLAUDE_DIR="$HOME/.claude"
SCRIPTS_DIR="$CLAUDE_DIR/scripts"
LOGS_DIR="$CLAUDE_DIR/logs"
PIDS_DIR="$CLAUDE_DIR/pids"

# Create necessary directories
mkdir -p "$LOGS_DIR" "$PIDS_DIR"

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Service definitions
declare -A SERVICES=(
    ["knowledge_monitor"]="python3 $SCRIPTS_DIR/knowledge_monitor.py"
    ["brain_sync"]="python3 $SCRIPTS_DIR/brain_sync.py"
)

# Functions
log_message() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

log_error() {
    echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1" >&2
}

log_warning() {
    echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

is_running() {
    local service=$1
    local pid_file="$PIDS_DIR/$service.pid"

    if [[ -f "$pid_file" ]]; then
        local pid=$(cat "$pid_file")
        if ps -p "$pid" > /dev/null 2>&1; then
            return 0
        fi
    fi
    return 1
}

start_service() {
    local service=$1

    if is_running "$service"; then
        log_warning "$service is already running (PID: $(cat "$PIDS_DIR/$service.pid"))"
        return 0
    fi

    if [[ ! ${SERVICES[$service]+isset} ]]; then
        log_error "Unknown service: $service"
        return 1
    fi

    local command="${SERVICES[$service]}"
    local log_file="$LOGS_DIR/$service.log"
    local pid_file="$PIDS_DIR/$service.pid"

    # Start service in background
    nohup $command >> "$log_file" 2>&1 &
    local pid=$!

    # Save PID
    echo "$pid" > "$pid_file"

    # Verify service started
    sleep 1
    if is_running "$service"; then
        log_message "Started $service (PID: $pid)"
    else
        log_error "Failed to start $service"
        rm -f "$pid_file"
        return 1
    fi
}

stop_service() {
    local service=$1
    local pid_file="$PIDS_DIR/$service.pid"

    if ! is_running "$service"; then
        log_warning "$service is not running"
        rm -f "$pid_file"
        return 0
    fi

    local pid=$(cat "$pid_file")

    # Try graceful shutdown
    kill "$pid" 2>/dev/null || true

    # Wait for process to stop
    local count=0
    while ps -p "$pid" > /dev/null 2>&1 && [[ $count -lt 10 ]]; do
        sleep 1
        count=$((count + 1))
    done

    # Force kill if still running
    if ps -p "$pid" > /dev/null 2>&1; then
        log_warning "Force stopping $service"
        kill -9 "$pid" 2>/dev/null || true
    fi

    rm -f "$pid_file"
    log_message "Stopped $service"
}

restart_service() {
    local service=$1
    stop_service "$service"
    sleep 1
    start_service "$service"
}

status_service() {
    local service=$1

    if is_running "$service"; then
        local pid=$(cat "$PIDS_DIR/$service.pid")
        echo -e "${GREEN}●${NC} $service is running (PID: $pid)"
    else
        echo -e "${RED}●${NC} $service is stopped"
    fi
}

status_all() {
    echo "Claude Code Services Status:"
    echo "============================"

    for service in "${!SERVICES[@]}"; do
        status_service "$service"
    done

    echo ""
    echo "Logs directory: $LOGS_DIR"
    echo "PIDs directory: $PIDS_DIR"
}

start_all() {
    log_message "Starting all services..."

    for service in "${!SERVICES[@]}"; do
        start_service "$service"
    done
}

stop_all() {
    log_message "Stopping all services..."

    for service in "${!SERVICES[@]}"; do
        stop_service "$service"
    done
}

restart_all() {
    log_message "Restarting all services..."
    stop_all
    sleep 2
    start_all
}

# Main script logic
main() {
    local command=${1:-status}
    local service=${2:-}

    case "$command" in
        start)
            if [[ -n "$service" ]]; then
                start_service "$service"
            else
                start_all
            fi
            ;;
        stop)
            if [[ -n "$service" ]]; then
                stop_service "$service"
            else
                stop_all
            fi
            ;;
        restart)
            if [[ -n "$service" ]]; then
                restart_service "$service"
            else
                restart_all
            fi
            ;;
        status)
            if [[ -n "$service" ]]; then
                status_service "$service"
            else
                status_all
            fi
            ;;
        logs)
            if [[ -n "$service" ]]; then
                tail -f "$LOGS_DIR/$service.log"
            else
                echo "Available logs:"
                ls -la "$LOGS_DIR/"
            fi
            ;;
        clean)
            log_message "Cleaning up stale PID files..."
            for pid_file in "$PIDS_DIR"/*.pid; do
                if [[ -f "$pid_file" ]]; then
                    local pid=$(cat "$pid_file")
                    if ! ps -p "$pid" > /dev/null 2>&1; then
                        rm -f "$pid_file"
                        log_message "Removed stale PID file: $(basename "$pid_file")"
                    fi
                fi
            done
            ;;
        *)
            echo "Usage: $0 {start|stop|restart|status|logs|clean} [service]"
            echo ""
            echo "Commands:"
            echo "  start [service]   - Start service(s)"
            echo "  stop [service]    - Stop service(s)"
            echo "  restart [service] - Restart service(s)"
            echo "  status [service]  - Show service(s) status"
            echo "  logs [service]    - Show service logs"
            echo "  clean            - Clean up stale PID files"
            echo ""
            echo "Available services:"
            for service in "${!SERVICES[@]}"; do
                echo "  - $service"
            done
            exit 1
            ;;
    esac
}

# Run main function
main "$@"