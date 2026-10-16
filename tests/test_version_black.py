import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import pytest
from checks import analyze
from preflight import load_rules
from pdf_engine import inspect_pdf
from generate_cases import cases,make_pdf

@pytest.mark.parametrize("major,verified,status",[(16,True,"green"),(17,True,"yellow"),(29,False,"unknown")])
def test_saved_version(major,verified,status):
    d=cases()[0][2];d["source"]="test.ai"
    d["ai_version"]={"saved_major":major,"saved_version_verified":verified,"saved_version_evidence":"Test fixture save setting"}
    r,a,*_=load_rules();f,_=analyze(d,r,a,"digital")
    assert next(x for x in f if x["code"]=="ai_version")["status"]==status

def test_creator_is_not_saved_version(tmp_path):
    import pikepdf
    p=tmp_path/"source.pdf";make_pdf(p,1)
    q=tmp_path/"source.ai"
    with pikepdf.open(p) as pdf:
        pdf.docinfo["/Creator"]="Adobe Illustrator 29.8 (Windows)"
        pdf.save(q)
    r,a,*_=load_rules();d=inspect_pdf(q,r);f,_=analyze(d,r,a,"digital")
    assert next(x for x in f if x["code"]=="ai_version")["status"]=="unknown"
    assert next(x for x in f if x["code"]=="ai_creator_version")["status"]=="yellow"

@pytest.mark.parametrize("kind,size,values,status",[("text",5,[100,100,100,100],"red"),("path",None,[60,40,40,100],"yellow"),("path",None,[0,0,0,100],None)])
def test_black_candidates(kind,size,values,status):
    d=cases()[0][2];o=d["objects"][0];o.update(kind=kind,font_size_pt=size,fill={"space":"CMYK","values":values})
    r,a,*_=load_rules();f,_=analyze(d,r,a,"digital")
    hits=[x for x in f if x["code"]=="multichannel_black"]
    assert (hits[0]["status"] if hits else None)==status
    assert not any(x["group"]=="accessibility" for x in f)

def test_black_stroke_is_checked():
    d=cases()[0][2];d["objects"][0]["stroke"]={"space":"CMYK","values":[100,100,100,100]}
    r,a,*_=load_rules();f,_=analyze(d,r,a,"digital")
    assert any(x["code"]=="multichannel_black" and x["current"]["channel"]=="stroke" for x in f)
