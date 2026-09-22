"""Test pinned downloads and reuse without network or a real release directory."""
import hashlib
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('static_fetch',Path(__file__).with_name('fetch-static-release.py'))
fetch=importlib.util.module_from_spec(spec)
spec.loader.exec_module(fetch)


class StaticFetchTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.old=self.root/'current';self.old.mkdir()
        self.new=self.root/'release';self.new.mkdir()
        self.sha=lambda value:hashlib.sha256(value).hexdigest()

    def test_reuse_is_a_separate_copy_and_pinned_download_is_verified(self):
        (self.old/'same.txt').write_bytes(b'same')
        seen=[]
        def opener(url,timeout):
            seen.append(url)
            return io.BytesIO(b'new')
        counts=fetch.populate({'same.txt':self.sha(b'same'),'image space.webp':self.sha(b'new')},'a'*40,self.new,self.old,opener)
        self.assertEqual(counts,{'reused':1,'downloaded':1,'retained':0})
        self.assertEqual(seen,['https://raw.githubusercontent.com/mirkenson/needleshark/'+'a'*40+'/dist/image%20space.webp'])
        (self.new/'same.txt').write_bytes(b'changed')
        self.assertEqual((self.old/'same.txt').read_bytes(),b'same')

    def test_bad_download_never_replaces_current_or_keeps_partial(self):
        (self.old/'index.html').write_bytes(b'old')
        with self.assertRaises(ValueError):
            fetch.populate({'index.html':self.sha(b'expected')},'a'*40,self.new,self.old,lambda *a,**k:io.BytesIO(b'wrong'))
        self.assertEqual((self.old/'index.html').read_bytes(),b'old')
        self.assertFalse((self.new/'index.html').exists())
        self.assertFalse((self.new/'index.html.download').exists())

    def test_invalid_manifest_fails_before_writing(self):
        for name in ('../outside','/outside','.'):
            with self.subTest(name=name),self.assertRaises(ValueError):
                fetch.populate({name:self.sha(b'x')},'a'*40,self.new,self.old)
        self.assertEqual(list(self.new.iterdir()),[])

    def test_matching_destination_is_retained(self):
        (self.new/'index.html').write_bytes(b'new')
        def unexpected(*args,**kwargs):
            raise AssertionError('Network is unnecessary')
        self.assertEqual(fetch.populate({'index.html':self.sha(b'new')},'a'*40,self.new,self.old,unexpected)['retained'],1)


if __name__=='__main__':
    unittest.main()
