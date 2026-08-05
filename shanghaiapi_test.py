import requests
import json
from datetime import datetime

# -------- 配置 --------
API_URL = (
    "https://data.sh.gov.cn/interface/idmp-api/gateway/portal/"
    "society-dataset/v1/sod-p4pm95e968tfxhil41cotzxyn"
)
TOKEN = "aba7e87eedb378280660e0d9377f4d2f"

# -------- 请求参数 --------
payload = {
    "cityCode": "310100",
    "lon": "121.4941",
    "lat": "31.1611",
    "nearRadiusDistance": "10000",
    "coordinateType": "1",   # WGS-84
    "isGetStopArrive": "1",  # 获取到站信息
}

headers = {
    "Content-Type": "application/json",
    "token": TOKEN,
    "cache-control": "no-cache",
}

# -------- 调用 --------
def fetch_nearby_bus(payload: dict) -> dict:
    resp = requests.post(API_URL, headers=headers, json=payload, timeout=10)
    resp.raise_for_status()
    return resp.json()

# -------- 解析并打印 --------
def display_result(data: dict):
    if data.get("retCode") != 0:
        print(f"调用失败: {data.get('retMsg')}")
        return

    stops = data.get("nearByTrafficLineStop", [])
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 共找到 {len(stops)} 条线路-站点信息\n")

    for item in stops:
        print(f"线路: {item['lineName']}  站点: {item['stopName']}")
        type_map = {'1': '公交', '2': '地铁', '3': '轮渡'}
        print(f"  方向: {'上行' if item['upDown'] == 0 else '下行'}  "
              f"类型: {type_map.get(str(item['type']), '未知')}")

        # 实时到站信息
        sai = item.get("sai")
        if sai:
            print(f"  ▶ 最近车: {sai.get('currentLicensePlate', 'N/A')} "
                  f"距离 {sai.get('currentBusDistance')}m "
                  f"约 {sai.get('currentBusArriveTime')} 分钟到达 "
                  f"({sai.get('currentBusStopCount')} 站)"
                  f"  预计到站时间: {sai.get('currentBusArriveTimeStr', 'N/A')}"
                  f"  拥挤度: {sai.get('currentBusComfort', 'N/A')}")
                

        # 调度信息
        schedule = item.get("dispatchCarSchedule")
        if schedule:
            print(f"  📅 调度: {schedule.get('scheduleMsgDefault')}")

        print()

# -------- 主程序 --------
if __name__ == "__main__":
    try:
        result = fetch_nearby_bus(payload)
        # 保存原始 JSON 供数据库导入用
        with open("raw_result.json", "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print("原始数据已保存至 raw_result.json\n")
        display_result(result)
    except requests.RequestException as e:
        print(f"网络请求失败: {e}")