import os
import discord
import re
import requests
from flask import Flask
import threading
from paapi5_python_sdk.api.default_api import DefaultApi
from paapi5_python_sdk.models.get_items_request import GetItemsRequest
from paapi5_python_sdk.models.partner_type import PartnerType

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

# ===============================
# 商品情報を取得する関数
# ===============================
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
                "ItemInfo.Features",
                "CustomerReviews.Count",
                "CustomerReviews.StarRating"
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
                features = item.item_info.features.display_values[:3]  # 最初の3件まで

            # 評価・レビュー数取得
            star_rating = None
            review_count = None
            if item.customer_reviews:
                star_rating = item.customer_reviews.star_rating if hasattr(item.customer_reviews, 'star_rating') else None
                review_count = item.customer_reviews.count if hasattr(item.customer_reviews, 'count') else None

            return title, price, image_url, features, star_rating, review_count
        else:
            return None, None, None, None, None, None
    except Exception as e:
        return None, None, None, None, None, None

# ===============================
# ASINを抽出する関数
# ===============================
def extract_asin(url):
    try:
        parsed_url = requests.get(url, allow_redirects=True, timeout=5).url  # timeoutで負荷軽減
        asin_match = re.search(r"/dp/([A-Z0-9]{10})", parsed_url)
        if asin_match:
            return asin_match.group(1)
        return None
    except Exception:
        return None

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

    checking_message = None
    try:
        checking_message = await message.channel.send("リンクを確認中です...🔍")
        for url in urls:
            asin = extract_asin(url)
            if not asin:
                await message.channel.send("ASINが取得できませんでした。❌")
                continue

            title, price, image_url, features, star_rating, review_count = fetch_amazon_data(asin)
            if title and price and image_url:
                affiliate_url = f"https://www.amazon.co.jp/dp/{asin}/?tag={AMAZON_ASSOCIATE_TAG}"

                # Amazonっぽい評価表示を再現
                # 例：評価: ⭐4.3 / 5 | レビュー数: 123件
                # 同一行に価格・評価・レビュー数を並べる
                line = f"**価格**: {price}"
                if star_rating is not None and review_count is not None and review_count > 0:
                    line += f" | **評価**: ⭐{star_rating:.1f}/5 | **レビュー数**: {review_count}件"
                elif star_rating is not None:
                    # レビュー数がない場合でも評価だけ表示
                    line += f" | **評価**: ⭐{star_rating:.1f}/5"

                description_text = line + "\n"
                if features:
                    bullet_points = "\n".join([f"- {f}" for f in features])
                    description_text += f"\n**特徴**:\n{bullet_points}\n"

                embed = discord.Embed(
                    title=title,
                    url=affiliate_url,
                    description=description_text,
                    color=discord.Color.blue()
                )
                embed.set_thumbnail(url=image_url)

                await message.channel.send(embed=embed)
            else:
                await message.channel.send("商品情報を取得できませんでした。リンクが正しいか確認してください。")
    except Exception:
        pass
    finally:
        if checking_message:
            await checking_message.delete()

client.run(TOKEN)
