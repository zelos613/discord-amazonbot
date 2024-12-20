import os
import discord
from discord.ext import commands
import re
import requests
from paapi5_python_sdk.api.default_api import DefaultApi
from paapi5_python_sdk.models.get_items_request import GetItemsRequest
from paapi5_python_sdk.models.partner_type import PartnerType

# ===============================
# Botの設定
# ===============================
intents = discord.Intents.default()
intents.message_content = True  # メッセージ内容の読み取りを有効化
bot = commands.Bot(command_prefix="!", intents=intents)

# Amazon PA-API設定
AMAZON_ASSOCIATE_TAG = os.getenv("AMAZON_ASSOCIATE_TAG")
AMAZON_ACCESS_KEY = os.getenv("AMAZON_ACCESS_KEY")
AMAZON_SECRET_KEY = os.getenv("AMAZON_SECRET_KEY")

# Amazon APIクライアントの初期化
def get_amazon_client():
    return DefaultApi(
        access_key=AMAZON_ACCESS_KEY,
        secret_key=AMAZON_SECRET_KEY,
        host="webservices.amazon.co.jp",
        region="us-west-2"
    )

# 商品情報を取得する関数
def get_amazon_product_info(asin):
    try:
        api_client = get_amazon_client()
        request = GetItemsRequest(
            partner_tag=AMAZON_ASSOCIATE_TAG,
            partner_type=PartnerType.ASSOCIATES,
            marketplace="www.amazon.co.jp",
            item_ids=[asin],
            resources=["ItemInfo.Title", "Offers.Listings.Price", "Images.Primary.Large"]
        )
        response = api_client.get_items(request)

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
        print(f"Error fetching product info: {e}")
        return None

# メッセージからASINを抽出する関数
def extract_asin(url):
    try:
        asin_match = re.search(r"/dp/([A-Z0-9]{10})", url)
        if asin_match:
            return asin_match.group(1)
        return None
    except Exception as e:
        print(f"Error extracting ASIN: {e}")
        return None

# ===============================
# イベント処理
# ===============================
@bot.event
async def on_ready():
    print(f"Bot connected as {bot.user}")

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    print(f"Received message: {message.content}")  # デバッグ用ログ

    amazon_urls = re.findall(r"https?://(www\.)?amazon\.(com|co\.jp)/[^\s]+", message.content)
    if amazon_urls:
        url = amazon_urls[0][0]  # 最初のAmazonリンクを処理
        await message.channel.send("Amazonリンクを検出しました！商品情報を取得しています...")

        try:
            asin = extract_asin(url)
            if not asin:
                await message.channel.send("ASINが取得できませんでした。")
                return

            product_info = get_amazon_product_info(asin)
            if product_info:
                embed = discord.Embed(
                    title=product_info["title"],
                    url=url,
                    description="商品情報を整理しました✨️",
                    color=0x00ff00
                )
                embed.add_field(name="価格", value=product_info["price"], inline=False)
                if product_info["image_url"]:
                    embed.set_image(url=product_info["image_url"])
                await message.channel.send(embed=embed)
            else:
                await message.channel.send("商品情報を取得できませんでした。")
        except Exception as e:
            print(f"Error: {e}")
            await message.channel.send("エラーが発生しました。")

# ===============================
# Botの起動
# ===============================
TOKEN = os.getenv("TOKEN")
bot.run(TOKEN)
