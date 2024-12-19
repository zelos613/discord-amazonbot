# ベースイメージを指定
FROM python:3.9-slim

# 作業ディレクトリを設定
WORKDIR /app

# 必要なファイルをコンテナにコピー
COPY requirements.txt requirements.txt

# 必要なライブラリをインストール
RUN pip install --no-cache-dir -r requirements.txt

# アプリケーションコードをコピー
COPY . .

# エントリーポイントを指定
CMD ["python", "bot.py"]
