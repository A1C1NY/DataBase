"""高德上游 DTO。

TODO: 按 bus_line_raw_gaode.json 与 bus_stop_by_name.json 定义宽容 Pydantic 模型；外部 ID
保持字符串，location 拆经纬度，HHmm 转 TIME；嵌套线路摘要不能冒充完整站序。
"""

