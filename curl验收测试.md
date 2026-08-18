# 公交站点与线路 API：按需求的 curl 验收测试

本文针对正在运行的 FastAPI 服务，使用 `curl` 模拟前端行为。默认服务地址为 `http://127.0.0.1:8000`，可按实际情况覆盖 `BASE_URL`。

## 0. 前置条件与变量

```bash
cd backend
# 已配置 TRANSIT_DATABASE_URL、TRANSIT_JWT_SECRET（至少 32 字符）以及可选的 TRANSIT_AMAP_API_KEY
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

另开终端执行：

```bash
export BASE_URL=http://127.0.0.1:8000
export CITY=021
curl -sS "$BASE_URL/health"
# 预期：{"status":"ok"}

export PASS_USER="passenger_$(date +%s)"
export PASS_PWD='passenger-password-123'
export ANALYST_USER="analyst_$(date +%s)"
export ADMIN_USER="admin_$(date +%s)"
```

响应中的 ID 使用 `jq` 保存（没有 jq 时手工替换后续变量）：

```bash
export PASS_TOKEN=$(curl -sS -X POST "$BASE_URL/api/auth/register" -H 'Content-Type: application/json' \
  -d "{\"username\":\"$PASS_USER\",\"password\":\"$PASS_PWD\"}" | jq -r .id >/dev/null; \
  curl -sS -X POST "$BASE_URL/api/auth/login" -H 'Content-Type: application/x-www-form-urlencoded' \
  --data-urlencode "username=$PASS_USER" --data-urlencode "password=$PASS_PWD" | jq -r .access_token)
export PASS_AUTH="Authorization: Bearer $PASS_TOKEN"
```

注册预期 HTTP `201`，返回 `id/username/role=passenger/is_active=true`，不返回密码；登录预期 HTTP `200`，返回 `access_token` 和 `token_type=bearer`。

## 1. 普通用户（passenger）

### 1.1 查看当前账号、退出

```bash
curl -sS -H "$PASS_AUTH" "$BASE_URL/api/auth/me"
```

预期 HTTP `200`，用户名和角色为当前账号。当前版本无服务端 logout 路由；前端退出应删除本地 `PASS_TOKEN`/清空 Authorization，再访问受保护接口应得到 HTTP `401`（`INVALID_CREDENTIALS`）。

### 1.2 站点搜索（数据库优先，高德补入）

```bash
curl -sS --get "$BASE_URL/api/stops/search" --data-urlencode 'q=人民广场' --data "city_code=$CITY" --data 'limit=5'


# 站点强制高德刷新
curl -sS --get "$BASE_URL/api/stops/search" \
  --data-urlencode 'q=人民广场' \
  --data-urlencode "city_code=$CITY" \
  --data-urlencode 'limit=20' \
  --data-urlencode 'refresh=true'
```

### 线路搜索

```bash
# 线路强制高德刷新
curl -sS --get "$BASE_URL/api/lines/search" \
  --data-urlencode 'q=986' \
  --data-urlencode "city_code=$CITY" \
  --data-urlencode 'limit=20' \
  --data-urlencode 'refresh=true'
```

预期 HTTP `200`，返回 `items`（站点名、坐标、`coordinate_system=GCJ02` 等）。命中本地时 `data_source=database`、`ingestion_run_id=null`；本地无有效结果且高德成功时 `data_source=amap` 且有 `ingestion_run_id`，随后重复同一请求应优先返回 `database`。高德空结果为 HTTP `404`、`detail.code=NOT_FOUND_AFTER_AMAP`；Key/网络/超时为 `503 AMAP_UNAVAILABLE`；高德业务错误为 `502 AMAP_BUSINESS_ERROR`。

```bash
export STOP_ID=41   # 用上一步 items[0].id 替换
```

### 1.3 站点详情、途经线路和访问事件

```bash
curl -sS -H "$PASS_AUTH" "$BASE_URL/api/stops/$STOP_ID?entry_point=direct"
curl -sS "$BASE_URL/api/stops/$STOP_ID/lines"
```

详情返回 `stop`、`data_source`；每次打开详情写入一次站点详情访问事件。可分别用 `entry_point=search/line_map/favorite/direct` 模拟入口。`/lines` 返回线路数组、`partial` 和可能的 `unresolved_summaries`。不存在站点预期 `404 NOT_FOUND`。注意：当前 `StopItem` 没有 `updated_at` 或记录级来源字段，因此“最后更新时间”和站点本身的数据来源验收会失败，见第 5 节。

### 1.4 线路详情、站序和地图

```bash
export LINE_ID=8  # 用站点线路响应中的 lines[0].id 替换
curl -sS "$BASE_URL/api/lines/$LINE_ID"
curl -sS "$BASE_URL/api/lines/$LINE_ID/stops"
curl -sS "$BASE_URL/api/lines/$LINE_ID/map"


响应中的 lines 是空数组，说明该站点的线路关系尚未补齐。需要使用 unresolved_summaries 中的 amap_line_id，调用高德线路补齐接口。
export AMAP_LINE_ID=310100025693

curl -sS "$BASE_URL/api/lines/by-amap/$AMAP_LINE_ID?refresh=true"
```

预期线路详情包含方向起终点、首末班、环线标记 `loop_flag`、公司和票价等；`/stops` 的 `stops[].sequence_no` 从小到大为完整经停顺序；`/map` 返回 `geojson` 线路地图。不存在线路为 `404 NOT_FOUND`。当前没有明确 `line_type` 字段，若“线路类型”要求独立字段，此项验收会失败。

### 1.5 地图点击站点/未补齐线路

```bash
export AMAP_LINE_ID='替换为 unresolved_summaries[].amap_line_id'
curl -sS "$BASE_URL/api/lines/by-amap/$AMAP_LINE_ID?refresh=true"

export AMAP_LINE_ID='310100025709'
curl -sS "$BASE_URL/api/lines/by-amap/$AMAP_LINE_ID?refresh=true"
```

预期高德补齐成功返回 HTTP `200`、`data_source=amap`、`ingestion_run_id`，之后再次请求可为 `database`；高德未查到返回 `404 NOT_FOUND_AFTER_AMAP`，响应消息明确“高德未查到该数据”（或等价中文提示），上游失败返回 `503/502`。地图/定位失败不影响上述站名搜索和列表接口（可在断网或浏览器拒绝定位时重复验证）。

### 1.6 收藏、取消收藏、分页

```bash
curl -i -X PUT -H "$PASS_AUTH" "$BASE_URL/api/me/favorite-stops/$STOP_ID"
curl -sS -H "$PASS_AUTH" "$BASE_URL/api/me/favorite-stops?page=1&page_size=20"
curl -i -X DELETE -H "$PASS_AUTH" "$BASE_URL/api/me/favorite-stops/$STOP_ID"
curl -i -X PUT -H "$PASS_AUTH" "$BASE_URL/api/me/favorite-lines/$LINE_ID"
curl -sS -H "$PASS_AUTH" "$BASE_URL/api/me/favorite-lines?page=1&page_size=20"
curl -i -X DELETE -H "$PASS_AUTH" "$BASE_URL/api/me/favorite-lines/$LINE_ID"
```

添加/删除预期 HTTP `204` 且重复添加幂等；列表返回 `page/page_size/total/items`，停用对象不出现在列表；无效 ID 为 `404 NOT_FOUND`。

## 2. 分析师（analyst）

先由管理员创建分析师（见 3.1），再登录：

```bash
export ANALYST_TOKEN=$(curl -sS -X POST "$BASE_URL/api/auth/login" -H 'Content-Type: application/x-www-form-urlencoded' \
  --data-urlencode "username=$ANALYST_USER" --data-urlencode 'password=analyst-password-123' | jq -r .access_token)
export ANALYST_AUTH="Authorization: Bearer $ANALYST_TOKEN"
```

### 2.1 站点/线路密度热力图

```bash
curl -sS --get -H "$ANALYST_AUTH" "$BASE_URL/api/analytics/heatmaps/stops" \
  --data-urlencode 'bbox=121.40,31.15,121.55,31.30' --data 'grid_size_m=300'
curl -sS --get -H "$ANALYST_AUTH" "$BASE_URL/api/analytics/heatmaps/lines" \
  --data-urlencode 'bbox=121.40,31.15,121.55,31.30' --data 'grid_size_m=300'
```

预期 HTTP `200`、`data_source=database`、`metric` 分别为 `stop_density`/`line_density`，`geojson` 为网格要素；同一线路多个轨迹点在一个网格只计一次。非法 bbox 预期 `422 INVALID_BBOX`。

### 2.2 站点详情访问次数排行（仅 passenger）

```bash
curl -sS --get -H "$ANALYST_AUTH" "$BASE_URL/api/analytics/stops/popularity" \
  --data-urlencode 'start_at=2026-01-01T00:00:00+08:00' --data-urlencode 'end_at=2026-12-31T23:59:59+08:00' --data 'limit=20'
```

预期 `metric_name` 必须为“站点详情访问次数”，条目含 `detail_view_count`、`unique_user_count`，按访问次数降序；只统计 `passenger`，匿名不混入排名。

### 2.3 单站点时间分布

```bash
curl -sS --get -H "$ANALYST_AUTH" "$BASE_URL/api/analytics/stops/$STOP_ID/view-distribution" \
  --data-urlencode 'start_at=2026-01-01T00:00:00+08:00' --data-urlencode 'end_at=2026-12-31T23:59:59+08:00' \
  --data 'bucket=hour' --data 'actor_scope=passenger'
curl -sS --get -H "$ANALYST_AUTH" "$BASE_URL/api/analytics/stops/$STOP_ID/view-distribution" \
  --data-urlencode 'start_at=2026-01-01T00:00:00+08:00' --data-urlencode 'end_at=2026-12-31T23:59:59+08:00' \
  --data 'bucket=day' --data 'actor_scope=all'
curl -sS --get -H "$ANALYST_AUTH" "$BASE_URL/api/analytics/stops/$STOP_ID/view-distribution" \
  --data-urlencode 'start_at=2026-01-01T00:00:00+08:00' --data-urlencode 'end_at=2026-12-31T23:59:59+08:00' \
  --data 'bucket=weekday_hour' --data 'actor_scope=all'
```

`hour` 应返回 0-23 小时桶（上海本地时间）；`day` 返回日期桶；`weekday_hour` 返回星期/小时桶。`actor_scope=passenger` 只含普通用户；当前 `all` 会合并所有角色，不能把 `anonymous` 独立标出，因此该细项验收失败。非法时间范围为 `422 INVALID_TIME_RANGE`。

### 2.4 导入运行记录

```bash
curl -sS -H "$ANALYST_AUTH" "$BASE_URL/api/admin/ingestion-runs?page=1&page_size=20"
curl -sS -H "$ANALYST_AUTH" "$BASE_URL/api/admin/ingestion-runs/1"
```

列表/详情应包含 endpoint、trigger_type、request_keyword、成功/失败计数、状态和错误摘要 `error_message`。

## 3. 管理员（admin）

以下假设已有首个管理员账号（通过数据库初始化或部署脚本创建）。先登录并保存 `ADMIN_AUTH`：

```bash
export ADMIN_TOKEN=$(curl -sS -X POST "$BASE_URL/api/auth/login" -H 'Content-Type: application/x-www-form-urlencoded' \
  --data-urlencode "username=$ADMIN_USER" --data-urlencode 'password=admin-password-123' | jq -r .access_token)
export ADMIN_AUTH="Authorization: Bearer $ADMIN_TOKEN"
```

### 3.1 创建、启用、停用账号和修改角色

```bash
export ADMIN_USER=bootstrap_admin
export ADMIN_PASSWORD='admin-password-123'

curl -sS -X POST "$BASE_URL/api/auth/register" \
  -H 'Content-Type: application/json' \
  -d "{\"username\":\"$ADMIN_USER\",\"password\":\"$ADMIN_PASSWORD\"}"

cd backend

python - <<'PY'
from sqlalchemy import select
from app.db.session import get_session_factory
from app.models.account import User

username = "bootstrap_admin"

with get_session_factory()() as session:
    user = session.scalar(select(User).where(User.username == username))
    if user is None:
        raise SystemExit(f"用户不存在：{username}")

    user.role = "admin"
    user.is_active = True
    session.commit()
    print(f"管理员初始化完成：id={user.id}, username={user.username}")
PY

export ADMIN_TOKEN=$(curl -sS -X POST "$BASE_URL/api/auth/login" \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  --data-urlencode "username=$ADMIN_USER" \
  --data-urlencode "password=$ADMIN_PASSWORD" |
  jq -r '.access_token')

export ADMIN_AUTH="Authorization: Bearer $ADMIN_TOKEN"
```

```bash
curl -sS -X POST "$BASE_URL/api/admin/users" -H "$ADMIN_AUTH" -H 'Content-Type: application/json' \
  -d "{\"username\":\"$ANALYST_USER\",\"password\":\"analyst-password-123\",\"role\":\"analyst\",\"is_active\":true}"
export USER_ID=2   # 替换为返回的 id
curl -sS -H "$ADMIN_AUTH" "$BASE_URL/api/admin/users?page=1&page_size=20"
curl -sS -X PATCH "$BASE_URL/api/admin/users/$USER_ID" -H "$ADMIN_AUTH" -H 'Content-Type: application/json' -d '{"role":"passenger"}'
curl -sS -X PATCH "$BASE_URL/api/admin/users/$USER_ID" -H "$ADMIN_AUTH" -H 'Content-Type: application/json' -d '{"is_active":false}'
curl -sS -X PATCH "$BASE_URL/api/admin/users/$USER_ID" -H "$ADMIN_AUTH" -H 'Content-Type: application/json' -d '{"is_active":true,"role":"analyst"}'
```

预期创建 `201`；列表分页字段齐全；角色/启停修改 `200`。管理员不能停用或降级自己，最后一个启用管理员不能被停用，预期 `4xx` 且返回明确业务错误码。

### 3.2 线路、站点逻辑启停

```bash
curl -sS -X PATCH "$BASE_URL/api/admin/stops/$STOP_ID/status" -H "$ADMIN_AUTH" -H 'Content-Type: application/json' -d '{"is_active":false}'
curl -sS -X PATCH "$BASE_URL/api/admin/lines/$LINE_ID/status" -H "$ADMIN_AUTH" -H 'Content-Type: application/json' -d '{"is_active":false}'
curl -sS -X PATCH "$BASE_URL/api/admin/stops/$STOP_ID/status" -H "$ADMIN_AUTH" -H 'Content-Type: application/json' -d '{"is_active":true}'
curl -sS -X PATCH "$BASE_URL/api/admin/lines/$LINE_ID/status" -H "$ADMIN_AUTH" -H 'Content-Type: application/json' -d '{"is_active":true}'
```

每次预期 `200` 返回 `{id,is_active}`；对象仍保留（逻辑停用，不物理删除），停用期间不能新增收藏且不出现在收藏列表。

## 4. 权限和故障降级验收

```bash
curl -i "$BASE_URL/api/analytics/heatmaps/stops?bbox=121.4,31.1,121.5,31.2"                 # 无 token
curl -i -H "$PASS_AUTH" "$BASE_URL/api/analytics/heatmaps/stops?bbox=121.4,31.1,121.5,31.2" # passenger
curl -i -H "$ANALYST_AUTH" -X PATCH "$BASE_URL/api/admin/stops/$STOP_ID/status" -H 'Content-Type: application/json' -d '{"is_active":false}'
```

三条分别预期 `401`、`403`、`403`，错误码为 `INVALID_CREDENTIALS` 或 `FORBIDDEN`。在浏览器拒绝定位、地图资源加载失败或高德不可用时，重复执行 1.2 的站名搜索及收藏分页接口，确认仍能返回数据库结果；不要把 `503/502` 上游错误显示为空列表。

## 5. 与需求的已知差异

- 当前 API 没有服务端 `/logout`，退出由客户端删除 token 完成。
- 站点详情的 `StopItem` 没有最后更新时间，也没有记录级来源；顶层 `data_source` 只能说明本次响应来自数据库还是高德补数。
- 线路响应没有独立的“线路类型”字段，仅有 `loop_flag`、公司等属性。
- 访问分布只支持 `actor_scope=passenger/all`；`all` 合并所有角色，不能将匿名访问独立标记展示。
- API 不返回预计到站、车辆距离、拥挤度、无障碍车辆或计划发车等上海专属字段。
- 未实现 CSV 导出、预测模型、真实客流推断和自由 SQL；分析指标固定为“站点详情访问次数”。
