import requests
from urllib.parse import quote

API_KEY = "2af1515dc2ef0e283aa1e086c3cbc14a"
STOP_NAME = "云台路杨南路"
CITY = "310000"

# 注意：bus/stopname 接口不支持 extensions=all 参数，keywords 用 UTF-8 编码即可
base_url = "https://restapi.amap.com/v3/bus/stopname"
full_url = f"{base_url}?key={API_KEY}&keywords={quote(STOP_NAME, encoding='utf-8')}&city={CITY}&output=json"
print(f"🔍 URL: {full_url}\n")

r = requests.get(full_url)
print(f"返回数据: {r.text}")