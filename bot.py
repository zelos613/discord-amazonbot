# bot.py
import os
import discord
from discord.ext import commands
import re
import requests
import asyncio

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
        print(f"[DEBUG] Original URL: {url}\n")

        # HTTPリクエストヘッダーを追加
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }

        # Amazonのリダイレクトを追跡
        response = requests.get(url, allow_redirects=True, timeout=TIMEOUT, headers=headers)
        print(f"[DEBUG] Final URL after redirection: {response.url}\n")

        # アフィリエイトタグを追加
        final_url = response.url
        if "dp/" not in final_url:
            print("[ERROR] URL does not contain a valid product identifier.\n")
            return None

        if "?" in final_url:
            affiliate_link = f"{final_url}&tag={AFFILIATE_ID}"
        else:
            affiliate_link = f"{final_url}?tag={AFFILIATE_ID}"

        print(f"[DEBUG] Generated affiliate link: {affiliate_link}\n")
        return affiliate_link
    except requests.exceptions.Timeout:
        print("[ERROR] Timeout occurred during URL processing.\n")
        return "TIMEOUT"
    except Exception as e:
        print(f"[ERROR] An error occurred: {e}\n")
        return None

# メッセージイベントの処理
@bot.event
async def on_message(message):
    # Bot自身のメッセージは無視
    if message.author.bot:
        return

    print(f"[DEBUG] Received message: {message.content}\n")

    # メッセージ内のURLを抽出
    urls = re.findall(r"https?://[\w\-_.~!*'();:@&=+$,/?#%[\]]+", message.content)
    amazon_urls = [url for url in urls if re.search(r"amazon\.com|amazon\.co\.jp|amzn\.asia", url)]

    if not amazon_urls:
        print("[DEBUG] No Amazon URLs found in the message.")
        return

    # 最初のAmazonリンクを処理
    url = amazon_urls[0]
    print(f"[DEBUG] Extracted Amazon URL: {url}\n")

    # メッセージが送信されたチャンネルに返信
    channel = message.channel

    # タイムアウト付きでリンク変換処理
    try:
        loop = asyncio.get_event_loop()
        affiliate_link = await loop.run_in_executor(None, convert_amazon_link, url)

        if affiliate_link == "TIMEOUT":
            await channel.send("エラー：タイムアウト")
        elif affiliate_link:
            await channel.send(f"アフィリエイトリンクへ変換 ↓ ↓\n{affiliate_link}")
        else:
            await channel.send("エラー：リンク変換に失敗しました")

    except Exception as e:
        print(f"[ERROR] Unexpected error: {e}")
        await channel.send("エラー：予期せぬ問題が発生しました")

# Botの起動
bot.run(TOKEN)
