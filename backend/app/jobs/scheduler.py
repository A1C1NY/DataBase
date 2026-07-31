"""固定坐标的基础定时采集。

TODO: 使用 APScheduler BackgroundScheduler，每隔配置的分钟数调用一次上海 API，并复用
refresh/ingestion service 保存到站与调度快照。只有 ENABLE_SCHEDULER=true 且经纬度完整
时启动；失败只记录简短日志，等待下一轮。课程版仅支持单 Uvicorn 进程，不实现缓存、
自动重试、互斥锁、多进程防重和历史清理。
"""

