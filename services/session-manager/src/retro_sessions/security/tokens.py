import hashlib
import hmac
from uuid import UUID

from pydantic import SecretStr


def derive_master_token(secret: SecretStr, participant_id: UUID) -> str:
    """Preserve the Runtime Agent create-idempotency token derivation from Milestone 8."""
    return hmac.new(
        secret.get_secret_value().encode(),
        participant_id.bytes,
        hashlib.sha256,
    ).hexdigest()


def derive_controller_token(secret: SecretStr, participant_id: UUID) -> str:
    """Derive a distinct opaque browser credential without persisting the credential."""
    return hmac.new(
        secret.get_secret_value().encode(),
        b"selkies-controller-v1\0" + participant_id.bytes,
        hashlib.sha256,
    ).hexdigest()
