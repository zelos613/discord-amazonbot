import os
import discord
from discord.ext import commands
import re
import requests
from flask import Flask
import threading
import time
from paapi5_python_sdk.api.default_api import DefaultApi
from paapi5_python_sdk.models.get_items_request import GetItemsRequest
from paapi5_python_sdk.models.partner_type import PartnerType

# ===============================
# HTTPサーバーのセットアップ
# ===============================
app = Flask(__name__)

@app.route("/")
def health_check():
    return "OK", 200

def run_http_server():
    app.run(host="0.0.0.0", port=8000)

# HTTPサーバーをバックグラウンドで実行
http_thread = threading.Thread(target=run_http_server)
http_thread.daemon = True
http_thread.start()

# ===============================
# 環境変数から設定を取得
# ===============================
TOKEN = os.getenv("TOKEN")
AFFILIATE_ID = os.getenv("AMAZON_ASSOCIATE_TAG")
AMAZON_ACCESS_KEY = os.getenv("AMAZON_ACCESS_KEY")
AMAZON_SECRET_KEY = os.getenv("AMAZON_SECRET_KEY")
TIMEOUT = 20  # タイムアウト時間（秒）

# ===============================
# Discord Botの準備
# ===============================
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ===============================
# Amazon PA-APIを使った商品情報取得
# ===============================
def get_amazon_product_info(asin):
    try:
        # PA-APIクライアント設定
        api = DefaultApi(
            access_key=AMAZON_ACCESS_KEY,
            secret_key=AMAZON_SECRET_KEY,
            host="webservices.amazon.co.jp",
            region="us-west-2"
        )

        # PA-APIリクエストの作成
        request = GetItemsRequest(
            partner_tag=AFFILIATE_ID,
            partner_type=PartnerType.ASSOCIATES,
            marketplace="www.amazon.co.jp",
            item_ids=[asin],
            resources=[
                "ItemInfo.Title",
                "Offers.Listings.Price",
                "Images.Primary.Large"
            ]
        )

        # リクエスト送信
        response = api.get_items(request)
        if response.items_result and response.items_result.items:
            item = response.items_result.items[0]
            return {
                "title": item.item_info.title.display_value if item.item_info and item.item_info.title else "商品名なし",
                "price": item.offers.listings[0].price.display_amount if item.offers and item.offers.listings else "価格情報なし",
                "image_url": item.images.primary.large.url if item.images and item.images.primary else "",
            }
        else:
            return None
    except Exception as e:
        print(f"Error fetching product info via PA-API: {e}")
        return None

# ===============================
# ASINを抽出する関数
# ===============================
def extract_asin(url):
    try:
        asin_match = re.search(r"/dp/([A-Z0-9]{10})", url)
        if asin_match:
            return asin_match.group(1)
        else:
            return None
    except Exception as e:
        print(f"Error extracting ASIN: {e}")
        return None

# ===============================
# メッセージイベントの処理
# ===============================
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    urls = re.findall(r"https?://[\w\-_.~!*'();:@&=+$,/?#%[\]]+", message.content)
    amazon_urls = [url for url in urls if re.search(r"amazon\\.com|amazon\\.co\\.jp|amzn\\.asia", url)]
    if not amazon_urls:
        return

    url = amazon_urls[0]
    asin = extract_asin(url)

    if not asin:
        await message.channel.send("ASINが取得できませんでした。")
        return

    affiliate_link = f"{url}?tag={AFFILIATE_ID}"
    product_info = get_amazon_product_info(asin)

    if product_info:
        embed = discord.Embed(
            title=product_info["title"],
            url=affiliate_link,
            description="商品情報を整理しました✨️",
            color=0x00ff00
        )
        embed.add_field(name="価格", value=product_info["price"], inline=False)
        if product_info["image_url"]:
            embed.set_image(url=product_info["image_url"])
        await message.channel.send(embed=embed)
    else:
        await message.channel.send("商品情報が見つかりませんでした。")

# ===============================
# Botの起動
# ===============================
bot.run(TOKEN)
