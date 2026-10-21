"use strict";

// No input logging, external process or timer. State lasts for this KWin session.
var pending = null;
var minimizing = false;

function usable(w) {
    return w && !w.deleted && !w.desktopWindow && !w.dock &&
        (w.normalWindow || w.dialog);
}

function maximize() {
    var w = pending && usable(pending) && pending.minimized ? pending : workspace.activeWindow;
    pending = null;
    if (!usable(w) || !w.maximizable) return;
    w.minimized = false;
    workspace.activeWindow = w;
    w.tile = null;
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
    var area = workspace.clientArea(KWin.MaximizeArea, w);
    var leftWidth = Math.floor(area.width / 2);
    w.tile = null;
    w.setMaximize(false, false);
    w.frameGeometry = {
        x: area.x + (right ? leftWidth : 0),
        y: area.y,
        width: right ? area.width - leftWidth : leftWidth,
        height: area.height
    };
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
