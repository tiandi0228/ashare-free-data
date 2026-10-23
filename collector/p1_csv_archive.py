"""Archive validated CSV shards to a free Git branch, independent from main.

A bounded job archives only the two newly validated shards. Failures do not
mark long-term CSV persistence as successful. No trading or certification.
"""
import argparse, hashlib, json, os, shutil, subprocess, tempfile
from pathlib import Path

BRANCH="research-csv-archive"

def git(*args,cwd=None,check=True):
    return subprocess.run(["git",*args],cwd=cwd,check=check,text=True,capture_output=True)

def collect(plan, selected):
    files=[]
    for index,folder in selected:
        shard=plan["shards"][index]
        receipt=json.loads((folder/"quality.json").read_text())
        if receipt["manifest_sha256"]!=shard["sha256"] or receipt["issuer_count"]!=shard["count"]:
            raise ValueError("shard receipt mismatch")
        if receipt.get("status")!="OBSERVED_SUBSET_UNVERIFIED" or receipt.get("trade_gate")!="BLOCKED":
            raise ValueError("unsafe receipt")
        for item in receipt["results"]:
            source=folder/(item["code"].replace(".","_")+".csv")
            raw=source.read_bytes()
            if hashlib.sha256(raw).hexdigest()!=item["sha256"]:
                raise ValueError("CSV digest mismatch")
            files.append((index,source,item["sha256"]))
    return files

def archive(plan, selected, repository):
    entries=collect(plan,selected)
    prefix=plan["source_sha256"][:16]
    if not repository or "/" not in repository:raise ValueError("GitHub repository required")
    with tempfile.TemporaryDirectory() as tmp:
        work=Path(tmp)/"archive"
        git("clone","--no-checkout",f"https://github.com/{repository}.git",str(work))
        git("config","user.name","github-actions[bot]",cwd=work)
        git("config","user.email","41898282+github-actions[bot]@users.noreply.github.com",cwd=work)
        found=git("ls-remote","--heads","origin",BRANCH,cwd=work).stdout.strip()
        if found:
            git("fetch","origin",BRANCH,cwd=work)
            git("checkout","-B",BRANCH,"FETCH_HEAD",cwd=work)
        else:
            git("checkout","--orphan",BRANCH,cwd=work)
            for item in work.iterdir():
                if item.name!=".git":
                    if item.is_dir():shutil.rmtree(item)
                    else:item.unlink()
        for index,source,digest in entries:
            destination=work/prefix/f"shard_{index:04d}"/source.name
            destination.parent.mkdir(parents=True,exist_ok=True)
            if destination.exists() and hashlib.sha256(destination.read_bytes()).hexdigest()!=digest:
                raise ValueError("refuse to overwrite archived CSV")
            shutil.copyfile(source,destination)
        manifest=work/prefix/"archive_status.json"
        previous=json.loads(manifest.read_text()) if manifest.exists() else {"source_sha256":plan["source_sha256"],"trade_gate":"BLOCKED","archived_shards":[]}
        if previous["source_sha256"]!=plan["source_sha256"] or previous["trade_gate"]!="BLOCKED":
            raise ValueError("archive epoch mismatch")
        previous["archived_shards"]=sorted(set(previous["archived_shards"])|{i for i,_,_ in entries})
        manifest.write_text(json.dumps(previous,indent=2)+chr(10))
        git("add",".",cwd=work)
        if git("diff","--cached","--quiet",cwd=work,check=False).returncode==0:
            print("Archive already up to date")
            return
        git("commit","-m","data(p1): archive SHA-verified research CSV shards [NO TRADES]",cwd=work)
        git("push","origin",f"HEAD:refs/heads/{BRANCH}",cwd=work)
        print("Archived",len(entries),"SHA-verified CSV files to",BRANCH)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--plan",required=True)
    p.add_argument("--first",required=True,type=int)
    p.add_argument("--second",type=int)
    p.add_argument("--repo",default=os.environ.get("GITHUB_REPOSITORY"))
    a=p.parse_args()
    plan=json.loads(Path(a.plan).read_text())
    selected=[(a.first,Path("evidence/first_shard"))]
    if a.second is not None:selected.append((a.second,Path("evidence/second_shard")))
    archive(plan,selected,a.repo)
if __name__=="__main__":main()
