#!/usr/bin/python3
"""Install Arrow Snap and change only its own KWin shortcuts."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parent
DATA = Path(os.environ.get('XDG_DATA_HOME') or Path.home() / '.local/share')
TARGET = DATA / 'kwin/scripts/windows-snap'
BACKUP = DATA / 'kwin/windows-snap-backup/shortcuts.json'
KEYS = {'WindowsSnapUp': 0x11000013, 'WindowsSnapDown': 0x11000015,
        'WindowsSnapLeft': 0x11000012, 'WindowsSnapRight': 0x11000014}
OLD = ['Window Quick Tile Top', 'Window Quick Tile Bottom',
       'Window Quick Tile Left', 'Window Quick Tile Right']


def deploy():
    if ROOT == TARGET.resolve():
        return
    TARGET.mkdir(parents=True, exist_ok=True)
    for name in ('metadata.json', 'manage.py', 'README.md', 'diagram.svg', 'LICENSE'):
        shutil.copy2(ROOT / name, TARGET / name)
    shutil.copytree(ROOT / 'contents', TARGET / 'contents', dirs_exist_ok=True)
    shutil.copytree(ROOT / 'docs', TARGET / 'docs', dirs_exist_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['install', 'enable', 'restore', 'uninstall'])
    command = parser.parse_args().command
    try:
        import dbus
    except ImportError:
        parser.exit(1, 'python3-dbus is required. Use /usr/bin/python3 with your distribution package.\n')
    bus = dbus.SessionBus()
    accel = dbus.Interface(bus.get_object('org.kde.kglobalaccel', '/kglobalaccel'), 'org.kde.KGlobalAccel')
    scripting = dbus.Interface(bus.get_object('org.kde.KWin', '/Scripting'), 'org.kde.kwin.Scripting')

    def action(name):
        return dbus.Array(['kwin', name, 'KWin', name], signature='s')

    def snapshot():
        return {n: list(map(int, accel.shortcut(action(n)))) for n in OLD + list(KEYS)}

    def assign(name, keys):
        result = accel.setShortcut(action(name), dbus.Array(keys, signature='i'), dbus.UInt32(4))
        if list(result) != keys:
            raise RuntimeError(f'Shortcut assignment failed: {name}: {result}')

    def enabled(value):
        subprocess.run(['kwriteconfig6', '--file', 'kwinrc', '--group', 'Plugins',
                        '--key', 'windows-snapEnabled', value], check=True)

    def load():
        script_id = bus.call_blocking('org.kde.KWin', '/Scripting', 'org.kde.kwin.Scripting',
                                     'loadScript', 'ss', (str(TARGET / 'contents/code/main.js'), 'windows-snap'))
        if script_id < 0:
            raise RuntimeError('KWin could not load the script')
        dbus.Interface(bus.get_object('org.kde.KWin', f'/Scripting/Script{script_id}'),
                       'org.kde.kwin.Script').run()

    loaded = scripting.isScriptLoaded('windows-snap')
    if command in ('install', 'enable'):
        previous = snapshot()
        created = not BACKUP.exists()
        if created:
            BACKUP.parent.mkdir(parents=True, exist_ok=True)
            # Exclusive creation prevents an accidental overwrite of the restore point.
            with BACKUP.open('x') as file:
                json.dump(previous, file, indent=2)
        try:
            deploy()
            if loaded:
                scripting.unloadScript('windows-snap')
            load()
            for name in OLD:
                assign(name, [])
            for name, key in KEYS.items():
                assign(name, [key])
            enabled('true')
        except Exception:
            # Release our arrows before restoring potentially overlapping assignments.
            for name in KEYS:
                assign(name, [])
            for name, keys in previous.items():
                assign(name, keys)
            if scripting.isScriptLoaded('windows-snap'):
                scripting.unloadScript('windows-snap')
            if loaded:
                load()
            else:
                enabled('false')
            if created:
                BACKUP.unlink()
            raise
        print('Enabled: Meta+Up/Down/Left/Right')
        return

    if BACKUP.exists():
        original = json.loads(BACKUP.read_text())
        # Validate before changing any live shortcuts. Also accepts the original
        # local version's backup, which only recorded the four standard actions.
        if not all(n in original for n in OLD) or not all(
            isinstance(v, list) and all(type(k) is int for k in v) for v in original.values()
        ):
            raise RuntimeError('Invalid shortcut backup; no changes made')
        if any(n not in OLD + list(KEYS) for n in original):
            raise RuntimeError('Unexpected actions in backup; no changes made')
        for name in KEYS:
            assign(name, [])
        for name, keys in original.items():
            assign(name, keys)
        enabled('false')
        if loaded:
            scripting.unloadScript('windows-snap')
        BACKUP.unlink()
        print('Restored original shortcuts')
    elif loaded:
        raise RuntimeError('Restore point missing; refusing to discard your shortcut configuration')
    else:
        enabled('false')
        print('Already disabled; no shortcuts changed')
    if command == 'uninstall':
        if TARGET.exists():
            shutil.rmtree(TARGET)
        print('Removed installed script')


if __name__ == '__main__':
    main()
