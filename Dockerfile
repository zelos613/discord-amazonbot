# ベースイメージとしてPython 3.9を使用
FROM python:3.9-slim

# 作業ディレクトリを設定
WORKDIR /app

# 必要なPythonパッケージをインストールするためのファイルをコピー
COPY requirements.txt .

# パッケージをインストール
RUN pip install --no-cache-dir -r requirements.txt

# アプリケーションコードをコンテナにコピー
COPY . .

# ポート8000を公開（HTTPサーバー用）
EXPOSE 8000

# コンテナ起動時に実行するコマンドを指定
CMD ["python", "bot.py"]
