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

# ===============================
# 環境変数の読み込み
# ===============================
load_dotenv()
TOKEN = os.getenv('TOKEN')
AMAZON_ACCESS_KEY = os.getenv('AMAZON_ACCESS_KEY')
AMAZON_SECRET_KEY = os.getenv('AMAZON_SECRET_KEY')
AMAZON_ASSOCIATE_TAG = os.getenv('AMAZON_ASSOCIATE_TAG')

# 正規表現: Amazonリンクの検出 (短縮URL含む)
AMAZON_URL_REGEX = r"(https?://(?:www\.)?(?:amazon\.co\.jp|amzn\.asia|amzn\.to)/[\w\-/\?=&%\.]+)"

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
# Amazon置合付きリクエストの生成
# ===============================
def amazon_signed_request(asin):
    endpoint = "webservices.amazon.co.jp"
    uri = "/paapi5/getitems"
    headers = {
        'Content-Type': 'application/json',
    }
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
        timestamp = datetime.datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
        string_to_sign = f"POST\n{endpoint}\n{uri}\n{timestamp}"
        signature = hmac.new(AMAZON_SECRET_KEY.encode(), string_to_sign.encode(), hashlib.sha256).hexdigest()
        headers['X-Amz-Date'] = timestamp
        headers['Authorization'] = f"AWS4-HMAC-SHA256 Credential={AMAZON_ACCESS_KEY}/{timestamp}, SignedHeaders=host;x-amz-date, Signature={signature}"
        url = f"https://{endpoint}{uri}"
        response = requests.post(url, json=payload, headers=headers)
        print(f"API Response: {response.status_code} - {response.text}")  # Debug
        return response.json() if response.status_code == 200 else None
    except Exception as e:
        print(f"APIリクエストエラー: {e}")
    return None

# ===============================
# ASINの抽出
# ===============================
def extract_asin(url):
    try:
        # 試行: dpやdを含むURLからASINを抽出
        match = re.search(r"(?:dp|gp/product|d)/([A-Z0-9]{10})", url)
        if match:
            return match.group(1)
        # 短縮URLのリダイレクト検索
        response = requests.get(url, allow_redirects=True, timeout=5)
        expanded_url = response.url
        match = re.search(r"(?:dp|gp/product|d)/([A-Z0-9]{10})", expanded_url)
        if match:
            return match.group(1)
        # URLの抽出に失敗した場合のログ出力
        print(f"ASIN抽出失敗: URL={url}")
    except Exception as e:
        print(f"ASIN抽出エラー: {e}")
    return None

# ===============================
# Amazon PA-APIから商品情報を取得
# ===============================
def fetch_amazon_data(asin):
    try:
        print(f"Fetching data for ASIN: {asin}")
        response = amazon_signed_request(asin)
        if response and "ItemsResult" in response and "Items" in response["ItemsResult"]:
            item = response["ItemsResult"]["Items"][0]
            title = item["ItemInfo"]["Title"]["DisplayValue"]
            price = item.get("Offers", {}).get("Listings", [{}])[0].get("Price", {}).get("DisplayAmount", "N/A")
            image_url = item["Images"]["Primary"]["Large"]["URL"]
            return title, price, image_url
    except Exception as e:
        print(f"Amazon情報取得エラー: {e}")
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
    if not urls:
        return

    for url in urls:
        await message.channel.send("リンクを確認中です...\ud83d\udd0d")
        asin = extract_asin(url)
        if not asin:
            await message.channel.send("ASINが取得できませんでした。\ud83d\udeab")
            continue

        title, price, image_url = fetch_amazon_data(asin)
        if title and price and image_url:
            embed = discord.Embed(
                title=title,
                url=url,
                description=f"**\u4fa1格**: {price}\n\n\u5546\u54c1\u60c5\u5831\u3092\u6574\u7406\u3057\u307e\u3057\u305f\uff01\u2728",
                color=discord.Color.blue()
            )
            embed.set_thumbnail(url=image_url)
            await message.channel.send(embed=embed)
        else:
            await message.channel.send("\u5546\u54c1\u60c5\u5831\u3092\u53d6\u5f97\u3067\u304d\u307e\u305b\u3093\u3067\u3057\u305f\u3002\u30ea\u30f3\u30af\u304c\u6b63\u3057\u3044\u304b\u78ba\u8a8d\u3057\u3066\u304f\u3060\u3055\u3044\u3002")

client.run(TOKEN)
