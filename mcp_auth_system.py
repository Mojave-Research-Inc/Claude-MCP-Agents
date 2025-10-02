#!/usr/bin/env python3
"""
MCP Authentication & Authorization System
Provides token-based authentication with role-based access control (RBAC)
Addresses CVSS 9.1 vulnerability - Unauthenticated API Access
"""

import os
import secrets
import hashlib
import hmac
import time
import json
import sqlite3
from typing import Optional, Dict, List, Set
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
from functools import wraps
from flask import Flask, request, jsonify, abort

# Configuration
CLAUDE_DIR = Path.home() / ".claude"
AUTH_DB = CLAUDE_DIR / "auth.db"
TOKEN_LENGTH = 32
TOKEN_PREFIX = "cmcp_"
HASH_ALGORITHM = "sha256"
TOKEN_EXPIRY_DAYS = 90
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_DURATION_MINUTES = 15

# Security headers
SECURITY_HEADERS = {
    'X-Content-Type-Options': 'nosniff',
    'X-Frame-Options': 'DENY',
    'X-XSS-Protection': '1; mode=block',
    'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
    'Content-Security-Policy': "default-src 'self'",
    'Referrer-Policy': 'strict-origin-when-cross-origin'
}


@dataclass
class APIKey:
    """Represents an API key with metadata"""
    key_id: str
    name: str
    key_hash: str
    role: str
    created_at: datetime
    expires_at: Optional[datetime]
    last_used: Optional[datetime]
    is_active: bool
    permissions: Set[str]


@dataclass
class AuditLog:
    """Audit log entry for authentication events"""
    timestamp: datetime
    key_id: Optional[str]
    action: str
    success: bool
    ip_address: str
    user_agent: str
    error_message: Optional[str]


class AuthDatabase:
    """SQLite database for authentication data"""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.conn = None
        self._initialize()

    def _initialize(self):
        """Initialize database schema"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row

        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS api_keys (
                key_id TEXT PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                key_hash TEXT NOT NULL,
                role TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP,
                last_used TIMESTAMP,
                is_active BOOLEAN DEFAULT 1,
                permissions TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                key_id TEXT,
                action TEXT NOT NULL,
                success BOOLEAN,
                ip_address TEXT,
                user_agent TEXT,
                error_message TEXT
            );

            CREATE TABLE IF NOT EXISTS rate_limits (
                key_id TEXT PRIMARY KEY,
                request_count INTEGER DEFAULT 0,
                window_start TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                failed_attempts INTEGER DEFAULT 0,
                locked_until TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS roles (
                role_name TEXT PRIMARY KEY,
                description TEXT,
                default_permissions TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp);
            CREATE INDEX IF NOT EXISTS idx_audit_key_id ON audit_log(key_id);
            CREATE INDEX IF NOT EXISTS idx_api_keys_name ON api_keys(name);
            CREATE INDEX IF NOT EXISTS idx_rate_limits_window ON rate_limits(window_start);
        """)

        # Initialize default roles
        self._initialize_roles()
        self.conn.commit()

    def _initialize_roles(self):
        """Initialize default RBAC roles"""
        default_roles = [
            ("admin", "Full system access", json.dumps([
                "read:*", "write:*", "delete:*", "admin:*"
            ])),
            ("operator", "Operational access", json.dumps([
                "read:*", "write:health", "write:metrics", "read:logs"
            ])),
            ("developer", "Development access", json.dumps([
                "read:*", "write:agents", "write:tools", "read:logs"
            ])),
            ("readonly", "Read-only access", json.dumps([
                "read:health", "read:metrics", "read:status"
            ]))
        ]

        for role_name, description, permissions in default_roles:
            self.conn.execute("""
                INSERT OR IGNORE INTO roles (role_name, description, default_permissions)
                VALUES (?, ?, ?)
            """, (role_name, description, permissions))

    def create_api_key(self, key: APIKey) -> bool:
        """Create new API key"""
        try:
            self.conn.execute("""
                INSERT INTO api_keys (
                    key_id, name, key_hash, role, expires_at, permissions
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                key.key_id,
                key.name,
                key.key_hash,
                key.role,
                key.expires_at,
                json.dumps(list(key.permissions))
            ))
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def get_api_key(self, key_id: str) -> Optional[APIKey]:
        """Retrieve API key by ID"""
        cursor = self.conn.execute("""
            SELECT * FROM api_keys WHERE key_id = ? AND is_active = 1
        """, (key_id,))

        row = cursor.fetchone()
        if not row:
            return None

        return APIKey(
            key_id=row['key_id'],
            name=row['name'],
            key_hash=row['key_hash'],
            role=row['role'],
            created_at=datetime.fromisoformat(row['created_at']),
            expires_at=datetime.fromisoformat(row['expires_at']) if row['expires_at'] else None,
            last_used=datetime.fromisoformat(row['last_used']) if row['last_used'] else None,
            is_active=bool(row['is_active']),
            permissions=set(json.loads(row['permissions']))
        )

    def update_last_used(self, key_id: str):
        """Update last used timestamp"""
        self.conn.execute("""
            UPDATE api_keys SET last_used = CURRENT_TIMESTAMP WHERE key_id = ?
        """, (key_id,))
        self.conn.commit()

    def log_audit_event(self, event: AuditLog):
        """Log authentication event"""
        self.conn.execute("""
            INSERT INTO audit_log (
                key_id, action, success, ip_address, user_agent, error_message
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (
            event.key_id,
            event.action,
            event.success,
            event.ip_address,
            event.user_agent,
            event.error_message
        ))
        self.conn.commit()

    def check_rate_limit(self, key_id: str, max_requests: int, window_seconds: int) -> bool:
        """Check if key is within rate limits"""
        cursor = self.conn.execute("""
            SELECT request_count, window_start, locked_until
            FROM rate_limits WHERE key_id = ?
        """, (key_id,))

        row = cursor.fetchone()
        now = datetime.now()

        # Check if locked out
        if row and row['locked_until']:
            locked_until = datetime.fromisoformat(row['locked_until'])
            if now < locked_until:
                return False

        # Check rate limit
        if row:
            window_start = datetime.fromisoformat(row['window_start'])
            elapsed = (now - window_start).total_seconds()

            if elapsed < window_seconds:
                if row['request_count'] >= max_requests:
                    return False

                # Increment counter
                self.conn.execute("""
                    UPDATE rate_limits SET request_count = request_count + 1
                    WHERE key_id = ?
                """, (key_id,))
            else:
                # Reset window
                self.conn.execute("""
                    UPDATE rate_limits SET request_count = 1, window_start = CURRENT_TIMESTAMP
                    WHERE key_id = ?
                """, (key_id,))
        else:
            # Create new rate limit entry
            self.conn.execute("""
                INSERT INTO rate_limits (key_id, request_count) VALUES (?, 1)
            """, (key_id,))

        self.conn.commit()
        return True

    def record_failed_attempt(self, key_id: str):
        """Record failed authentication attempt"""
        cursor = self.conn.execute("""
            SELECT failed_attempts FROM rate_limits WHERE key_id = ?
        """, (key_id,))

        row = cursor.fetchone()
        failed_attempts = (row['failed_attempts'] if row else 0) + 1

        locked_until = None
        if failed_attempts >= MAX_FAILED_ATTEMPTS:
            locked_until = datetime.now() + timedelta(minutes=LOCKOUT_DURATION_MINUTES)

        if row:
            self.conn.execute("""
                UPDATE rate_limits
                SET failed_attempts = ?, locked_until = ?
                WHERE key_id = ?
            """, (failed_attempts, locked_until, key_id))
        else:
            self.conn.execute("""
                INSERT INTO rate_limits (key_id, failed_attempts, locked_until)
                VALUES (?, ?, ?)
            """, (key_id, failed_attempts, locked_until))

        self.conn.commit()

    def reset_failed_attempts(self, key_id: str):
        """Reset failed attempts counter"""
        self.conn.execute("""
            UPDATE rate_limits SET failed_attempts = 0, locked_until = NULL
            WHERE key_id = ?
        """, (key_id,))
        self.conn.commit()


class APIKeyAuth:
    """API key authentication manager"""

    def __init__(self, db_path: Path = AUTH_DB):
        self.db = AuthDatabase(db_path)

    def generate_key(self, name: str, role: str, expires_days: Optional[int] = TOKEN_EXPIRY_DAYS) -> str:
        """Generate new API key"""
        # Generate secure random key
        key = f"{TOKEN_PREFIX}{secrets.token_urlsafe(TOKEN_LENGTH)}"
        key_id = hashlib.sha256(key.encode()).hexdigest()[:16]

        # Hash key for storage
        key_hash = self._hash_key(key)

        # Get role permissions
        cursor = self.db.conn.execute("""
            SELECT default_permissions FROM roles WHERE role_name = ?
        """, (role,))

        row = cursor.fetchone()
        if not row:
            raise ValueError(f"Invalid role: {role}")

        permissions = set(json.loads(row['default_permissions']))

        # Create API key object
        api_key = APIKey(
            key_id=key_id,
            name=name,
            key_hash=key_hash,
            role=role,
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(days=expires_days) if expires_days else None,
            last_used=None,
            is_active=True,
            permissions=permissions
        )

        if not self.db.create_api_key(api_key):
            raise ValueError(f"API key with name '{name}' already exists")

        return key

    def _hash_key(self, key: str) -> str:
        """Hash API key using PBKDF2"""
        salt = hashlib.sha256(key.encode()).digest()
        return hashlib.pbkdf2_hmac('sha256', key.encode(), salt, 100000).hex()

    def verify_key(self, provided_key: str) -> Optional[APIKey]:
        """Verify API key and return key object if valid"""
        if not provided_key or not provided_key.startswith(TOKEN_PREFIX):
            return None

        # Get key ID
        key_id = hashlib.sha256(provided_key.encode()).hexdigest()[:16]

        # Check rate limit
        if not self.db.check_rate_limit(key_id, max_requests=1000, window_seconds=3600):
            self.db.log_audit_event(AuditLog(
                timestamp=datetime.now(),
                key_id=key_id,
                action="verify_key",
                success=False,
                ip_address=request.remote_addr if request else "unknown",
                user_agent=request.headers.get('User-Agent', 'unknown') if request else "unknown",
                error_message="Rate limit exceeded"
            ))
            return None

        # Retrieve key
        api_key = self.db.get_api_key(key_id)
        if not api_key:
            self.db.record_failed_attempt(key_id)
            return None

        # Verify hash
        provided_hash = self._hash_key(provided_key)
        if not hmac.compare_digest(provided_hash, api_key.key_hash):
            self.db.record_failed_attempt(key_id)
            self.db.log_audit_event(AuditLog(
                timestamp=datetime.now(),
                key_id=key_id,
                action="verify_key",
                success=False,
                ip_address=request.remote_addr if request else "unknown",
                user_agent=request.headers.get('User-Agent', 'unknown') if request else "unknown",
                error_message="Invalid key"
            ))
            return None

        # Check expiry
        if api_key.expires_at and datetime.now() > api_key.expires_at:
            self.db.log_audit_event(AuditLog(
                timestamp=datetime.now(),
                key_id=key_id,
                action="verify_key",
                success=False,
                ip_address=request.remote_addr if request else "unknown",
                user_agent=request.headers.get('User-Agent', 'unknown') if request else "unknown",
                error_message="Key expired"
            ))
            return None

        # Reset failed attempts and update last used
        self.db.reset_failed_attempts(key_id)
        self.db.update_last_used(key_id)

        # Log successful authentication
        self.db.log_audit_event(AuditLog(
            timestamp=datetime.now(),
            key_id=key_id,
            action="verify_key",
            success=True,
            ip_address=request.remote_addr if request else "unknown",
            user_agent=request.headers.get('User-Agent', 'unknown') if request else "unknown",
            error_message=None
        ))

        return api_key

    def has_permission(self, api_key: APIKey, required_permission: str) -> bool:
        """Check if key has required permission"""
        # Check for wildcard permissions
        if "admin:*" in api_key.permissions:
            return True

        # Parse permission
        action, resource = required_permission.split(":", 1)

        # Check exact match
        if required_permission in api_key.permissions:
            return True

        # Check wildcard matches
        if f"{action}:*" in api_key.permissions:
            return True

        if f"*:{resource}" in api_key.permissions:
            return True

        return False


# Flask decorators for authentication
def require_api_key(f):
    """Decorator to require API key authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Extract token from header
        auth_header = request.headers.get('Authorization', '')

        if not auth_header.startswith('Bearer '):
            abort(401, description="Missing or invalid Authorization header")

        token = auth_header[7:]  # Remove 'Bearer ' prefix

        # Verify token
        auth = APIKeyAuth()
        api_key = auth.verify_key(token)

        if not api_key:
            abort(401, description="Invalid or expired API key")

        # Add key to request context
        request.api_key = api_key

        # Add security headers
        response = f(*args, **kwargs)
        if hasattr(response, 'headers'):
            for header, value in SECURITY_HEADERS.items():
                response.headers[header] = value

        return response

    return decorated_function


def require_permission(permission: str):
    """Decorator to require specific permission"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not hasattr(request, 'api_key'):
                abort(401, description="Authentication required")

            auth = APIKeyAuth()
            if not auth.has_permission(request.api_key, permission):
                abort(403, description=f"Missing required permission: {permission}")

            return f(*args, **kwargs)

        return decorated_function
    return decorator


# CLI tool for key management
def main():
    """CLI for managing API keys"""
    import argparse

    parser = argparse.ArgumentParser(description="MCP API Key Management")
    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # Generate key
    gen_parser = subparsers.add_parser('generate', help='Generate new API key')
    gen_parser.add_argument('name', help='Key name')
    gen_parser.add_argument('--role', default='readonly', choices=['admin', 'operator', 'developer', 'readonly'])
    gen_parser.add_argument('--expires', type=int, default=90, help='Expiry in days (0 for no expiry)')

    # List keys
    subparsers.add_parser('list', help='List all API keys')

    # Revoke key
    revoke_parser = subparsers.add_parser('revoke', help='Revoke API key')
    revoke_parser.add_argument('name', help='Key name to revoke')

    # Audit log
    audit_parser = subparsers.add_parser('audit', help='View audit log')
    audit_parser.add_argument('--limit', type=int, default=50, help='Number of entries')

    args = parser.parse_args()

    auth = APIKeyAuth()

    if args.command == 'generate':
        try:
            expires = args.expires if args.expires > 0 else None
            key = auth.generate_key(args.name, args.role, expires)
            print(f"\n✅ API Key Generated Successfully!")
            print(f"Name: {args.name}")
            print(f"Role: {args.role}")
            print(f"Key: {key}")
            print(f"\n⚠️  IMPORTANT: Save this key securely. It will not be shown again.")
            print(f"Add to requests: Authorization: Bearer {key}\n")
        except Exception as e:
            print(f"❌ Error: {e}")

    elif args.command == 'list':
        cursor = auth.db.conn.execute("""
            SELECT name, role, created_at, last_used, is_active, expires_at
            FROM api_keys ORDER BY created_at DESC
        """)

        print("\n📋 API Keys:")
        print(f"{'Name':<20} {'Role':<12} {'Created':<20} {'Last Used':<20} {'Status':<10}")
        print("=" * 90)

        for row in cursor.fetchall():
            status = "✅ Active" if row['is_active'] else "❌ Revoked"
            last_used = row['last_used'][:19] if row['last_used'] else "Never"
            created = row['created_at'][:19]
            print(f"{row['name']:<20} {row['role']:<12} {created:<20} {last_used:<20} {status:<10}")

        print()

    elif args.command == 'revoke':
        cursor = auth.db.conn.execute("""
            UPDATE api_keys SET is_active = 0 WHERE name = ?
        """, (args.name,))
        auth.db.conn.commit()

        if cursor.rowcount > 0:
            print(f"✅ API key '{args.name}' has been revoked")
        else:
            print(f"❌ API key '{args.name}' not found")

    elif args.command == 'audit':
        cursor = auth.db.conn.execute("""
            SELECT timestamp, key_id, action, success, ip_address, error_message
            FROM audit_log ORDER BY timestamp DESC LIMIT ?
        """, (args.limit,))

        print("\n📊 Audit Log:")
        print(f"{'Timestamp':<20} {'Key ID':<18} {'Action':<15} {'Success':<10} {'IP':<15} {'Error'}")
        print("=" * 100)

        for row in cursor.fetchall():
            timestamp = row['timestamp'][:19]
            key_id = (row['key_id'] or "N/A")[:16]
            success = "✅" if row['success'] else "❌"
            error = row['error_message'] or ""
            print(f"{timestamp:<20} {key_id:<18} {row['action']:<15} {success:<10} {row['ip_address']:<15} {error}")

        print()

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
