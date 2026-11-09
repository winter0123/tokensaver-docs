"""Run an isolated real-host check; never count CLI fallback as MCP success."""
import argparse,json,os,re,shutil,subprocess,tempfile
from pathlib import Path


def inspect_events(path):
    calls=[]
    for line in Path(path).read_text().splitlines():
        event=json.loads(line)  # Damaged or combined logs must fail verification.
        if event.get('type')!='tool_use':continue
        part=event['part'];state=part['state']
        if part['tool'] in ('shell','execute','bash','read','glob','grep','webfetch'):
            raise ValueError('Host used a CLI/code fallback')
        if part['tool'].endswith('_prepare_documents') or part['tool']=='tokensaver_docs_prepare':
            if state['status']!='completed':raise ValueError('Preparation tool did not complete')
            result=json.loads(state['output'])
            calls.append({'tool':part['tool'],'input':state['input'],'status':result['status'],'ai_calls':result.get('ai_calls')})
    return calls


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--plugin',required=True,type=Path)
    parser.add_argument('--env-file',required=True,type=Path)
    args=parser.parse_args()
    repo=Path(__file__).resolve().parents[1]
    from tokensaver_docs.providers import list_models,eligible
    model='nvidia/nemotron-3.5-super-vl:free'
    if not any(m['id']==model and eligible(m,'image') and eligible(m,'text') for m in list_models()):
        raise ValueError('Free model/input support not verified')
    key=None
    for line in args.env_file.read_text().splitlines():
        match=re.fullmatch(r'\s*(?:export\s+)?OPENROUTER_API_KEY\s*=\s*(.*?)\s*',line)
        if match:key=match[1].strip('"\'')
    if not key:raise ValueError('API key missing')
    root=Path(tempfile.mkdtemp(prefix='tokensaver-docs-host-')).resolve()
    plugins=root/'.opencode/plugins';plugins.mkdir(parents=True)
    (plugins/'tokensaver-docs.js').write_text('export {default} from '+json.dumps(args.plugin.resolve().as_uri())+';\n')
    (root/'opencode.json').write_text(json.dumps({'share':'disabled','permissions':[{'action':name,'resource':'*','effect':'deny'} for name in ('shell','execute','bash','read','glob','grep','write','edit')]}))
    for path in (repo/'benchmarks/image-eval/fixtures').iterdir():
        if path.is_file():shutil.copy2(path,root/path.name)
    env=dict(os.environ,PWD=str(root),OPENROUTER_API_KEY=key,XDG_CONFIG_HOME=str(root/'config'),TOKENSAVER_DOCS_CACHE_DIR=str(root/'cache'))
    info={'directory':str(root),'plugin':str(args.plugin.resolve()),'model':model,'version':subprocess.check_output(['opencode','--version'],text=True).strip()}
    (root/'run.json').write_text(json.dumps(info,indent=2))
    print('Evidence:',root,flush=True)
    prompt=f'''Use the available tokensaver-docs document preparation tool, with source={root/'examples.html'}, output={root/'output'}, image_mode=analyze, model_provider=openrouter, model={model}. User explicitly approves image analysis of these synthetic fixtures and one-time model use; do not save defaults. Use the actual tool schema from your available tool list, not a guessed name. Do not read source files or run code or shell. Once preparation succeeds, call the same tool again with identical arguments. Report both ai_calls values. Stop and report a tool error instead of using a CLI fallback.'''
    with (root/'events.jsonl').open('x') as out,(root/'stderr.log').open('x') as err:
        result=subprocess.run(['opencode','run','--standalone','--auto','--model','openrouter/'+model,'--format','json',prompt],cwd=root,env=env,stdout=out,stderr=err,timeout=600)
    calls=inspect_events(root/'events.jsonl')
    report={**info,'exit_code':result.returncode,'calls':calls,'passed':result.returncode==0 and len(calls)==2 and [c['status'] for c in calls]==['ready','ready'] and [c['ai_calls'] for c in calls]==[5,0]}
    (root/'result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print(json.dumps(report,ensure_ascii=False))
    if not report['passed']:raise SystemExit(1)


if __name__=='__main__':main()
