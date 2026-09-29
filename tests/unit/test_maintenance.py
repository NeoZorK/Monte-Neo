import os
import re
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
    """Verify that all markdown files in docs/ are registered in docs/docs-map.md."""
    root_dir = find_root()
    docs_dir = root_dir / "docs"
    index_file = docs_dir / "docs-map.md"

    if not index_file.exists():
        # Debug info for the user
        print(f"DEBUG: root_dir is {root_dir}")
        print(f"DEBUG: contents of root_dir: {os.listdir(root_dir)}")

    assert index_file.exists(), (
        f"docs/docs-map.md must exist at {index_file}. \n"
        f"If running in Docker, ensure you have: \n"
        f"1. Added 'COPY docs/ docs/' to your Dockerfile\n"
        f"2. Rebuilt the image: 'docker-compose build --no-cache'\n"
        f"3. Or mounted the folder in docker-compose.yml"
    )

    with open(index_file, encoding="utf-8") as f:
        index_content = f.read()

    # Get all .md files in docs/ (recursive)
    md_files = list(docs_dir.rglob("*.md"))

    # Exclude docs-map.md itself
    md_files = [f for f in md_files if f.name != "docs-map.md"]

    for md_file in md_files:
        # Get relative path from root
        rel_path = md_file.relative_to(root_dir)
        rel_path_str = str(rel_path)

        # Check if the path exists in docs-map.md
        assert rel_path_str in index_content, (
            f"File {rel_path_str} is not registered in docs/docs-map.md. "
            f"Please add it to maintain the project index."
        )


def test_version_consistency():
    """Verify that the version in src/monte_neo/_version.py follows vX.X.X pattern."""
    root_dir = find_root()
    version_file = root_dir / "src" / "monte_neo" / "_version.py"

    assert version_file.exists(), (
        f"src/monte_neo/_version.py must exist at {version_file}"
    )

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


def test_license_and_docs_version_sync():
    """Keep LICENSE, pyproject, and docs/docs-map version headers aligned."""
    root_dir = find_root()
    version_file = root_dir / "src" / "monte_neo" / "_version.py"
    version = re.search(
        r'__version__\s*=\s*["\'](v\d+\.\d+\.\d+)["\']',
        version_file.read_text(encoding="utf-8"),
    ).group(1)

    license_text = (root_dir / "LICENSE").read_text(encoding="utf-8")
    assert license_text.startswith("MIT License"), "LICENSE must be MIT"

    pyproject = (root_dir / "pyproject.toml").read_text(encoding="utf-8")
    assert ('license = "MIT"' in pyproject) or ('text = "MIT"' in pyproject), "pyproject.toml license must be MIT"

    index = (root_dir / "docs" / "docs-map.md").read_text(encoding="utf-8")
    assert version in index, f"docs/docs-map.md must mention {version}"

    roadmap = (root_dir / "docs" / "project" / "ROADMAP.md").read_text(encoding="utf-8")
    assert version in roadmap, f"docs/project/ROADMAP.md must mention {version}"


def test_referenced_assets_exist():
    """Every docs/assets file linked from README.md or docs/*.md must be in the tree.

    CI checks out only committed files, so an asset hidden by .gitignore fails here.
    """
    root_dir = find_root()
    sources = [root_dir / "README.md", *(root_dir / "docs").rglob("*.md")]
    pattern = re.compile(r"(?:docs/)?assets/([\w.\-/]+\.(?:png|gif|jpg|jpeg|svg))")
    missing = set()
    for src in sources:
        for name in pattern.findall(src.read_text(encoding="utf-8")):
            if not (root_dir / "docs" / "assets" / name).is_file():
                missing.add(f"{src.relative_to(root_dir)} -> docs/assets/{name}")
    assert not missing, f"referenced assets missing from the tree: {sorted(missing)}"


def test_version_is_the_same_everywhere():
    """Every place that names the release must match src/monte_neo/_version.py."""
    import json

    root = find_root()
    ver = re.search(r'__version__ = "v([^"]+)"', (root / "src/monte_neo/_version.py").read_text()).group(1)
    server = json.loads((root / "server.json").read_text())
    found = {
        "server.json": server["version"],
        "server.json packages": server["packages"][0]["version"],
        "claude plugin": json.loads((root / "integrations/claude-code/.claude-plugin/plugin.json").read_text())["version"],
        "gemini extension": json.loads((root / "integrations/gemini/gemini-extension.json").read_text())["version"],
        "CITATION.cff": re.search(r'^version: "([^"]+)"', (root / "CITATION.cff").read_text(), re.M).group(1),
        "installation.md": re.search(r"Current release: \*\*v([^*]+)\*\*", (root / "docs/setup/installation.md").read_text()).group(1),
        "README action pin": re.search(r"NeoZorK/Monte-Neo@v([0-9.]+)", (root / "README.md").read_text()).group(1),
        "CHANGELOG top": re.search(r"^## \[v([^\]]+)\]", (root / "docs/project/CHANGELOG.md").read_text(), re.M).group(1),
    }
    wrong = {k: v for k, v in found.items() if v != ver}
    assert not wrong, f"expected {ver}: {wrong}"


def test_every_github_action_is_pinned_to_a_commit_sha() -> None:
    """A moving tag can be re-pointed at malicious code: third-party Actions are pinned by SHA."""
    import re
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    files = [*(root / ".github" / "workflows").glob("*.yml"), root / "action.yml"]
    pattern = re.compile(r"^\s*(?:-\s*)?uses:\s*(\S+)(.*)$", re.MULTILINE)
    checked = 0
    for path in files:
        for ref, rest in pattern.findall(path.read_text(encoding="utf-8")):
            if ref.startswith("./"):
                continue  # this repository's own action
            checked += 1
            assert re.fullmatch(r"[\w.-]+/[\w./-]+@[0-9a-f]{40}", ref), f"{path.name}: {ref} is not pinned to a SHA"
            assert "#" in rest, f"{path.name}: {ref} needs a '# tag' comment so Dependabot can update it"
    assert checked >= 20


def test_workflows_grant_least_privilege() -> None:
    """Every workflow starts from read-only permissions; jobs that need more say so explicitly."""
    from pathlib import Path

    import yaml

    for path in (Path(__file__).resolve().parents[2] / ".github" / "workflows").glob("*.yml"):
        workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert workflow.get("permissions") in ({"contents": "read"}, "read-all"), f"{path.name} lacks a read-only default"
