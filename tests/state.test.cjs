const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const handlers = {};
function signal() { const f = []; return {connect: cb => f.push(cb), emit: (...args) => f.forEach(cb => cb(...args))}; }
const desktop = {};
const customRoot = {parent: null, tiles: [{}, {}, {}]};
const output = {x: -1920, y: 30, width: 1920, height: 1050, customRoot};
let active, detached = 0, bootstraps = 0;
function tile(root, geometry) {
    return {parent: root, relativeGeometry: geometry, windows: [],
        manage(w) {
            if (w.tile === this) return true;
            if (w.tile) w.tile.unmanage(w);
            this.windows.push(w); w.tile = this;
            const g = this.relativeGeometry, o = w.output;
            w.frameGeometry = {x: o.x + g.x * o.width, y: o.y + g.y * o.height, width: g.width * o.width, height: g.height * o.height};
            return true;
        },
        unmanage(w) {detached++; this.windows = this.windows.filter(x => x !== w); if (w.tile === this) w.tile = null;}
    };
}
const nativeRoot = {parent: null, tiles: []};
const left = tile(nativeRoot, {x: 0, y: 0, width: .5, height: 1});
const right = tile(nativeRoot, {x: .5, y: 0, width: .5, height: 1});
nativeRoot.tiles = [left, right, ...Array.from({length: 6}, () => tile(nativeRoot, {x:0,y:0,width:.5,height:.5}))];
const workspace = {
    currentDesktop: desktop, windowActivated: signal(), windowRemoved: signal(), currentDesktopChanged: signal(), currentActivityChanged: signal(),
    windowList: () => [a, b, c], tilingForScreen: o => ({rootTile: o.customRoot}),
    slotWindowQuickTileLeft: () => {bootstraps++; left.manage(active);},
    slotWindowQuickTileRight: () => {bootstraps++; right.manage(active);}
};
Object.defineProperty(workspace, 'activeWindow', {get: () => active, set: w => { if (active !== w) { active = w; workspace.windowActivated.emit(w); } }});
function window() {
    let minimized = false;
    return {normalWindow: true, maximizable: true, minimizable: true, resizeable: true, moveable: true, tile: null, output, desktops: [],
        get minimized() {return minimized;}, set minimized(v) {minimized = v; if (v) workspace.activeWindow = b;},
        setMaximize: function(v,h) {this.max = [v,h];}};
}
const a = window(), b = window(), c = window();
vm.runInNewContext(fs.readFileSync(__dirname + '/../contents/code/main.js', 'utf8'), {workspace, registerShortcut: (id, label, key, cb) => handlers[id] = cb});
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
workspace.activeWindow = a; a.minimized = false;
handlers.WindowsSnapLeft();
assert.equal(a.tile, left);
assert.equal(a.frameGeometry.x, -1920);
assert.equal(a.frameGeometry.y, 30);
assert.equal(a.frameGeometry.height, 1050);
assert.equal(bootstraps, 1);
workspace.activeWindow = b;
handlers.WindowsSnapRight();
assert.equal(b.tile, right);
assert.equal(bootstraps, 1, 'reuse native tile instead of toggling shortcut');
// Simulate the native engine changing the shared split after a pointer drag.
left.relativeGeometry.width = .625;
right.relativeGeometry.x = .625; right.relativeGeometry.width = .375;
const before = detached;
workspace.activeWindow = a;
handlers.WindowsSnapLeft();
assert.equal(detached, before, 'repeating a side must not detach/reset the native split');
handlers.WindowsSnapRight();
assert.equal(a.tile, right);
assert.equal(a.frameGeometry.x, -720);
assert.equal(a.frameGeometry.width, 720);
assert.equal(customRoot.tiles.length, 3, 'do not rewrite custom Meta+T layout');
const custom = tile(customRoot, {x:0,y:0,width:.25,height:1});
custom.manage(a);
handlers.WindowsSnapLeft();
assert.equal(a.tile, left, 'custom -> native full-height side');
assert.equal(a.frameGeometry.width, 1200, 'reuse adjusted ratio');
nativeRoot.tiles[4].manage(a);
handlers.WindowsSnapLeft();
assert.equal(a.tile, left, 'corner -> native full-height side');
handlers.WindowsSnapUp();
assert.equal(a.tile, null, 'maximize must leave tile membership');
handlers.WindowsSnapDown();
workspace.windowRemoved.emit(a);
handlers.WindowsSnapUp();
assert.equal(active, b);
assert.equal(a.minimized, true);
console.log('PASS: restore, explicit switch, native membership, negative origins, adjusted ratio, repeated side, custom/corner transitions, maximize, closed target');
