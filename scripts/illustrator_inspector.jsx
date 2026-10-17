/* Prepress Manager｜印前管理員 — read-only active-document inspector, ExtendScript ES3.
 * No save(), saveAs(), outline(), embed(), flatten(), or object mutation.
 * Run File > Scripts > Other Script after opening a COPY of the artwork.
 */
(function () {
    if (!app.documents.length) { alert("請先在 Illustrator 開啟欲檢查的檔案副本。"); return; }
    var doc = app.activeDocument;
    var parent = Folder.selectDialog("選擇健檢輸出資料夾（不修改 AI）");
    if (!parent) return;
    var folder = new Folder(parent.fsName + "/illustrator-inspection-" + new Date().getTime());
    if (folder.exists || !folder.create()) { alert("無法建立全新輸出資料夾。"); return; }
    function get(o,k,fallback) { try { var v=o[k]; return v === undefined ? fallback : v; } catch(e) { return fallback; } }
    function str(v) { return v === null || v === undefined ? "" : String(v); }
    function quote(s) { return '"'+str(s).replace(/\\/g,"\\\\").replace(/"/g,'\\"').replace(/\r/g,"\\r").replace(/\n/g,"\\n").replace(/\t/g,"\\t").replace(/[\x00-\x1f]/g,function(c){var h=c.charCodeAt(0).toString(16);return "\\u"+("0000"+h).slice(-4);})+'"'; }
    function json(v) {
        if (v === null || v === undefined) return "null";
        if (typeof v === "string") return quote(v);
        if (typeof v === "number") return isFinite(v) ? String(v) : "null";
        if (typeof v === "boolean") return v ? "true" : "false";
        var a=[],i,k;
        if (v instanceof Array) { for(i=0;i<v.length;i++) a.push(json(v[i])); return "["+a.join(",")+"]"; }
        for(k in v) if(v.hasOwnProperty(k)) a.push(quote(k)+":"+json(v[k]));
        return "{"+a.join(",")+"}";
    }
    function color(c) {
        if (!c) return null;
        var t=get(c,"typename","");
        if(t==="CMYKColor") return {space:"CMYK",values:[c.cyan,c.magenta,c.yellow,c.black]};
        if(t==="RGBColor") return {space:"RGB",values:[c.red/255,c.green/255,c.blue/255]};
        if(t==="GrayColor") return {space:"Gray",values:[1-c.gray/100]};
        if(t==="LabColor") return {space:"Lab",values:[c.l,c.a,c.b]};
        if(t==="SpotColor") return {space:"Spot",name:c.spot.name,tint:c.tint,alternate:color(c.spot.color)};
        if(t==="NoColor") return {space:"None"};
        return {space:"Unknown",type:t};
    }
    function rect(r) { return r ? [Number(r[0]),-Number(r[1]),Number(r[2]),-Number(r[3])] : null; }
    var data={schema_version:1,engine:"Illustrator ExtendScript",source:str(get(doc,"fullName",doc.name)),
        illustrator_version:app.version,document_color_space:str(doc.documentColorSpace),ruler_units:str(doc.rulerUnits),
        artboards:[],objects:[],limitations:[
        "Illustrator DOM 未可靠提供文件出血；請另外檢查最終 PDF 的 TrimBox／BleedBox。",
        "可讀取字型物件不證明原字型未被替代；Missing Font 仍須核對開檔警告或原始字型清單。",
        "路徑不等於外框文字；未有來源證據時無法確認外框文字與原始字級。",
        "Opacity Mask、Appearance 多重填色／效果、網格、外掛物件可能無法完整取得。",
        "文字背景、色彩資訊語意、Logo／QR 身分與反白狀態需另行標註。",
        "文字範圍位置使用 TextFrame 包圍盒；精確字元邊界、文字變形及沿路徑排文需人工確認。",
        "Illustrator DOM 不提供 AI 儲存相容版本；請核對另存時選擇的版本。"
    ]};
    var i,j;
    for(i=0;i<doc.artboards.length;i++) data.artboards.push({id:i+1,name:doc.artboards[i].name,rect:rect(doc.artboards[i].artboardRect),bleed_mm:null});
    function boards(r) {
        var a=[],b;
        if(!r) return [null];
        for(var n=0;n<data.artboards.length;n++) { b=data.artboards[n].rect; if(r[2]>=b[0] && r[0]<=b[2] && r[3]>=b[1] && r[1]<=b[3]) a.push(n+1); }
        return a.length ? a : [null];
    }
    function push(o) {
        var b=boards(o.bbox),n,k,c;
        for(n=0;n<b.length;n++) { c={}; for(k in o) if(o.hasOwnProperty(k)) c[k]=o[k]; c.artboard=b[n]; data.objects.push(c); }
    }
    function base(item,index) {
        var layer=get(item,"layer",null),r=rect(get(item,"geometricBounds",null));
        var hidden=get(item,"hidden",false),locked=get(item,"locked",false),nonprinting=false,p=item;
        while(p && p!==doc) {
            hidden=hidden || get(p,"hidden",false) || get(p,"visible",true)===false;
            locked=locked || get(p,"locked",false); nonprinting=nonprinting || get(p,"printable",true)===false;
            p=get(p,"parent",null);
        }
        return {kind:"path",name:get(item,"name","") || get(item,"typename","Object")+" "+index,
            bbox:r,layer:layer ? layer.name : null,hidden:hidden,locked:locked,non_printing:nonprinting,
            opacity:get(item,"opacity",100),blend_mode:str(get(item,"blendingMode","Normal")),opacity_mask:null,
            evidence:"Illustrator DOM "+get(item,"typename","")};
    }
    for(i=0;i<doc.pageItems.length;i++) {
        var item=doc.pageItems[i],t=get(item,"typename",""),o=base(item,i+1);
        if(t==="TextFrame") {
            // Group consecutive ranges by actual attributes; mixed size text is not collapsed.
            // textRanges are formatting runs (fast); fall back to per-character reading if unavailable.
            var chars=null,run=null,lastKey="";
            try { chars=item.textRanges; if(!chars.length && item.characters.length) chars=null; } catch(e) { chars=null; }
            if(!chars) chars=item.characters;
            for(j=0;j<chars.length;j++) {
                var ca=chars[j].characterAttributes,tf=get(ca,"textFont",null);
                var at={font:tf ? tf.name : null,weight:tf ? get(tf,"style",null) : null,
                    font_size_pt:get(ca,"size",null),fill:color(get(ca,"fillColor",null)),stroke:color(get(ca,"strokeColor",null)),
                    overprint_fill:get(ca,"overprintFill",null),overprint_stroke:get(ca,"overprintStroke",null),
                    horizontal_scale:get(ca,"horizontalScale",null),vertical_scale:get(ca,"verticalScale",null)};
                at.nominal_font_size_pt=at.font_size_pt;
                if(at.vertical_scale!==null && Math.abs(at.vertical_scale-100)>0.0001) {
                    at.font_size_pt=null;
                    data.limitations.push(o.name+"：文字垂直縮放不為 100%，保留名義字級，實際字級需人工核對。");
                }
                var key=json(at);
                if(!run || key!==lastKey) {
                    if(run) push(run);
                    run=base(item,i+1);run.kind="text";run.name += " / run "+(j+1);run.text="";
                    for(var k in at) if(at.hasOwnProperty(k)) run[k]=at[k];
                    run.missing_font=null;run.outlined=false;run.reverse=null;
                    run.bold=/bold|black|heavy/i.test(str(at.weight));
                    lastKey=key;
                }
                run.text+=chars[j].contents;
            }
            if(run) push(run);
        } else {
            if(get(item,"filled",false)) { o.fill=color(get(item,"fillColor",null)); o.overprint_fill=get(item,"fillOverprint",null); }
            if(get(item,"stroked",false)) { o.stroke=color(get(item,"strokeColor",null));o.stroke_width_pt=get(item,"strokeWidth",null);o.overprint_stroke=get(item,"strokeOverprint",null); }
            if(t==="PlacedItem" || t==="RasterItem") {
                o.kind="image";var file=null,fileError=null;
                try { file=item.file; } catch(e) { fileError=str(e.message || e); }
                o.path=file ? file.fsName : null;
                if(t==="PlacedItem") {
                    // Illustrator throws on PlacedItem.file when the linked file is gone; treat as missing, keep the message as evidence.
                    o.link_state=file ? (file.exists ? "linked" : "missing") : fileError!==null ? "missing" : "unknown";
                    if(fileError!==null) o.evidence+="；讀取連結檔失敗："+fileError+"（請在連結面板確認）";
                } else {
                    o.link_state=get(item,"embedded",null)===true ? "embedded" : file ? (file.exists ? "linked" : "missing") : "unknown";
                }
                o.image_color_space=str(get(item,"imageColorSpace",null));
                var bb=get(item,"boundingBox",null),mx=get(item,"matrix",null);
                if(bb && mx) {
                    var w=Math.abs(bb[2]-bb[0]),h=Math.abs(bb[1]-bb[3]);
                    o.image_transform=[w*mx.mValueA,-w*mx.mValueB,h*mx.mValueC,-h*mx.mValueD,0,0];
                    o.transform_basis="DOM boundingBox (untransformed) multiplied by item.matrix";
                }
                // Embedded source pixels are not inferred from width/height in points.
                o.pixels=null;
            }
            if(t==="MeshItem" || t==="PluginItem" || t==="SymbolItem" || t==="NonNativeItem") data.limitations.push(o.name+"：內容需人工或最終 PDF 確認。");
            push(o);
        }
    }
    // Include unused swatches distinctly; they are not claimed to be printed.
    for(i=0;i<doc.swatches.length;i++) data.objects.push({kind:"swatch",name:"色票（可能未使用）："+doc.swatches[i].name,fill:color(doc.swatches[i].color),artboard:null,evidence:"Illustrator swatches inventory; usage not asserted"});
    function layers(collection) {
        for(var n=0;n<collection.length;n++) {
            var l=collection[n];
            data.objects.push({kind:"layer",name:l.name,layer:l.name,hidden:!l.visible,locked:l.locked,non_printing:!l.printable,artboard:null,evidence:"Illustrator Layer DOM"});
            layers(l.layers);
        }
    }
    layers(doc.layers);
    var out=new File(folder.fsName+"/illustrator-inspection.json");out.encoding="UTF-8";
    if(out.exists || !out.open("w")) {alert("無法寫入新的檢查資料。");return;}
    out.write(json(data));out.close();
    // imageCapture reads artwork without altering active Artboard or export preferences.
    var previews=[];
    for(i=0;i<doc.artboards.length;i++) {
        try {
            var opts=new ImageCaptureOptions(); opts.resolution=120;opts.antiAliasing=true;opts.transparency=false;
            var pf=new File(folder.fsName+"/artboard-"+("0"+(i+1)).slice(-2)+"-original.png");
            if(pf.exists) throw new Error("Preview exists");
            doc.imageCapture(pf,doc.artboards[i].artboardRect,opts);
            previews.push(pf.fsName);
        } catch(e) { /* JSON remains useful when imageCapture unsupported. */ }
    }
    alert("唯讀擷取完成：\n"+out.fsName+"\n預覽 "+previews.length+" 張。未儲存或修改原 AI。");
})();
