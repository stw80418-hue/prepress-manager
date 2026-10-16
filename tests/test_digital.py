import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import json
from preflight import run, load_rules, write_json
from checks import analyze
from generate_cases import cases, make_pdf


def test_digital_excludes_accessibility_and_tac():
    rules, access, *_ = load_rules()
    doc = cases()[12][2]
    findings, _ = analyze(doc, rules, access, 'digital')
    assert all(f['group'] == 'prepress' for f in findings)
    assert {'outline_summary', 'text_type', 'bleed', 'dimensions'} <= {f['code'] for f in findings}
    assert not {'contrast', 'small_low_contrast', 'tac', 'raster_tac'} & {f['code'] for f in findings}


def test_digital_pdf_output(tmp_path):
    source = tmp_path / 'source.pdf'
    make_pdf(source, 12)
    out = tmp_path / 'result'
    run(source, out, scope='digital')
    assert (out / 'PREFLIGHT_REPORT.md').exists()
    assert not (out / 'ACCESSIBILITY_REPORT.md').exists()
    assert not (out / 'color-vision-preview').exists()
    assert (out / 'issue-preview/artboard-01-issues.png').exists()
    assert all(i['group'] == 'prepress' for i in json.loads((out / 'ISSUES.json').read_text(encoding='utf-8')))
