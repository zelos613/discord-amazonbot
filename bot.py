import requests

# プロキシ設定
PROXY_HTTP = "http://211.128.96.206:80"  # あなたが選択したプロキシ
PROXY_HTTPS = "http://211.128.96.206:80"
proxies = {
    "http": PROXY_HTTP,
    "https": PROXY_HTTPS
}

# テストURL
test_url = "http://httpbin.org/ip"

try:
    print("Sending request via proxy...")
    response = requests.get(test_url, proxies=proxies, timeout=10)
    print("Response from proxy:")
    print(response.json())  # プロキシを通じたIPが表示されるはずです
except Exception as e:
    print(f"Error during proxy test: {e}")
