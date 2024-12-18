# ベースイメージ
FROM python:3.10

# 作業ディレクトリの設定
WORKDIR /app

# 必要なファイルをコンテナにコピー
COPY . /app

# 依存関係をインストール
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# ポート番号の指定（Koyebの仕様）
EXPOSE 8000

# Botの実行コマンド
CMD ["python", "bot.py"]
