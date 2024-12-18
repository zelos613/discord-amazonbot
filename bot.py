import os
import re
import discord
import requests
from urllib.parse import urlparse
from dotenv import load_dotenv
from paapi5_python_sdk.api.default_api import DefaultApi
from paapi5_python_sdk.paapi5_sdk_exception import Paapi5SdkException
from paapi5_python_sdk.models.get_items_request import GetItemsRequest
from paapi5_python_sdk.models.partner_type import PartnerType
from paapi5_python_sdk.models.resources import Resources

# 環境変数読み込み
load_dotenv()
TOKEN = os.getenv('TOKEN')
AMAZON_ACCESS_KEY = os.getenv('AMAZON_ACCESS_KEY')
AMAZON_SECRET_KEY = os.getenv('AMAZON_SECRET_KEY')
AMAZON_ASSOCIATE_TAG = os.getenv('AMAZON_ASSOCIATE_TAG')

# Amazon PA-API設定
api_instance = DefaultApi(
    access_key=AMAZON_ACCESS_KEY,
    secret_key=AMAZON_SECRET_KEY,
    host="webservices.amazon.co.jp",
    region="us-west-2"
)

# ASIN抽出関数
def extract_asin(url):
    try:
        match = re.search(r"(?:dp|gp/product|d)/([A-Z0-9]{10})", url)
        return match.group(1) if match else None
    except Exception as e:
        print(f"ASIN抽出エラー: {e}")
    return None

# 商品情報取得関数
def fetch_amazon_data(asin):
    try:
        get_items_request = GetItemsRequest(
            partner_tag=AMAZON_ASSOCIATE_TAG,
            partner_type=PartnerType.ASSOCIATES,
            marketplace="www.amazon.co.jp",
            item_ids=[asin],
            resources=[
                Resources.ITEM_INFO_TITLE,
                Resources.OFFERS_LISTINGS_PRICE,
                Resources.IMAGES_PRIMARY_LARGE
            ]
        )
        response = api_instance.get_items(get_items_request)
        item = response.items_result.items[0]
        title = item.item_info.title.display_value
        price = item.offers.listings[0].price.display_amount
        image_url = item.images.primary.large.url
        return title, price, image_url
    except Paapi5SdkException as e:
        print(f"PA-APIエラー: {e}")
    return None, None, None

# Discord Bot
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f"Botがログインしました: {client.user}")

@client.event
async def on_message(message):
    if message.author.bot:
        return

    urls = re.findall(r"(https?://(?:www\.)?amazon\.co\.jp/[\w\-/]+)", message.content)
    for url in urls:
        await message.channel.send("リンクを確認中です...🔍")
        asin = extract_asin(url)
        if not asin:
            await message.channel.send("ASINが取得できませんでした。❌")
            continue

        title, price, image_url = fetch_amazon_data(asin)
        if title and price and image_url:
            embed = discord.Embed(
                title=title,
                url=url,
                description=f"**価格**: {price}\n✨ 商品情報を整理しました！",
                color=discord.Color.blue()
            )
            embed.set_thumbnail(url=image_url)
            await message.channel.send(embed=embed)
        else:
            await message.channel.send("商品情報を取得できませんでした。リンクが正しいか確認してください。")

client.run(TOKEN)
