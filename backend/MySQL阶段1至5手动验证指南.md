# MySQL 阶段 1-5 手动验证指南

本文用于验证已经完成的阶段 1-5 实现。以下操作会执行 Alembic 降级和重建，只能使用新建的专用测试数据库，禁止使用已有业务库。

## 1. 准备专用测试数据库

确认 MySQL 版本：

```bash
mysql --version
```

要求 MySQL 8.0。使用有建库权限的账号登录：

```bash
mysql -u root -p
```

在 MySQL 中执行，密码请换成你自己的测试密码：

```sql
DROP DATABASE IF EXISTS amap_transit_test;
CREATE DATABASE amap_transit_test
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_0900_ai_ci;

CREATE USER IF NOT EXISTS 'amap_test'@'127.0.0.1'
  IDENTIFIED BY '114514';
ALTER USER 'amap_test'@'127.0.0.1'
  IDENTIFIED BY '114514';
GRANT ALL PRIVILEGES ON amap_transit_test.* TO 'amap_test'@'127.0.0.1';
FLUSH PRIVILEGES;
```

`DROP DATABASE` 只允许针对这里明确写出的 `amap_transit_test`。

## 2. 配置后端环境

进入后端并启用现有虚拟环境：

```bash
cd /home/alcony/桌面/design/DataBase/backend
source ../.database/bin/activate
unset PYTHONPATH
cp -n .env.example .env
```

编辑 `.env`，至少修改：

```text
TRANSIT_APP_ENV=test
TRANSIT_DATABASE_URL=mysql+pymysql://amap_test:replace_with_test_password@127.0.0.1:3306/amap_transit_test?charset=utf8mb4
TRANSIT_JWT_SECRET=replace-with-a-random-string-of-at-least-32-characters
```

`.env` 已被 `.gitignore` 忽略，不要把真实密码或 Key 写入 `.env.example`。

## 3. 阶段 1：连接和事务验证

执行：

```bash
python -c "from sqlalchemy import text; from app.db.session import get_session_factory; s=get_session_factory()(); print(s.scalar(text('SELECT 1'))); s.rollback(); s.close()"
```

预期输出 `1`。

验证事务回滚：

```bash
python -c "from sqlalchemy import text; from app.db.session import get_session_factory; s=get_session_factory()(); s.execute(text('SELECT 1')); s.rollback(); print('rollback ok'); s.close()"
```

预期输出 `rollback ok`。

## 4. 阶段 2-3：迁移和表结构验证

首次升级：

```bash
alembic upgrade head
alembic current
```

预期当前版本：

```text
20260805_01 (head)
```

查看 9 张业务表：

```bash
mysql -h 127.0.0.1 -u amap_test -p amap_transit_test -e "SHOW TABLES;"
```

除 `alembic_version` 外必须存在：

```text
users
bus_stops
bus_lines
bus_line_stops
bus_line_path_points
favorite_stops
favorite_lines
stop_view_events
ingestion_runs
```

检查关键 DDL：

```bash
mysql -h 127.0.0.1 -u amap_test -p amap_transit_test -e "SHOW CREATE TABLE bus_stops\G"
mysql -h 127.0.0.1 -u amap_test -p amap_transit_test -e "SHOW CREATE TABLE bus_lines\G"
mysql -h 127.0.0.1 -u amap_test -p amap_transit_test -e "SHOW CREATE TABLE bus_line_stops\G"
mysql -h 127.0.0.1 -u amap_test -p amap_transit_test -e "SHOW CREATE TABLE stop_view_events\G"
```

人工确认：

- 主键为 `BIGINT UNSIGNED`；
- 坐标为 `DECIMAL(10,7)`；
- `polyline_raw` 为 `MEDIUMTEXT`；
- 时间为 `DATETIME(3)`；
- 引擎为 InnoDB，字符集为 `utf8mb4`；
- `bus_line_stops` 只有 `(line_id, sequence_no)` 唯一约束，没有 `(line_id, stop_id)` 唯一约束；
- 收藏的用户外键是 `ON DELETE CASCADE`；
- 访问事件的用户外键是 `ON DELETE SET NULL`；
- 导入运行相关外键是 `ON DELETE RESTRICT`。

在尚未导入样例前验证降级和再次升级：

```bash
alembic downgrade base
alembic upgrade head
alembic current
```

三条命令必须全部成功。

## 5. 阶段 4：无需 MySQL 的验证结果

这一部分已经自动完成。需要复查时运行：

```bash
pytest tests/unit/test_amap_stop_parser.py \
       tests/unit/test_amap_line_parser.py \
       tests/unit/test_amap_client.py \
       tests/unit/test_coord.py -q
```

预期 18 个测试通过，测试过程不会访问互联网。

## 6. 阶段 5：首次样例导入

确保迁移位于 head：

```bash
alembic upgrade head
python -m app.commands.import_samples
```

命令默认依次导入：

1. `bus_stop_by_name.json`；
2. `bus_stop_raw_gaode.json`；
3. `bus_line_raw_gaode.json`。

预期输出三个运行结果，状态应为 `success`，并各自包含 `ingestion_run_id`。

执行汇总查询：

```bash
mysql -h 127.0.0.1 -u amap_test -p amap_transit_test -e "
SELECT COUNT(*) AS stop_count FROM bus_stops;
SELECT COUNT(*) AS line_count FROM bus_lines;
SELECT COUNT(*) AS line_stop_count FROM bus_line_stops;
SELECT COUNT(*) AS path_point_count FROM bus_line_path_points;
SELECT COUNT(*) AS run_count FROM ingestion_runs;
SELECT amap_line_id, line_name, start_stop_name, end_stop_name
FROM bus_lines ORDER BY amap_line_id;
"
```

使用当前三个样例时，预期：

| 项目 | 数量 |
|---|---:|
| `bus_stops` | 36 |
| `bus_lines` | 2 |
| `bus_line_stops` | 58 |
| `bus_line_path_points` | 743 |
| `ingestion_runs` | 3 |

两条线路 ID 应为 `310100015143`、`310100015144`。

检查两个方向站序：

```bash
mysql -h 127.0.0.1 -u amap_test -p amap_transit_test -e "
SELECT l.amap_line_id,
       COUNT(ls.id) AS stop_count,
       MIN(ls.sequence_no) AS first_sequence,
       MAX(ls.sequence_no) AS last_sequence
FROM bus_lines AS l
JOIN bus_line_stops AS ls ON ls.line_id = l.id
GROUP BY l.id, l.amap_line_id
ORDER BY l.amap_line_id;
"
```

每个方向必须为 29 站，序号范围为 1-29。

## 7. 重复导入幂等验证

再次执行：

```bash
python -m app.commands.import_samples
```

再次运行上一节的汇总查询。预期：

- `bus_stops` 仍为 36；
- `bus_lines` 仍为 2；
- `bus_line_stops` 仍为 58；
- `bus_line_path_points` 仍为 743；
- `ingestion_runs` 增加到 6，因为每次上游响应都保留独立审计记录。

检查重复站序和轨迹：

```bash
mysql -h 127.0.0.1 -u amap_test -p amap_transit_test -e "
SELECT line_id, sequence_no, COUNT(*) AS duplicate_count
FROM bus_line_stops
GROUP BY line_id, sequence_no
HAVING COUNT(*) > 1;

SELECT line_id, sequence_no, COUNT(*) AS duplicate_count
FROM bus_line_path_points
GROUP BY line_id, sequence_no
HAVING COUNT(*) > 1;
"
```

两个查询都必须返回空结果。

## 8. 一键运行 MySQL 专用 pytest

测试必须指向名称明显包含 `test` 的专用数据库：

直接复用前面已经通过 `SELECT 1` 验证的 `.env` 数据库 URL，避免再次手工填写密码：

```bash
export TRANSIT_TEST_DATABASE_URL="$(python -c 'from app.core.config import get_settings; print(get_settings().database_url)')"
pytest -m mysql tests/mysql/test_stage_1_to_5_mysql.py -q
```

不要把示例中的 `replace_with_test_password` 原样放入环境变量。

预期 2 个测试通过。测试会先对专用测试库执行 `downgrade base` 和
`upgrade head`，然后覆盖精确数量幂等、多候选冲突不合并，以及线路写入中途异常时
业务数据完整回滚、失败运行记录仍保留。测试结束后会保留测试数据，便于失败后检查。

## 9. 把结果发回给我

请提供以下输出：

1. `alembic current`；
2. 9 张表的 `SHOW TABLES`；
3. 首次导入后的五个数量；
4. 第二次导入后的五个数量；
5. `pytest -m mysql ...` 的最终结果。

若任一步失败，请同时提供完整错误文本，并停止后续步骤，避免用错误结构继续导入。
