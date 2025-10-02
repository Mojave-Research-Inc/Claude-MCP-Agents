#!/usr/bin/env python3
"""
MCP Secrets Management System
Secure storage using system keyring with encryption at rest
Addresses CVSS 8.8 vulnerability - Plaintext Secret Storage
"""

import os
import json
import keyring
import hashlib
import base64
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2
from cryptography.hazmat.backends import default_backend

# Configuration
CLAUDE_DIR = Path.home() / ".claude"
SERVICE_NAME = "claude-mcp"
SECRETS_INDEX = CLAUDE_DIR / ".secrets_index.json"
BACKUP_DIR = CLAUDE_DIR / "backups" / "secrets"

# Secret categories
CATEGORY_API_KEYS = "api_keys"
CATEGORY_DB_CREDS = "database_credentials"
CATEGORY_SSH_KEYS = "ssh_keys"
CATEGORY_CERTIFICATES = "certificates"
CATEGORY_TOKENS = "tokens"


class SecretMetadata:
    """Metadata for a stored secret"""

    def __init__(
        self,
        key: str,
        category: str,
        description: str = "",
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
        rotation_days: Optional[int] = None
    ):
        self.key = key
        self.category = category
        self.description = description
        self.created_at = created_at or datetime.now()
        self.updated_at = updated_at or datetime.now()
        self.rotation_days = rotation_days

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'key': self.key,
            'category': self.category,
            'description': self.description,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'rotation_days': self.rotation_days
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'SecretMetadata':
        """Create from dictionary"""
        return SecretMetadata(
            key=data['key'],
            category=data['category'],
            description=data.get('description', ''),
            created_at=datetime.fromisoformat(data['created_at']),
            updated_at=datetime.fromisoformat(data['updated_at']),
            rotation_days=data.get('rotation_days')
        )


class SecretsManager:
    """
    Secure secrets management using system keyring
    Provides encryption at rest and secure retrieval
    """

    def __init__(self, service_name: str = SERVICE_NAME):
        self.service_name = service_name
        self.index_file = SECRETS_INDEX
        self.backup_dir = BACKUP_DIR
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self._load_index()

    def _load_index(self):
        """Load secrets index from disk"""
        if self.index_file.exists():
            with open(self.index_file, 'r') as f:
                data = json.load(f)
                self.index = {
                    k: SecretMetadata.from_dict(v)
                    for k, v in data.items()
                }
        else:
            self.index = {}

    def _save_index(self):
        """Save secrets index to disk"""
        self.index_file.parent.mkdir(parents=True, exist_ok=True)
        data = {k: v.to_dict() for k, v in self.index.items()}

        with open(self.index_file, 'w') as f:
            json.dump(data, f, indent=2)

        # Secure permissions (owner read/write only)
        os.chmod(self.index_file, 0o600)

    def _generate_key_name(self, key: str, category: str) -> str:
        """Generate unique key name for keyring"""
        return f"{category}:{key}"

    def store_secret(
        self,
        key: str,
        value: str,
        category: str = CATEGORY_API_KEYS,
        description: str = "",
        rotation_days: Optional[int] = None
    ) -> bool:
        """
        Store secret in system keyring

        Args:
            key: Secret identifier
            value: Secret value
            category: Secret category
            description: Human-readable description
            rotation_days: Days until rotation required

        Returns:
            True if stored successfully
        """
        try:
            # Generate keyring key name
            keyring_key = self._generate_key_name(key, category)

            # Store in system keyring
            keyring.set_password(self.service_name, keyring_key, value)

            # Update index
            self.index[key] = SecretMetadata(
                key=key,
                category=category,
                description=description,
                rotation_days=rotation_days
            )

            self._save_index()
            return True

        except Exception as e:
            print(f"Error storing secret: {e}")
            return False

    def get_secret(self, key: str, category: str = CATEGORY_API_KEYS) -> Optional[str]:
        """
        Retrieve secret from system keyring

        Args:
            key: Secret identifier
            category: Secret category

        Returns:
            Secret value or None if not found
        """
        try:
            # Check index
            if key not in self.index:
                return None

            # Check category matches
            if self.index[key].category != category:
                return None

            # Retrieve from keyring
            keyring_key = self._generate_key_name(key, category)
            value = keyring.get_password(self.service_name, keyring_key)

            return value

        except Exception as e:
            print(f"Error retrieving secret: {e}")
            return None

    def delete_secret(self, key: str) -> bool:
        """
        Delete secret from system keyring

        Args:
            key: Secret identifier

        Returns:
            True if deleted successfully
        """
        try:
            # Check if exists
            if key not in self.index:
                return False

            # Get category
            category = self.index[key].category
            keyring_key = self._generate_key_name(key, category)

            # Delete from keyring
            try:
                keyring.delete_password(self.service_name, keyring_key)
            except keyring.errors.PasswordDeleteError:
                pass  # Already deleted

            # Remove from index
            del self.index[key]
            self._save_index()

            return True

        except Exception as e:
            print(f"Error deleting secret: {e}")
            return False

    def list_secrets(self, category: Optional[str] = None) -> List[SecretMetadata]:
        """
        List all secrets (metadata only)

        Args:
            category: Filter by category (optional)

        Returns:
            List of secret metadata
        """
        secrets = list(self.index.values())

        if category:
            secrets = [s for s in secrets if s.category == category]

        return sorted(secrets, key=lambda s: s.created_at)

    def rotate_secret(self, key: str, new_value: str) -> bool:
        """
        Rotate secret with new value

        Args:
            key: Secret identifier
            new_value: New secret value

        Returns:
            True if rotated successfully
        """
        if key not in self.index:
            return False

        metadata = self.index[key]

        # Store new value
        success = self.store_secret(
            key=key,
            value=new_value,
            category=metadata.category,
            description=metadata.description,
            rotation_days=metadata.rotation_days
        )

        if success:
            # Update timestamp
            metadata.updated_at = datetime.now()
            self._save_index()

        return success

    def check_rotation_needed(self) -> List[SecretMetadata]:
        """
        Check which secrets need rotation

        Returns:
            List of secrets requiring rotation
        """
        needs_rotation = []
        now = datetime.now()

        for metadata in self.index.values():
            if metadata.rotation_days:
                days_since_update = (now - metadata.updated_at).days
                if days_since_update >= metadata.rotation_days:
                    needs_rotation.append(metadata)

        return needs_rotation

    def export_secrets(self, output_path: Path, encryption_password: str) -> bool:
        """
        Export secrets to encrypted backup file

        Args:
            output_path: Path to backup file
            encryption_password: Password for encryption

        Returns:
            True if exported successfully
        """
        try:
            # Collect all secrets
            secrets_data = {}

            for key, metadata in self.index.items():
                value = self.get_secret(key, metadata.category)
                if value:
                    secrets_data[key] = {
                        'value': value,
                        'metadata': metadata.to_dict()
                    }

            # Serialize to JSON
            json_data = json.dumps(secrets_data, indent=2)

            # Encrypt with password
            encrypted_data = self._encrypt_data(json_data.encode(), encryption_password)

            # Write to file
            with open(output_path, 'wb') as f:
                f.write(encrypted_data)

            os.chmod(output_path, 0o600)
            return True

        except Exception as e:
            print(f"Error exporting secrets: {e}")
            return False

    def import_secrets(self, input_path: Path, encryption_password: str) -> bool:
        """
        Import secrets from encrypted backup file

        Args:
            input_path: Path to backup file
            encryption_password: Password for decryption

        Returns:
            True if imported successfully
        """
        try:
            # Read encrypted file
            with open(input_path, 'rb') as f:
                encrypted_data = f.read()

            # Decrypt
            json_data = self._decrypt_data(encrypted_data, encryption_password)

            # Parse JSON
            secrets_data = json.loads(json_data.decode())

            # Store each secret
            for key, data in secrets_data.items():
                metadata_dict = data['metadata']
                self.store_secret(
                    key=key,
                    value=data['value'],
                    category=metadata_dict['category'],
                    description=metadata_dict.get('description', ''),
                    rotation_days=metadata_dict.get('rotation_days')
                )

            return True

        except Exception as e:
            print(f"Error importing secrets: {e}")
            return False

    def _encrypt_data(self, data: bytes, password: str) -> bytes:
        """Encrypt data using password-derived key"""
        # Derive key from password
        salt = os.urandom(16)
        kdf = PBKDF2(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
            backend=default_backend()
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))

        # Encrypt
        fernet = Fernet(key)
        encrypted = fernet.encrypt(data)

        # Prepend salt
        return salt + encrypted

    def _decrypt_data(self, encrypted_data: bytes, password: str) -> bytes:
        """Decrypt data using password-derived key"""
        # Extract salt
        salt = encrypted_data[:16]
        encrypted = encrypted_data[16:]

        # Derive key from password
        kdf = PBKDF2(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
            backend=default_backend()
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))

        # Decrypt
        fernet = Fernet(key)
        return fernet.decrypt(encrypted)

    def migrate_from_plaintext(self, config_path: Path) -> Dict[str, List[str]]:
        """
        Migrate secrets from plaintext configuration file to keyring

        Args:
            config_path: Path to plaintext config file (.mcp.json or .env)

        Returns:
            Dictionary with 'migrated' and 'failed' secret keys
        """
        migrated = []
        failed = []

        try:
            # Detect file type
            if config_path.suffix == '.json':
                migrated, failed = self._migrate_from_json(config_path)
            elif config_path.suffix == '.env' or config_path.name.startswith('.env'):
                migrated, failed = self._migrate_from_env(config_path)
            else:
                print(f"Unsupported file type: {config_path.suffix}")
                return {'migrated': [], 'failed': []}

            # Backup original file
            if migrated:
                backup_path = self.backup_dir / f"{config_path.name}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                backup_path.parent.mkdir(parents=True, exist_ok=True)

                import shutil
                shutil.copy2(config_path, backup_path)
                print(f"✅ Original file backed up to: {backup_path}")

        except Exception as e:
            print(f"Error during migration: {e}")
            failed.append(str(config_path))

        return {'migrated': migrated, 'failed': failed}

    def _migrate_from_json(self, json_path: Path) -> tuple:
        """Migrate secrets from JSON config"""
        migrated = []
        failed = []

        with open(json_path, 'r') as f:
            config = json.load(f)

        # Common secret patterns
        secret_patterns = [
            'api_key', 'apiKey', 'apikey', 'API_KEY',
            'secret', 'SECRET', 'password', 'PASSWORD',
            'token', 'TOKEN', 'auth', 'AUTH'
        ]

        def extract_secrets(obj, path=""):
            """Recursively extract secrets from nested JSON"""
            if isinstance(obj, dict):
                for key, value in obj.items():
                    current_path = f"{path}.{key}" if path else key

                    # Check if key indicates a secret
                    is_secret = any(pattern in key.lower() for pattern in secret_patterns)

                    if is_secret and isinstance(value, str) and value and value != "***MIGRATED***":
                        # Store in keyring
                        secret_key = current_path.replace('.', '_')
                        if self.store_secret(
                            key=secret_key,
                            value=value,
                            category=CATEGORY_API_KEYS,
                            description=f"Migrated from {json_path.name}: {current_path}"
                        ):
                            migrated.append(secret_key)
                            # Replace in config
                            obj[key] = "***MIGRATED_TO_KEYRING***"
                        else:
                            failed.append(secret_key)
                    elif isinstance(value, (dict, list)):
                        extract_secrets(value, current_path)

            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    extract_secrets(item, f"{path}[{i}]")

        extract_secrets(config)

        # Write updated config
        if migrated:
            with open(json_path, 'w') as f:
                json.dump(config, f, indent=2)

        return migrated, failed

    def _migrate_from_env(self, env_path: Path) -> tuple:
        """Migrate secrets from .env file"""
        migrated = []
        failed = []

        with open(env_path, 'r') as f:
            lines = f.readlines()

        updated_lines = []
        secret_patterns = [
            'API_KEY', 'SECRET', 'PASSWORD', 'TOKEN', 'AUTH', 'CREDENTIAL'
        ]

        for line in lines:
            # Skip comments and empty lines
            if line.strip().startswith('#') or not line.strip():
                updated_lines.append(line)
                continue

            # Parse key=value
            if '=' in line:
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")

                # Check if secret
                is_secret = any(pattern in key.upper() for pattern in secret_patterns)

                if is_secret and value and value != "***MIGRATED***":
                    # Store in keyring
                    if self.store_secret(
                        key=key,
                        value=value,
                        category=CATEGORY_API_KEYS,
                        description=f"Migrated from {env_path.name}"
                    ):
                        migrated.append(key)
                        updated_lines.append(f"{key}=***MIGRATED_TO_KEYRING***\n")
                    else:
                        failed.append(key)
                        updated_lines.append(line)
                else:
                    updated_lines.append(line)
            else:
                updated_lines.append(line)

        # Write updated file
        if migrated:
            with open(env_path, 'w') as f:
                f.writelines(updated_lines)

        return migrated, failed


# CLI interface
def main():
    """CLI for secrets management"""
    import argparse

    parser = argparse.ArgumentParser(description="MCP Secrets Manager")
    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # Store secret
    store_parser = subparsers.add_parser('store', help='Store a secret')
    store_parser.add_argument('key', help='Secret key')
    store_parser.add_argument('value', help='Secret value')
    store_parser.add_argument('--category', default=CATEGORY_API_KEYS, help='Secret category')
    store_parser.add_argument('--description', default='', help='Description')
    store_parser.add_argument('--rotation-days', type=int, help='Days until rotation')

    # Get secret
    get_parser = subparsers.add_parser('get', help='Retrieve a secret')
    get_parser.add_argument('key', help='Secret key')
    get_parser.add_argument('--category', default=CATEGORY_API_KEYS, help='Secret category')

    # Delete secret
    delete_parser = subparsers.add_parser('delete', help='Delete a secret')
    delete_parser.add_argument('key', help='Secret key')

    # List secrets
    list_parser = subparsers.add_parser('list', help='List all secrets')
    list_parser.add_argument('--category', help='Filter by category')

    # Rotate secret
    rotate_parser = subparsers.add_parser('rotate', help='Rotate a secret')
    rotate_parser.add_argument('key', help='Secret key')
    rotate_parser.add_argument('new_value', help='New secret value')

    # Check rotation
    subparsers.add_parser('check-rotation', help='Check secrets needing rotation')

    # Export
    export_parser = subparsers.add_parser('export', help='Export secrets to encrypted file')
    export_parser.add_argument('output', type=Path, help='Output file path')
    export_parser.add_argument('--password', required=True, help='Encryption password')

    # Import
    import_parser = subparsers.add_parser('import', help='Import secrets from encrypted file')
    import_parser.add_argument('input', type=Path, help='Input file path')
    import_parser.add_argument('--password', required=True, help='Decryption password')

    # Migrate
    migrate_parser = subparsers.add_parser('migrate', help='Migrate from plaintext config')
    migrate_parser.add_argument('config', type=Path, help='Config file to migrate')

    args = parser.parse_args()

    manager = SecretsManager()

    if args.command == 'store':
        if manager.store_secret(
            args.key,
            args.value,
            args.category,
            args.description,
            args.rotation_days
        ):
            print(f"✅ Secret '{args.key}' stored successfully")
        else:
            print(f"❌ Failed to store secret '{args.key}'")

    elif args.command == 'get':
        value = manager.get_secret(args.key, args.category)
        if value:
            print(value)
        else:
            print(f"❌ Secret '{args.key}' not found")

    elif args.command == 'delete':
        if manager.delete_secret(args.key):
            print(f"✅ Secret '{args.key}' deleted successfully")
        else:
            print(f"❌ Failed to delete secret '{args.key}'")

    elif args.command == 'list':
        secrets = manager.list_secrets(args.category)

        print("\n🔐 Stored Secrets:")
        print(f"{'Key':<30} {'Category':<20} {'Description':<40} {'Updated':<20}")
        print("=" * 120)

        for secret in secrets:
            print(f"{secret.key:<30} {secret.category:<20} {secret.description:<40} {secret.updated_at.strftime('%Y-%m-%d %H:%M'):<20}")

        print(f"\nTotal: {len(secrets)} secrets\n")

    elif args.command == 'rotate':
        if manager.rotate_secret(args.key, args.new_value):
            print(f"✅ Secret '{args.key}' rotated successfully")
        else:
            print(f"❌ Failed to rotate secret '{args.key}'")

    elif args.command == 'check-rotation':
        needs_rotation = manager.check_rotation_needed()

        if needs_rotation:
            print("\n⚠️  Secrets needing rotation:")
            for secret in needs_rotation:
                days_old = (datetime.now() - secret.updated_at).days
                print(f"  • {secret.key} ({days_old} days old, rotation due every {secret.rotation_days} days)")
            print()
        else:
            print("✅ All secrets are up to date")

    elif args.command == 'export':
        if manager.export_secrets(args.output, args.password):
            print(f"✅ Secrets exported to {args.output}")
        else:
            print(f"❌ Failed to export secrets")

    elif args.command == 'import':
        if manager.import_secrets(args.input, args.password):
            print(f"✅ Secrets imported from {args.input}")
        else:
            print(f"❌ Failed to import secrets")

    elif args.command == 'migrate':
        result = manager.migrate_from_plaintext(args.config)

        print("\n🔄 Migration Results:")
        print(f"✅ Migrated: {len(result['migrated'])} secrets")
        if result['migrated']:
            for key in result['migrated']:
                print(f"  • {key}")

        if result['failed']:
            print(f"\n❌ Failed: {len(result['failed'])} secrets")
            for key in result['failed']:
                print(f"  • {key}")

        print()

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
