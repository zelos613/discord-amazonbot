# ベースイメージの指定
FROM python:3.9-slim

# 作業ディレクトリを設定
WORKDIR /app

# 必要なファイルをコンテナ内にコピー
COPY requirements.txt requirements.txt
COPY . .

# 依存ライブラリのインストール
RUN pip install --no-cache-dir -r requirements.txt

# Flaskのポートを公開
EXPOSE 8000

# Botの起動
CMD ["python", "your_script_name.py"]
