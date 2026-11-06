"""Input integrity: compare input files with the manifest's SHA-256 hashes."""
import hashlib
from pathlib import Path


def verify_input_hashes(manifest: dict, data_dir: Path) -> list[str]:
    """Return one problem string per input file that is missing or altered."""
    problems: list[str] = []
    for entry in manifest["files"]:
        path = Path(data_dir) / entry["file"]
        if not path.exists():
            problems.append(f"{entry['file']}: file is missing")
            continue
        data = path.read_bytes()
        if len(data) != entry["bytes"]:
            problems.append(f"{entry['file']}: size {len(data)} != {entry['bytes']}")
        if hashlib.sha256(data).hexdigest() != entry["sha256"]:
            problems.append(f"{entry['file']}: SHA-256 does not match manifest")
    return problems