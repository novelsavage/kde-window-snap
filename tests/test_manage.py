"""Exercise install/restore transactions without touching the user's desktop."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


class InstallerTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location('snap_manage', ROOT / 'manage.py')
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.module.TARGET = Path(self.temp.name) / 'scripts/windows-snap'
        self.module.BACKUP = Path(self.temp.name) / 'backup/shortcuts.json'
        self.original = {n: [100 + i] for i, n in enumerate(self.module.OLD)}
        self.original.update({n: [] for n in self.module.KEYS})
        self.keys = {n: list(v) for n, v in self.original.items()}
        self.loaded = False
        self.running = False
        self.fail = False
        self.accel = SimpleNamespace(shortcut=lambda a: self.keys[a[1]], setShortcut=self.assign)
        self.scripting = SimpleNamespace(isScriptLoaded=lambda _: self.loaded, unloadScript=self.unload, start=self.start)
        self.bus = SimpleNamespace(get_object=lambda service, path: path, call_blocking=self.load)
        self.dbus = SimpleNamespace(SessionBus=lambda: self.bus, Array=lambda v, **_: v,
                                    UInt32=int, Interface=self.interface)

    def interface(self, obj, name):
        if name == 'org.kde.KGlobalAccel':
            return self.accel
        if name == 'org.kde.kwin.Scripting':
            return self.scripting
        raise AssertionError('Do not address Script<ID>: its object path may belong to another script')

    def assign(self, action, keys, flags):
        if self.fail and action[1] == 'WindowsSnapRight' and keys:
            self.fail = False
            return []
        self.keys[action[1]] = list(keys)
        return keys

    def unload(self, _):
        self.loaded = False
        self.running = False

    def start(self):
        self.running = self.loaded

    def load(self, *args):
        self.assertEqual(args[4], 'ss')
        self.assertTrue(Path(args[5][0]).is_file())
        self.loaded = True
        return 1

    def command(self, name):
        with patch.dict(sys.modules, {'dbus': self.dbus}), patch.object(
            sys, 'argv', ['manage.py', name]
        ), patch.object(self.module.subprocess, 'run'):
            self.module.main()

    def test_fresh_install_update_restore_and_uninstall(self):
        self.command('install')
        self.assertTrue(self.running)
        saved = self.module.BACKUP.read_text()
        self.assertEqual(json.loads(saved), self.original)
        self.assertTrue((self.module.TARGET / 'metadata.json').is_file())
        self.assertNotEqual(self.keys, self.original)
        self.command('install')
        self.assertTrue(self.running)
        self.assertEqual(self.module.BACKUP.read_text(), saved)
        self.command('restore')
        self.assertEqual(self.keys, self.original)
        self.assertFalse(self.loaded)
        self.assertFalse(self.module.BACKUP.exists())
        # A later installation captures the user's latest shortcuts.
        self.keys[self.module.OLD[0]] = [777]
        self.command('install')
        self.command('uninstall')
        self.assertEqual(self.keys[self.module.OLD[0]], [777])
        self.assertFalse(self.module.TARGET.exists())

    def test_failed_assignment_rolls_back(self):
        self.fail = True
        with self.assertRaisesRegex(RuntimeError, 'assignment failed'):
            self.command('install')
        self.assertEqual(self.keys, self.original)
        self.assertFalse(self.loaded)
        self.assertFalse(self.module.BACKUP.exists())

    def test_legacy_backup_preserved_and_restored(self):
        self.module.BACKUP.parent.mkdir(parents=True)
        legacy = {n: v for n, v in self.original.items() if n in self.module.OLD}
        self.module.BACKUP.write_text(json.dumps(legacy))
        self.command('install')
        self.assertEqual(json.loads(self.module.BACKUP.read_text()), legacy)
        self.command('restore')
        self.assertEqual(self.keys, self.original)

    def test_invalid_backup_does_not_change_shortcuts(self):
        self.module.BACKUP.parent.mkdir(parents=True)
        self.module.BACKUP.write_text('{}')
        with self.assertRaisesRegex(RuntimeError, 'Invalid shortcut backup'):
            self.command('restore')
        self.assertEqual(self.keys, self.original)


if __name__ == '__main__':
    unittest.main()
