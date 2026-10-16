import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import pytest
from checks import analyze
from preflight import load_rules, run
from generate_cases import cases, make_pdf
import json

@pytest.mark.parametrize("state,status", [("embedded","green"),("linked","yellow"),("missing","red"),("unknown","unknown")])
def test_native_image_states(state,status):
    doc=cases()[1][2]
    doc["objects"][0].update(link_state=state,path="photo.tif",layer="Photos")
    r,a,*_=load_rules()
    findings,_=analyze(doc,r,a,"digital")
    link=next(f for f in findings if f["code"]=="image_link")
    summary=next(f for f in findings if f["code"]=="image_embedding_summary")
    assert link["status"]==summary["status"]==status
    assert link["artboard"]==1
    assert link["current"]["path"]=="photo.tif"
    assert summary["current"]["placement_counts"][state]==1

def test_legacy_pdf_storage_is_not_ai_embedding():
    doc=cases()[1][2];doc["engine"]="PDF / legacy"
    r,a,*_=load_rules()
    findings,_=analyze(doc,r,a,"images")
    assert all(f["status"]=="unknown" for f in findings if f["code"] in ["image_link","image_embedding_summary"])

def test_pdf_report_keeps_ai_embedding_unknown(tmp_path):
    source=tmp_path/"image.pdf";make_pdf(source,2)
    out=tmp_path/"result";run(source,out,scope="digital")
    findings=json.loads((out/"ISSUES.json").read_text(encoding="utf-8"))
    links=[f for f in findings if f["code"]=="image_link"]
    assert links and all(f["status"]=="unknown" for f in links)
    assert all(f["current"]["pdf_storage"]=="embedded" for f in links)
    assert not (out/"ACCESSIBILITY_REPORT.md").exists()

def test_no_images_not_all_embedded():
    doc=cases()[0][2];r,a,*_=load_rules()
    findings,_=analyze(doc,r,a,"images")
    assert len(findings)==1 and findings[0]["status"]=="unknown"
