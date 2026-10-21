const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const handlers = {};
function signal() { const f = []; return {connect: cb => f.push(cb), emit: (...args) => f.forEach(cb => cb(...args))}; }
const workspace = {windowActivated: signal(), windowRemoved: signal(), currentDesktopChanged: signal(), currentActivityChanged: signal(), clientArea: () => ({x: -1920, y: 30, width: 1920, height: 1050})};
let active;
Object.defineProperty(workspace, 'activeWindow', {get: () => active, set: w => { if (active !== w) { active = w; workspace.windowActivated.emit(w); } }});
function window() {
    let minimized = false;
    return {normalWindow: true, maximizable: true, minimizable: true, resizeable: true, moveable: true, tile: {},
        get minimized() {return minimized;}, set minimized(v) {minimized = v; if (v) workspace.activeWindow = b;},
        setMaximize: function(v,h) {this.max = [v,h];}};
}
const a = window(), b = window(), c = window();
vm.runInNewContext(fs.readFileSync(__dirname + '/../contents/code/main.js', 'utf8'), {workspace, KWin: {MaximizeArea: 2}, registerShortcut: (id, label, key, cb) => handlers[id] = cb});
workspace.activeWindow = a;
handlers.WindowsSnapDown();
assert.equal(a.minimized, true);
assert.equal(active, b);
handlers.WindowsSnapUp();
assert.equal(active, a);
assert.equal(a.minimized, false);
assert.deepEqual(a.max, [true,true]);
handlers.WindowsSnapDown();
workspace.activeWindow = c;
handlers.WindowsSnapUp();
assert.equal(active, c);
assert.equal(a.minimized, true);
workspace.activeWindow = a;
a.minimized = false;
handlers.WindowsSnapLeft();
assert.equal(a.frameGeometry.x, -1920);
assert.equal(a.frameGeometry.y, 30);
assert.equal(a.frameGeometry.height, 1050);
handlers.WindowsSnapRight();
assert.equal(a.frameGeometry.x, -960);
assert.equal(a.frameGeometry.width, 960);
handlers.WindowsSnapRight();
assert.equal(a.frameGeometry.x, -960);
handlers.WindowsSnapDown();
workspace.windowRemoved.emit(a);
handlers.WindowsSnapUp();
assert.equal(active, b);
assert.equal(a.minimized, true);
console.log('PASS: fallback activation, restore, explicit switch, full-height/negative-origin placement, repeat, closed target');
