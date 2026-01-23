import re
import os
from pathlib import Path


def find_root() -> Path:
    """Find the project root by looking for pyproject.toml."""
    curr = Path(__file__).resolve().parent
    for _ in range(5):
        if (curr / "pyproject.toml").exists():
            return curr
        curr = curr.parent
    # Fallback to the old method if not found
    return Path(__file__).resolve().parent.parent.parent


def test_index_completeness():
    """Verify that all markdown files in docs/ are registered in docs/INDEX.md."""
    root_dir = find_root()
    docs_dir = root_dir / "docs"
    index_file = docs_dir / "INDEX.md"

    if not index_file.exists():
        # Debug info for the user
        print(f"DEBUG: root_dir is {root_dir}")
        print(f"DEBUG: contents of root_dir: {os.listdir(root_dir)}")

    assert index_file.exists(), (
        f"docs/INDEX.md must exist at {index_file}. \n"
        f"If running in Docker, ensure you have: \n"
        f"1. Added 'COPY docs/ docs/' to your Dockerfile\n"
        f"2. Rebuilt the image: 'docker-compose build --no-cache'\n"
        f"3. Or mounted the folder in docker-compose.yml"
    )

    with open(index_file, encoding="utf-8") as f:
        index_content = f.read()

    # Get all .md files in docs/ (recursive)
    md_files = list(docs_dir.rglob("*.md"))

    # Exclude INDEX.md itself
    md_files = [f for f in md_files if f.name != "INDEX.md"]

    for md_file in md_files:
        # Get relative path from root
        rel_path = md_file.relative_to(root_dir)
        rel_path_str = str(rel_path)

        # Check if the path exists in INDEX.md
        assert rel_path_str in index_content, (
            f"File {rel_path_str} is not registered in docs/INDEX.md. "
            f"Please add it to maintain the project index."
        )


def test_version_consistency():
    """Verify that the version in src/monte_neo/_version.py follows vX.X.X pattern."""
    root_dir = find_root()
    version_file = root_dir / "src" / "monte_neo" / "_version.py"

    assert version_file.exists(), f"src/monte_neo/_version.py must exist at {version_file}"

    with open(version_file, encoding="utf-8") as f:
        content = f.read()

    version_match = re.search(r'__version__\s*=\s*["\']v(\d+\.\d+\.\d+)["\']', content)
    
    # Extract actual version for better error message if it fails
    actual_version = "unknown"
    fallback_match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', content)
    if fallback_match:
        actual_version = fallback_match.group(1)

    assert version_match, (
        f"Version in {version_file} must follow 'vX.X.X' pattern (with leading 'v').\n"
        f"Actual value found: '{actual_version}'\n"
        f"Please change it to 'v{actual_version}' in the file."
    )
