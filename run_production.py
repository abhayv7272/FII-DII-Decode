from __future__ import annotations
import argparse,json
from src.data_hub import DataHub
from src.professional_report import create_report

def main():
 ap=argparse.ArgumentParser(description='9 PM resilient data → prediction → professional report pipeline')
 ap.add_argument('--date',default='auto',help='auto or YYYY-MM-DD');args=ap.parse_args()
 manifest=DataHub(args.date).run();md,js,obj=create_report()
 print(json.dumps({'manifest':manifest,'report_markdown':str(md),'report_json':str(js),'decision':obj['decision'],'prediction':obj['prediction']},indent=2,default=str))
if __name__=='__main__':main()
