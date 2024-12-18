# Python3.10を使用した環境
FROM python:3.10

# 作業ディレクトリ設定
WORKDIR /app

# 必要ファイルをコピー
COPY requirements.txt requirements.txt
COPY bot.py bot.py

# 必要ライブラリをインストール
RUN pip install --no-cache-dir -r requirements.txt

# ポート8000を公開（ヘルスチェック用）
EXPOSE 8000

# アプリケーション実行
CMD ["python", "bot.py"]
