"""Package the Gemini Notebook skill as a zip for Claude's skill upload.

Claude Desktop (Chat, Cowork) and claude.ai load skills uploaded to the user's
account (Customize > Skills > Add), not the local ~/.claude/skills folder. This
builds that upload file from the packaged data files.
"""

import os
import platform
import re
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

import yaml

from notebooklm_tools import __version__

SKILL_NAME = "nlm-skill"
ZIP_NAME = f"{SKILL_NAME}.zip"

# Frontmatter keys defined by the Agent Skills specification.
ALLOWED_KEYS = {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}
MAX_DESCRIPTION = 1024
_NAME_RE = re.compile(r"^[a-z0-9-]{1,64}$")


def _data_dir() -> Path:
    import notebooklm_tools

    return Path(notebooklm_tools.__file__).parent / "data"


def _split_frontmatter(text: str) -> tuple[str, str]:
    if not text.startswith("---"):
        raise ValueError("SKILL.md has no frontmatter")
    end = text.index("---", 3)
    return text[3:end], text[end + 3 :]


def packaged_skill_md(source_text: str, version: str) -> str:
    """Move the non-standard top-level `version:` into `metadata:`."""
    frontmatter, body = _split_frontmatter(source_text)
    frontmatter = re.sub(r"\nversion:.*", "", "\n" + frontmatter.strip("\n"))
    frontmatter = frontmatter.strip("\n") + f'\nmetadata:\n  version: "{version}"\n'
    return "---\n" + frontmatter + "---" + body


def validate_frontmatter(skill_md: str, folder_name: str) -> None:
    """Raise ValueError if the frontmatter would be rejected on upload."""
    try:
        frontmatter, _ = _split_frontmatter(skill_md)
    except ValueError as exc:
        raise ValueError("SKILL.md has no frontmatter") from exc
    data = yaml.safe_load(frontmatter) or {}
    unknown = set(data) - ALLOWED_KEYS
    if unknown:
        raise ValueError(f"Unsupported frontmatter keys: {', '.join(sorted(unknown))}")
    name = data.get("name", "")
    if not _NAME_RE.match(str(name)) or name != folder_name:
        raise ValueError(f"Skill name '{name}' must match folder '{folder_name}'")
    description = data.get("description")
    if not description:
        raise ValueError("Skill description is required")
    if len(description) > MAX_DESCRIPTION:
        raise ValueError(f"Skill description is {len(description)} chars (max {MAX_DESCRIPTION})")


def build_skill_zip(output_dir: Path, data_dir: Path | None = None) -> Path:
    """Build <output_dir>/nlm-skill.zip; replaces an existing one atomically."""
    data_dir = data_dir or _data_dir()
    skill_md = packaged_skill_md((data_dir / "SKILL.md").read_text(encoding="utf-8"), __version__)
    validate_frontmatter(skill_md, SKILL_NAME)

    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / ZIP_NAME
    fd, tmp_name = tempfile.mkstemp(prefix=".nlm-skill-", suffix=".zip", dir=output_dir)
    os.close(fd)
    try:
        with zipfile.ZipFile(tmp_name, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(f"{SKILL_NAME}/SKILL.md", skill_md)
            for ref in sorted((data_dir / "references").glob("*.md")):
                zf.write(ref, f"{SKILL_NAME}/references/{ref.name}")
        os.replace(tmp_name, target)
    except BaseException:
        Path(tmp_name).unlink(missing_ok=True)
        raise
    return target


def default_output_dir() -> Path:
    downloads = Path.home() / "Downloads"
    return downloads if downloads.is_dir() else Path.home()


def upload_instructions(zip_path: Path) -> list[str]:
    return [
        f"Saved: {zip_path}",
        "To add it: open Claude Desktop (or claude.ai) → Customize → Skills → Add →",
        "pick this file → turn the skill on.",
        "After updating nlm, re-upload the new file to get the latest skill.",
    ]


def reveal_in_file_manager(path: Path) -> bool:
    """Show the file in Finder (macOS only). Never raises."""
    if platform.system() != "Darwin":
        return False
    opener = shutil.which("open")
    if not opener:
        return False
    try:
        return subprocess.run([opener, "-R", str(path)], check=False, timeout=5).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False
