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

# Amazonリンクを検出する正規表現
AMAZON_URL_REGEX = r"(https?://(?:www\.)?(?:amazon\.co\.jp|amzn\.asia|amzn\.to)/[\w\-/\?=&%\.]+)"

def fetch_amazon_data(asin):
    try:
        api_client = DefaultApi(
            access_key=AMAZON_ACCESS_KEY,
            secret_key=AMAZON_SECRET_KEY,
            host="webservices.amazon.co.jp",
            region="us-west-2"
        )
        # BrowseNodeInfo.WebsiteSalesRankを取得するために必要なリソースを追加
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
                "BrowseNodeInfo.BrowseNodes.DisplayName",
                "BrowseNodeInfo.BrowseNodes.WebsiteSalesRank"
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
                features = item.item_info.features.display_values[:3]

            # カテゴリランキング情報取得
            category_rank_text = ""
            if item.browse_node_info and item.browse_node_info.browse_nodes:
                # 複数あっても一つめを表示するなど
                for bn in item.browse_node_info.browse_nodes:
                    if bn.website_sales_rank and bn.display_name:
                        # 例：「この商品は【〇〇カテゴリ】で第X位にランクイン！」と表示
                        category_rank_text = f"この商品は**{bn.display_name}**カテゴリで **第{bn.website_sales_rank}位** にランクイン！🔥"
                        # 一つ見つけたらbreakするなど
                        break

            return title, price, image_url, features, category_rank_text
        else:
            return None, None, None, None, ""
    except Exception:
        return None, None, None, None, ""

def extract_asin(url):
    try:
        parsed_url = requests.get(url, allow_redirects=True, timeout=5).url
        asin_match = re.search(r"/dp/([A-Z0-9]{10})", parsed_url)
        if asin_match:
            return asin_match.group(1)
        return None
    except Exception:
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

    checking_message = None
    try:
        checking_message = await message.channel.send("リンクを確認中です...🔍")
        for url in urls:
            asin = extract_asin(url)
            if not asin:
                await message.channel.send("ASINが取得できませんでした。❌")
                continue

            title, price, image_url, features, category_rank_text = fetch_amazon_data(asin)
            if title and price and image_url:
                affiliate_url = f"https://www.amazon.co.jp/dp/{asin}/?tag={AMAZON_ASSOCIATE_TAG}"

                description_text = f"**価格**: {price}\n"
                if features:
                    bullet_points = "\n".join([f"- {f}" for f in features])
                    description_text += f"\n**特徴**:\n{bullet_points}\n"

                if category_rank_text:
                    description_text += f"\n{category_rank_text}\n"

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
