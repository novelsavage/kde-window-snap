#!/usr/bin/python3
"""Run real boundary drags on a disposable headless KWin, never the host bus."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def wait_for(test, message, seconds=15):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if test():
            return
        time.sleep(.1)
    raise RuntimeError(message)


def inside(args):
    import dbus
    root = Path(args.workdir)
    if (os.environ.get('SNAP_TEST_ISOLATED') != str(root)
            or os.environ.get('XDG_RUNTIME_DIR') != str(root / 'runtime')
            or os.environ.get('DBUS_SESSION_BUS_ADDRESS') == os.environ.get('SNAP_TEST_HOST_BUS')):
        raise RuntimeError('Refusing to run outside the isolated test session')
    # These permission-check overrides exist ONLY in the disposable compositor.
    # They let our test client inject a drag and capture that virtual framebuffer.
    env = os.environ.copy()
    env.update(QT_QPA_PLATFORM='offscreen', LIBGL_ALWAYS_SOFTWARE='1', KWIN_COMPOSE='O2',
               KWIN_WAYLAND_NO_PERMISSION_CHECKS='1', KWIN_SCREENSHOT_NO_PERMISSION_CHECKS='1')
    children = []

    def spawn(command, child_env, log):
        with (root / log).open('w') as output:
            p = subprocess.Popen(command, env=child_env, stdout=output, stderr=subprocess.STDOUT)
        children.append(p)
        return p

    result = {'passed': [], 'states': {}, 'cua': {}}
    try:
        spawn(['kwin_wayland', '--virtual', '--width', '1280', '--height', '800',
               '--socket', 'snap-test', '--no-lockscreen', '--no-kactivities'], env, 'kwin.log')
        bus = dbus.SessionBus()
        wait_for(lambda: bus.name_has_owner('org.kde.KWin') and (root / 'runtime/snap-test').exists(), 'KWin did not start')
        client_env = os.environ.copy()
        client_env.update(QT_QPA_PLATFORM='wayland', WAYLAND_DISPLAY='snap-test',
                          XDG_SESSION_TYPE='wayland', XDG_CURRENT_DESKTOP='KDE')
        app = spawn([sys.executable, str(HERE / 'apps.py')], client_env, 'apps.log')
        spawn([sys.executable, str(HERE / 'observer.py'), str(root)], client_env, 'observer.log')
        wait_for(lambda: bus.name_has_owner('local.SnapTest'), 'Observer did not start')
        # Allow initial app surfaces to configure; no input goes to the host.
        time.sleep(1)
        source = root / 'script.js'
        source.write_text((REPO / 'contents/code/main.js').read_text() + '\n' + (HERE / 'harness.js').read_text())
        script_id = bus.call_blocking('org.kde.KWin', '/Scripting', 'org.kde.kwin.Scripting',
                                     'loadScript', 'ss', (str(source), 'snap-integration'))
        dbus.Interface(bus.get_object('org.kde.KWin', f'/Scripting/Script{script_id}'), 'org.kde.kwin.Script').run()
        component = dbus.Interface(bus.get_object('org.kde.kglobalaccel', '/component/kwin'), 'org.kde.kglobalaccel.Component')

        def action(*names):
            for name in names:
                component.invokeShortcut(name)
                time.sleep(.2)

        def snapshot(label):
            path = root / 'snapshot.json'
            path.unlink(missing_ok=True)
            action('SnapTestDump')
            wait_for(path.exists, 'No snapshot from KWin')
            value = json.loads(path.read_text())
            result['states'][label] = value
            return value

        def check(condition, message):
            if not condition:
                raise AssertionError(message)
            result['passed'].append(message)

        def drag(x1, x2):
            subprocess.run([args.input_helper, str(x1), '400', str(x2), '400'], env=client_env, check=True, timeout=10)
            time.sleep(.3)

        def capture(name):
            subprocess.run([sys.executable, str(HERE / 'screenshot.py'), str(root / name)],
                           env=client_env, check=True, timeout=15, stdout=subprocess.DEVNULL)

        action('SnapTestSelectLeft', 'SnapTestCorner', 'WindowsSnapLeft', 'SnapTestSelectRight', 'WindowsSnapRight')
        initial = snapshot('initial')
        check(initial['left']['frame']['width'] == initial['right']['frame']['width'] == 640, 'corner -> full-height native halves')
        custom = initial['custom']
        capture('before.png')
        drag(639, 800)
        resized = snapshot('resized')
        check(resized['left']['frame']['width'] == 800 and resized['right']['frame']['x'] == 800
              and resized['right']['frame']['width'] == 480, 'real pointer drag produces 800 + 480 = 1280')
        capture('after.png')
        action('SnapTestSelectLeft', 'WindowsSnapLeft', 'WindowsSnapLeft', 'SnapTestSelectRight', 'WindowsSnapRight')
        again = snapshot('repeated')
        check(again['left']['frame'] == resized['left']['frame'] and again['right']['frame'] == resized['right']['frame'], 'repeated arrows preserve split')
        action('SnapTestCustom', 'SnapTestSelectLeft', 'WindowsSnapLeft')
        value = snapshot('from_custom')
        check(value['left']['frame']['width'] == 800 and value['custom'] == custom, 'custom layout unchanged and native ratio reused')
        drag(800, 500)
        value = snapshot('reverse_drag')
        check(value['left']['frame']['width'] == 500 and value['right']['frame']['width'] == 780, 'reverse boundary drag resizes both windows')
        action('SnapTestSelectLeft', 'WindowsSnapDown')
        check(snapshot('minimized')['left']['minimized'], 'down minimizes')
        action('WindowsSnapUp')
        value = snapshot('restored')
        check(not value['left']['minimized'] and value['left']['max'] == 3 and not value['left']['tiled'], 'up restores and maximizes outside tile')
        action('WindowsSnapLeft')
        check(snapshot('retiled')['left']['frame']['width'] == 500, 'maximize -> tile preserves peer ratio')

        if args.cua:
            socket = str(root / 'cua.sock')
            cua_env = dict(client_env, CUA_DRIVER_RS_ENABLE_WAYLAND='1', CUA_DRIVER_RS_HOME=str(root / 'cua'), CUA_DRIVER_RS_TELEMETRY_ENABLED='0')
            spawn([args.cua, 'serve', '--socket', socket, '--pid-file', str(root / 'cua.pid'), '--no-overlay'], cua_env, 'cua.log')
            wait_for(lambda: Path(socket).exists(), 'Cua Driver did not start')

            def call(tool, payload):
                p = subprocess.run([args.cua, 'call', tool, json.dumps(payload), '--socket', socket],
                                   env=cua_env, capture_output=True, text=True, timeout=20)
                return json.loads(p.stdout)

            result['cua']['version'] = subprocess.check_output([args.cua, '--version'], env=cua_env, text=True).strip()
            windows = call('list_windows', {}).get('windows', [])
            windows = [w for w in windows if w.get('pid') == app.pid]
            result['cua']['test_windows'] = windows
            if windows:
                window_id = windows[0]['window_id']
                result['cua']['read'] = call('get_window_state', {'pid': app.pid, 'window_id': window_id, 'include_screenshot': False, 'max_elements': 15})
                result['cua']['drag'] = call('drag', {'pid': app.pid, 'window_id': window_id, 'from_x': 499, 'from_y': 400,
                    'to_x': 600, 'to_y': 400, 'coordinate_frame': 'desktop'})
            else:
                result['cua']['limitation'] = 'No target windows discovered'
        action('SnapTestSelectRight', 'WindowsSnapUp', 'SnapTestSelectLeft', 'WindowsSnapRight')
        value = snapshot('single_switch')
        check(value['left']['frame']['x'] == 500 and value['left']['frame']['width'] == 780,
              'last tiled window changes sides without resetting split')
        action('WindowsSnapLeft', 'WindowsSnapDown', 'SnapTestCloseLeft', 'WindowsSnapUp')
        check(snapshot('closed')['right']['max'] == 3, 'closed restore target discarded')
        # Reproduce KWin 6.6's reused object ID: unload script 0 while a higher
        # ID remains. The new script's path can address the other script.
        dummy = root / 'dummy.js'
        dummy.write_text('// intentionally left dormant\n')
        bus.call_blocking('org.kde.KWin', '/Scripting', 'org.kde.kwin.Scripting',
                         'loadScript', 'ss', (str(dummy), 'snap-test-dummy'))
        scripting = dbus.Interface(bus.get_object('org.kde.KWin', '/Scripting'), 'org.kde.kwin.Scripting')
        scripting.unloadScript('snap-integration')
        wait_for(lambda: not scripting.isScriptLoaded('snap-integration'), 'Script did not unload')
        marker = root / 'reloaded.js'
        marker.write_text('callDBus("local.SnapTest", "/test", "local.SnapTest", "report", JSON.stringify({reloaded:true}));\n')
        (root / 'snapshot.json').unlink(missing_ok=True)
        bus.call_blocking('org.kde.KWin', '/Scripting', 'org.kde.kwin.Scripting',
                         'loadScript', 'ss', (str(marker), 'snap-test-reloaded'))
        scripting.start()
        wait_for(lambda: (root / 'snapshot.json').exists(), 'Reloaded script did not execute')
        check(json.loads((root / 'snapshot.json').read_text()).get('reloaded'), 'reload starts despite reused script object ID')
        result['error'] = None
    except Exception as error:
        result['error'] = str(error)
        raise
    finally:
        (root / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
        for child in reversed(children):
            if child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    child.kill()
        if args.artifacts:
            target = Path(args.artifacts)
            target.mkdir(parents=True, exist_ok=True)
            for name in ('result.json', 'before.png', 'after.png', 'kwin.log', 'cua.log'):
                if (root / name).exists():
                    shutil.copy2(root / name, target / name)
    print('PASS:', ', '.join(result['passed']))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input-helper', required=True)
    parser.add_argument('--artifacts')
    parser.add_argument('--cua')
    parser.add_argument('--inside', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--workdir', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.inside:
        inside(args)
        return
    with tempfile.TemporaryDirectory(prefix='kde-snap-integration-') as directory:
        root = Path(directory)
        env = os.environ.copy()
        for name in ('DISPLAY', 'WAYLAND_DISPLAY', 'SESSION_MANAGER', 'DBUS_SESSION_BUS_ADDRESS'):
            env.pop(name, None)
        for key, name in [('XDG_RUNTIME_DIR', 'runtime'), ('XDG_CONFIG_HOME', 'config'), ('XDG_DATA_HOME', 'data'), ('XDG_CACHE_HOME', 'cache')]:
            (root / name).mkdir(mode=0o700)
            env[key] = str(root / name)
        # This test uses direct compositor protocols, not desktop portals. Avoid
        # auto-starting portal UI and document FUSE mounts in the disposable bus.
        services = root / 'data/dbus-1/services'
        services.mkdir(parents=True)
        (services / 'org.freedesktop.portal.Desktop.service').write_text(
            '[D-BUS Service]\nName=org.freedesktop.portal.Desktop\nExec=/bin/false\n')
        env.update(SNAP_TEST_ISOLATED=str(root), SNAP_TEST_HOST_BUS=os.environ.get('DBUS_SESSION_BUS_ADDRESS', ''))
        command = ['dbus-run-session', '--', sys.executable, str(Path(__file__).resolve()),
                   '--inside', '--workdir', directory, '--input-helper', str(Path(args.input_helper).resolve())]
        if args.cua:
            command += ['--cua', str(Path(args.cua).resolve())]
        if args.artifacts:
            command += ['--artifacts', str(Path(args.artifacts).resolve())]
        subprocess.run(command, env=env, check=True)


if __name__ == '__main__':
    main()
