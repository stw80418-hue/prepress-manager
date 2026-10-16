import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from preflight import ROOT,run
from generate_cases import generate,NAMES


def main():
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument("--out",type=Path,default=ROOT/"output/test-cases")
    output=parser.parse_args().out
    if output.exists():
        raise FileExistsError("Examples already exist; use a new copy of the skill to regenerate")
    fixtures=ROOT/"tests/fixtures"
    if not fixtures.exists():
        generate(fixtures)
    output.mkdir(parents=True)
    rows=["# 測試案例報告", "", "合成模型與生成 PDF；尚非 Illustrator 宿主驗證。", "", "| TEST | 案例 | 模型報告 | PDF 報告 |", "|---|---|---|---|"]
    for i,name in enumerate(NAMES,1):
        folder=f"{i:02d}-{name}"
        run(fixtures/folder/"inspection.json",output/folder/"inspector")
        run(fixtures/folder/"fixture.pdf",output/folder/"pdf")
        rows.append(f"| {i:02d} | {name} | [報告]({folder}/inspector/PREFLIGHT_REPORT.md) | [報告]({folder}/pdf/PREFLIGHT_REPORT.md) |")
    (output/"INDEX.md").write_text("\n".join(rows),encoding="utf-8")
    print(output/"INDEX.md")


if __name__=="__main__":
    main()
