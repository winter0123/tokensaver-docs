import importlib.util,json,tempfile,unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('verify_opencode',Path(__file__).resolve().parents[1]/'scripts/verify_opencode.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

class HostVerificationTests(unittest.TestCase):
    def check(self,lines):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'events';p.write_text('\n'.join(lines));return module.inspect_events(p)

    def test_counts_actual_mcp_results(self):
        events=[{'type':'tool_use','part':{'tool':'file-to-md_prepare_documents','state':{'status':'completed','input':{'image_mode':'analyze'},'output':json.dumps({'status':'ready','ai_calls':count})}}} for count in (5,0)]
        self.assertEqual([r['ai_calls'] for r in self.check([json.dumps(e) for e in events])],[5,0])

    def test_cli_fallback_is_not_success(self):
        with self.assertRaisesRegex(ValueError,'fallback'):
            self.check([json.dumps({'type':'tool_use','part':{'tool':'shell','state':{'status':'completed'}}})])

    def test_damaged_logs_are_rejected(self):
        with self.assertRaises(json.JSONDecodeError):self.check(['{"type":'])
