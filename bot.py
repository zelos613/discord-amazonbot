import os
import discord
import re
import requests
import xml.etree.ElementTree as ET
import hashlib
import hmac
import datetime
import base64
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from dotenv import load_dotenv
from bs4 import BeautifulSoup

# ===============================
# 環境変数の読み込み
# ===============================
load_dotenv()
TOKEN = os.getenv('TOKEN')
AMAZON_ACCESS_KEY = os.getenv('AMAZON_ACCESS_KEY')
AMAZON_SECRET_KEY = os.getenv('AMAZON_SECRET_KEY')
AMAZON_ASSOCIATE_TAG = os.getenv('AMAZON_ASSOCIATE_TAG')
BITLY_API_TOKEN = os.getenv('BITLY_API_TOKEN')

# Amazonリンク検出用の正規表現
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
# Amazon PA-API v5 リクエスト生成
# ===============================
def generate_amazon_request(asin):
    base_url = "https://webservices.amazon.co.jp/onca/xml"
    params = {
        "Service": "AWSECommerceService",
        "Operation": "ItemLookup",
        "AWSAccessKeyId": AMAZON_ACCESS_KEY,
        "AssociateTag": AMAZON_ASSOCIATE_TAG,
        "ItemId": asin,
        "ResponseGroup": "Images,ItemAttributes,Offers",
        "Timestamp": datetime.datetime.utcnow().isoformat()
    }
    sorted_params = "&".join(f"{k}={requests.utils.quote(str(v))}" for k, v in sorted(params.items()))
    signature = base64.b64encode(hmac.new(
        AMAZON_SECRET_KEY.encode(),
        f"GET\nwebservices.amazon.co.jp\n/onca/xml\n{sorted_params}".encode(),
        hashlib.sha256
    ).digest()).decode()
    return f"{base_url}?{sorted_params}&Signature={signature}"

# AmazonリンクからASINを取得
def extract_asin(url):
    try:
        response = requests.get(url, allow_redirects=True)
        expanded_url = response.url
        match = re.search(r"/(?:dp|gp/product|d)/([A-Z0-9]{10})", expanded_url)
        return match.group(1) if match else None
    except Exception as e:
        print(f"ASIN取得エラー: {e}")
        return None

# 商品情報取得
def fetch_amazon_data(asin):
    try:
        request_url = generate_amazon_request(asin)
        response = requests.get(request_url)
        if response.status_code == 200:
            root = ET.fromstring(response.content)
            title = root.find(".//Title").text
            price = root.find(".//FormattedPrice").text
            image_url = root.find(".//LargeImage/URL").text
            return title, price, image_url
    except Exception as e:
        print(f"APIエラー: {e}")
    return None, None, None

# Discord Bot設定
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f'Botがログインしました: {client.user}')

@client.event
async def on_message(message):
    if message.author.bot:  # 自分自身を除外
        return

    urls = re.findall(AMAZON_URL_REGEX, message.content)
    for url in urls:
        asin = extract_asin(url)
        if not asin:
            await message.channel.send("ASINが抽出できませんでした。")
            return

        title, price, image_url = fetch_amazon_data(asin)
        if title and price and image_url:
            embed = discord.Embed(
                title=title,
                url=f"{url}?tag={AMAZON_ASSOCIATE_TAG}",
                description=f"**価格**: {price}",
                color=discord.Color.blue()
            )
            embed.set_thumbnail(url=image_url)
            embed.set_footer(text="おすすめの商品です！")
            await message.channel.send(embed=embed)
        else:
            await message.channel.send("商品情報を取得できませんでした。")

client.run(TOKEN)
