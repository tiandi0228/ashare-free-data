"""Archive validated CSV shards to a free Git branch, independent from main.

A bounded job archives only the two newly validated shards. Failures do not
mark long-term CSV persistence as successful. No trading or certification.
"""
import argparse, hashlib, json, os, shutil, subprocess, tempfile
from pathlib import Path
from collector.p1_roster_shard_manifest import CODE

BRANCH="research-csv-archive"

def git(*args,cwd=None,check=True):
    return subprocess.run(["git",*args],cwd=cwd,check=check,text=True,capture_output=True,timeout=90)

def collect(plan, selected):
    files=[]
    seen_codes=set()
    seen_shards=set()
    for index,folder in selected:
        if type(index) is not int or not 0<=index<len(plan["shards"]) or index in seen_shards:
            raise ValueError("invalid or duplicate archive shard index")
        seen_shards.add(index)
        shard=plan["shards"][index]
        receipt=json.loads((folder/"quality.json").read_text())
        if receipt["manifest_sha256"]!=shard["sha256"] or receipt["issuer_count"]!=shard["count"]:
            raise ValueError("shard receipt mismatch")
        if receipt.get("status")!="OBSERVED_SUBSET_UNVERIFIED" or receipt.get("trade_gate")!="BLOCKED":
            raise ValueError("unsafe receipt")
        results=receipt.get("results")
        if not isinstance(results,list) or len(results)!=shard["count"]:
            raise ValueError("incomplete archive receipt")
        codes=[item.get("code") for item in results if isinstance(item,dict)]
        if len(codes)!=len(results) or any(not isinstance(code,str) or not CODE.fullmatch(code) for code in codes):
            raise ValueError("invalid archive batch issuer membership")
        membership=hashlib.sha256(("".join(code+"\n" for code in sorted(codes))).encode()).hexdigest()
        if membership!=shard["sha256"]:
            raise ValueError("archive issuer membership differs from original shard manifest")
        for item in results:
            if not isinstance(item,dict) or item.get("status")!="OBSERVED_UNVERIFIED":
                raise ValueError("invalid issuer result status in archive batch")
            code=item.get("code") if isinstance(item,dict) else None
            if not isinstance(code,str) or not CODE.fullmatch(code) or code in seen_codes:
                raise ValueError("invalid or duplicate issuer in archive batch")
            seen_codes.add(code)
            source=folder/(code.replace(".","_")+".csv")
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
        for index,folder in selected:
            receipt_source=folder/"quality.json"
            receipt_dest=work/prefix/f"shard_{index:04d}"/"quality.json"
            receipt_dest.parent.mkdir(parents=True,exist_ok=True)
            if receipt_dest.exists() and receipt_dest.read_bytes()!=receipt_source.read_bytes():
                raise ValueError("refuse to overwrite archived receipt")
            shutil.copyfile(receipt_source,receipt_dest)
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
    p.add_argument("--third",type=int)
    p.add_argument("--fourth",type=int)
    p.add_argument("--repo",default=os.environ.get("GITHUB_REPOSITORY"))
    a=p.parse_args()
    plan=json.loads(Path(a.plan).read_text())
    selected=[(a.first,Path("evidence/first_shard"))]
    if a.second is not None:selected.append((a.second,Path("evidence/second_shard")))
    if a.third is not None:selected.append((a.third,Path("evidence/third_shard")))
    if a.fourth is not None:selected.append((a.fourth,Path("evidence/fourth_shard")))
    if len(set(i for i,_ in selected))!=len(selected) or len(selected)>4:raise ValueError("invalid archive selection")
    archive(plan,selected,a.repo)
if __name__=="__main__":main()
