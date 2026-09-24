"""Small read-only Agent client. Examples: client.py cells --problem P1 --case 002; client.py watch --after 10."""
import argparse, json, urllib.request, urllib.parse
p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=['health','catalog','cells','records','watch']);p.add_argument('--url',default='http://127.0.0.1:52341');p.add_argument('--problem');p.add_argument('--case',dest='case_id');p.add_argument('--cores',type=int);p.add_argument('--after',type=int,default=0);p.add_argument('--limit',type=int,default=100);p.add_argument('--offset',type=int,default=0);a=p.parse_args()
q={k:v for k,v in vars(a).items() if k in ('problem','case_id','cores','limit','offset') and v is not None}
endpoint=a.command
if endpoint=='watch':endpoint='events';q={'after':a.after,'wait':20}
with urllib.request.urlopen(a.url+'/api/v1/'+endpoint+'?'+urllib.parse.urlencode(q),timeout=30) as r: print(json.dumps(json.load(r),ensure_ascii=False,indent=2))
