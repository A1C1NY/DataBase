# 城市公共交通系统后端模板

本目录是依据仓库根目录 `规划.md` 创建的课程简化版 FastAPI 后端骨架。系统支持本地样例
导入和基础上游 API 获取，但不实现独立同步中心、定时采集、缓存和生产化基础设施。

第一次开始开发时，请先阅读 [`开发顺序.md`](开发顺序.md)，并按其中的逐文件清单推进。

## 启动准备

```bash
cp .env.example .env
source ../.database/bin/activate
# 当前开发机的 ROS 配置会注入 Python 3.10 系统包，进入项目环境后必须清除。
unset PYTHONPATH
python -m pip install -e '.[dev]'
alembic upgrade head
uvicorn app.main:app --reload
```

依赖以 `pyproject.toml` 为唯一清单：`dependencies` 是部署运行所需库，
`project.optional-dependencies.dev` 是测试、检查和本地开发工具。不要再手工维护一份内容
重复的 `requirements.txt`，以免版本范围逐渐不一致。

依赖分组如下：

- Web 与校验：FastAPI、Uvicorn、Pydantic Settings；
- 数据库：同步 SQLAlchemy、PyMySQL、Alembic；
- 数据解析与时间：Pydantic、tzdata；
- 外部 API：HTTPX；
- 安全：PyJWT、pwdlib + Argon2；
- 开发检查：pytest、Ruff、mypy。

## 目录职责

```text
app/api/           REST 路由和鉴权依赖
app/core/          环境配置、JWT/密码、日志、上海时区
app/db/            ORM Base、会话和事务基础设施
app/models/        计划书规定的 10 张表
app/schemas/       请求、响应及上游 DTO
app/services/      直接使用 Session 完成业务查询和事务
app/integrations/  双 API 客户端、DTO 和解析器
alembic/           数据库迁移
tests/             单元与集成测试
```

每个 Python 文件顶部的 `TODO` 注释说明该文件应完成的工作。完成一个模块后，应删除对应 TODO，并添加计划书 6.6 节要求的测试。

## 推荐实施顺序

1. 补全 ORM 字段、关系和 `alembic/versions` 首次迁移，校对 10 张表的外键、索引、检查约束。
2. 完成三个样例 JSON 的 DTO、解析器和离线导入测试。
3. 完成认证、站点、线路、实时信息、收藏与查询日志。
4. 完成简单认证、乘客核心接口、收藏和手动 API 调用。
5. 完成四类简单分析和管理员接口。

## 完成边界

- 时间统一使用 `Asia/Shanghai`，入库为上海本地 `DATETIME(3)`。
- 外部 ID 都是可空字符串；市政府 `stopId` 属于线路站序，不属于物理站点。
- 线路和站点仅逻辑停用；可选 API 字段保留 `NULL` 语义。
- 不新增 Vehicle 表，不引入 Redis、Celery、GIS 或微服务。
- 不实现 Repository 层、异步 Session、定时任务、缓存和并发锁。
- 密钥只放 `.env`，不得提交真实配置。
