import os
import discord
import re
import requests
from datetime import datetime, timedelta
from paapi5_python_sdk.api.default_api import DefaultApi
from paapi5_python_sdk.models.get_items_request import GetItemsRequest
from paapi5_python_sdk.models.partner_type import PartnerType

# 環境変数
TOKEN = os.getenv('TOKEN')
AMAZON_ACCESS_KEY = os.getenv('AMAZON_ACCESS_KEY')
AMAZON_SECRET_KEY = os.getenv('AMAZON_SECRET_KEY')
AMAZON_ASSOCIATE_TAG = os.getenv('AMAZON_ASSOCIATE_TAG')

# Amazon URL 検出用正規表現
AMAZON_URL_REGEX = r"(https?://(?:www\.)?(?:amazon\.co\.jp|amzn\.asia|amzn\.to)/\S+)"

def fetch_amazon_data(asin):
    try:
        client = DefaultApi(
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
        resp = client.get_items(request)
        items = resp.items_result.items if resp.items_result else []
        if not items:
            return None, None, None, None, None, None, None, False

        item = items[0]
        title = getattr(item.item_info.title, 'display_value', '商品名なし')
        features = getattr(item.item_info.features, 'display_values', [])[:3]
        image_url = getattr(item.images.primary.large, 'url', '')

        listings = item.offers.listings if item.offers else []
        if not listings:
            return title, None, None, None, None, False, image_url, features

        listing = listings[0]
        current = listing.price.display_amount if listing.price else None
        saving = listing.saving_basis.display_amount if listing.saving_basis else None

        discount_pct = None
        discount_amt = None
        if saving and current:
            try:
                orig = float(saving.replace('¥','').replace(',',''))
                now = float(current.replace('¥','').replace(',',''))
                if orig > now:
                    discount_pct = int(round((orig - now) / orig * 100))
                    discount_amt = orig - now
            except:
                pass

        is_time_sale = any(
            promo.summary and ('タイムセール' in promo.summary or 'time sale' in promo.summary.lower())
            for promo in getattr(listing, 'promotions', [])
        )

        return title, saving, current, discount_pct, discount_amt, is_time_sale, image_url, features, True

    except Exception as e:
        print(f"Amazon情報取得エラー: {e}")
        return None, None, None, None, None, None, None, False


def extract_asin(url):
    try:
        final_url = requests.get(url, allow_redirects=True, timeout=5).url
        m = re.search(r"/dp/([A-Z0-9]{10})", final_url)
        return m.group(1) if m else None
    except Exception as e:
        print(f"ASIN抽出エラー: {e}")
        return None

# Discord Bot セットアップ
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

    checking = await message.channel.send("リンクを確認中です...🔍")
    try:
        for url in urls:
            asin = extract_asin(url)
            if not asin:
                await message.channel.send("ASINが取得できませんでした。❌")
                continue

            data = fetch_amazon_data(asin)
            if not data or not data[8]:
                await message.channel.send("商品情報を取得できませんでした。リンクが正しいか確認してください。")
                continue

            title, saving, current, pct, amt, on_sale, img, feats, _ = data
            affiliate = f"https://www.amazon.co.jp/dp/{asin}/?tag={AMAZON_ASSOCIATE_TAG}"

            now = datetime.utcnow() + timedelta(hours=9)
            time_str = now.strftime("%Y/%m/%d %H:%M")

            price_line = f"{current}"
            if saving:
                price_line = f"~~{saving}~~ → {price_line}"
            if pct and amt:
                off = f"({pct}%OFF)"
                disc = f"**¥{int(amt):,}引き**"
                if on_sale:
                    off = f"**{off} タイムセール中!**"
                price_line += f" {off} {disc}"
            price_line += f" （{time_str}時点）"

            desc = f"**価格**: {price_line}\n"
            if feats:
                desc += "\n**特徴**:\n" + '\n'.join(f"- {f}" for f in feats)

            embed = discord.Embed(
                title=title,
                url=affiliate,
                description=desc,
                color=discord.Color.orange() if on_sale else discord.Color.blue()
            )
            embed.set_thumbnail(url=img)

            await message.channel.send(embed=embed)

        # 元の埋め込みを抑制
        await message.edit(suppress=True)

    finally:
        await checking.delete()

# エントリーポイント
if __name__ == "__main__":
    if TOKEN:
        client.run(TOKEN)
    else:
        print("TOKENが設定されていません。BOTを起動できません。")
```
