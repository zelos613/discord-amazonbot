import os
import discord
import re
import requests
import json
import hmac
import hashlib
from datetime import datetime
from urllib.parse import urlparse
from dotenv import load_dotenv
from flask import Flask
import threading
import logging

# ===============================
# ログ設定
# ===============================
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ===============================
# 環境変数の読み込み
# ===============================
load_dotenv()
TOKEN = os.getenv('TOKEN')
AMAZON_ACCESS_KEY = os.getenv('AMAZON_ACCESS_KEY')
AMAZON_SECRET_KEY = os.getenv('AMAZON_SECRET_KEY')
AMAZON_ASSOCIATE_TAG = os.getenv('AMAZON_ASSOCIATE_TAG')

# Amazonリンクの正規表現
AMAZON_URL_REGEX = r"(https?://(?:www\.)?(?:amazon\.co\.jp|amzn\.to|amzn\.asia)/[\w\-/\?=&%\.]+)"

# ===============================
# AWS署名の生成
# ===============================
def generate_aws_signature(payload):
    method = "POST"
    service = "ProductAdvertisingAPI"
    host = "webservices.amazon.co.jp"
    region = "us-west-2"
    endpoint = f"https://{host}/paapi5/getitems"
    content_type = "application/json; charset=UTF-8"

    now = datetime.utcnow()
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    date_stamp = now.strftime("%Y%m%d")

    headers = {
        "content-type": content_type,
        "host": host,
        "x-amz-date": amz_date,
    }

    canonical_uri = "/paapi5/getitems"
    canonical_headers = ''.join([f"{k}:{v}\n" for k, v in headers.items()])
    signed_headers = ';'.join(headers.keys())
    payload_hash = hashlib.sha256(payload.encode('utf-8')).hexdigest()
    canonical_request = (f"{method}\n{canonical_uri}\n\n"
                         f"{canonical_headers}\n{signed_headers}\n{payload_hash}")

    string_to_sign = (f"AWS4-HMAC-SHA256\n{amz_date}\n"
                      f"{date_stamp}/{region}/{service}/aws4_request\n"
                      f"{hashlib.sha256(canonical_request.encode('utf-8')).hexdigest()}")

    def sign(key, msg):
        return hmac.new(key, msg.encode('utf-8'), hashlib.sha256).digest()

    k_date = sign(("AWS4" + AMAZON_SECRET_KEY).encode('utf-8'), date_stamp)
    k_region = sign(k_date, region)
    k_service = sign(k_region, service)
    k_signing = sign(k_service, "aws4_request")
    signature = hmac.new(k_signing, string_to_sign.encode('utf-8'), hashlib.sha256).hexdigest()

    authorization_header = (f"AWS4-HMAC-SHA256 Credential={AMAZON_ACCESS_KEY}/{date_stamp}/{region}/{service}/aws4_request, "
                             f"SignedHeaders={signed_headers}, Signature={signature}")
    headers["Authorization"] = authorization_header

    return headers, endpoint

# ===============================
# Amazon商品情報を取得
# ===============================
def fetch_amazon_data(asin):
    payload = json.dumps({
        "ItemIds": [asin],
        "PartnerTag": AMAZON_ASSOCIATE_TAG,
        "PartnerType": "Associates",
        "Marketplace": "www.amazon.co.jp"
    })
    headers, endpoint = generate_aws_signature(payload)
    
    logger.debug(f"Amazon PA-APIリクエストペイロード: {payload}")
    logger.debug(f"Amazon PA-APIリクエストヘッダー: {headers}")

    response = requests.post(endpoint, headers=headers, data=payload)

    if response.status_code != 200:
        logger.error(f"PA-APIエラー: ステータスコード={response.status_code}, レスポンス={response.text}")
        return None, None, None

    data = response.json()
    logger.debug(f"PA-APIレスポンス: {data}")

    if "ItemsResult" in data and "Items" in data["ItemsResult"]:
        item = data["ItemsResult"]["Items"][0]
        title = item["ItemInfo"]["Title"]["DisplayValue"] if "ItemInfo" in item and "Title" in item["ItemInfo"] else "タイトルなし"
        price = item["Offers"]["Listings"][0]["Price"]["DisplayAmount"] if "Offers" in item and "Listings" in item["Offers"] else "価格情報なし"
        image_url = item["Images"]["Primary"]["Large"]["URL"] if "Images" in item and "Primary" in item["Images"] else None
        return title, price, image_url
    else:
        logger.error("PA-APIレスポンスに商品情報が含まれていません。")
    return None, None, None


# ===============================
# 短縮URLの展開
# ===============================
def resolve_short_url(url):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        response = requests.get(url, allow_redirects=True, timeout=10, headers=headers)
        expanded_url = response.url
        logger.debug(f"短縮URL展開: {url} -> {expanded_url}")
        return expanded_url
    except Exception as e:
        logger.error(f"短縮URLの展開に失敗しました: {e}")
        return None

# ===============================
# ASINを抽出
# ===============================
def extract_asin(url):
    """URLからASINを抽出する"""
    try:
        # 短縮URLを展開
        url = resolve_short_url(url)
        if not url:
            return None
        
        # AmazonリンクからASINを抽出
        parsed_url = urlparse(url)
        path_parts = parsed_url.path.split("/")
        for part in path_parts:
            if len(part) == 10 and part.isalnum():  # ASINは10桁の英数字
                return part
        return None
    except Exception as e:
        logger.error(f"ASIN抽出エラー: {e}")
        return None

# ===============================
# Discord Bot設定
# ===============================
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    logger.info(f"Botがログインしました: {client.user}")

@client.event
async def on_message(message):
    if message.author.bot:
        return

    urls = re.findall(AMAZON_URL_REGEX, message.content)
    if not urls:
        return

    for url in urls:
        await message.channel.send("リンクを確認中です...🔍")
        
        # ASINを取得
        asin = extract_asin(url)
        if not asin:
            await message.channel.send("ASINが取得できませんでした。❌")
            continue

        # Amazon商品情報を取得
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
            await message.channel.send("商品情報を取得できませんでした。リンクが正しいか確認してください。")

# ===============================
# HTTPサーバー設定
# ===============================
app = Flask(__name__)

@app.route("/")
def health_check():
    return "OK", 200

def run_http_server():
    app.run(host="0.0.0.0", port=8000)

http_thread = threading.Thread(target=run_http_server)
http_thread.daemon = True
http_thread.start()

client.run(TOKEN)
