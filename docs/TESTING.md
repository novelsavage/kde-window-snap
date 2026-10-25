# 隔離GUIテスト

## 確認結果

2026-10-25、KWin 6.6.6 / Wayland / ソフトウェアOpenGL / 仮想画面1280×800で確認。
デスクトップを表示しない`kwin_wayland --virtual`を専用D-Bus・XDGディレクトリで起動しました。
本番のKWin、カーソル、フォーカスにはテスト操作を送っていません。

| 操作 | 結果 |
|---|---|
| 左上配置から左右タイルへ | 高さ800、左右640 + 640 |
| 実ポインターで境界を右へドラッグ | 左800 + 右480、境界の座標が一致 |
| 左右キーの繰り返し | 調整済みの比率を維持 |
| カスタムタイルから左右へ | 標準の調整済みタイルへ。3列カスタムレイアウトは不変 |
| 境界を左へドラッグ | 左500 + 右780 |
| ↓ → ↑ | 最小化した対象を復元して最大化、タイルから離脱 |
| 最大化から左右へ | 残っている相手の比率を利用 |
| 最後の1枚を反対側へ移す | 比率を維持 |
| 最小化した対象を閉じる → ↑ | 閉じた対象を破棄し、現在のウィンドウを最大化 |
| 他のスクリプトがある状態で再読込 | 再利用されたD-BusオブジェクトIDに依存せず、実行開始を確認 |

実機の複数画面・画面切断・アプリごとの最小サイズ制約は未検証です。
負の座標と比率保持は単体テストでも確認しています。

### 更新時の実行開始

KWin 6.6は読み込み中のスクリプト数をD-BusのオブジェクトIDに使用します。
途中のスクリプトを解除して再読込すると、別のスクリプトの既存パスと衝突する場合があります。
`isScriptLoaded()`がtrueでも、そのスクリプトが実行開始済みとは限りません。
インストーラーは有効設定を先に保存し、`/Scripting.start()`から内部リスト経由で開始します。
隔離テストでも、別のスクリプトを残して再読込した後にコードが実行されることを確認します。

## Cua Driver

Cua Driver 0.37.0を同じ隔離セッションで起動し、専用ソケットでCLIを接続しました。

- `list_windows`：テストアプリのプロセスを検出。ただしウィンドウごとの形状は0で返り、利用不可。
- `get_window_state`：AT-SPI経由でLEFT・RIGHTのラベルを取得。ただしdegraded応答。
- `drag`：`background_unavailable`で拒否。フォーカスを奪わない境界ドラッグは実行できませんでした。
- Cuaの前面操作への切り替えは行わず、代わりに隔離KWinだけへ接続する入力ヘルパーで実ドラッグを確認しました。

したがって、Cuaの導入成功を連動リサイズのGUIテスト成功とは扱っていません。
連動動作の証拠はKWinの実形状とスクリーンショットです。
KDE/KWinの対応範囲は[Cua公式](https://cua.ai/docs/cua-driver/concepts/platform-support)を参照。

## 再現方法

必要なもの：KWin 6.6、dbus-run-session、ディストリビューションのpython3-dbus・python3-gi・
python3-pyqt6、Cコンパイラー、Waylandクライアント開発ヘッダー、wayland-scanner。
Pythonパッケージの追加インストールは不要です。

KDEのfake-inputプロトコルXMLを別途用意して、テスト専用ヘルパーをビルドします。
XMLは`plasma-wayland-protocols`の開発用パッケージ、または
[KDE公式ソース](https://github.com/KDE/plasma-wayland-protocols/blob/master/src/protocols/fake-input.xml)で取得できます。
以下の`/path/to/fake-input.xml`をそのパスに置き換えて実行してください。

```sh
mkdir -p /tmp/snap-input-build
wayland-scanner client-header /path/to/fake-input.xml /tmp/snap-input-build/fake-input.h
wayland-scanner private-code /path/to/fake-input.xml /tmp/snap-input-build/fake-input.c
cc -I/tmp/snap-input-build tests/integration/drag.c /tmp/snap-input-build/fake-input.c \
  $(pkg-config --cflags --libs wayland-client) -lm -o /tmp/snap-input-build/drag
/usr/bin/python3 tests/integration/run.py \
  --input-helper /tmp/snap-input-build/drag --artifacts /tmp/snap-test-results
```

Cuaも検証する場合だけ、最後に`--cua /path/to/cua-driver`を追加します。
テストはCuaを自動インストールせず、MCP設定や自動起動設定も変更しません。

テストランナーが一時環境の作成と終了処理を行います。結果JSON・前後PNG・ログは
指定したartifactsディレクトリへ保存します。ログにはローカルパスなどが含まれ得るため、
公開前に内容を確認してください。

テスト用KWinに限り、fake-inputと直接スクリーンショットの権限チェックを解除しています。
この設定を通常のPlasmaセッションに適用しないでください。
入力ヘルパーも`WAYLAND_DISPLAY=snap-test`以外を拒否します。

## 仕組み

左右キーは、既存の標準クイックタイルのルートから左・右のタイルを探し、
`Tile.manage(window)`でウィンドウを参加させます。まだ標準タイルが存在しないときは
KWinの標準スナップ操作で参加を開始します。位置・サイズだけの代入は使いません。

同じ側への再配置は何も変更せず、最後の1枚が左右を移る際にKWinが一時的に
比率をリセットする場合も、操作直前の比率を戻します。通常の最大化では参加を解除します。

参照：[KWin QuickRootTile](https://github.com/KDE/kwin/blob/Plasma/6.6/src/tiles/quicktile.cpp)、
[Tile](https://github.com/KDE/kwin/blob/Plasma/6.6/src/tiles/tile.cpp)。
