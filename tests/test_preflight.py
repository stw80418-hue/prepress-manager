import copy
import hashlib
import json
import math
import sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from checks import analyze
from metrics import effective_ppi,contrast,raster_tac,simulate
from preflight import ROOT,load_rules,run,write_json
from pdf_engine import inspect_pdf
from generate_cases import cases,make_pdf,generate


EXPECTED={2:("rgb","yellow"),3:("image_ppi","red"),4:("image_link","red"),5:("font_size","yellow"),
          6:("small_multichannel_black","red"),7:("tac","red"),8:("white_overprint","red"),9:("spot","yellow"),
          10:("thin_line","yellow"),11:("color_only","yellow"),12:("contrast","yellow"),13:("small_low_contrast","red"),14:("bleed","red")}


@pytest.mark.parametrize("number,name,doc",cases(),ids=[x[1] for x in cases()])
def test_fifteen_cases(number,name,doc,tmp_path):
    rules,access,*_=load_rules()
    findings,special=analyze(doc,rules,access)
    if number==1:
        assert not any(f["status"]=="red" for f in findings)
    elif number==15:
        assert len(special)==2
        assert not any(f["status"]=="red" for f in findings)
    else:
        code,status=EXPECTED[number]
        assert any(f["code"]==code and f["status"]==status for f in findings)
    path=tmp_path/"fixture.json";write_json(path,doc)
    run(path,tmp_path/"report")
    assert (tmp_path/"report/PREFLIGHT_REPORT.md").stat().st_size>100
    assert (tmp_path/"report/ACCESSIBILITY_REPORT.md").stat().st_size>100
    if number in [12,13]:
        assert all(f["group"]=="accessibility" for f in findings if f["code"] in ["contrast","small_low_contrast"])


@pytest.mark.parametrize("number",[1,2,3,5,6,7,8,9,10,12,13,14,15])
def test_real_pdf_extraction(number,tmp_path):
    p=tmp_path/"fixture.pdf";make_pdf(p,number)
    rules,access,*_=load_rules()
    d=inspect_pdf(p,rules)
    findings,special=analyze(d,rules,access)
    if number==1:
        assert not any(f["status"]=="red" for f in findings)
    elif number==15:
        assert special
    else:
        code,status=EXPECTED[number]
        assert any(f["code"]==code and f["status"]==status for f in findings)


def test_metrics_rotation_shear_and_boundaries():
    assert effective_ppi([300,300],[0,72,-72,0,0,0])["minimum"]==pytest.approx(300)
    assert effective_ppi([300,300],[72,0,72,72,0,0])["minimum"] < 300/math.sqrt(2)
    assert contrast([0,0,0],[1,1,1])==21
    assert contrast([1,1,1],[1,1,1])==1
    with pytest.raises(ValueError):
        effective_ppi([300,300],[0,0,0,0,0,0])
    d=copy.deepcopy(cases()[2][2]);r,a,*_=load_rules()
    for pixels,status in [(600,"green"),(400,"yellow"),(399,"red")]:
        d["objects"][0]["pixels"]=[pixels,pixels]
        f,_=analyze(d,r,a)
        assert next(x for x in f if x["code"]=="image_ppi")["status"]==status


def test_raster_tac_native_only():
    from PIL import Image
    im=Image.new("CMYK",(2,1));im.putdata([(255,255,255,255),(0,0,0,255)])
    stats=raster_tac(im,300)
    assert stats["maximum"]==400 and stats["average"]==250 and stats["over_limit_percent"]==50
    with pytest.raises(ValueError):
        raster_tac(im.convert("RGB"),300)


def test_simulation_reference():
    import numpy as np
    # Linear red through Machado severity 100 protanopia has first channel .152286.
    value=simulate([1,0,0],"protanomaly")
    assert value[0]==pytest.approx(1.055*.152286**(1/2.4)-.055)
    assert not np.allclose(value,[.2126]*3)
    assert np.allclose(simulate([1,1,1],"deuteranomaly"),[1,1,1],atol=1e-5)


def test_printer_precedence_and_pending(tmp_path):
    user=tmp_path/"settings.json";write_json(user,{"maximum_tac_percent":320})
    spec=tmp_path/"spec.json"
    data={"schema_version":1,"source":"printer.txt","review_status":"reviewed","overrides":{"maximum_tac_percent":280},
          "evidence":{"maximum_tac_percent":{"quote":"TAC 280%","location":"line 1"}},"manual_requirements":[]}
    write_json(spec,data)
    r,*_=load_rules(spec,user);assert r["maximum_tac_percent"]==280
    data["review_status"]="needs_review";write_json(spec,data)
    with pytest.raises(ValueError):
        load_rules(spec,user)
    data["review_status"]="reviewed";data["evidence"]={};write_json(spec,data)
    with pytest.raises(ValueError):
        load_rules(spec,user)


def test_pdf_preview_and_source_integrity(tmp_path):
    path=tmp_path/"source.pdf";make_pdf(path,8)
    before=path.read_bytes();out=tmp_path/"report"
    run(path,out)
    assert path.read_bytes()==before
    assert len(list((out/"color-vision-preview").glob("*.png")))==4
    assert (out/"issue-preview/artboard-01-issues.png").is_file()
    issues=json.loads((out/"ISSUES.json").read_text(encoding="utf-8"))
    assert any(x["code"]=="white_overprint" for x in issues)
    with pytest.raises(FileExistsError):
        run(path,out)


def test_unknown_does_not_pass():
    r,a,*_=load_rules();d=copy.deepcopy(cases()[4][2])
    d["artboards"][0]["bleed_mm"]=None
    d["objects"][0].update(font_size_pt=None,missing_font=None,outlined=True)
    f,_=analyze(d,r,a)
    for code in ["font_size","bleed","contrast","font_missing"]:
        assert next(x for x in f if x["code"]==code)["status"]=="unknown"


def test_missing_trimbox_not_inferred(tmp_path):
    import pikepdf
    p=tmp_path/"test.pdf"
    with pikepdf.Pdf.new() as pdf:
        pdf.add_blank_page();pdf.save(p)
    r,*_=load_rules();d=inspect_pdf(p,r)
    assert d["artboards"][0]["bleed_mm"] is None


def test_private_ai_fails_without_writing(tmp_path):
    p=tmp_path/"private.ai";p.write_bytes(b"%!PS-Adobe-3.0\nnot a PDF")
    with pytest.raises(ValueError,match="JSX|jsx"):
        run(p,tmp_path/"out")
    assert not (tmp_path/"out").exists()


def test_spec_conflict(tmp_path):
    from spec_extract import extract
    p=tmp_path/"printer.txt";p.write_text("銅版紙 TAC 300%\n非塗佈紙 TAC 240%\n出血 3 mm",encoding="utf-8")
    spec,text=extract(p)
    assert spec["conflicts"] and spec["review_status"]=="needs_review" and not spec["overrides"]


def test_invalid_settings_rejected(tmp_path):
    p=tmp_path/"bad.json";write_json(p,{"bleed_mm":-1})
    with pytest.raises(Exception):
        load_rules(settings=p)


def test_filters(tmp_path):
    r,a,*_=load_rules();d=cases()[5][2]
    f,_=analyze(d,r,a,"images")
    assert len(f) == 1 and f[0]["code"] == "image_embedding_summary" and f[0]["status"] == "unknown"


def test_complex_background_not_passed(tmp_path):
    import pikepdf
    p=tmp_path/"complex.pdf";make_pdf(p,12)
    with pikepdf.open(p) as pdf:
        pg=pdf.pages[0]
        pg.obj.Contents=pikepdf.Stream(pdf,b"0 0 0 rg 40 198 30 30 re f .7 .7 .7 rg BT /F1 12 Tf 1 0 0 1 40 200 Tm (Fixture text) Tj ET")
        q=tmp_path/"modified.pdf";pdf.save(q)
    r,a,*_=load_rules();d=inspect_pdf(q,r)
    f,_=analyze(d,r,a)
    assert all(x["status"]=="unknown" for x in f if x["code"]=="contrast")
