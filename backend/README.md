# 城市公共交通系统后端模板

本目录是依据仓库根目录 `规划.md` 创建的 FastAPI 后端骨架。当前仅完成目录、模块边界和开发任务标注，不代表业务功能已经实现。建议按“数据库 -> 样例解析 -> 核心 API -> 分析管理”的顺序推进。

## 启动准备

```bash
cp .env.example .env
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
alembic upgrade head
uvicorn app.main:app --reload
```

## 目录职责

```text
app/api/           REST 路由、鉴权依赖，不写复杂 SQL
app/core/          环境配置、JWT/密码、日志、上海时区
app/db/            ORM Base、会话和事务基础设施
app/models/        计划书规定的 10 张表
app/schemas/       请求、响应及上游 DTO
app/repositories/  参数化数据库查询和聚合 SQL
app/services/      业务编排、权限之外的业务规则
app/integrations/  高德和上海市政府 API 客户端及解析器
app/jobs/          定时采集、清理和异常运行修复
alembic/           数据库迁移
tests/             单元与集成测试
```

每个 Python 文件顶部的 `TODO` 注释说明该文件应完成的工作。完成一个模块后，应删除对应 TODO，并添加计划书 6.6 节要求的测试。

## 推荐实施顺序

1. 补全 ORM 字段、关系和 `alembic/versions` 首次迁移，校对 10 张表的外键、索引、检查约束。
2. 完成三个样例 JSON 的 DTO、解析器和离线导入测试。
3. 完成认证、站点、线路、实时信息、收藏与查询日志。
4. 接入上游 API、采集运行记录、60 秒缓存和 APScheduler。
5. 完成四类分析、管理员接口、清理命令与 `EXPLAIN` 校对。

## 完成边界

- 时间统一使用 `Asia/Shanghai`，入库为上海本地 `DATETIME(3)`。
- 外部 ID 都是可空字符串；市政府 `stopId` 属于线路站序，不属于物理站点。
- 线路和站点仅逻辑停用；可选 API 字段保留 `NULL` 语义。
- 不新增 Vehicle 表，不引入 Redis、Celery、GIS 或微服务。
- 密钥只放 `.env`，不得提交真实配置。
