"""Read-only CLI for Illustrator inspector JSON, PDF-compatible AI, PDF, raster."""
import argparse
import hashlib
import json
import math
from datetime import datetime
from pathlib import Path
from checks import analyze
from metrics import PT_PER_MM, raster_tac

ROOT=Path(__file__).resolve().parents[1]


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write_json(path,data):
    Path(path).write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False),encoding="utf-8")


def digest(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""):
            h.update(chunk)
    return h.hexdigest()


def load_rules(spec=None, settings=None, accessibility=None):
    import jsonschema
    rules=read_json(ROOT/"print_rules.json")
    schema=read_json(ROOT/"references/PRINT_SPEC.schema.json")
    provenance={k:"Skill default" for k in rules}
    if settings:
        custom=read_json(settings)
        jsonschema.validate(custom,schema["properties"]["overrides"])
        rules.update(custom);provenance.update({k:"User settings" for k in custom})
    manual=[];spec_data=None
    if spec:
        spec_data=read_json(spec);jsonschema.validate(spec_data,schema)
        if spec_data["review_status"] != "reviewed" or spec_data.get("conflicts"):
            raise ValueError("PRINT_SPEC still needs review or has unresolved conflicts")
        for key in spec_data["overrides"]:
            if key not in spec_data["evidence"]:
                raise ValueError("Printer override missing source evidence: "+key)
        rules.update(spec_data["overrides"])
        provenance.update({k:"Printer: "+spec_data["source"] for k in spec_data["overrides"]})
        manual=spec_data["manual_requirements"]
    jsonschema.validate(rules,schema["properties"]["overrides"])
    if rules["image_warning_ppi"] > rules["minimum_image_ppi"]:
        raise ValueError("image_warning_ppi must not exceed minimum_image_ppi; adjust both settings")
    access=read_json(ROOT/"accessibility_rules.json")
    if accessibility:
        extra=read_json(accessibility)
        if set(extra)-set(access):
            raise ValueError("Unknown accessibility rule")
        access.update(extra)
    for key in ["contrast_normal","contrast_large"]:
        if not isinstance(access[key],(int,float)) or not 1 <= access[key] <= 21:
            raise ValueError("Invalid contrast threshold")
    if access["cvd_severity"] != 100:
        raise ValueError("Named -opia previews require severity 100")
    for key in ["large_text_pt","large_bold_text_pt","color_pair_delta_e76_warning","preview_dpi"]:
        if not isinstance(access[key],(int,float)) or not math.isfinite(access[key]) or access[key] <= 0:
            raise ValueError("Invalid accessibility rule: "+key)
    return rules,access,provenance,manual,spec_data


def validate_model(doc):
    if doc.get("schema_version") != 1:
        raise ValueError("Unsupported inspector schema_version")
    if not isinstance(doc.get("artboards"),list) or not doc["artboards"]:
        raise ValueError("Inspector needs at least one artboard")
    ids=set()
    def numbers(values,n):
        if not isinstance(values,list) or len(values)!=n or any(type(x) not in (int,float) or not math.isfinite(x) for x in values):
            raise ValueError("Invalid numeric array")
    for b in doc["artboards"]:
        if not isinstance(b.get("id"),int) or b["id"] in ids:
            raise ValueError("Artboard IDs must be unique integers")
        ids.add(b["id"]);numbers(b["rect"],4)
        if b["rect"][2]<=b["rect"][0] or b["rect"][3]<=b["rect"][1]:
            raise ValueError("Invalid artboard bounds")
        if b.get("bleed_mm") is not None:
            if set(b["bleed_mm"])!={"top","bottom","left","right"}:
                raise ValueError("Bleed needs all four sides")
            numbers(list(b["bleed_mm"].values()),4)
    for o in doc.get("objects",[]):
        if o.get("artboard") is not None and o["artboard"] not in ids:
            raise ValueError("Unknown object artboard")
        if o.get("bbox") is not None:
            numbers(o["bbox"],4)
        for key in ["font_size_pt","stroke_width_pt","opacity"]:
            v=o.get(key)
            if v is not None and (type(v) not in (int,float) or not math.isfinite(v) or v<0 or key=="opacity" and v>100):
                raise ValueError("Invalid object number: "+key)
        for channel in ["fill","stroke","color"]:
            c=o.get(channel)
            if c and c.get("values") is not None and c.get("space") in ["CMYK","RGB","Gray"]:
                n,maximum={"CMYK":(4,100),"RGB":(3,1),"Gray":(1,1)}[c["space"]]
                numbers(c["values"],n)
                if any(x<0 or x>maximum for x in c["values"]):
                    raise ValueError("Invalid color channel")
        if o.get("contrast_pair"):
            for k in ["foreground","background"]:
                numbers(o["contrast_pair"][k],3)
                if any(x<0 or x>1 for x in o["contrast_pair"][k]):
                    raise ValueError("Contrast needs 0..1 sRGB")
    for pair in doc.get("semantic_pairs",[]):
        for key in ["a","b"]:
            rgb=pair[key].get("srgb")
            if rgb is not None:
                numbers(rgb,3)
                if any(x<0 or x>1 for x in rgb):
                    raise ValueError("Semantic pair needs 0..1 sRGB")


def enrich_linked(doc,base,rules):
    from PIL import Image
    for o in doc.get("objects",[]):
        if o.get("kind") != "image" or o.get("link_state") != "linked" or not o.get("path"):
            continue
        path=Path(o["path"])
        if not path.is_absolute():
            path=base/path
        if not path.exists():
            o["link_state"]="missing";continue
        try:
            with Image.open(path) as im:
                o["pixels"]=list(im.size)
                o["color"]={"space":{"CMYK":"CMYK","RGB":"RGB","RGBA":"RGB","L":"Gray"}.get(im.mode,"Unknown")}
                dpi=im.info.get("dpi")
                if dpi and len(dpi)==2 and min(dpi)>0:
                    o["native_dpi"]=list(dpi)
                if im.mode=="CMYK":
                    o["tac_stats"]=raster_tac(im,rules["maximum_tac_percent"])
                else:
                    o["tac_reason"]="非原生 CMYK；不可轉 RGB 後反推 TAC。"
        except Exception as exc:
            o["tac_reason"]="連結檔不是可解碼 raster 或讀取失敗："+str(exc)


def inspect(path,rules,settings):
    ext=path.suffix.lower()
    if ext==".json":
        model=read_json(path);validate_model(model);enrich_linked(model,path.parent,rules)
        return model,[path.parent/f"artboard-{b['id']:02d}-original.png" for b in model["artboards"]],None
    with path.open("rb") as f:
        header=f.read(1024)
    if ext==".pdf" or ext==".ai" and b"%PDF-" in header:
        from pdf_engine import inspect_pdf
        model=inspect_pdf(path,rules)
        if ext==".ai":
            model["limitations"].append("目前僅解析 AI 的 PDF 相容內容；不是 Illustrator 私有編輯資料。請搭配 JSX。")
        return model,None,path
    if ext==".ai":
        raise ValueError("此 AI 沒有可辨識 PDF 相容資料；請在 Illustrator 執行 illustrator_inspector.jsx，再檢查輸出的 JSON。")
    from PIL import Image
    with Image.open(path) as im:
        pixels=list(im.size);dpi=im.info.get("dpi")
        size=rules.get("target_size_mm")
        # Never invent a print size from preview pixels; require explicit size.
        if not size:
            raise ValueError("Raster input requires target_size_mm in --settings or printer spec")
        rect=[0,0,size[0]*PT_PER_MM,size[1]*PT_PER_MM]
        obj={"kind":"image","name":path.name,"artboard":1,"bbox":rect,"pixels":pixels,
             "native_dpi":list(dpi) if dpi else None,"image_transform":[rect[2],0,0,rect[3],0,0],"link_state":"unknown","link_scope":"standalone_raster",
             "color":{"space":{"CMYK":"CMYK","RGB":"RGB","RGBA":"RGB","L":"Gray"}.get(im.mode,"Unknown")}}
        if im.mode=="CMYK":
            obj["tac_stats"]=raster_tac(im,rules["maximum_tac_percent"])
    return {"schema_version":1,"engine":"Raster / Pillow","source":str(path),"artboards":[{"id":1,"rect":rect,"bleed_mm":None}],
            "objects":[obj],"limitations":["Raster 無字型、物件、出血、疊印與 PDF/X 結構；圖中文字需人工確認。"]},[path],None


def apply_annotations(model,path):
    data=read_json(path)
    if data.get("source") != model.get("source"):
        raise ValueError("Annotations source must exactly match model source")
    allowed={"important","reverse","background_cmyk","contrast_pair","cvd_difficult","missing_font","outlined"}
    for annotation in data.get("objects",[]):
        if not annotation.get("evidence"):
            raise ValueError("Annotation needs evidence")
        matches=[o for o in model["objects"] if o.get("name")==annotation["name"] and o.get("artboard")==annotation["artboard"]]
        if len(matches)!=1:
            raise ValueError("Annotation must match exactly one object")
        fields=annotation["fields"]
        if set(fields)-allowed:
            raise ValueError("Unsupported annotation field")
        matches[0].update(fields);matches[0]["annotation_evidence"]=annotation["evidence"]
    model["semantic_pairs"]=data.get("semantic_pairs",model.get("semantic_pairs",[]))


STATUS={"red":"🔴 必須修正","yellow":"🟡 建議確認","green":"🟢 通過","unknown":"⚪ 無法自動確認"}


def report(out,doc,findings,special,previews,rules,provenance,scope):
    def fmt(x):
        if x is None:
            return "無法取得／未指定"
        return json.dumps(x,ensure_ascii=False) if isinstance(x,(dict,list)) else str(x).replace("\n"," ")
    sizes=[{"artboard":b["id"],"mm":[round((b["rect"][2]-b["rect"][0])/PT_PER_MM,3),round((b["rect"][3]-b["rect"][1])/PT_PER_MM,3)]} for b in doc["artboards"]]
    summary=f"檔案：{doc.get('source')}\n\n尺寸（寬 × 高 mm）：{fmt(sizes)}\n\nArtboard：{len(doc['artboards'])}\n\n使用印刷規格：見 EFFECTIVE_RULES.json（逐欄來源）\n\n檢查日期：{datetime.now().astimezone().isoformat()}\n\n引擎：{doc.get('engine')}；範圍：{scope}"
    limits="\n".join("- "+x for x in dict.fromkeys(doc.get("limitations",[])))
    limits+="\n- 本次範圍以外項目未檢查；通過僅代表該條證據符合目前門檻。\n- 報告計數以檢查結果為單位，同一物件可能有多條結果。\n- 無可靠位置的 Issue 只列報告，不猜測縮圖座標。"
    links="\n\n".join(f"Artboard {p['artboard']}\n\n"+"\n\n".join(f"{k}\n\n![{k}]({p[k]})" for k in ["original","protanopia","deuteranopia","tritanopia"] if k in p) for p in previews) or "⚪ 無法自動確認：未取得可渲染的 Artboard 預覽。"
    for group,filename in [("prepress","PREFLIGHT_REPORT.md"),("accessibility","ACCESSIBILITY_REPORT.md")]:
        if scope == "digital" and group == "accessibility":
            continue
        selected=[f for f in findings if f["group"]==group]
        counts="\n".join(f"- {v}：{sum(f['status']==k for f in selected)}" for k,v in STATUS.items())
        chunks=[]
        for f in selected:
            chunks.append(f"### {f['id']}｜{STATUS[f['status']]}｜{f['title']}\n\n"+"\n\n".join([
                "所在 Artboard："+fmt(f["artboard"]),"物件名稱："+fmt(f["object"]),
                "位置（pt；左、上、右、下；y 向下）："+fmt(f["bbox"]),
                "目前數值："+fmt(f["current"]),"建議數值："+fmt(f["expected"]),
                "原因："+(f["reason"] or "需要依實際製程與交付需求確認。"),
                "Illustrator 修正方式："+f["fix"],"證據："+f["evidence"]]))
        template=(ROOT/"templates"/filename).read_text(encoding="utf-8")
        text=template.format(summary=summary,counts=counts,issues="\n\n".join(chunks) or "本次範圍未執行此類檢查。",
                             special="\n".join("- "+fmt(s) for s in special) or "未辨識到名稱候選；不代表無加工項目。",
                             limitations=limits,previews=links,
                             issue_previews="\n\n".join(f"Artboard {p['artboard']}\n\n![Issue Preview]({p['issues']})\n\n未定位：{fmt(p['unplaced'])}" for p in previews) or "⚪ 無可用預覽；請參考物件／位置資料。")
        (out/filename).write_text(text,encoding="utf-8")


def run(input_path,out,*,spec=None,settings=None,accessibility=None,scope="all",annotations=None):
    path=Path(input_path).resolve();out=Path(out).resolve()
    if out.exists():
        raise FileExistsError("Output must be a NEW directory; existing files will not be overwritten")
    if path==out or out in path.parents:
        raise ValueError("Output must not contain the input")
    original_hash=digest(path)
    rules,access,provenance,manual,spec_data=load_rules(spec,settings,accessibility)
    doc,originals,pdf_path=inspect(path,rules,settings)
    doc["manual_requirements"]=manual
    if annotations:
        apply_annotations(doc,annotations)
    validate_model(doc)
    findings,special=analyze(doc,rules,access,scope)
    out.mkdir(parents=True,exist_ok=False)
    previews=[]
    try:
        if pdf_path:
            from pdf_engine import render_pdf
            temp=out/"rendered";temp.mkdir()
            originals=render_pdf(pdf_path,temp,int(access["preview_dpi"]))
        from previews import make_previews
        previews=make_previews(doc,findings,originals or [],out,access,simulate_cvd=scope != "digital")
    except Exception as exc:
        doc.setdefault("limitations",[]).append("預覽生成失敗："+str(exc))
    if len(previews)!=len(doc["artboards"]):
        findings.append(dict(id=f"Issue {len(findings)+1:03d}",code="preview_missing",status="unknown",title="部分 Artboard 色覺預覽無法產生",
            group="accessibility",artboard=None,object="文件",bbox=None,current=len(previews),expected=len(doc["artboards"]),
            reason="缺少預覽或渲染失敗；不可宣稱已完成色覺檢查。",fix="提供 Illustrator imageCapture 預覽或最終 PDF。",evidence="preview pipeline"))
    if scope == "digital":
        for issue in findings:
            if issue["code"] == "preview_missing":
                issue.update(group="prepress", title="部分頁面問題預覽無法產生", reason="缺少原始預覽或渲染失敗。")
        doc.setdefault("limitations", []).append("本次為數位印刷重點模式：色彩模式、文字外框、出血與尺寸、圖片解析度、圖片嵌入／連結狀態、AI 版本、四色黑、小字、安全邊距、細線與白色疊印。顏色對比與色覺模擬未執行；其他未列項目不代表通過。3 mm／300 PPI 是工作預設，不是所有數位印刷機的統一標準，印刷廠規格優先。")
    write_json(out/"INSPECTION.json",doc)
    write_json(out/"ISSUES.json",findings)
    write_json(out/"EFFECTIVE_RULES.json",{"print":rules,"accessibility":access,"provenance":provenance})
    write_json(out/"PREVIEWS.json",previews)
    if spec_data:
        write_json(out/"PRINT_SPEC.json",spec_data)
    final_hash=digest(path)
    if original_hash!=final_hash:
        raise RuntimeError("Source changed during inspection (possibly by another application); rerun on a stable copy")
    write_json(out/"RUN_MANIFEST.json",{"input":str(path),"sha256_before":original_hash,"sha256_after":final_hash,
               "scope":scope,"engine":doc.get("engine"),"timestamp":datetime.now().astimezone().isoformat(),
               "notice":"No source writes performed. JSX host behavior requires actual Illustrator verification."})
    report(out,doc,findings,special,previews,rules,provenance,scope)
    return findings


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("input",type=Path)
    p.add_argument("--out",type=Path,help="NEW output folder; defaults to <input-name>-preflight-<timestamp> next to the input")
    p.add_argument("--spec",type=Path)
    p.add_argument("--settings",type=Path,help="JSON print rule overrides; printer spec wins")
    p.add_argument("--accessibility-settings",type=Path)
    p.add_argument("--annotations",type=Path)
    p.add_argument("--pdf",type=Path,help="Also inspect a companion final PDF in a separate report; no unsafe object merging")
    p.add_argument("--scope",choices=["digital","all","text","images","color","tac","accessibility"],default="digital")
    a=p.parse_args()
    # Default beside the artwork so private reports never land inside the installed skill.
    out=a.out or a.input.resolve().parent/f"{a.input.stem}-preflight-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    try:
        findings=run(a.input,out,spec=a.spec,settings=a.settings,accessibility=a.accessibility_settings,scope=a.scope,annotations=a.annotations)
        if a.pdf:
            run(a.pdf,out/"final-pdf",spec=a.spec,settings=a.settings,accessibility=a.accessibility_settings,scope=a.scope)
            with (out/"PREFLIGHT_REPORT.md").open("a",encoding="utf-8") as f:
                f.write("\n\n最終 PDF 檢查：[獨立報告](final-pdf/PREFLIGHT_REPORT.md)。未自動假設與 AI 物件一一對應；請核對版本、尺寸與頁序。\n")
        print(str(out.resolve()))
        print(json.dumps({k:sum(f["status"]==k for f in findings) for k in STATUS}))
    except Exception as exc:
        p.exit(2,f"Preflight error: {exc}\n")


if __name__=="__main__":
    main()
