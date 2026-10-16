"""Install source-only skill into a new destination; never overwrite existing skills."""
import argparse
from pathlib import Path
import shutil
ROOT=Path(__file__).resolve().parents[1]

def install(target, home):
    base={"codex": ".agents", "claude": ".claude"}[target]
    dest=Path(home)/base/"skills"/"illustrator-preflight"
    if dest.exists():
        raise FileExistsError("Destination exists; review or back up before updating: "+str(dest))
    files=[ROOT/n for n in ["SKILL.md","README.md","print_rules.json","accessibility_rules.json","requirements.txt","requirements-tested.txt"]]
    for folder,exts in {"scripts":{'.py','.jsx'},"references":{'.md','.json'},"templates":{'.md','.json'},"agents":{'.yaml'},"tests":{'.py'}}.items():
        files.extend(p for p in (ROOT/folder).iterdir() if p.is_file() and not p.is_symlink() and p.suffix in exts)
    for p in files:
        q=dest/p.relative_to(ROOT);q.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,q)
    return dest

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--target',choices=['codex','claude'],required=True)
    p.add_argument('--home',type=Path,default=Path.home(),help='User home; override for an isolated install test')
    args=p.parse_args();print(install(args.target,args.home))
