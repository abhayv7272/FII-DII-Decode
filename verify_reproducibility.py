from __future__ import annotations
import argparse,json,subprocess,sys,tempfile
from pathlib import Path

PRED_FIELDS=['direction','p_up','p_down','confidence','gate','confidence_pass','research_approved','model_pass']

def main():
 ap=argparse.ArgumentParser(description='Run the production pipeline repeatedly and verify deterministic decision outputs.')
 ap.add_argument('--runs',type=int,default=2);ap.add_argument('--date',default='auto');args=ap.parse_args()
 outputs=[]
 for _ in range(args.runs):
  p=subprocess.run([sys.executable,'run_production.py','--date',args.date],check=True,capture_output=True,text=True)
  outputs.append(json.loads(p.stdout))
 first=outputs[0];checks={
  'prediction':all(all(x['prediction'][k]==first['prediction'][k] for k in PRED_FIELDS) for x in outputs[1:]),
  'decision':all(x['decision']==first['decision'] for x in outputs[1:]),
  'quality':all(x['manifest']['quality_score']==first['manifest']['quality_score'] for x in outputs[1:])}
 def src(x):return {r['dataset']:(r['source'],r['status'],r['as_of'],r['rows'],r['sha256']) for r in x['manifest']['results']}
 checks['sources_and_hashes']=all(src(x)==src(first) for x in outputs[1:])
 result={'result':'PASS' if all(checks.values()) else 'FAIL','runs':args.runs,'session':first['manifest']['session_date'],'checks':checks,'prediction':{k:first['prediction'][k] for k in PRED_FIELDS}}
 Path('reports/reproducibility_audit.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2));sys.exit(0 if result['result']=='PASS' else 2)
if __name__=='__main__':main()
