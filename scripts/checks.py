"""Evidence-based checks over the common inspector model."""
import re
from metrics import PT_PER_MM, effective_ppi, tac, contrast, simulate, delta_e76


def analyze(doc, rules, access, scope="all"):
    findings, special = [], []
    scopes = {"digital": {"document", "text", "images", "color"}, "all": {"document", "text", "images", "color", "tac", "accessibility"},
              "text": {"text"}, "images": {"images"}, "color": {"color", "tac"},
              "tac": {"tac"}, "accessibility": {"accessibility"}}
    selected = scopes[scope]

    def emit(code, status, title, obj=None, current=None, expected=None,
             reason="", fix="請在 Illustrator 檢查對應物件，並與印刷廠確認。", group="prepress", category="document"):
        if category not in selected:
            return
        if scope == "digital" and code not in {
            "ai_version", "ai_creator_version", "black_coverage", "multichannel_black", "small_multichannel_black", "k_black", "large_black", "thin_multichannel", "dimensions", "bleed", "bleed_artwork", "uniform_artboards", "coverage",
            "document_color_space", "rgb", "color_mode", "color_unknown", "spot",
            "font_missing", "text_type", "outline_summary", "image_link", "image_embedding_summary", "image_ppi",
            "font_size", "small_reverse_four", "safe_margin", "thin_line", "white_overprint", "overprint",
            "required_pdf_x", "required_pdf_version", "required_icc_profile", "printer_manual"
        }:
            return
        # Objects without overprint are not findings in the digital report; keep only overprint warnings.
        if scope == "digital" and code == "overprint" and status == "green":
            return
        o = obj or {}
        findings.append(dict(id=f"Issue {len(findings)+1:03d}", code=code, status=status,
                             title=title, group=group, artboard=o.get("artboard"),
                             object=o.get("name", "文件"), bbox=o.get("bbox"),
                             current=current, expected=expected, reason=reason, fix=fix,
                             evidence=o.get("evidence", doc.get("engine", "unknown"))))

    if str(doc.get("source", "")).lower().endswith(".ai") or doc.get("ai_version"):
        version = doc.get("ai_version", {})
        maximum = rules["maximum_ai_major_version"]
        saved = version.get("saved_major") if version.get("saved_version_verified") is True and version.get("saved_version_evidence") else None
        emit("ai_version", "unknown" if saved is None else "yellow" if saved > maximum else "green",
             "AI 儲存相容版本", current=version, expected={"maximum_major": maximum, "default_reference": "CS6 = 16"},
             reason="建立軟體、PDF 版本、ContainerVersion 與 RoundtripVersion 不等於已驗證的 AI 儲存相容版本；綠燈亦不保證機台支援。",
             fix="向廠商確認接收版本；必要時經確認另存舊版副本，再開啟比對外觀。舊版可能遺失效果，不自動降版。")
        creator = version.get("creator_major")
        if creator is not None and creator > maximum:
            emit("ai_creator_version", "yellow", "AI 建立軟體比指定舊版新：請確認相容性", current=version,
                 expected=maximum, reason="這是建立來源警示，不能據此認定檔案未另存成 CS6。",
                 fix="核對另存時的 Illustrator 版本選項，或以廠商舊版軟體開啟副本驗證。")
    emit("black_coverage", "unknown", "四色黑檢查範圍與限制",
         reason="只檢查可靠取得的 CMYK 填色與筆畫。外框字無法還原字級；圖片、漸層、圖樣與最終 RIP 分色未完整判定，不能宣稱全檔沒有四色黑。",
         fix="在 Illustrator 分色預視／顏色面板檢查黑字及細線；必要時由廠商檢查最終分色。", category="color")

    if scope == "digital":
        live = [o for o in doc.get("objects", []) if o.get("kind") == "text" and not o.get("outlined")]
        emit("outline_summary", "red" if live and rules["require_outlined_text"] else "yellow" if live else "unknown",
             "文字外框狀態", current="仍有可編輯文字" if live else "未取得足以證明全部文字已外框的證據",
             expected="依數位印刷廠交付規格確認外框或字型嵌入要求",
             reason="沒有偵測到文字不等於全部已外框；不能從一般路徑還原原始字型。",
             fix="在 Illustrator 檢查文字物件；廠商要求外框時另存副本後處理，不修改原稿。", category="text")
    def embedding_state(o):
        # PDF image storage is never proof of the editable AI's link state.
        if doc.get("engine", "").startswith("PDF") or o.get("link_scope") in ["pdf_document", "standalone_raster"]:
            return "unknown"
        state = o.get("link_state", "unknown")
        return state if state in ["embedded", "linked", "missing"] else "unknown"

    images = [o for o in doc.get("objects", []) if o.get("kind") == "image"]
    totals = {s: sum(embedding_state(o) == s for o in images) for s in ["embedded", "linked", "missing", "unknown"]}
    # AI header %%DocumentFiles lists external links even when only the PDF-compatible content is readable.
    linked_files = doc.get("ai_document_files") or []
    header = {s: sum(f["state"] == s for f in linked_files) for s in ["linked", "missing"]}
    for f in linked_files:
        emit("image_link", "red" if f["state"] == "missing" else "yellow",
             "連結檔遺失：找不到原始檔" if f["state"] == "missing" else "圖片未嵌入：使用外部連結",
             {"name": f["name"], "artboard": None, "evidence": "AI 檔頭 %%DocumentFiles（Illustrator 記錄的外部連結清單）"},
             {"state": f["state"], "path": f["path"], "found_at": f["found_at"]}, "已嵌入，或連結檔與 AI 一起交付",
             "AI 記錄了這個外部連結檔。" + ("在記錄路徑、AI 同資料夾與 Links 資料夾都找不到；送印時圖片可能變成低解析預覽或空白。只檢查這台電腦，換電腦執行時路徑可能不同。" if f["state"] == "missing" else "交付 AI 時需附上原圖或封裝，否則印刷廠開檔會缺圖。"),
             "視窗 > 連結：找到這個檔名，" + ("重新連結正確檔案" if f["state"] == "missing" else "依印刷廠要求封裝或嵌入（在副本操作）") + "。檔頭不記錄位置，需在連結面板定位。",
             category="images")
    status = "red" if totals["missing"] or header["missing"] else "yellow" if totals["linked"] or header["linked"] else "unknown" if totals["unknown"] or not images else "green"
    current = {"placement_counts": totals}
    if doc.get("ai_document_files") is not None:
        current["ai_header_links"] = header
    emit("image_embedding_summary", status, "原 AI 圖片嵌入／連結總覽", current=current,
         expected="已嵌入，或依印刷廠要求完整封裝外部連結圖",
         reason="計數為放置事件，跨 Artboard 或重複使用可能重複列出。PDF 內有圖片不代表原 AI 已嵌入；未取得圖片也不能證明全部已嵌入。",
         fix="Illustrator > 視窗 > 連結，或在原生文件副本執行 illustrator_inspector.jsx；確認嵌入、連結與遺失狀態。", category="images")
    boards = {b["id"]: b for b in doc.get("artboards", [])}
    sizes = []
    for b in boards.values():
        o = dict(name=b.get("name", f"Artboard {b['id']}"), artboard=b["id"])
        rect = b["rect"]
        size = [(rect[2]-rect[0])/PT_PER_MM, (rect[3]-rect[1])/PT_PER_MM]
        sizes.append(size)
        bleed = b.get("bleed_mm")
        status, title, current, reason = size_verdict(size, bleed, rules)
        if b.get("trim_explicit") is False:
            status, reason = "unknown", "PDF 未宣告 TrimBox，暫用 MediaBox；不能確認成品尺寸。" + reason
        emit("dimensions", status, title, o, current, rules["target_size_mm"] or "未指定成品尺寸", reason,
             "物件 > 工作區域 > 工作區域選項：核對寬高；出血在「檔案 > 文件設定」另外設定，不要做進工作區域。")
        emit("bleed", "unknown" if bleed is None else "red" if min(bleed.values()) < rules["bleed_mm"]-1e-6 else "green",
             "出血框：上、下、左、右", o, bleed, rules["bleed_mm"],
             "缺少可靠出血資料時不可用 MediaBox 或物件外觀猜測出血。", "文件設定 > 出血；輸出 PDF 後核對 TrimBox、BleedBox。")
        emit("bleed_artwork", "unknown", "圖像是否實際延伸至出血", o, reason="出血框合格不等於四邊滿版內容足夠。", fix="開啟裁切與出血參考線，逐邊檢查滿版圖像。")
    if len(sizes) > 1:
        same = all(all(abs(x-y) <= rules["size_tolerance_mm"] for x,y in zip(sizes[0], s)) for s in sizes[1:])
        emit("uniform_artboards", "green" if same else "red" if rules["require_uniform_artboards"] else "yellow",
             "多 Artboard 尺寸一致性", current=sizes, expected="一致" if rules["require_uniform_artboards"] else "依工作需求確認", reason="包裝或多品項可能刻意使用不同尺寸。")
    if doc.get("document_color_space"):
        emit("document_color_space", "yellow" if "RGB" in doc["document_color_space"] else "green", "文件色彩模式與尺標單位",
             current={"mode":doc["document_color_space"],"ruler_units":doc.get("ruler_units")},expected=rules["preferred_color_mode"],category="color",reason="文件模式不保證所有連結圖或色票皆為同一色彩模式。")

    for limitation in doc.get("limitations", []):
        emit("coverage", "unknown", limitation, category="document", reason="擷取器未提供足夠證據。")
    emit("semantic_inventory", "unknown", "Logo、QR Code、重要資訊與圖形的辨識完整性", reason="未經語意標註，無法保證所有重要物件都納入安全邊界檢查。")
    for key in ["required_pdf_x", "required_pdf_version", "required_icc_profile"]:
        expected = rules.get(key)
        if expected:
            observed = doc.get("metadata", {}).get(key.removeprefix("required_"))
            # Matching an identifier is not conformance proof.
            emit(key, "unknown" if observed is None else "yellow" if str(expected) in str(observed) else "red",
                 "輸出規格："+key, current=observed, expected=expected,
                 reason="PDF/X 標籤、版本與 ICC 名稱僅是宣告，仍須專用驗證器確認實際合規。")

    has_rgb = has_spot = has_transparency = False
    for o in doc.get("objects", []):
        kind = o.get("kind")
        cat = "text" if kind == "text" else "images" if kind == "image" else "color"
        colors = [(k, o[k]) for k in ["fill", "stroke"] if o.get(k)]
        if o.get("color"):
            colors.append(("image", o["color"]))
        for channel, color in colors:
            mode, values = color.get("space"), color.get("values")
            if mode == "CMYK" and values and values[3] >= rules["black_k_threshold"] and any(v > 0 for v in values[:3]):
                four = all(v > 0 for v in values)
                risky_text = kind == "text" and o.get("font_size_pt") is not None and o["font_size_pt"] <= rules["small_black_text_max_pt"]
                emit("multichannel_black", "red" if risky_text else "yellow",
                     ("四色黑" if four else "混色黑（非單 K）") + "：" + channel, o,
                     {"CMYK": values, "channel": channel, "size_pt": o.get("font_size_pt")},
                     "小字／細線依廠商要求採單 K；大面積黑色配方需確認",
                     "K 達黑色候選門檻且混入 CMY；深色可能為刻意設計。外框路徑不推算字級；未使用色票不等於實際印刷物件。",
                     "在顏色面板檢查物件填色與筆畫；不要直接改所有黑色。", category="text" if kind == "text" else "color")
            if mode == "RGB":
                has_rgb = True
                emit("rgb", "yellow", "發現 RGB："+channel, o, color, rules["preferred_color_mode"], "印刷轉換可能改變色彩；不要自動轉 CMYK。", "檢查文件色彩模式、連結圖片與色票；與印刷廠確認轉換設定。", category="color")
            elif mode in ["CMYK", "Gray", "Lab"]:
                emit("color_mode", "green", "已辨識色彩空間："+mode, o, color, reason="只確認色彩空間，不代表色彩輸出正確。", category="color")
            elif mode not in ["Spot", "None"]:
                emit("color_unknown", "unknown", "色彩來源無法完整解析", o, color, category="color")
            if mode == "Spot":
                has_spot = True
                emit("spot", "yellow" if rules["allow_spot_colors"] else "red", "發現特別色，請確認是否為預期印刷設定", o, color, category="color", reason="特別色名稱不代表已核對 Pantone 實體色票。")
            if mode == "CMYK" and values is not None:
                total = tac(values)
                emit("tac", ("yellow" if kind == "swatch" else "red") if total > rules["maximum_tac_percent"] else "green", "物件總墨量 TAC："+channel, o,
                     {"CMYK": values, "TAC": total, "excess": max(0, total-rules["maximum_tac_percent"])},
                     rules["maximum_tac_percent"], "C + M + Y + K；不含透明度疊加或 RIP 最終分色。色票清單可能包含未使用色。", "檢查色票／顏色面板，依紙材與印刷廠指定配方調整副本。", category="tac")
            white = (mode == "CMYK" and values == [0,0,0,0]) or (mode == "RGB" and values == [1,1,1]) or (mode == "Gray" and values == [1])
            op = o.get("overprint_"+channel)
            if op is not None:
                emit("white_overprint" if white and op else "overprint", "red" if white and op else "yellow" if op else "green",
                     "白色物件設定疊印：高風險" if white and op else "疊印設定："+channel, o,
                     {"overprint": op, "color": color}, reason="製程白墨特別色不等於 process white；白色疊印可能消失。", fix="視窗 > 屬性：檢查填色／筆畫疊印；以分色預覽核對。", category="color")

        name_text = " ".join(str(o.get(k, "")) for k in ["name", "layer"])
        name_text += " " + " ".join(str(c.get("name", "")) for _,c in colors)
        matches = [k for k in rules["special_process_keywords"] if (re.search(r"(?<![a-z])"+re.escape(k.lower())+r"(?![a-z])", name_text.lower()) if k.isascii() else k in name_text)]
        if matches:
            special.append({"object": o.get("name"), "artboard": o.get("artboard"), "matches": matches, "note": "名稱候選；請確認加工版、疊印與廠商要求。"})
        for k in ["hidden", "locked", "non_printing"]:
            if o.get(k):
                emit(k, "yellow", "隱藏／鎖定／非列印項目："+k, o, True, category=cat)
        transparency = o.get("opacity", 100) < 100 or o.get("blend_mode", "Normal").lower() not in ["normal", "blendmodes.normal", "/normal"] or o.get("opacity_mask") is True
        if transparency:
            has_transparency = True
            emit("transparency", "yellow", "透明度與混合模式：確認 RIP／PDF 相容性", o,
                 {k:o.get(k) for k in ["opacity", "blend_mode", "opacity_mask"]}, category="color",
                 fix="透明度面板與 PDF 輸出設定中檢查；不要直接平面化。")

        if o.get("important") or kind == "text":
            b, r = boards.get(o.get("artboard")), o.get("bbox")
            distance = None
            if b and r:
                t = b["rect"]
                distance = min(r[0]-t[0], r[1]-t[1], t[2]-r[2], t[3]-r[3])/PT_PER_MM
            emit("safe_margin", "unknown" if distance is None else "yellow" if distance < rules["safe_margin_mm"] else "green", "重要物件最近安全距離（mm）", o, distance, rules["safe_margin_mm"], "依物件包圍盒計算；剪裁、字框與實際字形邊緣可能不同。", "開啟尺標與裁切參考線，將重要內容移入安全距離。", category="text" if kind == "text" else "document")

        size = o.get("font_size_pt")
        small = kind == "text" and size is not None and size < rules["minimum_font_size_pt"]
        fill = o.get("fill", {})
        cmyk = fill.get("values") if fill.get("space") == "CMYK" else None
        multi_black = cmyk is not None and cmyk[3] >= rules["black_k_threshold"] and any(v > 0 for v in cmyk[:3])
        if kind == "text":
            missing = o.get("missing_font")
            emit("font_missing", "unknown" if missing is None else "red" if missing else "green", "缺字型檢查", o, missing,
                 reason="目前可存取的字型不保證原檔未發生替代；需原字型證據或 Illustrator 開檔警告。", category="text")
            outlined = o.get("outlined")
            emit("text_type", "green" if outlined else "red" if rules["require_outlined_text"] else "yellow", "已建立外框" if outlined else "Live Text：確認印刷廠交付規定", o,
                 expected="需外框" if rules["require_outlined_text"] else "依印刷廠規格", fix="確認字型授權、封裝與印刷廠需求；本工具不自動建立外框。", category="text")
            emit("font_size", "unknown" if size is None else "yellow" if small else "green", "文字尺寸過小" if small else "文字尺寸", o,
                 {"text": o.get("text", "")[:30], "font": o.get("font"), "weight": o.get("weight"), "size_pt": size, "color": fill, "reverse": o.get("reverse")}, rules["minimum_font_size_pt"],
                 "外框無法回推原始字級；印刷可讀性受紙材、印刷方式、網點與觀看距離影響。", "文字 > 字元：檢查字級，依需求調整副本；不要自動放大。", category="text")
            if size is not None and size <= rules["small_black_text_max_pt"] and cmyk and cmyk[3] >= rules["black_k_threshold"]:
                emit("small_multichannel_black" if multi_black else "k_black", "red" if multi_black else "green", "小字套印風險" if multi_black else "小型黑字使用單 K", o, cmyk, "C0 M0 Y0 K100（依廠商規格）", "多版套印誤差可能產生彩邊。", "顏色面板檢查文字填色，與印刷廠確認小字黑色配方。", category="text")
            if small and o.get("reverse") and o.get("background_cmyk") and all(v > 0 for v in o["background_cmyk"]):
                emit("small_reverse_four", "red", "小字反白＋四色背景：高印刷可讀性風險", o, category="text", reason="細小反白字容易因套印與網點擴大而糊合。")
            pair = o.get("contrast_pair")
            ratio = None
            limit = access["contrast_normal"]
            if size is not None and (size >= access["large_text_pt"] or o.get("bold") is True and size >= access["large_bold_text_pt"]):
                limit = access["contrast_large"]
            if "accessibility" in selected and pair and pair.get("verified") and pair.get("evidence") and pair.get("color_space") == "sRGB" and pair.get("background_type") == "solid":
                ratio = contrast(pair["foreground"], pair["background"])
            emit("contrast", "unknown" if ratio is None else "yellow" if ratio < limit else "green", "文字／背景 Contrast Ratio", o,
                 {"ratio": ratio, "pair": pair, "size_pt": size, "weight": o.get("weight")}, limit,
                 "僅在前景、背景、sRGB 定義與實際合成可靠時計算；複雜背景不得判通過。", "增加前景／背景明度差，或為文字加不透明底色；列印打樣確認。", group="accessibility", category="accessibility")
            thin = any(k in str(o.get("weight", "")).lower() for k in access["thin_weight_keywords"])
            if small and ratio is not None and ratio < limit:
                emit("small_low_contrast", "red", "小字＋低對比"+("＋細字重" if thin else "")+"：高可讀性風險", o,
                     {"size":size, "weight":o.get("weight"), "contrast":ratio}, reason="小字、細筆畫與低對比會共同降低辨識度。", group="accessibility", category="accessibility")
            if small and o.get("cvd_difficult") and ratio is not None and ratio < limit:
                emit("small_cvd", "red", "小字＋低對比＋色覺辨識困難", o, group="accessibility", category="accessibility")

        width = o.get("stroke_width_pt")
        if width is not None:
            thin = width < rules["minimum_line_width_pt"]
            stroke = o.get("stroke", {})
            white = stroke.get("space") == "CMYK" and stroke.get("values") == [0,0,0,0] or stroke.get("space") == "RGB" and stroke.get("values") == [1,1,1]
            emit("thin_line", "red" if thin and (white or o.get("reverse") or matches) else "yellow" if thin else "green", "細線（含 0 pt hairline）" if thin else "線寬", o, width, rules["minimum_line_width_pt"], "白色、反白與加工細線需要提高警示。", "筆畫面板檢查線寬；特殊加工線先與廠商核對。", category="color")
            if thin and stroke.get("space") == "CMYK" and sum(v > 0 for v in stroke["values"]) > 1:
                emit("thin_multichannel", "yellow", "細線＋多色版：套印偏移風險", o, category="color")
        if cmyk and cmyk[3] >= rules["black_k_threshold"] and o.get("bbox") and kind != "text":
            r = o["bbox"]
            if (r[2]-r[0])*(r[3]-r[1])/PT_PER_MM**2 >= rules["large_black_area_mm2"]:
                emit("large_black", "yellow", "大面積黑色候選：請確認是否需要 Rich Black", o, cmyk, reason="以包圍盒篩選，並非實際填色面積；不可擅改配方。", category="color")

        if kind == "image":
            state = embedding_state(o)
            titles = {"embedded": "圖片已嵌入（原生資料）", "linked": "圖片未嵌入：使用外部連結", "missing": "圖片連結遺失", "unknown": "無法確認原 AI 圖片是否嵌入"}
            emit("image_link", {"missing":"red", "linked":"yellow", "embedded":"green"}.get(state, "unknown"), titles[state], o,
                 {"state":state, "path":o.get("path"), "layer":o.get("layer"), "evidence_scope":o.get("link_scope",doc.get("engine")), "pdf_storage":o.get("pdf_storage")},
                 reason="外部連結不等於遺失；交付 AI 時需確認附圖、封裝或嵌入。PDF 內嵌只代表 PDF 本身，不證明原 AI 狀態。",
                 fix="視窗 > 連結：定位此圖片並檢查狀態。遺失者重新連結；未嵌入者依廠商要求封裝，或另存副本後嵌入；本工具不自動修改。", category="images")
            ppi = o.get("effective_ppi")
            if not ppi and o.get("pixels") and o.get("image_transform"):
                try:
                    ppi = effective_ppi(o["pixels"], o["image_transform"])
                except ValueError:
                    ppi = None
            minimum = ppi.get("minimum") if ppi else None
            status = "unknown" if minimum is None else "green" if minimum >= rules["minimum_image_ppi"]-1e-6 else "yellow" if minimum >= rules["image_warning_ppi"]-1e-6 else "red"
            native = o.get("native_dpi")
            scale = [native[i]/ppi[k]*100 for i,k in enumerate(["x","y"])] if native and ppi else None
            emit("image_ppi", status, "圖片 Effective PPI", o,
                 {"pixels":o.get("pixels"), "original_dpi":native, "effective_ppi":ppi, "scale_percent":scale, "link":state}, rules["minimum_image_ppi"],
                 "像素數除以實際置入英吋；旋轉不使用軸向包圍盒，剪切另採最低主方向解析度。", "連結面板核對有效 PPI，替換高解析圖片或縮小置入尺寸。", category="images")
            stats = o.get("tac_stats")
            emit("raster_tac", "unknown" if stats is None else "red" if stats["maximum"] > rules["maximum_tac_percent"] else "green", "圖片內部 TAC", o, stats, rules["maximum_tac_percent"],
                 o.get("tac_reason", "僅分析原始 CMYK 樣本；不包含透明度、疊印與最終分色。"), category="tac")

    if has_rgb and has_spot and has_transparency:
        emit("mixed_output", "yellow", "RGB＋Spot Color＋Transparency：輸出前需確認色彩與透明度處理", category="color")
    for pair in (doc.get("semantic_pairs", []) if "accessibility" in selected else []):
        a, b = dict(pair["a"]), dict(pair["b"])
        for c in [a,b]:
            if c.get("srgb") is not None:
                c["RGB"]=[round(v*255) for v in c["srgb"]]
                c["HEX"]="#"+"".join(f"{v:02X}" for v in c["RGB"])
                c.setdefault("CMYK",None)
        affected = {}
        if pair.get("verified") and pair.get("evidence") and a.get("srgb") is not None and b.get("srgb") is not None:
            for label, kind in [("Protanopia","protanomaly"),("Deuteranopia","deuteranomaly"),("Tritanopia","tritanomaly")]:
                de = delta_e76(simulate(a["srgb"],kind,access["cvd_severity"]), simulate(b["srgb"],kind,access["cvd_severity"]))
                affected[label] = de
            risk = any(v < access["color_pair_delta_e76_warning"] for v in affected.values())
            emit("color_pair", "yellow" if risk else "green", "資訊色彩辨識風險篩選", pair,
                 {"A":a,"B":b,"simulated_delta_e76":affected}, access["color_pair_delta_e76_warning"],
                 "ΔE76 為可調啟發式篩選，不是可辨識性或無障礙合規認證。", "加入文字、Icon、形狀、線型、Pattern 或 Label。", group="accessibility", category="accessibility")
        else:
            emit("color_pair", "unknown", "資訊色彩對缺少可驗證的 sRGB 值", pair, group="accessibility", category="accessibility")
        redundant = pair.get("non_color_cue")
        emit("color_only", "unknown" if redundant is None else "green" if redundant else "yellow", "資訊是否僅透過色彩傳遞", pair,
             redundant, "文字／Icon／形狀／Pattern", "語意需人工或可靠標註核對，不能只看色票推定。", "紅色加驚嘆號、綠色加勾勾，並補上文字標籤。", group="accessibility", category="accessibility")
    if not doc.get("semantic_pairs"):
        emit("semantic_color", "unknown", "圖表、圖例與狀態是否只靠顏色", reason="未取得具資訊意義的色彩對與非色彩線索標註。", fix="人工確認色彩語意後，加入 semantic_pairs 證據再計算。", group="accessibility", category="accessibility")
    for req in doc.get("manual_requirements", []):
        emit("printer_manual", "unknown", "印刷廠其他完稿要求", current=req, reason="此要求需人工確認；不因未實作而忽略。")
    return findings, special


COMMON_SIZES = {"A3": (297, 420), "A4": (210, 297), "A5": (148, 210), "A6": (105, 148), "B5": (182, 257),
                "16K": (195, 270), "8K": (270, 390), "名片": (90, 54), "名片（日式）": (91, 55), "明信片": (148, 100)}


def size_verdict(size, bleed, rules):
    """Compare an Artboard with the finished size; catch bleed built into the Artboard and swapped orientation."""
    tol, need, target = rules["size_tolerance_mm"], rules["bleed_mm"], rules["target_size_mm"]
    w, h = (round(v, 2) for v in size)
    current = {"artboard_mm": [w, h]}
    if bleed is not None:
        current["with_bleed_mm"] = [round(w+bleed["left"]+bleed["right"], 2), round(h+bleed["top"]+bleed["bottom"], 2)]
    has_bleed = bleed is not None and max(bleed.values()) > 1e-6

    def match(a, b):
        return all(abs(x-y) <= tol for x, y in zip(a, b))

    def grown(t):
        return [t[0]+2*need, t[1]+2*need]

    if not target:
        hints = []
        for name, t in COMMON_SIZES.items():
            for label, shape in [("", t), ("（橫式）", t[::-1])]:
                if match(size, shape):
                    hints.append(f"{name}{label} {shape[0]}×{shape[1]}")
                elif match(size, grown(shape)):
                    hints.append(f"{name}{label} {shape[0]}×{shape[1]} 含四邊 {need:g} mm 出血")
        current["looks_like"] = hints or None
        return ("unknown", "文件尺寸：未指定成品尺寸，請自行確認", current,
                "沒有成品尺寸可比對；請對照印刷廠或客戶需求。" + ("尺寸看起來是：" + "、".join(hints) + "。" if hints else ""))
    t = list(target)
    current["target_mm"] = t
    if match(size, t):
        return "green", "成品尺寸符合", current, "工作區域等於成品尺寸。"
    if match(size, t[::-1]):
        return "yellow", "尺寸符合但方向相反（直式／橫式）", current, "寬高互換；請確認版面方向是否正確。"
    if match(size, grown(t)) or match(size, grown(t[::-1])):
        if has_bleed:
            return ("red", "出血重複：工作區域已含出血，又另外設了出血", current,
                    f"工作區域 = 成品 + 四邊 {need:g} mm，文件又另設出血；輸出後成品會多一圈，裁切位置錯誤。")
        return ("yellow", "工作區域含出血：成品 = 工作區域 − 四邊出血", current,
                f"工作區域比成品大四邊 {need:g} mm，看起來把出血做進版面。有些印刷廠接受，但需另外標示裁切線；建議工作區域設成成品尺寸、出血另外設定。")
    diff = [round(x-y, 2) for x, y in zip(size, t)]
    current["difference_mm"] = diff
    return "red", "成品尺寸不符", current, f"工作區域與成品尺寸相差 寬 {diff[0]:+g} mm、高 {diff[1]:+g} mm。"
