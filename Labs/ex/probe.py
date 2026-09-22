# probe_api.py
import requests

BASE_URL = "http://172.10.0.2:8080"

print(f"[*] 正在探測 {BASE_URL} 的 API 路由...")

try:
    resp = requests.get(f"{BASE_URL}/openapi.json", timeout=5)
    if resp.status_code == 200:
        spec = resp.json()
        paths = spec.get("paths", {})
        print("\n[+] 成功讀取 OpenAPI 規格！伺服器支援的端點與方法如下：")
        for path, methods in paths.items():
            for method, details in methods.items():
                print(f"  - {method.upper()} {path} (摘要: {details.get('summary', '無')})")
    else:
        print(f"[-] 無法獲取 openapi.json (HTTP {resp.status_code})")
except Exception as e:
    print(f"[-] 連線探測失敗: {e}")

# 測試幾種常見路徑的 OPTIONS/GET/POST
test_paths = [
    "/v1/chat/completions",
    "/v1/chat/completions/",
    "/api/chat",
    "/chat",
    "/docs"
]

print("\n[*] 常用路徑探測：")
for p in test_paths:
    url = f"{BASE_URL}{p}"
    try:
        r_get = requests.get(url, timeout=3)
        r_post = requests.post(url, json={}, timeout=3)
        print(f"  {p:<25} -> GET: {r_get.status_code} | POST: {r_post.status_code}")
    except Exception as err:
        print(f"  {p:<25} -> 連線異常: {err}")