import os
import discord
import json
import requests
import threading
from flask import Flask
from discord.ext import commands
from datetime import datetime
import hmac
import hashlib

# 環境変数から設定を読み込み
TOKEN = os.getenv('TOKEN')
AMAZON_ACCESS_KEY = os.getenv('AMAZON_ACCESS_KEY')
AMAZON_SECRET_KEY = os.getenv('AMAZON_SECRET_KEY')
AMAZON_ASSOCIATE_TAG = os.getenv('AMAZON_ASSOCIATE_TAG')
HOST = "webservices.amazon.co.jp"
REGION = "us-west-2"
URI_PATH = "/paapi5/searchitems"

# Discord Botの設定
intents = discord.Intents.default()
intents.messages = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Flaskを使用してHTTPサーバーをセットアップ
app = Flask(__name__)

@app.route("/")
def health_check():
    return "OK", 200

def run_http_server():
    app.run(host="0.0.0.0", port=8000)

http_thread = threading.Thread(target=run_http_server)
http_thread.daemon = True
http_thread.start()

# AWS署名を生成する関数
def generate_signature(request_payload):
    method = "POST"
    service = "ProductAdvertisingAPI"
    date = datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
    datestamp = datetime.utcnow().strftime('%Y%m%d')

    headers = {
        "host": HOST,
        "content-type": "application/json; charset=UTF-8",
        "x-amz-target": "com.amazon.paapi5.v1.ProductAdvertisingAPIv1.SearchItems",
        "x-amz-date": date
    }

    canonical_request = (
        f"{method}\n{URI_PATH}\n\n"
        + "\n".join([f"{key}:{value}" for key, value in headers.items()]) + "\n\n"
        + ";".join(headers.keys()) + "\n"
        + hashlib.sha256(request_payload.encode('utf-8')).hexdigest()
    )

    string_to_sign = (
        f"AWS4-HMAC-SHA256\n{date}\n{datestamp}/{REGION}/ProductAdvertisingAPI/aws4_request\n"
        + hashlib.sha256(canonical_request.encode('utf-8')).hexdigest()
    )

    def sign(key, msg):
        return hmac.new(key, msg.encode('utf-8'), hashlib.sha256).digest()

    k_date = sign(f"AWS4{AMAZON_SECRET_KEY}".encode('utf-8'), datestamp)
    k_region = sign(k_date, REGION)
    k_service = sign(k_region, service)
    k_signing = sign(k_service, "aws4_request")

    signature = hmac.new(k_signing, string_to_sign.encode('utf-8'), hashlib.sha256).hexdigest()
    return signature, headers

# Amazon商品情報を取得する関数
def fetch_amazon_product(keywords):
    request_payload = json.dumps({
        "Keywords": keywords,
        "PartnerTag": AMAZON_ASSOCIATE_TAG,
        "PartnerType": "Associates",
        "Marketplace": "www.amazon.co.jp"
    })
    signature, headers = generate_signature(request_payload)

    headers["Authorization"] = f"AWS4-HMAC-SHA256 Credential={AMAZON_ACCESS_KEY}/{datetime.utcnow().strftime('%Y%m%d')}/{REGION}/ProductAdvertisingAPI/aws4_request, SignedHeaders={';'.join(headers.keys())}, Signature={signature}"
    
    response = requests.post(f"https://{HOST}{URI_PATH}", data=request_payload, headers=headers)
    return response.json()

# Discordコマンド
@bot.event
async def on_ready():
    print(f"Bot logged in as {bot.user}")

@bot.event
async def on_message(message):
    if "amazon.co.jp" in message.content and not message.author.bot:
        keywords = "検出したキーワード"  # キーワード抽出ロジックを追加
        product_data = fetch_amazon_product(keywords)

        if product_data.get("SearchResult", {}).get("Items"):
            item = product_data["SearchResult"]["Items"][0]
            embed = discord.Embed(
                title=item["ItemInfo"]["Title"]["DisplayValue"],
                url=item["DetailPageURL"],
                description=f"価格: {item['Offers']['Listings'][0]['Price']['DisplayAmount']}",
                color=0x00ff00
            )
            embed.set_thumbnail(url=item["Images"]["Primary"]["Medium"]["URL"])
            await message.channel.send("商品情報を整理しました✨️")
            await message.channel.send(embed=embed)
        else:
            await message.channel.send("商品が見つかりませんでした。")

# Botを起動
bot.run(TOKEN)
