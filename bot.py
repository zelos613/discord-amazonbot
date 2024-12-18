import os
import discord
import re
import requests
import xml.etree.ElementTree as ET
import hashlib
import hmac
import datetime
import base64
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from dotenv import load_dotenv
from bs4 import BeautifulSoup  # HTML解析用ライブラリ

# ===============================
# 環境変数の読み込み
# ===============================
load_dotenv()
TOKEN = os.getenv('TOKEN')
AMAZON_ACCESS_KEY = os.getenv('AMAZON_ACCESS_KEY')
AMAZON_SECRET_KEY = os.getenv('AMAZON_SECRET_KEY')
AMAZON_ASSOCIATE_TAG = os.getenv('AMAZON_ASSOCIATE_TAG')
BITLY_API_TOKEN = os.getenv('BITLY_API_TOKEN')

# 正規表現: Amazonリンクの検出 (短縮URL含む)
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
# Amazon署名付きリクエストの生成
# ===============================
def amazon_signed_request(asin):
    endpoint = "webservices.amazon.co.jp"
    uri = "/onca/xml"
    params = {
        "Service": "AWSECommerceService",
        "Operation": "ItemLookup",
        "AWSAccessKeyId": AMAZON_ACCESS_KEY,
        "AssociateTag": AMAZON_ASSOCIATE_TAG,
        "ItemId": asin,
        "ResponseGroup": "Images,ItemAttributes,Offers",
        "Timestamp": datetime.datetime.utcnow().isoformat()
    }
    sorted_params = "&".join([f"{key}={requests.utils.quote(str(value))}" for key, value in sorted(params.items())])
    string_to_sign = f"GET\n{endpoint}\n{uri}\n{sorted_params}"
    signature = base64.b64encode(hmac.new(AMAZON_SECRET_KEY.encode(), string_to_sign.encode(), hashlib.sha256).digest()).decode()
    return f"https://{endpoint}{uri}?{sorted_params}&Signature={signature}"

# 短縮URLを展開してASINを取得
def extract_asin(url):
    try:
        # 短縮URLを展開
        print(f"元のURL: {url}")
        response = requests.get(url, allow_redirects=True)
        expanded_url = response.url
        print(f"展開されたURL: {expanded_url}")

        # ASIN抽出
        match = re.search(r"/(?:dp|gp/product|d)/([A-Z0-9]{10})", expanded_url)
        if match:
            print(f"抽出されたASIN: {match.group(1)}")
            return match.group(1)
        else:
            print("ASINが見つかりませんでした。")
    except Exception as e:
        print(f"URL展開中にエラー: {e}")
    return None


# Amazon PA-APIから商品情報を取得
def fetch_amazon_data(asin):
    try:
        url = amazon_signed_request(asin)
        print(f"Amazon APIリクエストURL: {url}")
        response = requests.get(url)

        print(f"Amazon APIステータスコード: {response.status_code}")
        print(f"Amazon APIレスポンス内容: {response.text}")

        if response.status_code == 200:
            root = ET.fromstring(response.content)
            ns = {"ns": "http://webservices.amazon.com/AWSECommerceService/2011-08-01"}
            title = root.find(".//ns:Title", ns)
            price = root.find(".//ns:FormattedPrice", ns)
            image_url = root.find(".//ns:LargeImage/ns:URL", ns)

            # 各値がNoneでないかチェック
            title_text = title.text if title is not None else "N/A"
            price_text = price.text if price is not None else "N/A"
            image_url_text = image_url.text if image_url is not None else "N/A"

            print(f"取得した商品タイトル: {title_text}")
            print(f"取得した価格: {price_text}")
            print(f"取得した画像URL: {image_url_text}")

            return title_text, price_text, image_url_text
        else:
            print(f"Amazon APIリクエスト失敗: {response.status_code}")
    except Exception as e:
        print(f"エラー: {e}")
    return None, None, None


# BitlyでURLを短縮
def shorten_url(long_url):
    try:
        headers = {"Authorization": f"Bearer {BITLY_API_TOKEN}"}
        data = {"long_url": long_url}
        response = requests.post("https://api-ssl.bitly.com/v4/shorten", json=data, headers=headers)
        if response.status_code == 200:
            return response.json().get("link")
        return long_url
    except Exception as e:
        print(f"Bitlyエラー: {e}")
        return long_url

# ===============================
# Discord Bot本体
# ===============================
intents = discord.Intents.default()
intents.message_content = True  # メッセージ内容取得を有効化
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f'Botがログインしました: {client.user}')

@client.event
async def on_message(message):
    if message.author.bot:
        return  # Bot自身のメッセージは無視

    print(f"受信者: {message.author}, メッセージ: {message.content!r}")

    if not message.content:  # メッセージが空の場合
        return

    sanitized_content = message.content.replace("\n", " ")  # 改行をスペースに置き換え
    urls = re.findall(AMAZON_URL_REGEX, sanitized_content)

    print(f"検出されたURL: {urls}")

    if not urls:
        print("Amazonリンクが検出されませんでした。")
        return

    for url in urls:
        asin = extract_asin(url)
        print(f"処理するURL: {url}, 抽出されたASIN: {asin}")

        if not asin:
            await message.channel.send("ASINが抽出できませんでした。")
            continue

        title, price, image_url = fetch_amazon_data(asin)
        print(f"取得した商品情報: タイトル={title}, 価格={price}, 画像URL={image_url}")

        if title and price and image_url:
            associate_link = f"{url}?tag={AMAZON_ASSOCIATE_TAG}"
            short_url = shorten_url(associate_link)
            print(f"アソシエイトリンク: {short_url}")

            embed = discord.Embed(
                title=title,
                url=short_url,
                description=f"**価格**: {price}",
                color=discord.Color.blue()
            )
            embed.set_thumbnail(url=image_url)
            embed.set_footer(text="こちらの商品情報をお届けしました！")

            await message.channel.send(embed=embed)
        else:
            print("商品情報が取得できませんでした。")
            await message.channel.send("商品情報を取得できませんでした。")


# Botを起動
client.run(TOKEN)
