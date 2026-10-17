"""Install the source-only skill, with its own Python venv. Never overwrites: --update moves the old copy to a backup folder."""
import argparse
from datetime import datetime
from pathlib import Path
import shutil
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]
NAME="prepress-manager"
BASES={"codex": ".agents", "claude": ".claude"}
# Old locations or names that would load a second copy of this skill.
LEGACY={"codex": [".codex/skills/"+NAME, ".codex/skills/illustrator-preflight", ".agents/skills/illustrator-preflight"],
        "claude": [".claude/skills/illustrator-preflight"]}


def venv_python(dest):
    return dest/".venv"/("Scripts/python.exe" if sys.platform=="win32" else "bin/python")


def make_venv(dest):
    subprocess.run([sys.executable,"-m","venv",str(dest/".venv")],check=True)
    py=venv_python(dest)
    subprocess.run([str(py),"-m","pip","install","--disable-pip-version-check","-q","-r",str(dest/"requirements.txt")],check=True)
    return py


def install(target, home, update=False, venv=True):
    base=BASES[target]
    dest=Path(home)/base/"skills"/NAME
    backup=None
    if dest.exists():
        if not update:
            raise FileExistsError("Destination exists; rerun with --update to back it up and reinstall: "+str(dest))
        # Backups live outside skills/ so the assistant does not load two copies.
        backup=Path(home)/base/"skill-backups"/f"{NAME}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        backup.parent.mkdir(parents=True,exist_ok=True)
        shutil.move(str(dest),str(backup))
    files=[ROOT/n for n in ["SKILL.md","README.md","CHANGELOG.md","LICENSE","print_rules.json","accessibility_rules.json","requirements.txt","requirements-tested.txt"] if (ROOT/n).exists()]
    for folder,exts in {"scripts":{'.py','.jsx'},"references":{'.md','.json'},"templates":{'.md','.json'},"agents":{'.yaml'},"tests":{'.py'}}.items():
        files.extend(p for p in (ROOT/folder).iterdir() if p.is_file() and not p.is_symlink() and p.suffix in exts)
    for p in files:
        q=dest/p.relative_to(ROOT);q.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,q)
    python=make_venv(dest) if venv else None
    legacy=[str(Path(home)/x) for x in LEGACY[target] if (Path(home)/x).exists()]
    return {"dest":dest,"python":python,"backup":backup,"legacy":legacy}


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--target',choices=['codex','claude','both'],required=True)
    p.add_argument('--update',action='store_true',help='Move an existing install to skill-backups/ and reinstall')
    p.add_argument('--no-venv',action='store_true',help='Skip creating .venv and installing requirements')
    p.add_argument('--home',type=Path,default=Path.home(),help='User home; override for an isolated install test')
    args=p.parse_args()
    if sys.version_info<(3,10):
        p.exit(2,"需要 Python 3.10 以上；目前是 "+sys.version.split()[0]+"\n")
    for target in (['codex','claude'] if args.target=='both' else [args.target]):
        try:
            r=install(target,args.home,args.update,not args.no_venv)
        except FileExistsError as exc:
            p.exit(2,f"[{target}] 已經安裝過。要更新請加上 --update（舊版會移到備份資料夾）。\n{exc}\n")
        except subprocess.CalledProcessError as exc:
            p.exit(2,f"[{target}] Skill 已複製，但 Python 套件安裝失敗：{exc}\n請檢查網路後加上 --update 重跑。\n")
        print(f"[{target}] 已安裝：{r['dest']}")
        if r["backup"]:
            print(f"[{target}] 舊版備份：{r['backup']}")
        if r["python"]:
            print(f"[{target}] Python：{r['python']}")
        for path in r["legacy"]:
            print(f"[{target}] 注意：發現舊版 {path}，請移到 skills 資料夾外，避免重複載入。")
    print("完成。請重新開啟 Codex／Claude Code 的對話。")
