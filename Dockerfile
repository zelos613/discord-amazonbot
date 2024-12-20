# ベースイメージの指定
FROM python:3.9-slim

# 作業ディレクトリを設定
WORKDIR /app

# 必要なファイルをコンテナ内にコピー
COPY requirements.txt requirements.txt
COPY ./paapi5_python_sdk /app/paapi5_python_sdk  # SDKフォルダをコピー
COPY . .

# 依存ライブラリのインストール
RUN pip install --no-cache-dir -r requirements.txt

# PYTHONPATHを設定
ENV PYTHONPATH="/app"

# Flaskのポートを公開
EXPOSE 8000

# Botの起動
CMD ["python", "bot.py"]
