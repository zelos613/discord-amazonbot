import os
import discord
import re
import requests
import json
import hashlib
import hmac
import datetime
from urllib.parse import urlparse, parse_qs
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
# ASINの抽出
# ===============================
def extract_asin(url):
    try:
        response = requests.head(url, allow_redirects=True, timeout=5)  # HEADで高速化
        expanded_url = response.url
        print(f"Expanded URL: {expanded_url}")  # Debug用
        match = re.search(r"(?:dp|gp/product|d)/([A-Z0-9]{10})", expanded_url)
        if match:
            return match.group(1)
    except Exception as e:
        print(f"ASIN抽出エラー: {e}")
    return None

# ===============================
# Amazon PA-APIリクエスト
# ===============================
def amazon_signed_request(asin):
    url = "https://webservices.amazon.co.jp/paapi5/getitems"
    payload = {
        "PartnerTag": AMAZON_ASSOCIATE_TAG,
        "PartnerType": "Associates",
        "Marketplace": "www.amazon.co.jp",
        "Resources": ["Images.Primary.Large", "ItemInfo.Title", "Offers.Listings.Price"],
        "ItemIds": [asin]
    }
    try:
        headers = {
            'Content-Type': 'application/json'
        }
        response = requests.post(url, json=payload, headers=headers)
        print(f"API Response: {response.status_code} - {response.text}")
        return response.json() if response.status_code == 200 else None
    except Exception as e:
        print(f"APIリクエストエラー: {e}")
    return None

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

    processed_asins = set()  # 重複防止
    for url in urls:
        await message.channel.send("リンクを確認中です...🔍")
        asin = extract_asin(url)
        if not asin or asin in processed_asins:
            await message.channel.send("ASINが取得できませんでした。")
            continue
        processed_asins.add(asin)

        response = amazon_signed_request(asin)
        if response:
            try:
                item = response["ItemsResult"]["Items"][0]
                title = item["ItemInfo"]["Title"]["DisplayValue"]
                price = item["Offers"]["Listings"][0]["Price"]["DisplayAmount"]
                image_url = item["Images"]["Primary"]["Large"]["URL"]

                embed = discord.Embed(
                    title=title,
                    url=url,
                    description=f"**価格**: {price}\n\n商品情報を整理しました！✨",
                    color=discord.Color.blue()
                )
                embed.set_thumbnail(url=image_url)
                await message.channel.send(embed=embed)
            except Exception as e:
                print(f"商品情報処理エラー: {e}")
                await message.channel.send("商品情報を取得できませんでした。")
        else:
            await message.channel.send("Amazon APIから商品情報が取得できませんでした。")

client.run(TOKEN)
