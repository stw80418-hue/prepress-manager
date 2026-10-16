"""PDF output inspection; deliberately not a PDF/X conformance validator."""
import copy
import io
from pathlib import Path
from metrics import PT_PER_MM, raster_tac


def inspect_pdf(path, rules):
    import pymupdf as fitz
    import pikepdf
    from PIL import Image
    model = {"schema_version":1,"engine":"PDF / PyMuPDF + pikepdf", "source":str(Path(path).resolve()),
             "artboards":[],"objects":[],"limitations":[
                 "PDF 無法證明原 AI 連結是否遺失、原圖層鎖定與隱藏內容。",
                 "未辨識為文字的路徑不能直接當作外框文字；原始字型與字級無法還原。",
                 "PDF/X 宣告不等於合規；需 Acrobat Preflight 或專用驗證器。",
                 "PDF 原始繪製事件部分無可靠位置；不在縮圖上猜測標記。",
                 "文字背景、加工語意與實際出血覆蓋需另外確認。",
                 "TAC 僅為物件與原始圖片樣本，不是整頁 RIP 分色後的最終 TAC。"
             ]}
    with pikepdf.open(path) as pdf, fitz.open(path) as rendered:
        intents = []
        for oi in pdf.Root.get("/OutputIntents", []):
            profile = oi.get("/DestOutputProfile")
            intents.append({"identifier":str(oi.get("/OutputConditionIdentifier", "")),
                            "info":str(oi.get("/Info", "")), "profile_present": profile is not None,
                            "channels":int(profile.get("/N", 0)) if profile is not None else None})
        xmp = ""
        if pdf.Root.get("/Metadata") is not None:
            xmp = pdf.Root.Metadata.read_bytes().decode("utf-8", errors="replace")
        import re
        pdfx = str(pdf.docinfo.get("/GTS_PDFXVersion", ""))
        if not pdfx:
            match = re.search(r"PDF/X-[^<\"\s]+", xmp)
            pdfx = match.group(0) if match else None
        model["metadata"] = {"pdf_version":str(pdf.pdf_version), "pdf_x":pdfx,
                              "icc_profile":intents, "xmp_present":bool(xmp)}
        if Path(path).suffix.lower() == ".ai":
            evidence = {"pdf_creator": str(pdf.docinfo.get("/Creator", "")), "private_markers": []}
            for pg in pdf.pages:
                private = pg.obj.get("/PieceInfo", {}).get("/Illustrator", {}).get("/Private", {})
                evidence["private_markers"].append({k: str(private.get(k, "")) for k in
                    ["/CreatorVersion", "/ContainerVersion", "/RoundtripVersion"]})
            # CreatorVersion describes the writer, not the selected save compatibility.
            match = re.search(r"Adobe Illustrator(?:\(R\))?\s+(\d+)", evidence["pdf_creator"])
            evidence["creator_major"] = int(match.group(1)) if match else None
            evidence["saved_major"] = None
            model["ai_version"] = evidence
        for index, (pp, page) in enumerate(zip(pdf.pages, rendered), 1):
            raw = pp.obj
            trim_explicit, bleed_explicit = raw.get("/TrimBox"), raw.get("/BleedBox")
            # Use raw PDF user space for box subtraction, including UserUnit.
            unit = float(raw.get("/UserUnit", 1))
            trim = [float(x) for x in trim_explicit] if trim_explicit is not None else list(map(float,pp.mediabox))
            bleed = [float(x) for x in bleed_explicit] if bleed_explicit is not None else None
            sides = None
            if bleed is not None and trim_explicit is not None:
                sides = dict(left=(trim[0]-bleed[0])*unit/PT_PER_MM, bottom=(trim[1]-bleed[1])*unit/PT_PER_MM,
                             right=(bleed[2]-trim[2])*unit/PT_PER_MM, top=(bleed[3]-trim[3])*unit/PT_PER_MM)
            # Normalize to media viewport at rotation 0, only in-memory, never save.
            page.set_rotation(0)
            page.set_cropbox(page.mediabox)
            rect = fitz.Rect(trim)*page.transformation_matrix
            model["artboards"].append({"id":index,"name":f"PDF Page {index}","rect":list(rect),
                                        "bleed_mm":sides, "trim_explicit":trim_explicit is not None,
                                        "preview_rect":list(page.rect),"preview_rotation":0})
            if trim_explicit is None:
                model["limitations"].append(f"第 {index} 頁未宣告 TrimBox，尺寸暫用 MediaBox，成品尺寸無法確認。")
            page_text=[]
            for block in page.get_text("dict", flags=fitz.TEXTFLAGS_TEXT)["blocks"]:
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        text_object={"kind":"text","name":f"Text {len(model['objects'])+1}","artboard":index,
                            "bbox":list(span["bbox"]),"text":span["text"],"font":span["font"],
                            "font_size_pt":span["size"],"weight":"Bold" if span["flags"] & 16 else "unknown",
                            "bold":bool(span["flags"] & 16),"outlined":False,"missing_font":None,
                            "render_srgb":[((span["color"] >> shift)&255)/255 for shift in [16,8,0]],
                            "evidence":"PDF extracted text span; rendered RGB is not original process color"}
                        model["objects"].append(text_object);page_text.append(text_object)
            for info in page.get_image_info(xrefs=True):
                o = {"kind":"image", "name":f"Image xref {info['xref']} instance {len(model['objects'])+1}",
                     "artboard":index,"bbox":list(info["bbox"]),"pixels":[info["width"],info["height"]],
                     "image_transform":list(info["transform"]),"native_dpi":None,"link_state":"unknown","link_scope":"pdf_document","pdf_storage":"embedded",
                     "evidence":"PDF image occurrence transform; original AI link state unknown"}
                xref = info["xref"]
                try:
                    if not xref:
                        raise ValueError("Inline image / xref unavailable")
                    img = pdf.get_object((xref,0))
                    cs = img.get("/ColorSpace")
                    mode = str(cs)
                    if isinstance(cs, pikepdf.Array) and str(cs[0]) == "/ICCBased":
                        mode = {1:"/DeviceGray",3:"/DeviceRGB",4:"/DeviceCMYK"}.get(int(cs[1].get("/N",0)), "unknown")
                    o["color"] = {"space": {"/DeviceRGB":"RGB","/DeviceCMYK":"CMYK","/DeviceGray":"Gray"}.get(mode,"Unknown"), "pdf_space":str(cs)}
                    if mode != "/DeviceCMYK":
                        raise ValueError("Not a native CMYK image")
                    # Conservative: only direct 8-bit uncompressed/Flate samples,
                    # identity/default Decode. JPEG inversion and DeviceN are unknown.
                    filters = img.get("/Filter")
                    filters = list(filters) if isinstance(filters,pikepdf.Array) else [filters] if filters else []
                    if any(str(f) != "/FlateDecode" for f in filters):
                        raise ValueError("CMYK JPEG/other filter decoding is not validated by this engine")
                    if int(img.get("/BitsPerComponent",0)) != 8:
                        raise ValueError("Only 8-bit native CMYK sample TAC supported")
                    decode = img.get("/Decode")
                    if decode is not None and list(map(float,decode)) != [0,1]*4:
                        raise ValueError("Non-identity Decode requires manual analysis")
                    data = img.read_bytes()
                    w,h = int(img.Width),int(img.Height)
                    if len(data) != w*h*4:
                        raise ValueError("Unexpected decoded CMYK byte length")
                    o["tac_stats"] = raster_tac(Image.frombytes("CMYK",(w,h),data),rules["maximum_tac_percent"])
                    o["tac_reason"] = "原始 CMYK 像素（包含遮罩／裁切外像素）；不代表最終合成頁面。"
                except Exception as exc:
                    o["tac_reason"] = str(exc)
                model["objects"].append(o)
            # Path geometry: color values from get_drawings are converted RGB, so
            # preserve only geometry and explicitly avoid treating them as source RGB.
            for n, drawing in enumerate(page.get_drawings()):
                o = {"kind":"path","name":f"Rendered path {n+1}","artboard":index,"bbox":list(drawing["rect"]),
                     "evidence":"PDF rendered path geometry; original color is in raw paint events"}
                if drawing.get("color") is not None:
                    o["stroke_width_pt"] = drawing["width"]
                model["objects"].append(o)
            read_paints(pp, raw.get("/Resources", {}), index, model, set(), pikepdf, user_unit=unit)
            resolve_simple_contrast(page,page_text,model,index)
    return model


def resolve_simple_contrast(page,text_objects,model,board):
    """Only flat, non-overprinted opaque preview colors and a proven flat backdrop.

    Ratios refer to the renderer's RGB screen interpretation, never printed ink.
    Reject effects, complex shading, ambiguous order, strokes and later overlaps.
    """
    import pymupdf as fitz
    paints=[o for o in model["objects"] if o.get("artboard")==board and o.get("evidence","").startswith("PDF content")]
    if any(o.get("opacity",100)<100 or o.get("opacity_mask") or o.get("overprint_fill") or o.get("overprint_stroke") or
           o.get("blend_mode","Normal") not in ["Normal","/Normal"] for o in paints):
        return
    if any(c.get("space") not in ["CMYK","RGB","Gray","None"] for o in paints for c in [o.get("fill",{}),o.get("stroke",{})] if c):
        return
    drawings={d["seqno"]:d for d in page.get_drawings()}
    log=page.get_bboxlog();traces=page.get_texttrace()
    for o in text_objects:
        matches=[t for t in traces if t["type"]==0 and t.get("opacity",1)==1 and
                 "".join(chr(c[0]) for c in t["chars"])==o["text"] and fitz.Rect(t["bbox"]).intersects(fitz.Rect(o["bbox"]))]
        if len(matches)!=1:
            continue
        trace=matches[0];seq=trace["seqno"];box=fitz.Rect(trace["bbox"])
        if trace["colorspace"] not in [1,3]:
            continue
        # A clipping path, transparency group or unsupported paint invalidates inference.
        if any(d.get("type") in ["clip","group"] for d in page.get_drawings(extended=True)):
            continue
        if any(fitz.Rect(b).intersects(box) for typ,b in log[seq+1:]):
            continue
        bg=[1,1,1];verified=True
        for n in range(seq-1,-1,-1):
            typ,b=log[n]
            if not fitz.Rect(b).intersects(box):
                continue
            d=drawings.get(n)
            if typ!="fill-path" or not d or d.get("fill") is None or d.get("fill_opacity",1)!=1 or len(d["items"])!=1:
                verified=False;break
            item=d["items"][0]
            if item[0]!="re" or not fitz.Rect(item[1]).contains(box):
                verified=False;break
            bg=list(d["fill"]);break
        if verified:
            fg=list(trace["color"])
            if len(fg)==1:
                fg*=3
            o["contrast_pair"]={"foreground":fg,"background":bg,"color_space":"sRGB","background_type":"solid","verified":True,
                                "evidence":"Opaque PDF text trace + ordered flat rectangle/background; renderer RGB treated as sRGB for screen-reference only, not print proof"}
            o["reverse"]=min(fg)>.95 and max(bg)<.5


def read_paints(stream, resources, board, model, active, pikepdf, initial=None, depth=0, user_unit=1):
    """Track PDF graphics state and native paint colors, recurse Form resources.

    This is not a full PDF renderer: geometry/text sizing is not fabricated.
    """
    if depth > 30:
        model["limitations"].append("PDF Form 深度超限，部分內容未分析。")
        return
    import math
    def mult(a,b):
        return [a[0]*b[0]+a[2]*b[1],a[1]*b[0]+a[3]*b[1],a[0]*b[2]+a[2]*b[3],a[1]*b[2]+a[3]*b[3]]
    state = copy.deepcopy(initial) if initial else {"fill":{"space":"Gray","values":[0]},"stroke":{"space":"Gray","values":[0]},
             "overprint_fill":False,"overprint_stroke":False,"opacity":100,"blend_mode":"Normal",
             "ctm":[user_unit,0,0,user_unit],"text_matrix":[1,0,0,1],"text_render_mode":0,"fill_alpha":1,"stroke_alpha":1}
    stack = []
    try:
        instructions = pikepdf.parse_content_stream(stream)
        for instruction in instructions:
            if not hasattr(instruction, "operator"):
                continue
            operands, operator = instruction.operands, str(instruction.operator)
            if operator == "q":
                stack.append(copy.deepcopy(state))
            elif operator == "Q":
                if stack:
                    state = stack.pop()
            elif operator == "cm":
                state["ctm"]=mult(state["ctm"],list(map(float,operands[:4])))
            elif operator == "BT":
                state["text_matrix"]=[1,0,0,1]
            elif operator == "Tm":
                state["text_matrix"]=list(map(float,operands[:4]))
            elif operator == "Tf":
                state["font_ref"]=str(operands[0]);state["font_size"]=float(operands[1])
            elif operator == "Tr":
                state["text_render_mode"]=int(operands[0])
            elif operator in ["k","K","rg","RG","g","G"]:
                key = "stroke" if operator.isupper() else "fill"
                space = "CMYK" if operator.lower() == "k" else "RGB" if operator.lower() == "rg" else "Gray"
                state[key] = {"space":space,"values":[float(x)*(100 if space == "CMYK" else 1) for x in operands]}
            elif operator in ["cs","CS"]:
                key = "fill" if operator == "cs" else "stroke"
                name = str(operands[0])
                cs = resources.get("/ColorSpace",{}).get(name,operands[0])
                if isinstance(cs,pikepdf.Array) and str(cs[0]) in ["/Separation","/DeviceN"]:
                    state[key] = {"space":"Spot","name":str(cs[1]),"pdf_space":str(cs[0])}
                else:
                    state[key] = {"space": {"/DeviceCMYK":"CMYK","/DeviceRGB":"RGB","/DeviceGray":"Gray"}.get(str(cs),"Unknown"),"pdf_space":str(cs)}
            elif operator in ["sc","SC","scn","SCN"]:
                key = "stroke" if operator.isupper() else "fill"
                color = state[key]
                try:
                    color["values"] = [float(x)*(100 if color["space"] == "CMYK" else 1) for x in operands]
                except (ValueError,TypeError):
                    color["values"] = None
            elif operator == "gs":
                gs = resources.get("/ExtGState",{}).get(operands[0],{})
                for pdfkey,outkey in [("/op","overprint_fill"),("/OP","overprint_stroke")]:
                    if pdfkey in gs:
                        state[outkey] = bool(gs[pdfkey])
                if "/OP" in gs and "/op" not in gs:
                    state["overprint_fill"] = bool(gs["/OP"])
                if "/ca" in gs:
                    state["fill_alpha"]=float(gs["/ca"])
                if "/CA" in gs:
                    state["stroke_alpha"]=float(gs["/CA"])
                state["opacity"]=min(state["fill_alpha"],state["stroke_alpha"])*100
                if "/BM" in gs:
                    state["blend_mode"] = str(gs["/BM"])
                if "/SMask" in gs:
                    state["opacity_mask"] = str(gs["/SMask"]) != "/None"
            elif operator == "Do":
                form = resources.get("/XObject",{}).get(operands[0])
                if form is not None and str(form.get("/Subtype")) == "/Form":
                    identity = tuple(form.objgen)
                    if identity not in active:
                        child=copy.deepcopy(state)
                        child["ctm"]=mult(state["ctm"],list(map(float,form.get("/Matrix",[1,0,0,1,0,0])[:4])))
                        read_paints(form,form.get("/Resources",resources),board,model,active|{identity},pikepdf,child,depth+1)
                    else:
                        model["limitations"].append("循環 Form 引用已略過。")
            elif operator in ["f","F","f*","S","s","B","B*","b","b*","Tj","TJ","'",'"']:
                istext=operator in ["Tj","TJ","'",'"']
                if istext and state["text_render_mode"] in [3,7]:
                    continue
                o = {"kind":"paint","name":f"PDF paint event {len(model['objects'])+1}","artboard":board,
                     "evidence":"PDF content operators; no proven object bounding box", **copy.deepcopy(state)}
                if istext:
                    font=resources.get("/Font",{}).get(state.get("font_ref"),{}) if state.get("font_ref") else {}
                    matrix=mult(state["ctm"],state["text_matrix"])
                    size=abs(state.get("font_size",0))*math.hypot(matrix[2],matrix[3])
                    o.update(kind="text",font_size_pt=size if size and str(font.get("/Subtype"))!="/Type3" else None,
                             font=str(font.get("/BaseFont","unknown")),missing_font=None,outlined=False,
                             text="[PDF encoded text; content shown in extracted text spans]",weight="unknown")
                if operator in ["f","F","f*"] or istext and state["text_render_mode"] in [0,4]:
                    o.pop("stroke",None)
                elif operator in ["S","s"] or istext and state["text_render_mode"] in [1,5]:
                    o.pop("fill",None)
                model["objects"].append(o)
            elif operator == "sh":
                model["limitations"].append(f"第 {board} 頁 Shading／漸層內部顏色與 TAC 未解析。")
    except Exception as exc:
        model["limitations"].append(f"第 {board} 頁部分 content stream 未解析：{type(exc).__name__}: {exc}")


def render_pdf(path, output, dpi):
    import pymupdf as fitz
    paths = []
    with fitz.open(path) as pdf:
        for i,page in enumerate(pdf,1):
            page.set_rotation(0)
            page.set_cropbox(page.mediabox)
            target = Path(output)/f"artboard-{i:02d}-original.png"
            page.get_pixmap(dpi=dpi,colorspace=fitz.csRGB,alpha=False).save(target)
            paths.append(target)
    return paths
