import argparse
from pathlib import Path

def main():
    parser=argparse.ArgumentParser(description='Real-data marketing measurement pipeline')
    parser.add_argument('command',choices=['run','ingest','clean','transform','qa','experiment','report','render-cloud','cloud-upload','cloud-transform','cloud-qa'])
    parser.add_argument('--root',type=Path,default=Path.cwd())
    parser.add_argument('--project')
    parser.add_argument('--dataset',default='marketing_measurement')
    parser.add_argument('--location',default='US')
    parser.add_argument('--maximum-bytes-billed',type=int,default=5_000_000_000)
    parser.add_argument('--costs',type=Path)
    args=parser.parse_args()
    root=args.root.resolve()
    from measurement.sources import ingest
    from measurement.warehouse import clean,transform,qa
    from measurement.experiment import analyze
    from measurement.reporting import report
    if args.command=='run':
        ingest(root); clean(root); transform(root); qa(root); analyze(root,args.costs); report(root)
    elif args.command=='experiment': analyze(root,args.costs)
    elif args.command.startswith('cloud-') or args.command=='render-cloud':
        from measurement import cloud
        if not args.project: parser.error('--project required for cloud commands')
        if args.command=='render-cloud': print(cloud.render(root,args.project,args.dataset))
        elif args.command=='cloud-upload': cloud.upload(root,args.project,args.dataset,args.location)
        else: cloud.execute(root,args.project,args.dataset,args.location,qa_only=args.command=='cloud-qa',maximum_bytes_billed=args.maximum_bytes_billed)
    else:
        {'ingest':ingest,'clean':clean,'transform':transform,'qa':qa,'report':report}[args.command](root)

if __name__=='__main__': main()
