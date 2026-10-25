var leftWindow = workspace.windowList().filter(function(w) { return w.caption === "Snap Test LEFT"; })[0];
var rightWindow = workspace.windowList().filter(function(w) { return w.caption === "Snap Test RIGHT"; })[0];
function state(w) {
    return {frame: w.frameGeometry, minimized: w.minimized, max: w.maximizeMode,
        tiled: !!w.tile, relative: w.tile ? w.tile.relativeGeometry : null};
}
registerShortcut("SnapTestSelectLeft", "Test left", "", function() { workspace.activeWindow = leftWindow; });
registerShortcut("SnapTestSelectRight", "Test right", "", function() { workspace.activeWindow = rightWindow; });
registerShortcut("SnapTestCorner", "Test corner", "", function() { workspace.slotWindowQuickTileTopLeft(); });
registerShortcut("SnapTestCustom", "Test custom", "", function() {
    workspace.tilingForScreen(leftWindow.output).rootTile.tiles[1].manage(leftWindow);
});
registerShortcut("SnapTestCloseLeft", "Test close", "", function() { leftWindow.closeWindow(); });
registerShortcut("SnapTestDump", "Test snapshot", "", function() {
    callDBus("local.SnapTest", "/test", "local.SnapTest", "report", JSON.stringify({
        left: workspace.windowList().indexOf(leftWindow) < 0 ? null : state(leftWindow), right: state(rightWindow),
        active: workspace.activeWindow.caption,
        custom: workspace.tilingForScreen(rightWindow.output).rootTile.tiles.map(function(t) { return t.relativeGeometry; })
    }));
});
