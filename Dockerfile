# Dockerfile
FROM python:3.9-slim

# 作業ディレクトリの設定
WORKDIR /app

# 必要なパッケージをインストール
RUN apt-get update && apt-get install -y \
    gcc \
    libxml2 \
    libxml2-dev \
    libxslt1-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 依存関係をコピー
COPY requirements.txt .

# Pythonパッケージのインストール
RUN pip install --no-cache-dir -r requirements.txt

# SDKをプロジェクトにコピー
COPY paapi5_python_sdk ./paapi5_python_sdk

# ソースコードをコピー
COPY . .

# Botを起動
CMD ["python", "bot.py"]
