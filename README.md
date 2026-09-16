# ipv4-run

Mac全体のネットワーク設定を変えずに、**gcloudのPythonプロセス内の通信をIPv4に限定する**小さなラッパーです。IPv6の接続待ちでgcloudが長時間止まる環境のための暫定的な回避策です。

```sh
ipv4-run gcloud auth login
ipv4-run gcloud projects list
```

## 対応範囲

- 初版はGoogle Cloud CLIの通常のPython版 `bin/gcloud` 専用です。任意のコマンドを制限するツールではありません。
- macOS / Linux、ラッパー用Python 3.10以上が必要です。gcloudには、SDK自身が選択したPythonを使います。
- gcloud 585.0.0で起動を確認しています。SDKの内部起動方式に依存する非公式の回避策です。
- 標準入力・出力・エラー、引数、終了コード、シグナルを引き継ぎます。ブラウザでの本人確認は通常どおり必要です。
- `gcloud` が別プロセスで実行するSSH、ブラウザ、gsutil等には制限が及びません。ネイティブ拡張などPythonのsocket APIを使わない通信も対象外です。
- セキュリティ境界や通信遮断の保証を提供するツールではありません。通常の `gcloud` や他のアプリの動作は変更しません。

## インストール

### ソースから試す

```sh
git clone https://github.com/s4na/ipv4-run.git
cd ipv4-run
./bin/ipv4-run gcloud version
```

`bin` と `libexec` の配置を保ってください。`bin/ipv4-run` のシンボリックリンクをPATH上に置くこともできます。gcloudは別途インストールし、PATHに追加してください。

### Homebrew（mainへのマージ後）

このリポジトリ自身を明示的なURLでtapとして登録します。初版は未リリースのため、HEAD版のみです。

```sh
brew tap s4na/ipv4-run https://github.com/s4na/ipv4-run.git
brew install --HEAD s4na/ipv4-run/ipv4-run
```

削除する場合：

```sh
brew uninstall ipv4-run
brew untap s4na/ipv4-run
```

## 仕組み

1. PATH上の `gcloud` を探し、SDKの `lib/gcloud.py` があることを確認します。
2. 子プロセスにだけ `CLOUDSDK_PYTHON_ARGS` を設定し、元のSDK起動スクリプトを実行します。
3. SDKが選んだPython内で `socket.getaddrinfo` をIPv4専用にし、IPv6 socketの作成を拒否してから `gcloud.py` を実行します。

SDKファイル、シェル設定、Macのネットワーク設定は書き換えません。ラッパーは標準入力をコードの受け渡しに使わないので、認証コードなどの対話入力が可能です。gcloud自体による通常の認証情報・設定の保存は発生します。

カスタム `CLOUDSDK_PYTHON_ARGS` とGo版を選ぶ `CLOUDSDK_USE_GOCLOUD` は対応外としてエラーにします。独自のgcloud起動スクリプトやシェル関数も対応外です。`CLOUDSDK_PYTHON` による通常のPython選択は引き続きSDKが扱います。

## 検証

```sh
python3 -m unittest discover -s tests -v
```

テストは外部アカウント不要です。SDKを模した起動スクリプトとローカルのIPv4サーバーで、名前解決・通信、IPv6拒否、空文字や空白を含む引数、標準入力、終了コード、SIGINT/SIGTERM、未対応コマンドの拒否を確認します。

実際のSDKの更新後は `ipv4-run gcloud version` と、利用権限のある読み取り専用APIコマンドでも動作確認してください。トークンが出力される可能性があるため、認証時のdebugログをそのまま公開しないでください。
