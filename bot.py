import os
import discord
import re
import requests
from paapi5_python_sdk.api.default_api import DefaultApi
from paapi5_python_sdk.models.get_items_request import GetItemsRequest
from paapi5_python_sdk.models.get_items_resource import GetItemsResource
from paapi5_python_sdk.configuration import Configuration
from paapi5_python_sdk.api_client import ApiClient
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
# PA-API クライアントの初期化
# ===============================
config = Configuration(
    access_key=AMAZON_ACCESS_KEY,
    secret_key=AMAZON_SECRET_KEY,
    host="webservices.amazon.co.jp"
)
api_client = DefaultApi(ApiClient(config))

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
        get_items_request = GetItemsRequest(
            partner_tag=AMAZON_ASSOCIATE_TAG,
            partner_type="Associates",
            marketplace="www.amazon.co.jp",
            item_ids=[asin],
            resources=[
                GetItemsResource.IMAGES_PRIMARY_LARGE,
                GetItemsResource.ITEM_INFO_TITLE,
                GetItemsResource.OFFERS_LISTINGS_PRICE
            ]
        )
        response = api_client.get_items(get_items_request)
        if response.items_result and response.items_result.items:
            item = response.items_result.items[0]
            title = item.item_info.title.display_value
            price = item.offers.listings[0].price.display_amount if item.offers and item.offers.listings else "価格情報なし"
            image_url = item.images.primary.large.url
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
        await message.channel.send("リンクを確認中です...🔍")
        asin = extract_asin(url)
        if not asin:
            await message.channel.send("ASINが取得できませんでした。🚫")
            continue

        title, price, image_url = fetch_amazon_data(asin)
        if title and price and image_url:
            embed = discord.Embed(
                title=title,
                url=url,
                description=f"**価格**: {price}\n\n✨ 商品情報を整理しました！",
                color=discord.Color.blue()
            )
            embed.set_thumbnail(url=image_url)
            await message.channel.send(embed=embed)
        else:
            await message.channel.send("商品情報を取得できませんでした。リンクが正しいか確認してください。")

client.run(TOKEN)
