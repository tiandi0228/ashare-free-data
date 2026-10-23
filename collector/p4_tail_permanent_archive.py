"""Commit independently verified P4 tail source bytes to immutable research branch."""
import argparse,hashlib,json,os,subprocess,tempfile
from pathlib import Path
from collector.p4_tail_independent_verify import verify

def git(*args,cwd=None):
    return subprocess.run(["git",*args],cwd=cwd,check=True,text=True,capture_output=True).stdout.strip()

def persist(archive,tail,repository,source_run):
    result=verify(archive,tail)
    if not result["restored_exit_date_observations"] or result["trade_gate"]!="BLOCKED":
        raise ValueError("no independently recovered targets")
    root=Path(tail);manifest=root/"backfill_attempt.json"
    if not repository or "/" not in repository or not str(source_run).isdigit():
        raise ValueError("invalid repository or source run")
    with tempfile.TemporaryDirectory() as temp:
        work=Path(temp)/"branch"
        git("clone","--branch","research-csv-archive","--single-branch",
            "https://x-access-token:"+os.environ["GH_TOKEN"]+"@github.com/"+repository+".git",str(work))
        git("config","user.name","github-actions[bot]",cwd=work)
        git("config","user.email","41898282+github-actions[bot]@users.noreply.github.com",cwd=work)
        target=work/"p4-tail-backfill"/("actions-"+str(source_run))
        target.mkdir(parents=True,exist_ok=True)
        files=[manifest]+[root/item["filename"] for item in json.loads(manifest.read_text())["results"] if item["status"]=="OBSERVED_RESEARCH_ONLY"]
        for source in files:
            dest=target/source.name
            if dest.exists() and hashlib.sha256(dest.read_bytes()).digest()!=hashlib.sha256(source.read_bytes()).digest():
                raise ValueError("immutable archive conflict")
            dest.write_bytes(source.read_bytes())
        audit_path=target/"independent_verification.json"
        report=json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2)+"\n"
        if audit_path.exists() and audit_path.read_text()!=report:raise ValueError("verification conflict")
        audit_path.write_text(report)
        git("add","p4-tail-backfill",cwd=work)
        if subprocess.run(["git","diff","--cached","--quiet"],cwd=work).returncode!=0:
            git("commit","-m",f"data(p4): archive {result['verified_source_rows']} independently verified vendor tail bars [NO TRADES]",cwd=work)
            git("push","origin","HEAD:refs/heads/research-csv-archive",cwd=work)
        return {"persisted":True,"branch":"research-csv-archive","run":source_run,
                "rows":result["verified_source_rows"],"matched_exit_observations":result["restored_exit_date_observations"],
                "trade_gate":"BLOCKED"}
def main():
    p=argparse.ArgumentParser();p.add_argument("--archive",required=True);p.add_argument("--tail",required=True)
    p.add_argument("--source-run",required=True);p.add_argument("--repository",default=os.getenv("GITHUB_REPOSITORY"))
    a=p.parse_args();print(json.dumps(persist(a.archive,a.tail,a.repository,a.source_run)))
if __name__=="__main__":main()
