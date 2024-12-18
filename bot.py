import os
import discord
import re
import boto3
from urllib.parse import urlparse
from dotenv import load_dotenv

# 環境変数読み込み
load_dotenv()
TOKEN = os.getenv('TOKEN')
AMAZON_ASSOCIATE_TAG = os.getenv('AMAZON_ASSOCIATE_TAG')
AMAZON_ACCESS_KEY = os.getenv('AMAZON_ACCESS_KEY')
AMAZON_SECRET_KEY = os.getenv('AMAZON_SECRET_KEY')

# Amazonリンクの正規表現
AMAZON_URL_REGEX = r"(https?://(?:www\.)?amazon\.co\.jp/(?:[^ ]*))"

# boto3クライアント
client = boto3.client(
    'paapi5',
    aws_access_key_id=AMAZON_ACCESS_KEY,
    aws_secret_access_key=AMAZON_SECRET_KEY,
    region_name='us-west-2'  # PA-APIのリージョンに応じて変更
)

# ASIN抽出関数
def extract_asin(url):
    try:
        match = re.search(r"(?:dp|gp/product|d)/([A-Z0-9]{10})", url)
        return match.group(1) if match else None
    except Exception as e:
        print(f"ASIN抽出エラー: {e}")
    return None

# 商品情報取得
def fetch_amazon_data(asin):
    try:
        response = client.get_items(
            PartnerTag=AMAZON_ASSOCIATE_TAG,
            PartnerType="Associates",
            Marketplace="www.amazon.co.jp",
            ItemIds=[asin],
            Resources=["ItemInfo.Title", "Offers.Listings.Price", "Images.Primary.Large"]
        )
        item = response["ItemsResult"]["Items"][0]
        title = item["ItemInfo"]["Title"]["DisplayValue"]
        price = item["Offers"]["Listings"][0]["Price"]["DisplayAmount"]
        image_url = item["Images"]["Primary"]["Large"]["URL"]
        return title, price, image_url
    except Exception as e:
        print(f"Amazon APIエラー: {e}")
    return None, None, None

# Discord Bot設定
intents = discord.Intents.default()
intents.message_content = True
bot = discord.Client(intents=intents)

@bot.event
async def on_ready():
    print(f"Botログイン: {bot.user}")

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    urls = re.findall(AMAZON_URL_REGEX, message.content)
    if not urls:
        return

    for url in urls:
        asin = extract_asin(url)
        if not asin:
            await message.channel.send("ASINが取得できませんでした。")
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
            await message.channel.send("商品情報を取得できませんでした。")

bot.run(TOKEN)
