import os
import discord
from discord.ext import commands
import re
import requests
import asyncio
from flask import Flask

# Flaskアプリケーションの作成
app = Flask(__name__)

# ヘルスチェック用のエンドポイント
@app.route('/')
def health_check():
    return "Bot is running!", 200

# 設定
TOKEN = os.getenv("TOKEN")
AFFILIATE_ID = os.getenv("AMAZON_ASSOCIATE_TAG")
TIMEOUT = 10  # タイムアウト時間（秒）

# Discord Botの準備
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Amazonリンクをアフィリエイトリンクに変換する関数
def convert_amazon_link(url):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        response = requests.get(url, allow_redirects=True, timeout=TIMEOUT, headers=headers)
        final_url = response.url
        if "dp/" not in final_url:
            return None
        if "?" in final_url:
            affiliate_link = f"{final_url}&tag={AFFILIATE_ID}"
        else:
            affiliate_link = f"{final_url}?tag={AFFILIATE_ID}"
        return affiliate_link
    except requests.exceptions.Timeout:
        return "TIMEOUT"
    except Exception:
        return None

# メッセージイベントの処理
@bot.event
async def on_message(message):
    if message.author.bot:
        return
    urls = re.findall(r"https?://[\w\-_.~!*'();:@&=+$,/?#%[\]]+", message.content)
    amazon_urls = [url for url in urls if re.search(r"amazon\\.com|amazon\\.co\\.jp|amzn\\.asia", url)]
    if not amazon_urls:
        return
    url = amazon_urls[0]
    channel = message.channel
    try:
        loop = asyncio.get_event_loop()
        affiliate_link = await loop.run_in_executor(None, convert_amazon_link, url)
        if affiliate_link == "TIMEOUT":
            await channel.send("エラー：タイムアウト")
        elif affiliate_link:
            await channel.send(f"アフィリエイトリンクへ変換 ↓ ↓\n{affiliate_link}")
        else:
            await channel.send("エラー：リンク変換に失敗しました")
    except Exception:
        await channel.send("エラー：予期せぬ問題が発生しました")

# Flaskサーバーを非同期で実行するタスク
def run_flask():
    app.run(host="0.0.0.0", port=8000)

# Flaskサーバーを非同期で実行
loop = asyncio.get_event_loop()
loop.run_in_executor(None, run_flask)

# Botの起動
bot.run(TOKEN)
