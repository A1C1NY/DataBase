"""历史数据维护。

TODO: arrival/dispatch 保留 90 天，query_logs 180 天，成功 ingestion_runs 180 天；失败和
partial 至少一年。每批最多删除 1000 行并提交，调度明细依赖父表级联删除。
"""

