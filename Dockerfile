# ベースイメージ
FROM python:3.10

# 作業ディレクトリを設定
WORKDIR /app

# 必要ファイルをコピー
COPY requirements.txt requirements.txt
COPY bot.py bot.py
COPY paapi5-python-sdk /app/paapi5-python-sdk

# 必要ライブラリをインストール
RUN pip install --no-cache-dir -r requirements.txt

# PYTHONPATHを設定
ENV PYTHONPATH=/app/paapi5-python-sdk:/app

# ポート8000を公開（ヘルスチェック用）
EXPOSE 8000

# アプリケーション実行
CMD ["python", "bot.py"]
