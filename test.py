import requests
import json
from urllib.parse import quote

# ============================================
# 配置区（你只需要改这里！）
# ============================================
API_KEY = "2af1515dc2ef0e283aa1e086c3cbc14a"  # 替换成你的Key
CITY = "上海"                # 查询城市
LINE_NAME = "980路"          # 公交线路名称
# ============================================

def get_bus_line_info(api_key, keywords, city):
    """
    调用高德公交线路查询API
    """
    # API文档：https://lbs.amap.com/api/webservice/guide/api/busline
    base_url = "https://restapi.amap.com/v3/bus/linename"
    
    params = {
        'key': api_key,
        'keywords': keywords,
        'city': city,
        'extensions': 'all',      # 返回详细信息（包含站点坐标）
        'output': 'json'
    }
    
    try:
        response = requests.get(base_url, params=params, timeout=10)
        response.raise_for_status()
        return response.json()
    
    except requests.exceptions.RequestException as e:
        print(f"❌ API请求失败: {e}")
        return None


def parse_bus_line_data(data):
    """
    解析返回的公交线路数据
    """
    if not data or data.get('status') != '1':
        error_msg = data.get('info', '未知错误') if data else '无返回数据'
        print(f"❌ API返回错误: {error_msg}")
        return
    
    print(f"\n✅ 查询成功！共找到 {data.get('count', 0)} 条线路\n")
    
    for idx, line in enumerate(data.get('buslines', []), 1):
        print(f"{'='*60}")
        print(f"线路 {idx}: {line.get('name')}")
        print(f"起终点: {line.get('start_stop')} → {line.get('end_stop')}")
        print(f"方向: {line.get('type')} ({line.get('loop')})")
        print(f"总站数: {line.get('total_price')} 站")
        print(f"票价: {line.get('total_price')} 元")
        
        # 打印站点信息
        print(f"\n【站点顺序】(前5站示例):")
        via_stops = line.get('via_stops', [])
        for i, stop in enumerate(via_stops[:5], 1):
            name = stop.get('name', '未知站')
            location = stop.get('location', '未知坐标')
            print(f"  {i}. {name} - 坐标: {location}")
        
        if len(via_stops) > 5:
            print(f"  ... 还有 {len(via_stops) - 5} 个站点")
        
        print()


def main():
    print("="*60)
    print(f"🔍 正在查询 {CITY} 的 {LINE_NAME} 公交线路...")
    print("="*60)
    
    # 调用API
    result = get_bus_line_info(API_KEY, LINE_NAME, CITY)
    
    if result:
        # 解析并打印结果
        parse_bus_line_data(result)
        
        # 保存原始JSON（方便你查看完整结构）
        with open('bus_line_raw.json', 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"\n💾 原始数据已保存到: bus_line_raw.json")


if __name__ == "__main__":
    main()