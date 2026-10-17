import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import pytest
from install_skill import install


def test_install_refuses_then_updates_with_backup(tmp_path):
    first = install("claude", tmp_path, venv=False)
    assert (first["dest"] / "SKILL.md").exists() and first["backup"] is None
    with pytest.raises(FileExistsError):
        install("claude", tmp_path, venv=False)
    second = install("claude", tmp_path, update=True, venv=False)
    # Backup must sit outside skills/ so it is never loaded as a second skill.
    assert (second["backup"] / "SKILL.md").exists()
    assert "skills" not in second["backup"].relative_to(tmp_path).parts
    assert [p.name for p in (tmp_path / ".claude/skills").iterdir()] == ["prepress-manager"]


def test_install_warns_about_legacy_copy(tmp_path):
    (tmp_path / ".codex/skills/prepress-manager").mkdir(parents=True)
    result = install("codex", tmp_path, venv=False)
    assert result["dest"] == tmp_path / ".agents/skills/prepress-manager"
    assert any(".codex" in p for p in result["legacy"])
