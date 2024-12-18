import os
import discord
import re
import requests
import json
import hashlib
import hmac
import datetime
import base64
import asyncio
from dotenv import load_dotenv

# ===============================
# 環境変数の読み込み
# ===============================
load_dotenv()
TOKEN = os.getenv('TOKEN')
AMAZON_ACCESS_KEY = os.getenv('AMAZON_ACCESS_KEY')
AMAZON_SECRET_KEY = os.getenv('AMAZON_SECRET_KEY')
AMAZON_ASSOCIATE_TAG = os.getenv('AMAZON_ASSOCIATE_TAG')

AMAZON_URL_REGEX = r"(https?://(?:www\.)?(?:amazon\.co\.jp|amzn\.to|amzn\.asia)/[\w\-/\?=&%\.]+)"

# ===============================
# Amazon PA-APIリクエスト署名
# ===============================
def amazon_signed_request(asin):
    endpoint = "webservices.amazon.co.jp"
    uri = "/paapi5/getitems"
    headers = {'Content-Type': 'application/json'}
    payload = {
        "PartnerTag": AMAZON_ASSOCIATE_TAG,
        "PartnerType": "Associates",
        "Marketplace": "www.amazon.co.jp",
        "Resources": ["Images.Primary.Large", "ItemInfo.Title", "Offers.Listings.Price"],
        "ItemIds": [asin]
    }

    try:
        timestamp = datetime.datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
        string_to_sign = f"POST\n{endpoint}\n{uri}\n{timestamp}"
        signature = hmac.new(AMAZON_SECRET_KEY.encode(), string_to_sign.encode(), hashlib.sha256).hexdigest()
        headers['X-Amz-Date'] = timestamp
        headers['Authorization'] = f"AWS4-HMAC-SHA256 Credential={AMAZON_ACCESS_KEY}/{timestamp}, Signature={signature}"
        url = f"https://{endpoint}{uri}"
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        return response.json() if response.status_code == 200 else None
    except Exception as e:
        print(f"APIリクエストエラー: {e}")
    return None

# ===============================
# ASINの抽出（リトライ機能付き）
# ===============================
def extract_asin(url, retries=3):
    for i in range(retries):
        try:
            response = requests.get(url, allow_redirects=True, timeout=10)
            expanded_url = response.url
            match = re.search(r"(?:dp|gp/product|d)/([A-Z0-9]{10})", expanded_url)
            if match:
                return match.group(1)
            print(f"ASIN抽出失敗: URL={url} (試行 {i+1}/{retries})")
        except requests.RequestException as e:
            print(f"ASIN抽出エラー: {e}")
    return None

# ===============================
# Discord Bot本体
# ===============================
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    await asyncio.sleep(1)
    print(f'Botがログインしました: {client.user}')

@client.event
async def on_message(message):
    if message.author.bot:
        return

    urls = re.findall(AMAZON_URL_REGEX, message.content)
    if not urls:
        return

    for url in urls:
        await message.channel.send("リンクを確認中です... 🔍")
        asin = extract_asin(url)
        if not asin:
            await message.channel.send("ASINが取得できませんでした。❌")
            continue

        title, price, image_url = fetch_amazon_data(asin)
        if title and price and image_url:
            embed = discord.Embed(
                title=title,
                url=url,
                description=f"**価格**: {price}\n\n商品情報を整理しました！✨️",
                color=discord.Color.blue()
            )
            embed.set_thumbnail(url=image_url)
            await message.channel.send(embed=embed)
        else:
            await message.channel.send("商品情報を取得できませんでした。リンクが正しいか確認してください。")

def fetch_amazon_data(asin):
    try:
        response = amazon_signed_request(asin)
        if response and "ItemsResult" in response and "Items" in response["ItemsResult"]:
            item = response["ItemsResult"]["Items"][0]
            title = item["ItemInfo"]["Title"]["DisplayValue"]
            price = item.get("Offers", {}).get("Listings", [{}])[0].get("Price", {}).get("DisplayAmount", "N/A")
            image_url = item["Images"]["Primary"]["Large"]["URL"]
            return title, price, image_url
    except Exception as e:
        print(f"商品情報取得エラー: {e}")
    return None, None, None

client.run(TOKEN)
