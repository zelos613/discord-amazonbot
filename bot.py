import os
import discord
import re
import requests
import hashlib
import hmac
import datetime
import base64
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from dotenv import load_dotenv

# ===============================
# 環境変数の読み込み
# ===============================
load_dotenv()
TOKEN = os.getenv('TOKEN')
AMAZON_ACCESS_KEY = os.getenv('AMAZON_ACCESS_KEY')
AMAZON_SECRET_KEY = os.getenv('AMAZON_SECRET_KEY')
AMAZON_ASSOCIATE_TAG = os.getenv('AMAZON_ASSOCIATE_TAG')

# 正規表現: Amazonリンクの検出 (短縮URL含む)
AMAZON_URL_REGEX = r"(https?://(?:www\.)?(?:amazon\.co\.jp|amzn\.asia)/[\w\-/\?=&%\.]+)"

# ===============================
# ヘルスチェック用HTTPサーバー
# ===============================
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'text/plain')
        self.end_headers()
        self.wfile.write(b'OK')

def run_health_check_server():
    server = HTTPServer(('0.0.0.0', 8000), HealthCheckHandler)
    print("Health check server is running on port 8000...")
    server.serve_forever()

threading.Thread(target=run_health_check_server, daemon=True).start()

# ===============================
# Amazon署名付きリクエストの生成
# ===============================
def amazon_signed_request(asin):
    endpoint = "webservices.amazon.co.jp"
    uri = "/paapi5/getitems"
    headers = {'Content-Type': 'application/json'}
    payload = {
        "PartnerTag": AMAZON_ASSOCIATE_TAG,
        "PartnerType": "Associates",
        "Marketplace": "www.amazon.co.jp",
        "Resources": [
            "Images.Primary.Large",
            "ItemInfo.Title",
            "Offers.Listings.Price"
        ],
        "ItemIds": [asin]
    }
    try:
        timestamp = datetime.datetime.utcnow().isoformat()
        string_to_sign = f"POST\n{endpoint}\n{uri}\n{timestamp}"
        signature = base64.b64encode(hmac.new(AMAZON_SECRET_KEY.encode(), string_to_sign.encode(), hashlib.sha256).digest()).decode()
        headers['X-Amz-Date'] = timestamp
        headers['Authorization'] = f"AWS4-HMAC-SHA256 Credential={AMAZON_ACCESS_KEY}/{timestamp}, SignedHeaders=host;x-amz-date, Signature={signature}"
        url = f"https://{endpoint}{uri}"
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        return response.json()
    except Exception as e:
        print(f"APIリクエストエラー: {e}")
    return None

# ===============================
# ASINを抽出
# ===============================
def expand_and_extract_asin(url):
    try:
        response = requests.head(url, allow_redirects=True, timeout=5)
        expanded_url = response.url
    except Exception as e:
        print(f"URL展開エラー: {e}")
        return None
    match = re.search(r"/(?:dp|gp/product|d)/([A-Z0-9]{10})", expanded_url)
    return match.group(1) if match else None

# ===============================
# Amazon PA-APIから商品情報を取得
# ===============================
def fetch_amazon_data(asin):
    try:
        response = amazon_signed_request(asin)
        if response and "ItemsResult" in response:
            item = response["ItemsResult"]["Items"][0]
            title = item["ItemInfo"]["Title"]["DisplayValue"]
            price = item["Offers"]["Listings"][0]["Price"]["DisplayAmount"]
            image_url = item["Images"]["Primary"]["Large"]["URL"]
            return title, price, image_url
    except Exception as e:
        print(f"商品情報取得エラー: {e}")
    return None, None, None

# ===============================
# Discord Bot本体
# ===============================
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f'Botがログインしました: {client.user}')

@client.event
async def on_message(message):
    if message.author.bot:
        return

    urls = re.findall(AMAZON_URL_REGEX, message.content)
    for url in urls:
        await message.channel.send("リンクを確認中です... 🔍")
        asin = expand_and_extract_asin(url)
        if not asin:
            await message.channel.send("ASINが取得できませんでした。リンクが正しいか確認してください。")
            continue

        title, price, image_url = fetch_amazon_data(asin)
        if title and price and image_url:
            embed = discord.Embed(
                title=title,
                url=url,
                description=f"**価格**: {price}\n\n商品情報を整理しました！✨",
                color=discord.Color.blue()
            )
            embed.set_thumbnail(url=image_url)
            await message.channel.send(embed=embed)
        else:
            await message.channel.send("商品情報を取得できませんでした。少し時間をおいてお試しください。")

client.run(TOKEN)
