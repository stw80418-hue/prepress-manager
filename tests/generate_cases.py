"""Reproducible fixtures; synthetic inspector data is NOT an Illustrator host test."""
import copy
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from metrics import PT_PER_MM

NAMES=["normal_cmyk","rgb_image","150_ppi","missing_link","5pt_text","four_color_small_text","tac_350",
       "white_overprint","spot_color","thin_line","red_green_chart","low_contrast","small_light_low_contrast",
       "missing_bleed","packaging_dieline_white"]


def cases():
    board={"id":1,"name":"Artboard 1","rect":[0,0,100*PT_PER_MM,100*PT_PER_MM],"bleed_mm":dict.fromkeys(["top","bottom","left","right"],3)}
    normal={"kind":"path","name":"CMYK box","artboard":1,"bbox":[30,30,100,100],"fill":{"space":"CMYK","values":[0,0,0,100]},"overprint_fill":False}
    text={"kind":"text","name":"Test text","artboard":1,"bbox":[30,30,80,40],"text":"本活動主辦單位保留最終修改權利","font":"Fixture Sans","weight":"Regular","font_size_pt":5,"missing_font":False,"outlined":False,"fill":{"space":"CMYK","values":[0,0,0,100]}}
    image={"kind":"image","name":"Placed fixture","artboard":1,"bbox":[30,30,174,174],"pixels":[300,300],"image_transform":[144,0,0,144,30,30],"link_state":"embedded","color":{"space":"CMYK"}}
    pair={"foreground":[.7,.7,.7],"background":[1,1,1],"color_space":"sRGB","background_type":"solid","verified":True,"evidence":"Fixture defines foreground and solid background, no effects"}
    all_cases=[]
    for number,name in enumerate(NAMES,1):
        d={"schema_version":1,"engine":"Synthetic inspector fixture (not real AI)","source":f"TEST {number:02d} / {name}","artboards":[copy.deepcopy(board)],"objects":[copy.deepcopy(normal)],"limitations":["本測試為合成物件資料，不能驗證 Illustrator DOM 實際行為。"]}
        if number in [2,3,4]:
            o=copy.deepcopy(image)
            if number==2:
                o["color"]={"space":"RGB"};o["pixels"]=[600,600]
            if number==4:
                o["link_state"]="missing";o["path"]="missing-source.tif"
            d["objects"]=[o]
        if number in [5,6,12,13]:
            o=copy.deepcopy(text)
            if number==6:
                o["fill"]["values"]=[100,100,100,100]
            if number in [12,13]:
                o["contrast_pair"]=copy.deepcopy(pair)
                o["font_size_pt"]=12 if number==12 else 5
            if number==13:
                o["weight"]="Light"
            d["objects"]=[o]
        if number==7:
            d["objects"][0]["fill"]["values"]=[90,80,80,100]
        if number==8:
            d["objects"][0].update(fill={"space":"CMYK","values":[0,0,0,0]},overprint_fill=True)
        if number==9:
            d["objects"][0]["fill"]={"space":"Spot","name":"PANTONE fixture","tint":100}
        if number==10:
            d["objects"][0].update(stroke={"space":"CMYK","values":[0,0,0,100]},stroke_width_pt=.1)
        if number==11:
            d["semantic_pairs"]=[{"name":"付款圖例","artboard":1,"verified":True,"evidence":"Fixture: two categories without labels or icons","non_color_cue":False,
                                  "a":{"srgb":[1,0,0],"HEX":"#FF0000","RGB":[255,0,0],"CMYK":None},
                                  "b":{"srgb":[0,.68,0],"HEX":"#00AD00","RGB":[0,173,0],"CMYK":None}}]
        if number==14:
            d["artboards"][0]["bleed_mm"]=dict.fromkeys(["top","bottom","left","right"],0)
        if number==15:
            d["objects"][0].update(name="Dieline",layer="刀模",fill={"space":"Spot","name":"CutContour"})
            o=copy.deepcopy(normal);o.update(name="白墨",layer="White Ink",fill={"space":"Spot","name":"White Ink"})
            d["objects"].append(o)
        all_cases.append((number,name,d))
    return all_cases


def make_pdf(path,number):
    import pikepdf
    from pikepdf import Name,Dictionary,Array
    pdf=pikepdf.Pdf.new();page=pdf.add_blank_page(page_size=(300,300))
    page.obj.TrimBox=Array([10,10,290,290]);page.obj.BleedBox=Array([0,0,300,300])
    if number==14:
        page.obj.BleedBox=Array([10,10,290,290])
    font=pdf.make_indirect(Dictionary(Type=Name.Font,Subtype=Name.Type1,BaseFont=Name.Helvetica))
    page.obj.Resources=Dictionary(Font=Dictionary(F1=font))
    content="0 0 0 1 k 40 40 100 100 re f"
    if number in [2,3]:
        cs=Name.DeviceRGB if number==2 else Name.DeviceCMYK
        channels=3 if number==2 else 4
        pixels=600 if number==2 else 300
        stream=pikepdf.Stream(pdf,bytes([0]*(pixels*pixels*channels)))
        stream.Type=Name.XObject;stream.Subtype=Name.Image;stream.Width=pixels;stream.Height=pixels
        stream.ColorSpace=cs;stream.BitsPerComponent=8
        page.obj.Resources.XObject=Dictionary(Im1=pdf.make_indirect(stream))
        content="q 144 0 0 144 30 30 cm /Im1 Do Q"
    if number in [5,6,12,13]:
        color="1 1 1 1 k" if number==6 else ".7 .7 .7 rg" if number in [12,13] else "0 0 0 1 k"
        content=f"{color} BT /F1 {12 if number==12 else 5} Tf 1 0 0 1 40 200 Tm (Fixture text) Tj ET"
    if number==7:
        content=".9 .8 .8 1 k 40 40 100 100 re f"
    if number==8:
        page.obj.Resources.ExtGState=Dictionary(GS1=Dictionary(op=True,OP=True))
        content="/GS1 gs 0 0 0 0 k 40 40 100 100 re f"
    if number in [9,15]:
        fn=Dictionary(FunctionType=2,Domain=Array([0,1]),C0=Array([0,0,0,0]),C1=Array([1,0,0,0]),N=1)
        page.obj.Resources.ColorSpace=Dictionary(SP=Array([Name.Separation,Name('/CutContour' if number==15 else '/PANTONE_Fixture'),Name.DeviceCMYK,fn]))
        content="/SP cs 1 scn 40 40 100 100 re f"
    if number==10:
        content="0 0 0 1 K .1 w 30 30 m 200 200 l S"
    if number==11:
        content="1 0 0 rg 40 40 100 100 re f 0 .68 0 rg 160 40 100 100 re f"
    page.obj.Contents=pikepdf.Stream(pdf,content.encode("ascii"));pdf.save(path)


def generate(destination):
    from PIL import Image,ImageDraw
    destination=Path(destination);destination.mkdir(parents=True,exist_ok=False)
    for number,name,doc in cases():
        folder=destination/f"{number:02d}-{name}";folder.mkdir(exist_ok=True)
        (folder/"inspection.json").write_text(json.dumps(doc,ensure_ascii=False,indent=2),encoding="utf-8")
        # Test thumbnail is illustrative and not a render of the fixture document.
        im=Image.new("RGB",(400,400),"white");draw=ImageDraw.Draw(im)
        draw.rectangle([50,50,160,160],fill="red");draw.rectangle([200,50,310,160],fill=(0,173,0))
        draw.text((20,350),f"Synthetic preview TEST {number:02d}",fill="black")
        im.save(folder/"artboard-01-original.png")
        make_pdf(folder/"fixture.pdf",number)


if __name__=="__main__":
    generate(Path(__file__).parent/"fixtures")
