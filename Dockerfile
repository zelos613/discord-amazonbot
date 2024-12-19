# ベースイメージを指定
FROM python:3.10

# 作業ディレクトリを設定
WORKDIR /app

# 必要ファイルをコピー
COPY requirements.txt requirements.txt
COPY bot.py bot.py

# 必要ライブラリをインストール
RUN pip install --no-cache-dir -r requirements.txt

# アプリケーションを実行
CMD ["python", "bot.py"]
