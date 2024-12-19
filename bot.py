import os
import discord
from discord.ext import commands
import re
import requests
from bs4 import BeautifulSoup
import asyncio
from flask import Flask
import threading

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

# Amazon商品情報を取得する関数
# Amazon商品情報を取得する関数
def get_amazon_product_info(affiliate_link):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        response = requests.get(affiliate_link, headers=headers, timeout=TIMEOUT)
        soup = BeautifulSoup(response.content, "html.parser")

        # 商品名を取得
        title_element = soup.find(id="productTitle")
        title = title_element.get_text(strip=True) if title_element else "商品名が取得できません"

        # 価格を取得
        price_element = soup.find("span", {"class": "a-price-whole"}) or soup.find(id="priceblock_ourprice")
        price_fraction = soup.find("span", {"class": "a-price-fraction"})  # 小数点以下を取得
        if price_element:
            price = f"￥{price_element.get_text(strip=True)}"
            if price_fraction:
                price += f".{price_fraction.get_text(strip=True)}"
        else:
            price = "価格情報なし"

        # 画像URLを取得
        image_element = soup.find("img", {"id": "landingImage"})
        image_url = image_element["src"] if image_element else ""

        # デバッグ情報
        print(f"Extracted Title: {title}")
        print(f"Extracted Price: {price}")
        print(f"Extracted Image URL: {image_url}")

        return {
            "title": title,
            "price": price,
            "image_url": image_url,
            "link": affiliate_link
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
    amazon_urls = [url for url in urls if re.search(r"amazon\.com|amazon\.co\.jp|amzn\.asia", url)]
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
            product_info = get_amazon_product_info(affiliate_link)
            if product_info:
                embed = discord.Embed(
                    title=product_info["title"] or "商品情報",
                    url=product_info["link"],
                    description="商品情報を整理しました✨️",
                    color=0x00ff00
                )
                embed.add_field(name="価格", value=product_info["price"], inline=False)
                if product_info["image_url"]:
                    embed.set_image(url=product_info["image_url"])
                await channel.send(embed=embed)
            else:
                await channel.send("商品情報の取得に失敗しました")
        else:
            await channel.send("エラー：リンク変換に失敗しました")
    except Exception as e:
        print(f"Error: {e}")
        await channel.send("エラー：予期せぬ問題が発生しました")

# Botの起動
bot.run(TOKEN)
