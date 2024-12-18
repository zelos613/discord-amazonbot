import os
import discord
import re
import requests
from urllib.parse import urlparse
from dotenv import load_dotenv

# ===============================
# 環境変数の読み込み
# ===============================
load_dotenv()
TOKEN = os.getenv('TOKEN')
AMAZON_ACCESS_KEY = os.getenv('AMAZON_ACCESS_KEY')
AMAZON_SECRET_KEY = os.getenv('AMAZON_SECRET_KEY')
AMAZON_ASSOCIATE_TAG = os.getenv('AMAZON_ASSOCIATE_TAG')

# 正規表現: Amazonリンク検出
AMAZON_URL_REGEX = r"(https?://(?:www\.)?(?:amazon\.co\.jp|amzn\.asia)/[\w\-/\?=&%\.]+)"

# ===============================
# 短縮URLの展開処理
# ===============================
def expand_short_url(url):
    try:
        response = requests.head(url, allow_redirects=True, timeout=5)
        return response.url
    except Exception as e:
        print(f"URL展開エラー: {e}")
    return url

# ===============================
# ASIN抽出処理
# ===============================
def extract_asin(url):
    url = expand_short_url(url)  # 短縮URLを展開
    match = re.search(r"(?:dp|gp/product|d)/([A-Z0-9]{10})", url)
    if match:
        return match.group(1)
    print(f"ASIN抽出失敗: URL={url}")
    return None

# ===============================
# Amazon商品情報取得
# ===============================
def fetch_amazon_data(asin):
    url = f"https://api.example.com/mock/amazon/{asin}"  # ダミーAPIエンドポイント（テスト用）
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return data.get("title"), data.get("price"), data.get("image_url")
    except Exception as e:
        print(f"商品情報取得エラー: {e}")
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
    for url in urls:
        await message.channel.send("リンクを確認中です...🔍")
        asin = extract_asin(url)
        if not asin:
            await message.channel.send("ASINが取得できませんでした。リンクが正しいか確認してください。")
            return

        title, price, image_url = fetch_amazon_data(asin)
        if title and price and image_url:
            embed = discord.Embed(
                title=title,
                url=url,
                description=f"**価格**: {price}\n\n商品情報を整理しました！✨",
                color=discord.Color.green()
            )
            embed.set_thumbnail(url=image_url)
            await message.channel.send(embed=embed)
        else:
            await message.channel.send("商品情報を取得できませんでした。リンクが正しいか確認してください。")

client.run(TOKEN)
