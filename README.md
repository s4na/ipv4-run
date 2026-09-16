# ipv4-run

Mac全体のネットワーク設定を変えずに、**gcloudのPythonプロセス内の通信をIPv4に限定する**小さなラッパーです。IPv6の接続待ちでgcloudが長時間止まる環境のための暫定的な回避策です。

```sh
ipv4-run gcloud auth login
ipv4-run gcloud projects list
```

## 必要な環境

| 項目 | 要件 |
| --- | --- |
| OS | macOS / Linux。Windowsは対応対象外です。CIでは `macos-latest` / `ubuntu-latest` で検証しています。 |
| ラッパー用Python | Python 3.10以上。システム・Homebrew・miseなど、導入方法は問いません。ソースから使う場合は `python3` としてPATH上で実行できる必要があります。追加のpipパッケージは不要です。 |
| Google Cloud CLI | 通常のPython版Google Cloud SDKを別途インストールし、`gcloud` をPATHに追加してください。SDK内に `bin/gcloud` と `lib/gcloud.py` がある構成が必要です。実機での起動確認済みバージョンは585.0.0です。 |
| gcloud用Python | インストールしたGoogle Cloud CLIが対応するPythonが必要です。SDK自身が選択するPython（同梱Pythonや `CLOUDSDK_PYTHON` による指定）を使うため、ラッパー用Pythonとは別の場合があります。 |
| ネットワーク | 利用するGoogle Cloud APIなどにIPv4で接続できることが必要です。このツールはIPv4接続自体の不具合を解消するものではありません。 |

ソースから取得する場合はGit、Homebrewで導入する場合はHomebrewが必要です。Homebrew版はフォールバック用の `python@3.14` を依存関係として導入しますが、Google Cloud CLIは導入しません。ラッパー自体にGoogle Cloudアカウントは不要ですが、認証が必要なgcloudコマンドには通常どおりアカウントと権限が必要です。

導入前に、次のコマンドでPythonとGoogle Cloud CLIを確認できます（Homebrew版ではラッパー用Pythonの手動準備は不要です）。

```sh
python3 --version  # ソースから使う場合: 3.10以上
gcloud version
```

Go版gcloud（`CLOUDSDK_USE_GOCLOUD` を設定した構成）、独自の起動スクリプトやシェル関数、カスタム `CLOUDSDK_PYTHON_ARGS` は対応外です。

## 対応範囲

- 初版はGoogle Cloud CLIの通常のPython版 `bin/gcloud` 専用です。任意のコマンドを制限するツールではありません。
- SDKの内部起動方式に依存する非公式の回避策です。
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

### mise管理のPythonで使う

ソース版の起動には `#!/usr/bin/env python3` を使っているため、PATH上の `python3` がmise管理のPythonなら、そのまま利用できます。miseでPython 3.10以上を選択し、[シェルで有効化](https://mise.jdx.dev/cli/activate.html)している場合、起動コマンドは通常と同じです。

```sh
# 上記の手順でcloneしたipv4-runディレクトリ内で実行
python3 --version
./bin/ipv4-run gcloud version
```

シェルの有効化に依存せず実行するには、[mise exec](https://mise.jdx.dev/dev-tools/)を使います。以下はmiseで選択済みのPythonを使う例です。

```sh
mise exec -- python3 --version
mise exec -- ./bin/ipv4-run gcloud version
```

これはラッパー用Pythonの選択です。gcloud用Pythonは引き続きSDKに選択を任せます。gcloudにもmise管理のPythonを指定する場合は、そのバージョンが利用中のGoogle Cloud CLIに対応していることを確認し、コマンド単位で指定できます。

```sh
mise exec -- sh -c 'CLOUDSDK_PYTHON="$(command -v python3)" ./bin/ipv4-run gcloud version'
```

### Homebrew

このリポジトリ自身を明示的なURLでtapとして登録します。通常は安定版をインストールできます。

```sh
brew tap s4na/ipv4-run https://github.com/s4na/ipv4-run.git
brew install s4na/ipv4-run/ipv4-run
```

バージョンを完全に固定する場合は、バージョン付きformulaを指定します。現在は **0.1.0** を提供しています。

```sh
brew install s4na/ipv4-run/ipv4-run@0.1.0
"$(brew --prefix s4na/ipv4-run/ipv4-run@0.1.0)/bin/ipv4-run" gcloud version
```

バージョン付きformulaは通常版と共存できるよう、自動ではPATHにリンクしません。普段使うバージョンにする場合は、その `bin` をPATHの先頭に追加してください。

```sh
export PATH="$(brew --prefix s4na/ipv4-run/ipv4-run@0.1.0)/bin:$PATH"
ipv4-run gcloud version
```

`@0.1.0` は0.1.0のソースに固定され、通常版の更新には追従しません。任意の過去バージョンを自動取得する仕組みではなく、tapに用意したバージョンだけ指定できます。Pythonなどの依存関係は固定されません。

開発中のmainを使う場合は、引き続きHEAD版も選べます。

```sh
brew install --HEAD s4na/ipv4-run/ipv4-run
```

Homebrew版も、PATH上の `python3`（mise管理のPythonを含む）がPython 3.10以上で起動できれば優先して使います。`python3` が見つからない、バージョンが古い、miseのshimが未設定などで起動できない場合は、依存関係として導入したHomebrewのPythonにフォールバックします。miseのPythonが有効なシェルなら、通常どおり実行できます。

```sh
ipv4-run gcloud version
# シェルでmiseを有効化していない場合（miseでPythonを選択済み）
mise exec -- ipv4-run gcloud version
```

この選択はラッパー用Pythonだけに適用します。gcloud用Pythonは引き続きSDKが選択します。

削除する場合：

```sh
brew uninstall ipv4-run
# バージョン付きformulaを入れた場合はこちらも削除
brew uninstall ipv4-run@0.1.0
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

## 自動パッチリリース

mainへのPRマージごとにGitHub Actionsの `Patch release` が起動し、パッチ番号を1つ上げます（例: `0.1.0` → `0.1.1`）。ドキュメントだけのPRも対象です。

1. 未処理のマージ済みPRをmainの履歴順に確認し、各マージコミットに `vX.Y.Z` タグを作成します。
2. ソースアーカイブのSHA-256を計算し、通常版formula、対応する `ipv4-run@X.Y.Z`、README、処理記録 `.release-state.json` を更新します。既存の固定版は保持します。
3. Pythonテストと、実際のHomebrewインストール・テストを実行します。
4. `github-actions[bot]` が更新をmainにコミット・pushし、GitHub Releaseを公開します。

自動更新コミットはPRマージではないため、リリースを再発火しません。組み込みの `GITHUB_TOKEN` を使い、PATの追加は不要です。mainへのbotの直接pushが許可されている必要があります。

同時実行は直列化し、未処理PRもまとめて回収します。再実行では処理済みPRの番号を上げ直しません。途中失敗時はActionsの該当runを再実行するか、mainで `Patch release` を手動実行してください。作成済みタグは再利用し、異なるコミットへの付け替えは拒否します。テスト失敗時はタグだけ残ることがありますが、formula更新のpushとRelease公開は行いません。

自動化導入前のPRは対象外です。メジャー・マイナーバージョンの変更はこの自動化の対象外です。
