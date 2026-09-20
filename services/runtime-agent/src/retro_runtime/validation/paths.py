import hashlib
from pathlib import Path


def resolve_existing_file_beneath(candidate: str, root: Path) -> Path:
    resolved_root = root.resolve(strict=True)
    resolved_candidate = Path(candidate).resolve(strict=True)
    if not resolved_candidate.is_file():
        raise ValueError("ROM path is not a regular file")
    if not resolved_candidate.is_relative_to(resolved_root):
        raise ValueError("ROM path escapes the approved ROM root")
    return resolved_candidate


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
