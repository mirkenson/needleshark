import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path


SPEC = importlib.util.spec_from_file_location("obsidian_sync", Path(__file__).with_name("sync-obsidian.py"))
sync = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sync)


class ObsidianSyncTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.vault = self.root / "vault"
        self.git("init", "-q")
        self.git("config", "user.name", "Synthetic QA")
        self.git("config", "user.email", "qa@example.invalid")
        self.write("docs/PROJECT_CONTEXT.md", "# Test context\n")
        self.write("dist/image.png", b"\x89PNG\x00synthetic")
        self.write("docs/verification/test.json", '{"status":"synthetic"}\n')
        self.commit()

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.repo), *args], stderr=subprocess.STDOUT)

    def write(self, name, value):
        path = self.repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(value.encode() if isinstance(value, str) else value)

    def commit(self):
        self.git("add", ".")
        self.git("commit", "-qm", "Synthetic snapshot")

    def target(self, name="docs/PROJECT_CONTEXT.md"):
        return self.vault / sync.MIRROR / name

    def test_complete_snapshot_and_untracked_exclusion(self):
        self.write("outputs/private.txt", "do not export")
        result = sync.sync(self.repo, self.vault)
        self.assertEqual(result["source_files"], 3)
        self.assertEqual(self.target().read_bytes(), (self.repo / "docs/PROJECT_CONTEXT.md").read_bytes())
        self.assertEqual(self.target("dist/image.png").read_bytes(), (self.repo / "dist/image.png").read_bytes())
        self.assertFalse(self.target("outputs/private.txt").exists())
        self.assertTrue((self.vault / "Сайт/Отчёты проверок/test.md").exists())
        sync.sync(self.repo, self.vault, check=True)

    def test_idempotent_and_check_does_not_write(self):
        with self.assertRaises(ValueError):
            sync.sync(self.repo, self.vault, check=True)
        self.assertFalse(self.vault.exists())
        sync.sync(self.repo, self.vault)
        before = {p: p.stat().st_mtime_ns for p in self.vault.rglob("*") if p.is_file()}
        self.assertEqual(sync.sync(self.repo, self.vault)["written"], 0)
        sync.sync(self.repo, self.vault, check=True)
        self.assertEqual(before, {p: p.stat().st_mtime_ns for p in before})

    def test_conflict_stops_all_writes_and_preserves_personal_note(self):
        sync.sync(self.repo, self.vault)
        self.target().write_text("Owner's correction\n")
        personal = self.vault / "Personal.md"
        personal.write_text("Private ideas\n")
        self.write("docs/new.md", "New committed file\n")
        self.commit()
        with self.assertRaisesRegex(ValueError, "Ручные изменения"):
            sync.sync(self.repo, self.vault)
        self.assertFalse(self.target("docs/new.md").exists())
        self.assertEqual(self.target().read_text(), "Owner's correction\n")
        self.assertEqual(personal.read_text(), "Private ideas\n")

    def test_committed_update_and_dirty_tree_refusal(self):
        sync.sync(self.repo, self.vault)
        self.write("docs/PROJECT_CONTEXT.md", "New context\n")
        with self.assertRaisesRegex(ValueError, "коммит"):
            sync.sync(self.repo, self.vault)
        self.commit()
        sync.sync(self.repo, self.vault)
        self.assertEqual(self.target().read_text(), "New context\n")

    def test_removed_sources_retained_as_history(self):
        sync.sync(self.repo, self.vault)
        (self.repo / "dist/image.png").unlink()
        self.commit()
        sync.sync(self.repo, self.vault)
        self.assertTrue(self.target("dist/image.png").exists())
        manifest = json.loads((self.vault / sync.MANIFEST).read_text())
        self.assertIn(sync.MIRROR + "/dist/image.png", manifest["retired"])
        sync.sync(self.repo, self.vault, check=True)

    def test_symlink_cannot_redirect_writes(self):
        self.vault.mkdir()
        outside = self.root / "outside"
        outside.mkdir()
        (self.vault / "Сайт").symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "Символическая ссылка"):
            sync.sync(self.repo, self.vault)
        self.assertEqual(list(outside.iterdir()), [])

    def test_committed_environment_file_is_rejected(self):
        self.write(".env.production", "SYNTHETIC_ONLY=example\n")
        self.commit()
        with self.assertRaisesRegex(ValueError, "закрытый файл"):
            sync.sync(self.repo, self.vault)
        self.assertFalse(self.vault.exists())

    def test_archive_cannot_silently_omit_tracked_files(self):
        self.write(".gitattributes", "docs/PROJECT_CONTEXT.md export-ignore\n")
        self.commit()
        with self.assertRaisesRegex(ValueError, "Архив отличается"):
            sync.sync(self.repo, self.vault)
        self.assertFalse(self.vault.exists())


if __name__ == "__main__":
    unittest.main()
