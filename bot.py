import os
import discord
import re
import requests
from datetime import datetime, timedelta
from flask import Flask
import threading
from paapi5_python_sdk.api.default_api import DefaultApi
from paapi5_python_sdk.models.get_items_request import GetItemsRequest
from paapi5_python_sdk.models.partner_type import PartnerType

app = Flask(__name__)

@app.route("/")
def health_check():
    return "OK", 200

def run_http_server():
    port = int(os.getenv("PORT", "8000"))
    app.run(host="0.0.0.0", port=port)

http_thread = threading.Thread(target=run_http_server)
http_thread.daemon = True
http_thread.start()

TOKEN = os.getenv('TOKEN')
AMAZON_ACCESS_KEY = os.getenv('AMAZON_ACCESS_KEY')
AMAZON_SECRET_KEY = os.getenv('AMAZON_SECRET_KEY')
AMAZON_ASSOCIATE_TAG = os.getenv('AMAZON_ASSOCIATE_TAG')

# 日本語や全角記号が入ったURLに対応するため、\S+を使用
AMAZON_URL_REGEX = r"(https?://(?:www\.)?(?:amazon\.co\.jp|amzn\.asia|amzn\.to)/\S+)"

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
                "ItemInfo.Features",
                "Images.Primary.Large",
                "Offers.Listings.Price",
                "Offers.Listings.SavingBasis",
                "Offers.Listings.Promotions"
            ]
        )
        response = api_client.get_items(request)

        if response.items_result and response.items_result.items:
            item = response.items_result.items[0]
            
            title = item.item_info.title.display_value if item.item_info and item.item_info.title else "商品名なし"
            features = []
            if (item.item_info and item.item_info.features 
                and item.item_info.features.display_values):
                features = item.item_info.features.display_values[:3]
            
            image_url = ""
            if item.images and item.images.primary and item.images.primary.large:
                image_url = item.images.primary.large.url

            # オファー情報
            if not (item.offers and item.offers.listings and len(item.offers.listings) > 0):
                return title, None, None, None, None, image_url, features, False

            listing = item.offers.listings[0]
            current_price = listing.price.display_amount if listing.price else None
            
            # SavingBasis(参考価格)がある場合
            saving_basis = listing.saving_basis
            if saving_basis and saving_basis.display_amount:
                strike_price = saving_basis.display_amount
            else:
                strike_price = None

            # 割引率の計算
            discount_percentage = None
            discount_amount = None
            if strike_price and current_price:
                try:
                    strike_num = float(strike_price.replace(",", "").replace("¥", ""))
                    current_num = float(current_price.replace(",", "").replace("¥", ""))
                    if strike_num > current_num:  # 割引されているときだけ
                        discount_percentage = int(round((strike_num - current_num) / strike_num * 100))
                        discount_amount = strike_num - current_num
                except:
                    pass
            
            # タイムセール(簡易判定)
            is_time_sale = False
            if listing.promotions:
                for promo in listing.promotions:
                    if promo.summary and ("タイムセール" in promo.summary or "time sale" in promo.summary.lower()):
                        is_time_sale = True
                        break

            return (title, strike_price, current_price, discount_percentage, discount_amount, 
                    is_time_sale, image_url, features, True)
        else:
            return None, None, None, None, None, None, None, False
    except Exception as e:
        print(f"Amazon情報取得エラー: {e}")
        return None, None, None, None, None, None, None, False

def extract_asin(url):
    try:
        parsed_url = requests.get(url, allow_redirects=True, timeout=5).url
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

    checking_message = None
    try:
        checking_message = await message.channel.send("リンクを確認中です...🔍")

        for url in urls:
            asin = extract_asin(url)
            if not asin:
                await message.channel.send("ASINが取得できませんでした。❌")
                continue

            (title, strike_price, current_price, 
             discount_percentage, discount_amount, 
             is_time_sale, image_url, features, has_offer) = fetch_amazon_data(asin)

            if not (title and has_offer and current_price):
                await message.channel.send("商品情報を取得できませんでした。リンクが正しいか確認してください。")
                continue

            affiliate_url = f"https://www.amazon.co.jp/dp/{asin}/?tag={AMAZON_ASSOCIATE_TAG}"

            # 現在のUTC→JST
            now_utc = datetime.utcnow()
            jst = now_utc + timedelta(hours=9)
            time_str = jst.strftime("%Y/%m/%d %H:%M")

            # 価格表示部分
            price_line = ""
            # 定価があれば打ち消し線を入れる
            if strike_price:
                price_line += f"~~{strike_price}~~ → "

            price_line += current_price

            # 割引率と値引き額
            if discount_percentage and discount_percentage > 0 and discount_amount:
                # 「(XX%OFF)」と 「**¥YYY引き**」を表示
                off_str = f"({discount_percentage}%OFF)"
                discount_str = f"**¥{int(discount_amount):,}引き**"  # 3桁区切り
                if is_time_sale:
                    off_str = f"**{off_str} タイムセール中!**"
                price_line += f" {off_str} {discount_str}"

            # 時刻
            price_line += f" （{time_str}時点）"

            desc = f"**価格**: {price_line}\n"
            if features:
                bullet_points = "\n".join([f"- {f}" for f in features])
                desc += f"\n**特徴**:\n{bullet_points}\n"

            embed_color = discord.Color.orange() if is_time_sale else discord.Color.blue()
            embed = discord.Embed(
                title=title,
                url=affiliate_url,
                description=desc,
                color=embed_color
            )
            embed.set_thumbnail(url=image_url)

            await message.channel.send(embed=embed)

            # 元のメッセージの埋め込みを抑制する (ここを追加)
        await message.edit(suppress=True) #★

    except Exception as e:
        print(f"on_messageエラー: {e}")
    finally:
        if checking_message:
            await checking_message.delete()

if TOKEN:
    client.run(TOKEN)
else:
    print("TOKENが設定されていません。BOTは起動せず、Flaskサーバーのみ稼働します。")
