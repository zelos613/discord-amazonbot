import os
import discord
from discord.ext import commands
import re
import requests
from flask import Flask
import threading
from paapi5_python_sdk.api.default_api import DefaultApi
from paapi5_python_sdk.models.get_items_request import GetItemsRequest
from paapi5_python_sdk.models.get_items_resource import GetItemsResource

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
AMAZON_ACCESS_KEY = os.getenv("AMAZON_ACCESS_KEY")
AMAZON_SECRET_KEY = os.getenv("AMAZON_SECRET_KEY")
PROXY_HTTP = os.getenv("PROXY_HTTP")
PROXY_HTTPS = os.getenv("PROXY_HTTPS")
TIMEOUT = 20  # タイムアウト時間

# プロキシ設定
proxies = {
    "http": PROXY_HTTP,
    "https": PROXY_HTTPS
}

# プロキシテスト
def test_proxy_connection():
    test_url = "http://httpbin.org/ip"
    try:
        print("Testing proxy connection...")
        response = requests.get(test_url, proxies=proxies, timeout=10)
        print(f"Proxy Test Response: {response.json()}")
    except Exception as e:
        print(f"Proxy Test Error: {e}")

# プロキシテストを実行
test_proxy_connection()

# Discord Botの準備
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Amazonリンクをアフィリエイトリンクに変換する関数
def convert_amazon_link(url):
    try:
        if "dp/" not in url:
            return None
        if "?" in url:
            affiliate_link = f"{url}&tag={AFFILIATE_ID}"
        else:
            affiliate_link = f"{url}?tag={AFFILIATE_ID}"
        return affiliate_link
    except Exception as e:
        print(f"Error converting link: {e}")
        return None

# Amazon PA-APIを使った商品情報取得
def get_amazon_product_info_via_api(asin):
    try:
        # APIの設定
        api = DefaultApi(
            access_key=AMAZON_ACCESS_KEY,
            secret_key=AMAZON_SECRET_KEY,
            host="webservices.amazon.co.jp",
            region="us-west-2"
        )

        # リクエストの作成
        request = GetItemsRequest(
            partner_tag=AFFILIATE_ID,
            partner_type="Associates",
            marketplace="www.amazon.co.jp",
            item_ids=[asin],
            resources=[
                GetItemsResource.ITEM_INFO_TITLE,
                GetItemsResource.OFFERS_LISTINGS_PRICE,
                GetItemsResource.IMAGES_PRIMARY_LARGE
            ]
        )

        # リクエスト送信
        print(f"Sending request to Amazon PA-API with ASIN: {asin}")
        response = api.get_items(request, proxies=proxies)

        # デバッグ出力
        print("=== API Debug Information ===")
        print(f"ASIN: {asin}")
        print(f"Request: {request}")
        print(f"Response: {response}")

        # レスポンスから商品情報を抽出
        if response.items_result and response.items_result.items:
            item = response.items_result.items[0]
            return {
                "title": item.item_info.title.display_value if item.item_info and item.item_info.title else "商品名なし",
                "price": item.offers.listings[0].price.display_amount if item.offers and item.offers.listings else "価格情報なし",
                "image_url": item.images.primary.large.url if item.images and item.images.primary else "",
            }
        else:
            print("商品情報が見つかりませんでした")
            return None
    except Exception as e:
        print(f"Error fetching product info via PA-API: {e}")
        return None

# ASINを抽出する関数
def extract_asin(url):
    try:
        asin_match = re.search(r"/dp/([A-Z0-9]{10})", url)
        if asin_match:
            print(f"Extracted ASIN: {asin_match.group(1)}")
            return asin_match.group(1)

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        }
        response = requests.get(url, headers=headers, allow_redirects=True, timeout=TIMEOUT, proxies=proxies)
        redirect_url = response.url
        asin_match = re.search(r"/dp/([A-Z0-9]{10})", redirect_url)
        if asin_match:
            print(f"Extracted ASIN from redirected URL: {asin_match.group(1)}")
            return asin_match.group(1)

        print("ASIN not found in URL")
        return None
    except Exception as e:
        print(f"Error extracting ASIN: {e}")
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
        asin = extract_asin(url)
        print(f"Extracted ASIN: {asin}")

        if not asin:
            await channel.send("ASINが取得できませんでした。")
            return

        affiliate_link = convert_amazon_link(url)
        if affiliate_link:
            await channel.send(f"アフィリエイトリンク: {affiliate_link}")

        product_info = get_amazon_product_info_via_api(asin)
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
