import os
import discord
import re
import requests
import json
import hmac
import hashlib
from datetime import datetime
from urllib.parse import quote, urlparse, parse_qs
from dotenv import load_dotenv
from flask import Flask
import threading

# ===============================
# 環境変数の読み込み
# ===============================
load_dotenv()
TOKEN = os.getenv('TOKEN')
AMAZON_ACCESS_KEY = os.getenv('AMAZON_ACCESS_KEY')
AMAZON_SECRET_KEY = os.getenv('AMAZON_SECRET_KEY')
AMAZON_ASSOCIATE_TAG = os.getenv('AMAZON_ASSOCIATE_TAG')

# 正規表現: Amazonリンクの検出 (短縮URL含む)
AMAZON_URL_REGEX = r"(https?://(?:www\.)?(?:amazon\.co\.jp|amzn\.asia|amzn\.to)/[\w\-/\?=&%\.]+)"

# ===============================
# AWS署名バージョン4の生成
# ===============================
def generate_aws_signature(payload):
    method = "POST"
    service = "ProductAdvertisingAPI"
    host = "webservices.amazon.co.jp"
    region = "us-west-2"
    endpoint = f"https://{host}/paapi5/getitems"
    content_type = "application/json; charset=UTF-8"
    
    # 日付情報
    now = datetime.utcnow()
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    date_stamp = now.strftime("%Y%m%d")

    # 必須ヘッダー
    headers = {
        "content-type": content_type,
        "host": host,
        "x-amz-date": amz_date,
    }

    # Canonicalリクエスト
    canonical_uri = "/paapi5/getitems"
    canonical_querystring = ""
    canonical_headers = ''.join([f"{k}:{v}\n" for k, v in headers.items()])
    signed_headers = ';'.join(headers.keys())
    payload_hash = hashlib.sha256(payload.encode('utf-8')).hexdigest()
    canonical_request = (f"{method}\n{canonical_uri}\n{canonical_querystring}\n"
                         f"{canonical_headers}\n{signed_headers}\n{payload_hash}")

    # String to Sign
    algorithm = "AWS4-HMAC-SHA256"
    credential_scope = f"{date_stamp}/{region}/{service}/aws4_request"
    string_to_sign = (f"{algorithm}\n{amz_date}\n{credential_scope}\n"
                      f"{hashlib.sha256(canonical_request.encode('utf-8')).hexdigest()}")

    # 署名の計算
    def sign(key, msg):
        return hmac.new(key, msg.encode('utf-8'), hashlib.sha256).digest()

    k_date = sign(("AWS4" + AMAZON_SECRET_KEY).encode('utf-8'), date_stamp)
    k_region = sign(k_date, region)
    k_service = sign(k_region, service)
    k_signing = sign(k_service, "aws4_request")
    signature = hmac.new(k_signing, string_to_sign.encode('utf-8'), hashlib.sha256).hexdigest()

    # Authorizationヘッダー
    authorization_header = (f"{algorithm} Credential={AMAZON_ACCESS_KEY}/{credential_scope}, "
                             f"SignedHeaders={signed_headers}, Signature={signature}")
    headers["Authorization"] = authorization_header

    return headers, endpoint

# ===============================
# Amazon PA-APIから商品情報を取得
# ===============================
def fetch_amazon_data(asin):
    try:
        payload = json.dumps({
            "ItemIds": [asin],
            "Resources": [
                "Images.Primary.Large",
                "ItemInfo.Title",
                "Offers.Listings.Price"
            ],
            "PartnerTag": AMAZON_ASSOCIATE_TAG,
            "PartnerType": "Associates",
            "Marketplace": "www.amazon.co.jp"
        })
        print(f"リクエストペイロード: {payload}")  # ペイロード内容を出力
        headers, endpoint = generate_aws_signature(payload)
        print(f"生成されたリクエストヘッダー: {headers}")  # ヘッダー内容を出力
        response = requests.post(endpoint, headers=headers, data=payload)
        print(f"APIレスポンスコード: {response.status_code}")  # ステータスコードを出力
        print(f"APIレスポンス内容: {response.text}")  # レスポンス内容を出力

        if response.status_code == 200:
            data = response.json()
            if "ItemsResult" in data and "Items" in data["ItemsResult"]:
                item = data["ItemsResult"]["Items"][0]
                title = item["ItemInfo"]["Title"]["DisplayValue"]
                price = item["Offers"]["Listings"][0]["Price"]["DisplayAmount"]
                image_url = item["Images"]["Primary"]["Large"]["URL"]
                return title, price, image_url
            else:
                print(f"レスポンス構造が予期しない形式です: {data}")  # 構造エラー時
        else:
            print(f"エラー応答: {response.text}")  # APIエラー時
    except Exception as e:
        print(f"Amazon情報取得エラー: {e}")
    return None, None, None

# ===============================
# ASINをURLから抽出する関数
# ===============================
def extract_asin(url):
    try:
        parsed_url = urlparse(url)
        print(f"解析されたURL: {parsed_url}")  # 解析されたURL情報
        if "amzn.asia" in parsed_url.netloc or "amzn.to" in parsed_url.netloc:
            asin = url.split("/")[-1]
            print(f"短縮URLから抽出されたASIN: {asin}")
            return asin
        elif "amazon.co.jp" in parsed_url.netloc:
            path_parts = parsed_url.path.split("/")
            for part in path_parts:
                if len(part) == 10 and part.isalnum():
                    print(f"完全URLから抽出されたASIN: {part}")
                    return part
        print("ASINが抽出できませんでした。")
        return None
    except Exception as e:
        print(f"ASIN抽出エラー: {e}")
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

    for url in urls:
        await message.channel.send("リンクを確認中です...🔍")
        asin = extract_asin(url)
        if not asin:
            await message.channel.send("ASINが取得できませんでした。❌")
            continue

        title, price, image_url = fetch_amazon_data(asin)
        if title and price and image_url:
            embed = discord.Embed(
                title=title,
                url=url,
                description=f"**価格**: {price}\n\n商品情報を整理しました！✨",
                color=discord.Color.blue()
            )
            embed.set_thumbnail(url=image_url)
            await message.channel.send(embed=embed)
        else:
            await message.channel.send("商品情報を取得できませんでした。リンクが正しいか確認してください。")

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

client.run(TOKEN)
