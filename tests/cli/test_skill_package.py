import zipfile
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from notebooklm_tools import __version__
from notebooklm_tools.cli import skill_package as sp
from notebooklm_tools.cli.main import app as main_app


def _frontmatter(text):
    return yaml.safe_load(text.split("---")[1])


def test_zip_layout_and_contents(tmp_path):
    zip_path = sp.build_skill_zip(tmp_path)
    assert zip_path == tmp_path / "nlm-skill.zip"
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
        assert all(n.startswith("nlm-skill/") for n in names)
        assert "nlm-skill/SKILL.md" in names
        refs = {n for n in names if n.startswith("nlm-skill/references/")}
        assert refs == {
            f"nlm-skill/references/{f}"
            for f in (
                "command_reference.md",
                "remote-mcp.md",
                "studio-prompt-examples.md",
                "studio-prompting-guide.md",
                "troubleshooting.md",
                "workflows.md",
            )
        }
        fm = _frontmatter(zf.read("nlm-skill/SKILL.md").decode())
    assert fm["name"] == "nlm-skill"
    assert "version" not in fm
    assert fm["metadata"] == {"version": __version__}


def test_packaged_skill_md_moves_version_to_metadata():
    src = "---\nname: nlm-skill\nversion: \"0.1.0\"\ndescription: 'd'\n---\n\n# Body\n"
    out = sp.packaged_skill_md(src, "9.9.9")
    fm = _frontmatter(out)
    assert fm == {"name": "nlm-skill", "description": "d", "metadata": {"version": "9.9.9"}}
    assert out.endswith("# Body\n")


def test_source_skill_md_is_untouched(tmp_path):
    src = sp._data_dir() / "SKILL.md"
    before = src.read_text(encoding="utf-8")
    sp.build_skill_zip(tmp_path)
    assert src.read_text(encoding="utf-8") == before


@pytest.mark.parametrize(
    ("text", "folder", "message"),
    [
        ("---\nname: other\ndescription: d\n---\n", "nlm-skill", "must match"),
        ("---\nname: nlm-skill\ndescription: " + "x" * 1025 + "\n---\n", "nlm-skill", "1024"),
        ("---\nname: nlm-skill\ndescription: d\nversion: '1'\n---\n", "nlm-skill", "version"),
        ("---\nname: nlm-skill\n---\n", "nlm-skill", "description"),
        ("no frontmatter", "nlm-skill", "frontmatter"),
    ],
)
def test_validate_frontmatter_rejects(text, folder, message):
    with pytest.raises(ValueError, match=message):
        sp.validate_frontmatter(text, folder)


def test_overwrites_existing_zip(tmp_path):
    (tmp_path / "nlm-skill.zip").write_text("stale")
    zip_path = sp.build_skill_zip(tmp_path)
    assert zipfile.is_zipfile(zip_path)


def test_failed_validation_leaves_existing_zip_untouched(tmp_path, monkeypatch):
    (tmp_path / "nlm-skill.zip").write_text("stale")
    monkeypatch.setattr(
        sp, "validate_frontmatter", lambda *a: (_ for _ in ()).throw(ValueError("bad"))
    )
    with pytest.raises(ValueError):
        sp.build_skill_zip(tmp_path)
    assert (tmp_path / "nlm-skill.zip").read_text() == "stale"
    assert [p.name for p in tmp_path.iterdir()] == ["nlm-skill.zip"]  # no temp leftovers


def test_creates_missing_output_dir(tmp_path):
    out = tmp_path / "a" / "b"
    assert sp.build_skill_zip(out).exists()


def test_default_output_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    assert sp.default_output_dir() == tmp_path
    (tmp_path / "Downloads").mkdir()
    assert sp.default_output_dir() == tmp_path / "Downloads"


def test_upload_instructions_mention_path_and_steps(tmp_path):
    lines = sp.upload_instructions(tmp_path / "nlm-skill.zip")
    text = "\n".join(lines)
    assert str(tmp_path / "nlm-skill.zip") in text
    assert "Customize" in text and "Skills" in text and "Add" in text
    assert "re-upload" in text


def test_reveal_never_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(sp.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(sp.shutil, "which", lambda _: None)
    assert sp.reveal_in_file_manager(tmp_path) is False
    monkeypatch.setattr(sp.platform, "system", lambda: "Linux")
    assert sp.reveal_in_file_manager(tmp_path) is False


def test_cli_package_writes_zip_and_prints_steps(tmp_path, monkeypatch):
    monkeypatch.setattr(sp, "reveal_in_file_manager", lambda p: False)
    result = CliRunner().invoke(main_app, ["skill", "package", "--output", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert (tmp_path / "nlm-skill.zip").exists()
    assert "Customize" in result.output


def test_cli_package_failure_exits_1(tmp_path, monkeypatch):
    def boom(*_a, **_k):
        raise ValueError("bad frontmatter")

    monkeypatch.setattr(sp, "build_skill_zip", boom)
    result = CliRunner().invoke(main_app, ["skill", "package", "--output", str(tmp_path)])
    assert result.exit_code == 1
    assert "bad frontmatter" in result.output
