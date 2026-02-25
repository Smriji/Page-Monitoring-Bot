# Web Page Update Monitor Bot

指定したウェブページ、またはページ内の特定要素を定期的に監視し、更新があった場合に Webhook 経由で通知を送る Python スクリプトです。
Google Cloud Run ジョブ、Cloud Storage、Cloud Scheduler を組み合わせて、サーバーレス環境で定期実行（1日1回など）を行うことを前提に設計されています。

## 特徴

* 変更検知の軽量化: HTML をそのまま保存するのではなく、取得した要素を SHA-256 でハッシュ化して比較するため、ストレージ容量を圧迫しません。
* 柔軟な監視範囲: BeautifulSoup を使用し、ページ全体だけでなく特定のタグや属性（id や class 指定など）に絞った監視が可能です。
* 状態と設定の分離: 監視設定である target.json と、過去のハッシュ値を記録する状態データ state.json（Cloud Storage に保存）を分離しているため、運用中の監視対象の追加や変更が安全に行えます。
* 汎用的な通知: ページのタイトルを抽出し、Slack などの主要な Webhook に変更があったことのみをシンプルに通知します。

## 前提条件

* Python 3.x
* Google Cloud プロジェクト（Cloud Run、Cloud Storage、Cloud Scheduler が有効化されていること）
* 通知先の Webhook URL

## インストール（ローカル環境でのテスト用）

必要なライブラリをインストールします。

```bash
pip install beautifulsoup4 google-cloud-storage
```

## 設定方法

スクリプトと同じディレクトリに target.json という名前のファイルを作成し、監視対象のリストを定義します。

```json
[
    {
        "url": "https://example.com/index.html",
        "tag_name": "div",
        "attrs": null
    },
    {
        "url": "[https://example.com/news.html",
        "tag_name": "main",
        "attrs": {
            "id": "main"
        }
    }
]
```

* url: 監視対象の URL
* tag_name: 監視するタグ名（ページ全体を対象とする場合は null を指定）
* attrs: 監視するタグの属性（id や class など。不要な場合は null を指定）

## 環境変数

実行時には以下の環境変数を設定する必要があります。

* GCS_BUCKET_NAME: 状態ファイル state.json を保存する Cloud Storage のバケット名
* WEBHOOK_URL: 通知を送信する Webhook URL

注意: Discord の Webhook を使用する場合は、通知が正しく機能するようにスクリプト内の Webhook 送信関数にて、ペイロードのキーを text から content に変更してください。

## ローカルでのテスト実行

Google Cloud の認証情報をセットアップした上で、スクリプトを実行して動作を確認できます。

```powershell
# Google Cloud への認証（初回のみ）
gcloud auth application-default login

# 環境変数の設定
$env:GCS_BUCKET_NAME="your-bucket-name"
$env:WEBHOOK_URL="https://your-webhook-url"

# スクリプトの実行
python main.py
```

## Google Cloud へのデプロイ手順

1. Cloud Storage バケットの作成
   状態保存用のバケットを作成します。
2. Cloud Run ジョブの作成
   target.json、main.py、および requirements.txt を含むコンテナイメージをビルドし、Cloud Run ジョブとしてデプロイします。
   デプロイの際、上記2つの環境変数を設定し、実行するサービスアカウントに「ストレージ オブジェクト管理者」などの GCS 読み書き権限を付与してください。
3. Cloud Scheduler の設定
   作成した Cloud Run ジョブをターゲットとして指定し、定期実行のスケジュールを設定します（例: 毎朝9時に実行する場合は 0 9 * * * と指定します）。