import os
import discord
import re
import requests
from flask import Flask
import threading
from paapi5_python_sdk.api.default_api import DefaultApi
from paapi5_python_sdk.models.get_items_request import GetItemsRequest
from paapi5_python_sdk.models.partner_type import PartnerType
from bs4 import BeautifulSoup

from selenium import webdriver
from selenium.webdriver.chrome.options import Options

# ===============================
# HTTPサーバーのセットアップ
# ===============================
app = Flask(__name__)

@app.route("/")
def health_check():
    return "OK", 200

def run_http_server():
    app.run(host="0.0.0.0", port=8000)

http_thread = threading.Thread(target=run_http_server)
http_thread.daemon = True
http_thread.start()

# ===============================
# 環境変数の設定
# ===============================
TOKEN = os.getenv('TOKEN')
AMAZON_ACCESS_KEY = os.getenv('AMAZON_ACCESS_KEY')
AMAZON_SECRET_KEY = os.getenv('AMAZON_SECRET_KEY')
AMAZON_ASSOCIATE_TAG = os.getenv('AMAZON_ASSOCIATE_TAG')

# 正規表現: Amazonリンクの検出
AMAZON_URL_REGEX = r"(https?://(?:www\.)?(?:amazon\.co\.jp|amzn\.asia|amzn\.to)/[\w\-/\?=&%\.]+)"

def fetch_amazon_data(asin):
    try:
        api_client = DefaultApi(
            access_key=AMAZON_ACCESS_KEY,
            secret_key=AMAZON_SECRET_KEY,
            host="webservices.amazon.co.jp",
            region="us-west-2"
        )
        request = GetItemsRequest(
            partner_tag=AMAZON_ASSOCIATE_TAG,
            partner_type=PartnerType.ASSOCIATES,
            marketplace="www.amazon.co.jp",
            item_ids=[asin],
            resources=[
                "ItemInfo.Title",
                "Offers.Listings.Price",
                "Images.Primary.Large",
                "ItemInfo.Features"
            ]
        )
        response = api_client.get_items(request)

        if response.items_result and response.items_result.items:
            item = response.items_result.items[0]
            title = item.item_info.title.display_value if item.item_info and item.item_info.title else "商品名なし"
            price = (item.offers.listings[0].price.display_amount
                     if item.offers and item.offers.listings and item.offers.listings[0].price
                     else "価格情報なし")
            image_url = item.images.primary.large.url if item.images and item.images.primary else ""

            features = []
            if item.item_info and item.item_info.features and item.item_info.features.display_values:
                features = item.item_info.features.display_values[:3]  # 最初の3件のみ

            return title, price, image_url, features
        else:
            return None, None, None, None
    except Exception as e:
        print(f"Amazon情報取得エラー: {e}")
        return None, None, None, None

def fetch_sakura_checker_rating(asin):
    url = f"https://sakura-checker.jp/search/{asin}/"
    # Seleniumによるヘッドレスブラウザ起動
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument('--lang=ja-JP')
    chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                                'AppleWebKit/537.36 (KHTML, like Gecko) '
                                'Chrome/108.0.0.0 Safari/537.36')

    driver = webdriver.Chrome(options=chrome_options)
    try:
        driver.get(url)
        # JSレンダリング待ち (必要なら明示的なウェイトを追加可能)
        # from selenium.webdriver.common.by import By
        # from selenium.webdriver.support.ui import WebDriverWait
        # from selenium.webdriver.support import expected_conditions as EC
        # WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, "p.item-rv-lv")))
        
        html_source = driver.page_source
        match = re.search(r'(/images/rv_level0[1-4]\.png)', html_source)
        if match:
            rating_url = "https://sakura-checker.jp" + match.group(1)
            return rating_url
        else:
            print("サクラチェッカー評価は見つかりませんでした（Selenium使用後）。")
            return None
    except Exception as e:
        print(f"サクラチェッカー評価取得エラー: {e}")
        return None
    finally:
        driver.quit()

def extract_asin(url):
    try:
        parsed_url = requests.get(url, allow_redirects=True).url
        asin_match = re.search(r"/dp/([A-Z0-9]{10})", parsed_url)
        if asin_match:
            return asin_match.group(1)
        return None
    except Exception as e:
        print(f"ASIN抽出エラー: {e}")
        return None

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
        checking_message = await message.channel.send("リンクを確認中です...🔍")
        asin = extract_asin(url)
        if not asin:
            await checking_message.delete()
            await message.channel.send("ASINが取得できませんでした。❌")
            continue

        title, price, image_url, features = fetch_amazon_data(asin)
        if title and price and image_url:
            affiliate_url = f"https://www.amazon.co.jp/dp/{asin}/?tag={AMAZON_ASSOCIATE_TAG}"

            description_text = f"**価格**: {price}\n"
            if features:
                bullet_points = "\n".join([f"- {f}" for f in features])
                description_text += f"\n**特徴**:\n{bullet_points}\n"

            sakura_rating_url = fetch_sakura_checker_rating(asin)
            if sakura_rating_url:
                description_text += "\nサクラチェッカーでの評価はこちら！"
            else:
                description_text += "\nサクラチェッカーでの評価は見つかりませんでした。"

            embed = discord.Embed(
                title=title,
                url=affiliate_url,
                description=description_text,
                color=discord.Color.blue()
            )
            embed.set_thumbnail(url=image_url)

            if sakura_rating_url:
                embed.set_image(url=sakura_rating_url)

            await checking_message.delete()
            await message.channel.send(embed=embed)
        else:
            await checking_message.delete()
            await message.channel.send("商品情報を取得できませんでした。リンクが正しいか確認してください。")

client.run(TOKEN)
