"""Generate simulations and marked thumbnails without editing source media."""
from pathlib import Path
import shutil


def make_previews(doc, findings, originals, output, access, simulate_cvd=True):
    import numpy as np
    from PIL import Image, ImageDraw
    from metrics import simulate
    output=Path(output)
    cvd=output/("color-vision-preview" if simulate_cvd else "original-preview")
    marked=output/"issue-preview"
    cvd.mkdir(exist_ok=True);marked.mkdir(exist_ok=True)
    results=[]
    for board,path in zip(doc["artboards"], originals):
        if path is None or not Path(path).exists():
            continue
        i=board["id"]
        with Image.open(path) as im:
            rgb=im.convert("RGB")
        orig=cvd/f"artboard-{i:02d}-original.png"
        rgb.save(orig)
        entry={"artboard":i,"original":str(orig.relative_to(output))}
        array=np.asarray(rgb,dtype=float)/255 if simulate_cvd else None
        for label,kind in [("protanopia","protanomaly"),("deuteranopia","deuteranomaly"),("tritanopia","tritanomaly")]:
            if not simulate_cvd:
                continue
            target=cvd/f"artboard-{i:02d}-{label}.png"
            Image.fromarray(np.round(simulate(array,kind,access["cvd_severity"])*255).astype("uint8")).save(target)
            entry[label]=str(target.relative_to(output))
        canvas=rgb.copy();draw=ImageDraw.Draw(canvas)
        rect=board.get("preview_rect",board["rect"])
        sx,sy=canvas.width/(rect[2]-rect[0]),canvas.height/(rect[3]-rect[1])
        unplaced=[]
        labels=[]
        for issue in findings:
            if issue["artboard"] != i or issue["status"] not in ["red","yellow"]:
                continue
            b=issue.get("bbox")
            if b is None:
                unplaced.append(issue["id"]);continue
            box=[(b[0]-rect[0])*sx,(b[1]-rect[1])*sy,(b[2]-rect[0])*sx,(b[3]-rect[1])*sy]
            color="#d32020" if issue["status"]=="red" else "#a65f00"
            draw.rectangle(box,outline=color,width=2)
            pos=(max(0,min(canvas.width-70,box[0])),max(0,min(canvas.height-12,box[1]-12)))
            for attempt in range(100):
                if not any(abs(pos[0]-x)<75 and abs(pos[1]-y)<12 for x,y in labels):
                    break
                pos=(pos[0],pos[1]+12)
                if pos[1]>canvas.height-12:
                    pos=((pos[0]+80) % max(81,canvas.width-70),0)
            else:
                unplaced.append(issue["id"])
                continue
            labels.append(pos)
            draw.text(pos,issue["id"],fill=color,stroke_width=1,stroke_fill="white")
        target=marked/f"artboard-{i:02d}-issues.png"
        canvas.save(target)
        entry["issues"]=str(target.relative_to(output));entry["unplaced"]=unplaced
        results.append(entry)
    return results
