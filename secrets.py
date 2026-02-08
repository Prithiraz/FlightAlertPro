import os
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass

try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent.parent / '.env'
    load_dotenv(env_path)
except ImportError:
    env_path = Path(__file__).parent.parent.parent / '.env'
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()

@dataclass
class SecretStatus:
    name: str
    exists: bool
    value: Optional[str] = None
    required: bool = True

class SecretsManager:
    REQUIRED_SECRETS = [
        'RAPIDAPI_KEY',
        'FLIGHTAPI_KEY',
        'DUFFEL_API_KEY',
        'OPENAI_API_KEY',
        'YCLOUD_API_KEY',
        'WABA_ACCESS_TOKEN',
        'WABA_BUSINESS_ID',
        'STRIPE_SECRET_KEY',
        'STRIPE_PUBLISHABLE_KEY',
        'STRIPE_WEBHOOK_KEY',
        'PRO_PLAN_PRICE_ID',
        'ELITE_PLAN_PRICE_ID',
        'BUSINESS_PLAN_PRICE_ID',
        'GMAIL_USER',
        'GMAIL_APP_PASSWORD',
        'FRANKFURTER_API_URL',
        'VITE_SUPABASE_URL',
        'VITE_SUPABASE_ANON_KEY',
    ]

    OPTIONAL_SECRETS = [
        'WABA_PHONE_NUMBER_ID',
        'TELEGRAM_BOT_TOKEN',
        'REDIS_URL',
        'SENTRY_DSN',
        'DATABASE_URL',
    ]

    def __init__(self):
        self.secrets: Dict[str, SecretStatus] = {}
        self._load_secrets()

    def _load_secrets(self):
        for secret_name in self.REQUIRED_SECRETS:
            value = os.getenv(secret_name)
            self.secrets[secret_name] = SecretStatus(
                name=secret_name,
                exists=value is not None and value != '',
                value=value,
                required=True
            )

        for secret_name in self.OPTIONAL_SECRETS:
            value = os.getenv(secret_name)
            self.secrets[secret_name] = SecretStatus(
                name=secret_name,
                exists=value is not None and value != '',
                value=value,
                required=False
            )

    def verify_all(self) -> tuple[bool, List[str]]:
        missing = []
        for name, status in self.secrets.items():
            if name == 'WABA_PHONE_NUMBER_ID':
                continue
            if status.required and not status.exists:
                missing.append(name)

        return len(missing) == 0, missing

    def get(self, name: str, default: Optional[str] = None) -> Optional[str]:
        if name in self.secrets:
            return self.secrets[name].value or default
        return os.getenv(name, default)

    def is_available(self, name: str) -> bool:
        return name in self.secrets and self.secrets[name].exists

    def get_report(self) -> str:
        lines = ["=" * 60, "SECRET VERIFICATION REPORT (C1)", "=" * 60, ""]

        lines.append("REQUIRED SECRETS:")
        for name in self.REQUIRED_SECRETS:
            status = self.secrets.get(name)
            if status:
                icon = "✓" if status.exists else "✗"
                lines.append(f"  {icon} {name}")

        lines.append("\nOPTIONAL SECRETS:")
        for name in self.OPTIONAL_SECRETS:
            status = self.secrets.get(name)
            if status:
                icon = "✓" if status.exists else "○"
                note = " (OK to be empty for now)" if name == 'WABA_PHONE_NUMBER_ID' else ""
                lines.append(f"  {icon} {name}{note}")

        all_valid, missing = self.verify_all()
        lines.append("\n" + "=" * 60)
        if all_valid:
            lines.append("✓ ALL REQUIRED SECRETS PRESENT - PROCEEDING")
        else:
            lines.append(f"✗ {len(missing)} REQUIRED SECRETS MISSING - STOPPING")
            lines.append("\nMissing secrets:")
            for secret in missing:
                lines.append(f"  - {secret}")
            lines.append("\nPlease add these to your .env file before continuing.")

        lines.append("=" * 60)
        return "\n".join(lines)

secrets_manager = SecretsManager()

if __name__ == "__main__":
    print(secrets_manager.get_report())
    all_valid, missing = secrets_manager.verify_all()
    if not all_valid:
        import sys
        sys.exit(1)
