import json
import os
import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch
import yaml
from scripts import configure, customize

class ProvisioningTests(TestCase):
    def test_unique_credentials_idempotency_and_safe_input(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            with patch.object(configure,'ROOT',root), patch.dict(os.environ,{'PUBLIC_URL':'https://example.com','BUSINESS_NAME':'$(do-not-execute)\nBusiness','AI_PROMPT':'A multiline\nbrief'},clear=True):
                configure.configure()
                first=json.loads((root/'.private/runtime.json').read_text())
                configure.configure()
                second=json.loads((root/'.private/runtime.json').read_text())
                self.assertEqual(first['ADMIN_PASSWORD'],second['ADMIN_PASSWORD'])
                self.assertGreater(len(first['ADMIN_PASSWORD']),24)
                self.assertEqual((root/'.private/runtime.json').stat().st_mode & 0o777,0o600)
                self.assertEqual(json.loads((root/'.private/brief.json').read_text())['BUSINESS_NAME'],'$(do-not-execute)\nBusiness')
    def test_public_origin_resolved_from_exposure_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(configure,'ROOT',Path(directory)), patch.dict(os.environ,{'PORTACODE_EXPOSED_SERVICES_JSON':json.dumps([{'port':8080,'hostname':'site.example.com'}])},clear=True):
                configure.configure()
                self.assertEqual(json.loads((Path(directory)/'.private/runtime.json').read_text())['PUBLIC_URL'],'https://site.example.com')
    def test_empty_prompt_skips_codex(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'.private').mkdir();(root/'.private/brief.json').write_text('{"AI_PROMPT":""}')
            with patch.object(customize,'ROOT',root),patch('scripts.customize.subprocess.run') as run:
                customize.run()
                run.assert_not_called()
    def test_prompt_uses_stdin_not_shell(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'.private').mkdir();(root/'.private/brief.json').write_text(json.dumps({'AI_PROMPT':'$(bad); newline\nquote "'}))
            with patch.object(customize,'ROOT',root),patch('scripts.customize.subprocess.run') as run:
                customize.run()
                call=run.call_args
                self.assertEqual(call.args[0][0:2],['codex','exec'])
                self.assertIn('$(bad)',call.kwargs['input'])
                self.assertFalse(call.kwargs.get('shell',False))
    def test_template_optional_inputs_and_ordered_readiness(self):
        data=yaml.safe_load((Path(__file__).resolve().parent.parent/'portafile.yaml').read_text())
        self.assertTrue(all(not row.get('required') for row in data['inputs']))
        self.assertIn('wait_for',data['instructions'][-1])
        self.assertFalse(any('persist_environment' in row for row in data['inputs']))
