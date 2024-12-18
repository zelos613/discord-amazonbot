import os
import discord
import re
import requests
import hashlib
import hmac
import datetime
import json
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from dotenv import load_dotenv

# ===============================
# 環境変数の読み込み
# ===============================
load_dotenv()
TOKEN = os.getenv('TOKEN')
AMAZON_ACCESS_KEY = os.getenv('AMAZON_ACCESS_KEY')
AMAZON_SECRET_KEY = os.getenv('AMAZON_SECRET_KEY')
AMAZON_ASSOCIATE_TAG = os.getenv('AMAZON_ASSOCIATE_TAG')

# Amazonリンクの正規表現
AMAZON_URL_REGEX = r"(https?://(?:www\.)?(?:amazon\.co\.jp|amzn\.asia)/[\w\-/\?=&%\.]+)"

# ===============================
# ヘルスチェック用HTTPサーバー
# ===============================
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'text/plain')
        self.end_headers()
        self.wfile.write(b'OK')

def run_health_check_server():
    server = HTTPServer(('0.0.0.0', 8000), HealthCheckHandler)
    print("Health check server is running on port 8000...")
    server.serve_forever()

# 別スレッドでHTTPサーバーを実行
threading.Thread(target=run_health_check_server, daemon=True).start()

# ===============================
# Amazon PA-API v5 リクエスト関数
# ===============================
def sign(key, msg):
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()

def get_signature_key(key, date_stamp, region, service):
    k_date = sign(("AWS4" + key).encode("utf-8"), date_stamp)
    k_region = sign(k_date, region)
    k_service = sign(k_region, service)
    k_signing = sign(k_service, "aws4_request")
    return k_signing

def fetch_amazon_data_v5(asin):
    endpoint = "webservices.amazon.co.jp"
    service = "ProductAdvertisingAPI"
    region = "us-east-1"
    host = "webservices.amazon.co.jp"
    uri = "/paapi5/getitems"

    now = datetime.datetime.utcnow()
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    date_stamp = now.strftime("%Y%m%d")

    # リクエストボディ
    payload = {
        "ItemIds": [asin],
        "PartnerTag": AMAZON_ASSOCIATE_TAG,
        "PartnerType": "Associates",
        "Marketplace": "www.amazon.co.jp",
        "Resources": ["Images.Primary.Large", "ItemInfo.Title", "Offers.Listings.Price"]
    }
    payload_json = json.dumps(payload)

    canonical_request = f"""POST
{uri}

content-type:application/json
host:{host}
x-amz-date:{amz_date}

content-type;host;x-amz-date
{hashlib.sha256(payload_json.encode('utf-8')).hexdigest()}"""

    string_to_sign = f"""AWS4-HMAC-SHA256
{amz_date}
{date_stamp}/{region}/{service}/aws4_request
{hashlib.sha256(canonical_request.encode('utf-8')).hexdigest()}"""

    signing_key = get_signature_key(AMAZON_SECRET_KEY, date_stamp, region, service)
    signature = hmac.new(signing_key, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()

    headers = {
        "Content-Type": "application/json",
        "Host": host,
        "X-Amz-Date": amz_date,
        "Authorization": f"AWS4-HMAC-SHA256 Credential={AMAZON_ACCESS_KEY}/{date_stamp}/{region}/{service}/aws4_request, SignedHeaders=content-type;host;x-amz-date, Signature={signature}"
    }

    response = requests.post(f"https://{host}{uri}", headers=headers, data=payload_json)
    if response.status_code == 200:
        data = response.json()
        try:
            item = data["ItemsResult"]["Items"][0]
            title = item["ItemInfo"]["Title"]["DisplayValue"]
            price = item["Offers"]["Listings"][0]["Price"]["DisplayAmount"]
            image_url = item["Images"]["Primary"]["Large"]["URL"]
            return title, price, image_url
        except Exception as e:
            print(f"データ解析エラー: {e}")
    print(f"Amazon APIリクエスト失敗: {response.status_code}")
    return None, None, None

# ===============================
# Discord Bot
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

    print(f"受信者: {message.author}, メッセージ: {message.content!r}")
    urls = re.findall(AMAZON_URL_REGEX, message.content)
    if not urls:
        return

    for url in urls:
        asin_match = re.search(r"/(?:dp|gp/product|d)/([A-Z0-9]{10})", url)
        if asin_match:
            asin = asin_match.group(1)
            title, price, image_url = fetch_amazon_data_v5(asin)
            if title and price and image_url:
                embed = discord.Embed(
                    title=title,
                    url=url,
                    description=f"**価格**: {price}",
                    color=discord.Color.green()
                )
                embed.set_thumbnail(url=image_url)
                embed.set_footer(text="Amazonでのお買い物をお楽しみください！")
                await message.channel.send(embed=embed)
            else:
                await message.channel.send("商品情報を取得できませんでした。")
        else:
            print("ASINが抽出されませんでした。")

client.run(TOKEN)
