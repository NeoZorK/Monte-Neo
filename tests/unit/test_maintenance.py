import re
from pathlib import Path


def test_index_completeness():
    """Verify that all markdown files in docs/ are registered in docs/INDEX.md."""
    root_dir = Path(__file__).parent.parent.parent
    docs_dir = root_dir / "docs"
    index_file = docs_dir / "INDEX.md"

    assert index_file.exists(), "docs/INDEX.md must exist"

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
            f"File {rel_path_str} is not registered in docs/INDEX.md"
        )

def test_version_consistency():
    """Verify that the version in src/monte_neo/_version.py follows vX.X.X pattern."""
    root_dir = Path(__file__).parent.parent.parent
    version_file = root_dir / "src" / "monte_neo" / "_version.py"

    assert version_file.exists(), "src/monte_neo/_version.py must exist"

    with open(version_file, encoding="utf-8") as f:
        content = f.read()

    version_match = re.search(r'__version__ = "v(\d+\.\d+\.\d+)"', content)
    assert version_match, (
        "Version must follow vX.X.X pattern in src/monte_neo/_version.py"
    )
