import os
import re
import requests
import hmac
import hashlib
import datetime
import json
import discord
from dotenv import load_dotenv
from urllib.parse import urlencode

# 環境変数の読み込み
load_dotenv()
TOKEN = os.getenv('TOKEN')
AMAZON_ACCESS_KEY = os.getenv('AMAZON_ACCESS_KEY')
AMAZON_SECRET_KEY = os.getenv('AMAZON_SECRET_KEY')
AMAZON_ASSOCIATE_TAG = os.getenv('AMAZON_ASSOCIATE_TAG')

# 正規表現: Amazonリンクの検出
AMAZON_URL_REGEX = r"(https?://(?:www\.)?(?:amazon\.co\.jp|amzn\.to)/[\w\-/\?=&%\.]+)"

# AWS Signature Version 4 の署名生成
def sign(key, msg):
    return hmac.new(key, msg.encode('utf-8'), hashlib.sha256).digest()

def get_signature_key(key, date_stamp, region_name, service_name):
    k_date = sign(("AWS4" + key).encode('utf-8'), date_stamp)
    k_region = sign(k_date, region_name)
    k_service = sign(k_region, service_name)
    k_signing = sign(k_service, "aws4_request")
    return k_signing

# PA-APIリクエストの生成
def create_paapi_request(asin):
    service = "ProductAdvertisingAPI"
    host = "webservices.amazon.co.jp"
    region = "us-west-2"
    endpoint = "https://webservices.amazon.co.jp/paapi5/getitems"

    payload = {
        "PartnerTag": AMAZON_ASSOCIATE_TAG,
        "PartnerType": "Associates",
        "Marketplace": "www.amazon.co.jp",
        "ItemIds": [asin],
        "Resources": [
            "Images.Primary.Large",
            "ItemInfo.Title",
            "Offers.Listings.Price"
        ]
    }

    amz_date = datetime.datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
    date_stamp = datetime.datetime.utcnow().strftime('%Y%m%d')

    # Canonical Requestの生成
    canonical_uri = "/paapi5/getitems"
    canonical_querystring = ""
    canonical_headers = f"content-type:application/json\nhost:{host}\nx-amz-date:{amz_date}\n"
    signed_headers = "content-type;host;x-amz-date"
    payload_hash = hashlib.sha256(json.dumps(payload).encode('utf-8')).hexdigest()
    canonical_request = f"POST\n{canonical_uri}\n{canonical_querystring}\n{canonical_headers}\n{signed_headers}\n{payload_hash}"

    # String to Signの生成
    algorithm = "AWS4-HMAC-SHA256"
    credential_scope = f"{date_stamp}/{region}/{service}/aws4_request"
    string_to_sign = f"{algorithm}\n{amz_date}\n{credential_scope}\n{hashlib.sha256(canonical_request.encode('utf-8')).hexdigest()}"

    # 署名の生成
    signing_key = get_signature_key(AMAZON_SECRET_KEY, date_stamp, region, service)
    signature = hmac.new(signing_key, string_to_sign.encode('utf-8'), hashlib.sha256).hexdigest()

    # Authorization ヘッダーの作成
    authorization_header = (
        f"{algorithm} Credential={AMAZON_ACCESS_KEY}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )

    # ヘッダーの追加
    headers = {
        "Content-Type": "application/json",
        "Host": host,
        "X-Amz-Date": amz_date,
        "Authorization": authorization_header
    }

    return endpoint, headers, payload

# Amazon APIから商品情報取得
def fetch_amazon_data(asin):
    try:
        endpoint, headers, payload = create_paapi_request(asin)
        response = requests.post(endpoint, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
        print(f"API Response: {data}")

        items = data.get("ItemsResult", {}).get("Items", [])
        if items:
            item = items[0]
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
    print(f"Botがログインしました: {bot.user}")

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    urls = re.findall(AMAZON_URL_REGEX, message.content)
    if not urls:
        return

    for url in urls:
        await message.channel.send("🔍 リンクを確認中です...")
        asin = re.search(r"(?:dp|gp/product|d)/([A-Z0-9]{10})", url)
        if asin:
            asin = asin.group(1)
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
                await message.channel.send("❌ 商品情報を取得できませんでした。")
        else:
            await message.channel.send("❌ ASINが取得できませんでした。")

bot.run(TOKEN)
