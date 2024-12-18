import os
import discord
import re
import requests
import json
import hashlib
import hmac
import datetime
import base64
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from dotenv import load_dotenv

# ダミーHTTPサーバー（Koyebのヘルスチェック用）
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'text/plain')
        self.end_headers()
        self.wfile.write(b'OK')  # Koyebのヘルスチェック用レスポンス

# ヘルスチェックサーバーを別スレッドで実行
def run_health_check_server():
    server = HTTPServer(('0.0.0.0', 8000), HealthCheckHandler)
    print("Health check server is running on port 8000...")
    server.serve_forever()

# HTTPサーバーを別スレッドで起動
threading.Thread(target=run_health_check_server, daemon=True).start()

# ===============================
# 環境変数の読み込み
# ===============================
load_dotenv()
TOKEN = os.getenv('TOKEN')  # Discord Botトークン
AMAZON_ACCESS_KEY = os.getenv('AMAZON_ACCESS_KEY')  # Amazon PA-APIアクセスキー
AMAZON_SECRET_KEY = os.getenv('AMAZON_SECRET_KEY')  # Amazon PA-APIシークレットキー
AMAZON_ASSOCIATE_TAG = os.getenv('AMAZON_ASSOCIATE_TAG')  # Amazonアソシエイトタグ
BITLY_API_TOKEN = os.getenv('BITLY_API_TOKEN')  # Bitly APIトークン

# Amazonリンクの正規表現
AMAZON_URL_REGEX = r"(https?://(www\.)?amazon\.co\.jp/[\S]+|https?://amzn\.asia/[\S]+)"

# ===============================
# 関数部分
# ===============================

# Amazon署名付きリクエストの生成
def amazon_signed_request(asin):
    endpoint = "webservices.amazon.co.jp"
    uri = "/onca/xml"
    params = {
        "Service": "AWSECommerceService",
        "Operation": "ItemLookup",
        "AWSAccessKeyId": AMAZON_ACCESS_KEY,
        "AssociateTag": AMAZON_ASSOCIATE_TAG,
        "ItemId": asin,
        "ResponseGroup": "Images,ItemAttributes,Offers",
        "Timestamp": datetime.datetime.utcnow().isoformat()
    }
    sorted_params = "&".join([f"{key}={requests.utils.quote(str(value))}" for key, value in sorted(params.items())])
    string_to_sign = f"GET\n{endpoint}\n{uri}\n{sorted_params}"
    signature = base64.b64encode(hmac.new(AMAZON_SECRET_KEY.encode(), string_to_sign.encode(), hashlib.sha256).digest()).decode()
    return f"https://{endpoint}{uri}?{sorted_params}&Signature={signature}"

# 短縮URLを展開
def expand_short_url(short_url):
    try:
        response = requests.head(short_url, allow_redirects=True)
        return response.url  # リダイレクト先のURLを取得
    except requests.RequestException:
        return short_url  # 取得失敗時はそのまま返す

# BitlyでURLを短縮
def shorten_url(long_url):
    try:
        headers = {"Authorization": f"Bearer {BITLY_API_TOKEN}"}
        data = {"long_url": long_url}
        response = requests.post("https://api-ssl.bitly.com/v4/shorten", json=data, headers=headers)
        if response.status_code == 200:
            return response.json().get("link")
        else:
            print(f"Bitlyエラー: {response.text}")
            return long_url
    except Exception as e:
        print(f"Bitly例外: {e}")
        return long_url

# ASINをURLから抽出
def extract_asin(url):
    match = re.search(r"/dp/([A-Z0-9]+)", url)
    return match.group(1) if match else None

# Amazon PA-APIから商品情報を取得
def fetch_amazon_data(asin):
    url = amazon_signed_request(asin)
    response = requests.get(url)
    if response.status_code == 200:
        try:
            data = json.loads(response.text)
            item = data['ItemLookupResponse']['Items']['Item']
            title = item['ItemAttributes']['Title']
            price = item['Offers']['Offer']['Price']['FormattedPrice']
            image_url = item['LargeImage']['URL']
            return title, price, image_url
        except Exception:
            pass
    return None, None, None

# ===============================
# Discord Bot本体
# ===============================

intents = discord.Intents.default()
intents.messages = True
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f'Botがログインしました: {client.user}')
    # Botが正常に起動したサインとしてチャンネルにメッセージを送信
    for guild in client.guilds:
        for channel in guild.text_channels:
            try:
                await channel.send("Botが正常に起動しました！")
                print(f"通知を送信しました: {channel.name}")
                return  # 最初のチャンネルに通知を送信して終了
            except Exception as e:
                print(f"チャンネル送信エラー: {e}")


@client.event
async def on_message(message):
    if message.author.bot:
        return

    # Amazonリンクを検出
    print(f"Received message: {message.content}")  # 受信したメッセージを表示
    urls = re.findall(AMAZON_URL_REGEX, message.content)
    print(f"Extracted URLs: {urls}")  # 正規表現で抽出されたURLを表示
    for url in urls:
        # 短縮URLを展開
        expanded_url = expand_short_url(url)
        asin = extract_asin(expanded_url)

        if asin:
            # Amazon PA-APIから商品情報取得
            title, price, image_url = fetch_amazon_data(asin)

            # アソシエイトリンクを生成
            associate_link = f"{expanded_url}?tag={AMAZON_ASSOCIATE_TAG}"

            # Bitlyでリンクを短縮
            short_url = shorten_url(associate_link)

            # 埋め込みメッセージの生成（商品名にリンクを設定）
            embed = discord.Embed(
                title=title or "Amazon商品リンク",
                url=short_url,  # 商品名部分に短縮リンクを埋め込む
                description=f"**価格**: {price or '情報なし'}",
                color=discord.Color.blue()
            )
            if image_url:
                embed.set_thumbnail(url=image_url)
            embed.set_footer(text="Botが情報をお届けしました！")

            # 埋め込みメッセージを送信
            await message.channel.send(embed=embed)

# Botを起動
client.run(TOKEN)
