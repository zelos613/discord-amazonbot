# Python3.10を使用した環境
FROM python:3.10

# 作業ディレクトリ設定
WORKDIR /app

# 必要ファイルをコピー
COPY requirements.txt requirements.txt
COPY bot.py bot.py

# 必要ライブラリをインストール
RUN pip install --no-cache-dir -r requirements.txt

# boto3を直接インストール（冗長防止：requirementsで追加済みだが確認用）
RUN pip install boto3

# ポート8000を公開（ヘルスチェック用）
EXPOSE 8000

# アプリケーション実行
CMD ["python", "bot.py"]
