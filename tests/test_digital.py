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


def test_digital_includes_print_risk_checks():
    rules, access, *_ = load_rules()
    doc = cases()[0][2]
    doc['objects'].append({'kind': 'text', 'name': 'tiny', 'artboard': 1, 'bbox': [1, 1, 20, 8], 'font_size_pt': 4,
                           'fill': {'space': 'CMYK', 'values': [0, 0, 0, 100]}, 'outlined': False})
    doc['objects'].append({'kind': 'path', 'name': 'white-op', 'artboard': 1, 'bbox': [50, 50, 60, 60],
                           'fill': {'space': 'CMYK', 'values': [0, 0, 0, 0]}, 'overprint_fill': True})
    doc['objects'].append({'kind': 'path', 'name': 'hairline', 'artboard': 1, 'bbox': [50, 50, 60, 60],
                           'stroke': {'space': 'CMYK', 'values': [0, 0, 0, 100]}, 'stroke_width_pt': 0.1})
    findings, _ = analyze(doc, rules, access, 'digital')
    by = {(f['code'], f['object']): f['status'] for f in findings}
    assert by[('font_size', 'tiny')] == 'yellow'
    assert by[('safe_margin', 'tiny')] == 'yellow'
    assert by[('white_overprint', 'white-op')] == 'red'
    assert by[('thin_line', 'hairline')] == 'yellow'
    assert not any(f['code'] == 'overprint' and f['status'] == 'green' for f in findings)
