import os
import discord
from discord.ext import commands
import re
from amazon.paapi import AmazonAPI

# ===============================
# HTTPサーバーのセットアップ
# ===============================
from flask import Flask
import threading

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

# 設定
TOKEN = os.getenv("TOKEN")
AMAZON_ACCESS_KEY = os.getenv("AMAZON_ACCESS_KEY")
AMAZON_SECRET_KEY = os.getenv("AMAZON_SECRET_KEY")
AMAZON_ASSOCIATE_TAG = os.getenv("AMAZON_ASSOCIATE_TAG")

# Amazon API設定
COUNTRY = "JP"
amazon = AmazonAPI(AMAZON_ACCESS_KEY, AMAZON_SECRET_KEY, AMAZON_ASSOCIATE_TAG, COUNTRY)

# Discord Botの準備
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Amazonリンクをアフィリエイトリンクに変換する関数
def convert_amazon_link(url):
    if "dp/" not in url:
        return None
    if "?" in url:
        return f"{url}&tag={AMAZON_ASSOCIATE_TAG}"
    return f"{url}?tag={AMAZON_ASSOCIATE_TAG}"

# ASINを抽出する関数
def extract_asin(url):
    asin_match = re.search(r"/dp/([A-Z0-9]{10})", url)
    if asin_match:
        return asin_match.group(1)
    return None

# 商品情報を取得する関数
def get_amazon_product_info(asin):
    try:
        products = amazon.get_items(asin)
        product = products.get("data")[0]

        return {
            "title": product.item_info.title.display_value if product.item_info and product.item_info.title else "商品名なし",
            "price": f"¥{product.offers.listings[0].price.amount}" if product.offers and product.offers.listings else "価格情報なし",
            "url": product.detail_page_url,
            "image_url": product.images.primary.large.url if product.images and product.images.primary else "",
        }
    except Exception as e:
        print(f"Error fetching product info: {e}")
        return None

# メッセージイベントの処理
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    urls = re.findall(r"https?://[\w\-_.~!*'();:@&=+$,/?#%[\]]+", message.content)
    amazon_urls = [url for url in urls if re.search(r"amazon\.co\.jp|amzn\.asia", url)]
    if not amazon_urls:
        return

    url = amazon_urls[0]
    channel = message.channel

    try:
        asin = extract_asin(url)
        if not asin:
            await channel.send("ASINが取得できませんでした。")
            return

        affiliate_link = convert_amazon_link(url)
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
            await channel.send(embed=embed)
        else:
            await channel.send(f"商品情報が見つかりませんでした。ASIN: {asin}")
    except Exception as e:
        print(f"Error: {e}")
        await channel.send("エラー：予期せぬ問題が発生しました")

# Botの起動
bot.run(TOKEN)
