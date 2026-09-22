"""Exercise deploy ordering/failure paths with fake transports; never contact a VPS."""
from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import unittest


class DeployTests(unittest.TestCase):
    def run_deploy(self, mode='--from-github', failure=''):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            for folder in ('ops','dist','bin'):
                (root/folder).mkdir()
            (root/'dist/index.html').write_text('checked release')
            shutil.copy2(Path(__file__).with_name('deploy.sh'),root/'ops/deploy.sh')
            shutil.copy2(Path(__file__).with_name('fetch-static-release.py'),root/'ops/fetch-static-release.py')
            fake='''#!/usr/bin/env python3
import os,sys,pathlib
name=pathlib.Path(sys.argv[0]).name; command=' '.join(sys.argv[1:])
with open(os.environ['DEPLOY_TEST_LOG'],'a') as log: log.write(name+' '+command+'\\n')
failure=os.environ.get('DEPLOY_TEST_FAILURE','')
if name=='git':
 if 'rev-parse' in command: print('a'*40)
 elif failure=='dirty' and 'diff' in command: sys.exit(1)
 elif failure=='unpushed' and 'merge-base' in command: sys.exit(1)
elif name=='ssh':
 if '--worker' in command:
  pathlib.Path(os.environ['DEPLOY_TEST_FETCH']).write_bytes(sys.stdin.buffer.read())
  if failure=='download': sys.exit(22)
 if 'sha256sum' in command:
  pathlib.Path(os.environ['DEPLOY_TEST_MANIFEST']).write_bytes(sys.stdin.buffer.read())
  if failure=='checksum': sys.exit(1)
elif name=='scp' and failure=='upload': sys.exit(1)
'''
            for name in ('git','ssh','scp'):
                path=root/'bin'/name;path.write_text(fake);path.chmod(0o755)
            env={**os.environ,'PATH':str(root/'bin')+os.pathsep+os.environ['PATH'],
                 'DEPLOY_TEST_LOG':str(root/'calls'),'DEPLOY_TEST_MANIFEST':str(root/'manifest'),
                 'DEPLOY_TEST_FETCH':str(root/'fetch'),
                 'DEPLOY_TEST_FAILURE':failure,'NEEDLE_SHARK_SSH_KEY':str(root/'fake-key')}
            result=subprocess.run(['bash',str(root/'ops/deploy.sh'),mode],env=env,capture_output=True,text=True)
            log=(root/'calls').read_text() if (root/'calls').exists() else ''
            manifest=(root/'manifest').read_text() if (root/'manifest').exists() else ''
            self.fetch=json.loads((root/'fetch').read_text()) if (root/'fetch').exists() else None
            return result,log,manifest

    def test_pinned_public_files_verified_before_atomic_switch(self):
        result,log,manifest=self.run_deploy()
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(self.fetch['revision'],'a'*40)
        self.assertEqual(self.fetch['files'],{'index.html':hashlib.sha256(b'checked release').hexdigest()})
        self.assertIn('raw.githubusercontent.com',log)
        self.assertLess(log.index('--worker'),log.index('sha256sum'))
        self.assertLess(log.index('sha256sum'),log.index('mv -Tf'))
        self.assertIn('previous',log)
        self.assertEqual(manifest,hashlib.sha256(b'checked release').hexdigest()+'  index.html\n')

    def test_download_or_checksum_failure_never_switches_current(self):
        for failure in ('download','checksum'):
            with self.subTest(failure=failure):
                result,log,_=self.run_deploy(failure=failure)
                self.assertNotEqual(result.returncode,0)
                self.assertNotIn('mv -Tf',log)

    def test_dirty_or_unpushed_revision_never_contacts_server(self):
        for failure in ('dirty','unpushed'):
            with self.subTest(failure=failure):
                result,log,_=self.run_deploy(failure=failure)
                self.assertNotEqual(result.returncode,0)
                self.assertNotIn('ssh ',log)

    def test_original_local_upload_is_retained_and_verified(self):
        result,log,_=self.run_deploy(mode='local')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('scp -r',log)
        self.assertNotIn('curl ',log)
        self.assertLess(log.index('scp -r'),log.index('sha256sum'))

    def test_failed_local_upload_never_switches_current(self):
        result,log,_=self.run_deploy(mode='local',failure='upload')
        self.assertNotEqual(result.returncode,0)
        self.assertNotIn('mv -Tf',log)


if __name__=='__main__':
    unittest.main()
