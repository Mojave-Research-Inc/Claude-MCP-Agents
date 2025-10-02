#!/usr/bin/env python3
"""
MCP Health Check Endpoints
Comprehensive health monitoring API with detailed status reporting
Addresses CVSS 6.5 vulnerability - Missing Health Check Endpoint
"""

import os
import sys
import json
import time
import psutil
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from flask import Flask, jsonify, request
from functools import wraps

# Import authentication if available
try:
    from mcp_auth_system import require_api_key, require_permission
    AUTH_AVAILABLE = True
except ImportError:
    AUTH_AVAILABLE = False
    def require_api_key(f):
        return f
    def require_permission(perm):
        def decorator(f):
            return f
        return decorator

# Configuration
CLAUDE_DIR = Path.home() / ".claude"
PID_DIR = CLAUDE_DIR / "pids"
DATA_DIR = CLAUDE_DIR / "data"
LOG_DIR = CLAUDE_DIR / "logs"

# Health thresholds
CPU_WARNING_THRESHOLD = 70.0
CPU_CRITICAL_THRESHOLD = 85.0
MEMORY_WARNING_THRESHOLD = 75.0
MEMORY_CRITICAL_THRESHOLD = 90.0
DISK_WARNING_THRESHOLD = 80.0
DISK_CRITICAL_THRESHOLD = 90.0
UPTIME_WARNING_THRESHOLD = 3600  # 1 hour
DATABASE_SIZE_WARNING_MB = 1000
DATABASE_SIZE_CRITICAL_MB = 5000

# Service categories
CRITICAL_SERVICES = [
    "brain-comprehensive",
    "knowledge-manager",
    "checklist-sentinel",
    "claude-brain",
    "agent-orchestration"
]

OPTIONAL_SERVICES = [
    "context-intelligence",
    "resource-monitor",
    "repo-harvester",
    "security-architect"
]


@dataclass
class HealthStatus:
    """Overall health status"""
    status: str  # healthy, degraded, unhealthy
    timestamp: datetime
    uptime_seconds: int
    version: str
    checks: Dict[str, Any]
    warnings: List[str]
    errors: List[str]


@dataclass
class ServiceHealth:
    """Individual service health"""
    name: str
    status: str  # running, stopped, crashed
    pid: Optional[int]
    cpu_percent: float
    memory_mb: float
    uptime_seconds: int
    last_restart: Optional[datetime]
    restart_count: int


@dataclass
class DatabaseHealth:
    """Database health metrics"""
    name: str
    path: str
    size_mb: float
    status: str  # healthy, warning, critical, corrupted
    integrity_check: bool
    last_vacuum: Optional[datetime]
    connection_count: int


@dataclass
class SystemHealth:
    """System resource health"""
    cpu_percent: float
    cpu_count: int
    memory_percent: float
    memory_total_gb: float
    memory_available_gb: float
    disk_percent: float
    disk_total_gb: float
    disk_free_gb: float
    load_average: List[float]


class HealthMonitor:
    """Health monitoring service"""

    def __init__(self):
        self.start_time = datetime.now()
        self.version = "3.0.0-EDGE"

    def check_service(self, service_name: str) -> ServiceHealth:
        """Check health of individual service"""
        pid_file = PID_DIR / f"{service_name}.pid"

        service = ServiceHealth(
            name=service_name,
            status="stopped",
            pid=None,
            cpu_percent=0.0,
            memory_mb=0.0,
            uptime_seconds=0,
            last_restart=None,
            restart_count=0
        )

        # Check if PID file exists
        if not pid_file.exists():
            return service

        # Read PID
        try:
            with open(pid_file, 'r') as f:
                pid = int(f.read().strip())
                service.pid = pid
        except (ValueError, FileNotFoundError):
            return service

        # Check if process is running
        try:
            process = psutil.Process(pid)

            if process.is_running():
                service.status = "running"
                service.cpu_percent = process.cpu_percent(interval=0.1)
                service.memory_mb = process.memory_info().rss / 1024 / 1024
                service.uptime_seconds = int(time.time() - process.create_time())

                # Check restart count from health DB if available
                try:
                    health_db = CLAUDE_DIR / "health_monitor.db"
                    if health_db.exists():
                        conn = sqlite3.connect(str(health_db))
                        cursor = conn.execute("""
                            SELECT restart_count, last_restart
                            FROM server_status
                            WHERE name = ?
                            ORDER BY recorded_at DESC
                            LIMIT 1
                        """, (service_name,))

                        row = cursor.fetchone()
                        if row:
                            service.restart_count = row[0] or 0
                            if row[1]:
                                service.last_restart = datetime.fromisoformat(row[1])

                        conn.close()
                except Exception:
                    pass

            else:
                service.status = "crashed"

        except psutil.NoSuchProcess:
            service.status = "crashed"
        except psutil.AccessDenied:
            service.status = "unknown"

        return service

    def check_all_services(self) -> Dict[str, ServiceHealth]:
        """Check health of all services"""
        services = {}

        # Check critical services
        for service_name in CRITICAL_SERVICES:
            services[service_name] = self.check_service(service_name)

        # Check optional services
        for service_name in OPTIONAL_SERVICES:
            services[service_name] = self.check_service(service_name)

        # Check for any additional PID files
        if PID_DIR.exists():
            for pid_file in PID_DIR.glob("*.pid"):
                service_name = pid_file.stem
                if service_name not in services:
                    services[service_name] = self.check_service(service_name)

        return services

    def check_database(self, db_path: Path) -> DatabaseHealth:
        """Check health of individual database"""
        db_name = db_path.stem

        db_health = DatabaseHealth(
            name=db_name,
            path=str(db_path),
            size_mb=0.0,
            status="unknown",
            integrity_check=False,
            last_vacuum=None,
            connection_count=0
        )

        # Check if database exists
        if not db_path.exists():
            db_health.status = "missing"
            return db_health

        # Get size
        db_health.size_mb = db_path.stat().st_size / 1024 / 1024

        # Check size thresholds
        if db_health.size_mb > DATABASE_SIZE_CRITICAL_MB:
            db_health.status = "critical"
        elif db_health.size_mb > DATABASE_SIZE_WARNING_MB:
            db_health.status = "warning"
        else:
            db_health.status = "healthy"

        # Check integrity
        try:
            conn = sqlite3.connect(str(db_path), timeout=5)
            cursor = conn.execute("PRAGMA integrity_check;")
            result = cursor.fetchone()

            if result and result[0] == "ok":
                db_health.integrity_check = True
                if db_health.status == "unknown":
                    db_health.status = "healthy"
            else:
                db_health.status = "corrupted"
                db_health.integrity_check = False

            # Get connection count (approximate from wal file)
            wal_file = db_path.with_suffix('.db-wal')
            if wal_file.exists():
                db_health.connection_count = 1  # At least one connection

            conn.close()

        except sqlite3.DatabaseError:
            db_health.status = "corrupted"
        except Exception:
            pass

        return db_health

    def check_all_databases(self) -> Dict[str, DatabaseHealth]:
        """Check health of all databases"""
        databases = {}

        if DATA_DIR.exists():
            for db_path in DATA_DIR.glob("*.db"):
                db_name = db_path.stem
                databases[db_name] = self.check_database(db_path)

        return databases

    def check_system_resources(self) -> SystemHealth:
        """Check system resource health"""
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage(str(CLAUDE_DIR))
        load = psutil.getloadavg()

        return SystemHealth(
            cpu_percent=cpu_percent,
            cpu_count=psutil.cpu_count(),
            memory_percent=memory.percent,
            memory_total_gb=memory.total / 1024**3,
            memory_available_gb=memory.available / 1024**3,
            disk_percent=disk.percent,
            disk_total_gb=disk.total / 1024**3,
            disk_free_gb=disk.free / 1024**3,
            load_average=list(load)
        )

    def get_overall_health(self) -> HealthStatus:
        """Get overall system health status"""
        warnings = []
        errors = []
        checks = {}

        # Check services
        services = self.check_all_services()
        checks['services'] = {name: asdict(svc) for name, svc in services.items()}

        # Count service statuses
        critical_running = sum(
            1 for name in CRITICAL_SERVICES
            if name in services and services[name].status == "running"
        )
        critical_total = len(CRITICAL_SERVICES)

        if critical_running < critical_total:
            errors.append(f"Only {critical_running}/{critical_total} critical services running")

        # Check for crashed services
        crashed = [name for name, svc in services.items() if svc.status == "crashed"]
        if crashed:
            errors.append(f"Crashed services: {', '.join(crashed)}")

        # Check databases
        databases = self.check_all_databases()
        checks['databases'] = {name: asdict(db) for name, db in databases.items()}

        # Check for database issues
        corrupted = [name for name, db in databases.items() if db.status == "corrupted"]
        if corrupted:
            errors.append(f"Corrupted databases: {', '.join(corrupted)}")

        oversized = [name for name, db in databases.items() if db.status == "critical"]
        if oversized:
            warnings.append(f"Oversized databases: {', '.join(oversized)}")

        # Check system resources
        system = self.check_system_resources()
        checks['system'] = asdict(system)

        # Check thresholds
        if system.cpu_percent > CPU_CRITICAL_THRESHOLD:
            errors.append(f"CPU usage critical: {system.cpu_percent:.1f}%")
        elif system.cpu_percent > CPU_WARNING_THRESHOLD:
            warnings.append(f"CPU usage high: {system.cpu_percent:.1f}%")

        if system.memory_percent > MEMORY_CRITICAL_THRESHOLD:
            errors.append(f"Memory usage critical: {system.memory_percent:.1f}%")
        elif system.memory_percent > MEMORY_WARNING_THRESHOLD:
            warnings.append(f"Memory usage high: {system.memory_percent:.1f}%")

        if system.disk_percent > DISK_CRITICAL_THRESHOLD:
            errors.append(f"Disk usage critical: {system.disk_percent:.1f}%")
        elif system.disk_percent > DISK_WARNING_THRESHOLD:
            warnings.append(f"Disk usage high: {system.disk_percent:.1f}%")

        # Determine overall status
        if errors:
            status = "unhealthy"
        elif warnings:
            status = "degraded"
        else:
            status = "healthy"

        uptime = int((datetime.now() - self.start_time).total_seconds())

        return HealthStatus(
            status=status,
            timestamp=datetime.now(),
            uptime_seconds=uptime,
            version=self.version,
            checks=checks,
            warnings=warnings,
            errors=errors
        )


# Flask application
app = Flask(__name__)
monitor = HealthMonitor()


# Response formatter with security headers
def jsonify_secure(data, status=200):
    """Return JSON response with security headers"""
    response = jsonify(data)
    response.status_code = status

    # Security headers
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate'
    response.headers['Pragma'] = 'no-cache'

    return response


@app.route('/health', methods=['GET'])
@require_permission('read:health')
def health_check():
    """
    Main health check endpoint
    Returns overall system health status
    """
    health = monitor.get_overall_health()

    status_code = 200
    if health.status == "degraded":
        status_code = 200  # Still healthy, just warnings
    elif health.status == "unhealthy":
        status_code = 503  # Service unavailable

    return jsonify_secure(asdict(health), status_code)


@app.route('/health/live', methods=['GET'])
def liveness_probe():
    """
    Kubernetes-style liveness probe
    Returns 200 if application is alive (can accept requests)
    """
    return jsonify_secure({
        'status': 'alive',
        'timestamp': datetime.now().isoformat()
    })


@app.route('/health/ready', methods=['GET'])
@require_permission('read:health')
def readiness_probe():
    """
    Kubernetes-style readiness probe
    Returns 200 if application is ready to serve traffic
    """
    health = monitor.get_overall_health()

    # Check if critical services are running
    services = health.checks.get('services', {})
    critical_running = sum(
        1 for name in CRITICAL_SERVICES
        if name in services and services[name]['status'] == 'running'
    )

    ready = critical_running == len(CRITICAL_SERVICES) and health.status != "unhealthy"

    status_code = 200 if ready else 503

    return jsonify_secure({
        'status': 'ready' if ready else 'not_ready',
        'critical_services': f"{critical_running}/{len(CRITICAL_SERVICES)}",
        'overall_health': health.status,
        'timestamp': datetime.now().isoformat()
    }, status_code)


@app.route('/health/services', methods=['GET'])
@require_permission('read:health')
def services_health():
    """
    Detailed service health information
    Returns status of all MCP services
    """
    services = monitor.check_all_services()

    return jsonify_secure({
        'services': {name: asdict(svc) for name, svc in services.items()},
        'total': len(services),
        'running': sum(1 for svc in services.values() if svc.status == 'running'),
        'stopped': sum(1 for svc in services.values() if svc.status == 'stopped'),
        'crashed': sum(1 for svc in services.values() if svc.status == 'crashed'),
        'timestamp': datetime.now().isoformat()
    })


@app.route('/health/services/<service_name>', methods=['GET'])
@require_permission('read:health')
def service_health(service_name):
    """
    Individual service health
    Returns detailed status of specific service
    """
    service = monitor.check_service(service_name)

    if service.status == "stopped":
        status_code = 404
    elif service.status == "crashed":
        status_code = 503
    else:
        status_code = 200

    return jsonify_secure(asdict(service), status_code)


@app.route('/health/databases', methods=['GET'])
@require_permission('read:health')
def databases_health():
    """
    Database health information
    Returns status of all SQLite databases
    """
    databases = monitor.check_all_databases()

    return jsonify_secure({
        'databases': {name: asdict(db) for name, db in databases.items()},
        'total': len(databases),
        'healthy': sum(1 for db in databases.values() if db.status == 'healthy'),
        'warning': sum(1 for db in databases.values() if db.status == 'warning'),
        'critical': sum(1 for db in databases.values() if db.status == 'critical'),
        'corrupted': sum(1 for db in databases.values() if db.status == 'corrupted'),
        'timestamp': datetime.now().isoformat()
    })


@app.route('/health/system', methods=['GET'])
@require_permission('read:health')
def system_health():
    """
    System resource health
    Returns CPU, memory, disk usage
    """
    system = monitor.check_system_resources()

    return jsonify_secure(asdict(system))


@app.route('/health/metrics', methods=['GET'])
@require_permission('read:metrics')
def health_metrics():
    """
    Prometheus-compatible metrics endpoint
    Returns metrics in Prometheus exposition format
    """
    health = monitor.get_overall_health()

    metrics = []

    # Overall status (0=healthy, 1=degraded, 2=unhealthy)
    status_value = {'healthy': 0, 'degraded': 1, 'unhealthy': 2}.get(health.status, 2)
    metrics.append(f'mcp_health_status {status_value}')
    metrics.append(f'mcp_uptime_seconds {health.uptime_seconds}')

    # Service metrics
    services = health.checks.get('services', {})
    for name, svc in services.items():
        label = f'service="{name}"'
        status_val = 1 if svc['status'] == 'running' else 0
        metrics.append(f'mcp_service_up{{{label}}} {status_val}')

        if svc['status'] == 'running':
            metrics.append(f'mcp_service_cpu_percent{{{label}}} {svc["cpu_percent"]}')
            metrics.append(f'mcp_service_memory_mb{{{label}}} {svc["memory_mb"]}')
            metrics.append(f'mcp_service_uptime_seconds{{{label}}} {svc["uptime_seconds"]}')

    # System metrics
    system = health.checks.get('system', {})
    if system:
        metrics.append(f'mcp_system_cpu_percent {system["cpu_percent"]}')
        metrics.append(f'mcp_system_memory_percent {system["memory_percent"]}')
        metrics.append(f'mcp_system_disk_percent {system["disk_percent"]}')

    # Database metrics
    databases = health.checks.get('databases', {})
    for name, db in databases.items():
        label = f'database="{name}"'
        status_val = 1 if db['integrity_check'] else 0
        metrics.append(f'mcp_database_integrity{{{label}}} {status_val}')
        metrics.append(f'mcp_database_size_mb{{{label}}} {db["size_mb"]}')

    return '\n'.join(metrics) + '\n', 200, {'Content-Type': 'text/plain; charset=utf-8'}


@app.errorhandler(401)
def unauthorized(e):
    """Handle unauthorized access"""
    return jsonify_secure({
        'error': 'Unauthorized',
        'message': str(e.description) if hasattr(e, 'description') else 'Authentication required'
    }, 401)


@app.errorhandler(403)
def forbidden(e):
    """Handle forbidden access"""
    return jsonify_secure({
        'error': 'Forbidden',
        'message': str(e.description) if hasattr(e, 'description') else 'Insufficient permissions'
    }, 403)


@app.errorhandler(500)
def internal_error(e):
    """Handle internal server errors"""
    return jsonify_secure({
        'error': 'Internal Server Error',
        'message': 'An unexpected error occurred'
    }, 500)


def main():
    """Run health check server"""
    import argparse

    parser = argparse.ArgumentParser(description="MCP Health Check Server")
    parser.add_argument('--host', default='127.0.0.1', help='Host to bind to')
    parser.add_argument('--port', type=int, default=8080, help='Port to bind to')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')

    args = parser.parse_args()

    print(f"Starting MCP Health Check Server on {args.host}:{args.port}")
    print(f"Endpoints:")
    print(f"  GET /health           - Overall health status")
    print(f"  GET /health/live      - Liveness probe")
    print(f"  GET /health/ready     - Readiness probe")
    print(f"  GET /health/services  - All services status")
    print(f"  GET /health/databases - All databases status")
    print(f"  GET /health/system    - System resources")
    print(f"  GET /health/metrics   - Prometheus metrics")
    print()

    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()
