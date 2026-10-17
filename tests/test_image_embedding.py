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

def test_ai_header_links_detect_missing_file(tmp_path):
    import pikepdf
    from pdf_engine import inspect_pdf
    pdf_path=tmp_path/"source.pdf";make_pdf(pdf_path,1)
    kept=tmp_path/"kept 照片.jpg";kept.write_bytes(b"x")
    gone=tmp_path/"deleted.jpg"
    header=("%!PS-Adobe-3.0\r\n%%DocumentFiles:"+str(kept)+"\r\n%%+"+str(gone)+"\r\n%AI5_FileFormat 14.0\r\n").encode("utf-8")
    ai=tmp_path/"design.ai"
    with pikepdf.open(pdf_path) as pdf:
        meta=pikepdf.Stream(pdf,header)
        pdf.pages[0].obj["/PieceInfo"]=pikepdf.Dictionary({"/Illustrator":pikepdf.Dictionary({"/Private":pikepdf.Dictionary({"/AIMetaData":meta})})})
        pdf.save(ai)
    r,a,*_=load_rules()
    doc=inspect_pdf(ai,r)
    assert [f["state"] for f in doc["ai_document_files"]]==["linked","missing"]
    findings,_=analyze(doc,r,a,"digital")
    links={f["object"]:f["status"] for f in findings if f["code"]=="image_link" and f["artboard"] is None}
    assert links=={"kept 照片.jpg":"yellow","deleted.jpg":"red"}
    summary=next(f for f in findings if f["code"]=="image_embedding_summary")
    assert summary["status"]=="red" and summary["current"]["ai_header_links"]=={"linked":1,"missing":1}

def test_ai_without_header_links_stays_unknown(tmp_path):
    from pdf_engine import inspect_pdf
    import pikepdf
    pdf_path=tmp_path/"source.pdf";make_pdf(pdf_path,1)
    ai=tmp_path/"plain.ai"
    with pikepdf.open(pdf_path) as pdf:
        pdf.save(ai)
    r,a,*_=load_rules()
    doc=inspect_pdf(ai,r)
    assert doc["ai_document_files"] is None
