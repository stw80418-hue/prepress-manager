import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import argparse
import pytest
from checks import size_verdict
from preflight import load_rules, parse_size

NO_BLEED = {"top": 0, "bottom": 0, "left": 0, "right": 0}
BLEED3 = {"top": 3, "bottom": 3, "left": 3, "right": 3}


def rules(target=None, bleed=3):
    r, *_ = load_rules(cli={"target_size_mm": target, "bleed_mm": bleed} if target else {"bleed_mm": bleed})
    return r


@pytest.mark.parametrize("size,bleed,status,title", [
    ([210, 297], BLEED3, "green", "成品尺寸符合"),
    ([297, 210], BLEED3, "yellow", "方向相反"),
    ([216, 303], NO_BLEED, "yellow", "工作區域含出血"),
    ([216, 303], BLEED3, "red", "出血重複"),
    ([200, 297], BLEED3, "red", "成品尺寸不符"),
])
def test_size_cases(size, bleed, status, title):
    got, got_title, current, _ = size_verdict(size, bleed, rules([210, 297]))
    assert got == status and title in got_title
    assert current["with_bleed_mm"] == [size[0]+2*bleed["left"], size[1]+2*bleed["top"]]


def test_no_target_lists_common_size_hint():
    status, _, current, reason = size_verdict([216, 303], NO_BLEED, rules())
    assert status == "unknown"
    assert any("A4" in h and "出血" in h for h in current["looks_like"])
    assert "A4" in reason


def test_cli_size_overrides_defaults():
    r, _, provenance, *_ = load_rules(cli={"target_size_mm": [90, 54], "bleed_mm": 2})
    assert r["target_size_mm"] == [90, 54] and r["bleed_mm"] == 2
    assert provenance["bleed_mm"] == "User settings (command line)"


@pytest.mark.parametrize("text,expected", [("210x297", [210, 297]), ("90×54", [90, 54]), ("148*210mm", [148, 210])])
def test_parse_size(text, expected):
    assert parse_size(text) == expected


def test_parse_size_rejects_bad_input():
    with pytest.raises(argparse.ArgumentTypeError):
        parse_size("A4")
