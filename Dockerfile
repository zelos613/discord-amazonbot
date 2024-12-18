# ベースイメージ
FROM python:3.10

# 作業ディレクトリの設定
WORKDIR /app

# 必要なファイルをコンテナにコピー
COPY . /app

# 依存関係をインストール
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# ポート番号の指定（Koyebのヘルスチェック用）
EXPOSE 8000

# ヘルスチェックサーバーとDiscord Botを起動する
CMD ["python", "-u", "bot.py"]
