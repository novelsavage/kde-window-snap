"use strict";

// No input logging, external process or timer. State lasts for this KWin session.
var pending = null;
var minimizing = false;

function usable(w) {
    return w && !w.deleted && !w.desktopWindow && !w.dock &&
        (w.normalWindow || w.dialog);
}

function untile(w) {
    if (!w.tile) return;
    if (typeof w.tile.unmanage === "function") w.tile.unmanage(w);
    else w.tile = null; // Compatibility with earlier Plasma 6 releases.
}

function customRoot(output) {
    if (typeof workspace.rootTile === "function") return workspace.rootTile(output, workspace.currentDesktop);
    return workspace.tilingForScreen(output).rootTile;
}

// Quick tiles have their own eight-child root, separate from Meta+T layouts.
// Reuse a live native tile to retain its split and avoid the standard shortcut's
// directional composition (top-left) and repeated-key monitor cycling.
function nativeSide(w, right) {
    var windows = workspace.windowList();
    for (var i = 0; i < windows.length; ++i) {
        var peer = windows[i];
        if (peer.deleted || peer.output !== w.output) continue;
        if (peer.desktops.length && peer.desktops.indexOf(workspace.currentDesktop) < 0) continue;
        var tile = peer.tile;
        if (!tile || !tile.parent || tile.parent.parent) continue;
        if (tile.parent === customRoot(w.output)) continue;
        var siblings = tile.parent.tiles;
        if (siblings.length !== 8) continue;
        for (var j = 0; j < siblings.length; ++j) {
            var candidate = siblings[j];
            var g = candidate.relativeGeometry;
            if (Math.abs(g.y) > 0.001 || Math.abs(g.height - 1) > 0.001) continue;
            if (right ? g.x > 0 && Math.abs(g.x + g.width - 1) < 0.001
                      : Math.abs(g.x) < 0.001 && g.width < 1) return candidate;
        }
    }
    return null;
}

function maximize() {
    var w = pending && usable(pending) && pending.minimized ? pending : workspace.activeWindow;
    pending = null;
    if (!usable(w) || !w.maximizable) return;
    w.minimized = false;
    workspace.activeWindow = w;
    untile(w);
    w.setMaximize(true, true);
}

function minimize() {
    var w = workspace.activeWindow;
    if (!usable(w) || !w.minimizable) return;
    pending = w;
    // KWin synchronously activates the fallback window in setMinimized().
    // Ignore that activation, but invalidate on subsequent activation changes.
    minimizing = true;
    try { w.minimized = true; }
    finally { minimizing = false; }
}

function snap(right) {
    pending = null;
    var w = workspace.activeWindow;
    if (!usable(w) || !w.resizeable || !w.moveable) return;
    var target = nativeSide(w, right);
    // Nothing to do: importantly, do not detach the last window and reset its split.
    if (target && w.tile === target) return;
    w.setMaximize(false, false);
    if (target) {
        var g = target.relativeGeometry;
        var saved = {x: g.x, y: g.y, width: g.width, height: g.height};
        if (typeof target.manage === "function") target.manage(w);
        else w.tile = target;
        // Moving the last native window between sides briefly empties the root;
        // KWin resets its split at that moment. Retain the user's adjusted ratio.
        if (w.tile === target) target.relativeGeometry = saved;
    } else {
        // Bootstrap the native root without inheriting a custom or corner tile.
        untile(w);
        if (right) workspace.slotWindowQuickTileRight();
        else workspace.slotWindowQuickTileLeft();
    }
}

workspace.windowActivated.connect(function () {
    if (!minimizing) pending = null;
});
workspace.windowRemoved.connect(function (w) {
    if (pending === w) pending = null;
});
workspace.currentDesktopChanged.connect(function () { pending = null; });
workspace.currentActivityChanged.connect(function () { pending = null; });

registerShortcut("WindowsSnapUp", "Arrow Snap: Maximize or restore last minimized", "", maximize);
registerShortcut("WindowsSnapDown", "Arrow Snap: Minimize and remember", "", minimize);
registerShortcut("WindowsSnapLeft", "Arrow Snap: Full-height left half", "", function () { snap(false); });
registerShortcut("WindowsSnapRight", "Arrow Snap: Full-height right half", "", function () { snap(true); });
