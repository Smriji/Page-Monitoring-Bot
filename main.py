import sys
import os
import json
import urllib.request
import hashlib
from bs4 import BeautifulSoup
from google.cloud import storage

# 設定ファイル
CONFIG_FILE = "target.json"

# GCS設定
BUCKET_NAME = os.getenv("GCS_BUCKET_NAME", "chk-web-state")
STATE_FILE = "state.json"

def get_element_hash(url, tag_name=None, attrs=None):
    """指定されたURLからHTMLを取得し、ハッシュを計算する関数"""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req) as response:
            html_content = response.read()
    except Exception as e:
        print(f"URLの取得に失敗しました: {url} {e}")
        return None, None
    
    soup = BeautifulSoup(html_content, "html.parser")
    title_tag = soup.title
    page_title = title_tag.string if title_tag else "(タイトルなし)"
    
    if tag_name or attrs:
        target_element = soup.find_all(tag_name, attrs=attrs or {})

        if target_element:
            content_to_hash = str(target_element).encode('utf-8')
        else:
            print(f"指定された要素が見つかりませんでした: {url} {tag_name} {attrs}")
            return None, page_title
    else:
        content_to_hash = html_content

    hash_value = hashlib.sha256(content_to_hash).hexdigest()
    return hash_value, page_title

def load_state_from_gcs(bucket_name, file_name):
    """GCSから状態を読み込む関数"""
    try:
        client = storage.Client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(file_name)

        if blob.exists():
            state_data = blob.download_as_text()
            return json.loads(state_data)
        else:
            return {}
    except Exception as e:
        print(f"GCSから状態の読み込みに失敗しました: {e}")
        return {}

def save_state_to_gcs(bucket_name, file_name, state):
    """GCSに状態を保存する関数"""
    try:
        client = storage.Client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(file_name)

        content = json.dumps(state, indent=4, ensure_ascii=False)
        blob.upload_from_string(content, content_type="application/json")
        print(f"GCSに状態を保存しました: {bucket_name}/{file_name}")
    except Exception as e:
        print(f"GCSへの状態の保存に失敗しました: {e}")

def send_to_slack(message):
    """Slackにメッセージを送信する関数"""
    slack_webhook_url = os.getenv("WEBHOOK_URL")
    
    if not slack_webhook_url:
        print("Slack Webhook URLが設定されていません", file=sys.stderr)
        return

    try:
        from slack_sdk import WebhookClient
        webhook = WebhookClient(slack_webhook_url)
        response = webhook.send(text=message)
        if response.status_code != 200:
            print(f"Slackへのメッセージ送信に失敗しました: {response.status_code} - {response.body}", file=sys.stderr)
        else:
            print(f"Slackへのメッセージ送信に成功しました: {response.status_code}")

    except Exception as e:
        print(f"Slackへのメッセージ送信中にエラーが発生しました: {e}", file=sys.stderr)

def main():
    # 設定ファイルの読み込み
    if not os.path.exists(CONFIG_FILE):
        print(f"設定ファイルが見つかりません: {CONFIG_FILE}")
        sys.exit(1)
    
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        try:
            targets = json.load(f)
        except json.JSONDecodeError as e:
            print(f"設定ファイルの読み込みに失敗しました: {e}")
            sys.exit(1)

    # GCSから状態を読み込む
    state = load_state_from_gcs(BUCKET_NAME, STATE_FILE)
    
    has_updates = False

    # 各URLの要素のハッシュを計算し、状態と比較
    for item in targets:
        url = item.get("url")
        tag_name = item.get("tag_name")
        attrs = item.get("attrs")

        if not url:
            print("URLが指定されていません: ", item)
            continue

        new_hash, page_title = get_element_hash(url, tag_name, attrs)

        if new_hash is None:
            continue

        old_hash = state.get(url)

        if old_hash != new_hash:
            print(f"変更が検出されました: {url}")
            state[url] = new_hash
            send_to_slack(f"更新がありました\n{page_title}\n{url}")
            has_updates = True
        else:
            print(f"変更はありません\n{page_title}\n{url}")

    # 状態に変更があった場合、GCSに保存
    if has_updates:
        save_state_to_gcs(BUCKET_NAME, STATE_FILE, state)

    sys.exit(0)

if __name__ == "__main__":
    main()
