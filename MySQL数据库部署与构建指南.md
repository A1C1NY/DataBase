# MySQL 数据库部署与构建指南

## 1. 指南用途

本文档用于独立完成“城市公共交通实时状态查询与分析系统”的 MySQL 数据库部署、建库、建表和基础验证。完成本文档后，应得到一个可供后续 FastAPI 后端连接的 MySQL 8 数据库。

数据库最终包含以下 10 张表：

1. `users`
2. `lines`
3. `stops`
4. `line_routes`
5. `favorite_stops`
6. `query_logs`
7. `ingestion_runs`
8. `arrival_infos`
9. `dispatch_schedules`
10. `dispatch_cars`

原报告中的 `Vehicle` 表不再建立。无障碍状态保存在到站快照和发车明细中。市政府 API 的 `stopId` 随线路变化，因此保存在 `line_routes.shanghai_stop_id`，不放在 `stops` 中。

## 2. 完成标准

全部步骤完成后，应满足：

- [ ] MySQL 8 服务正常运行；
- [ ] 数据库 `transit_system` 使用 `utf8mb4`；
- [ ] 10 张表全部存在；
- [ ] 主键、唯一约束、外键、删除策略和索引与本指南一致；
- [ ] 中文站名、提示文本和车牌可以正确读写；
- [ ] 同一市政府线路 ID 的 0/1 两个方向可以同时保存；
- [ ] 重复快照会被唯一约束拒绝；
- [ ] 删除用户时收藏被删除、查询日志的用户 ID 被置空；
- [ ] 线路和站点保留历史引用，不能被误删；
- [ ] 已保存数据库连接参数，供后端阶段使用。

## 3. 软件准备

### 3.1 推荐方式：Ubuntu 22.04 原生安装

如果数据库准备部署在 Ubuntu 22.04 服务器上，推荐直接通过 Ubuntu 软件源安装 MySQL Server。这样不依赖 Docker，服务可由 `systemd` 自动启动，也方便后续把 FastAPI 部署在同一台服务器。

先确认系统：

```bash
lsb_release -a
uname -m
```

系统应为 Ubuntu 22.04，架构通常为 `x86_64` 或 `aarch64`。后续命令需要具备 `sudo` 权限。

### 3.2 可选方式：Docker Desktop

Windows 下推荐使用 Docker Desktop。优点是版本一致、不会污染系统环境、数据库文件通过 Docker volume 持久化。

在 PowerShell 中检查 Docker：

```powershell
docker --version
docker info
```

两个命令都应成功。若 `docker info` 失败，先启动 Docker Desktop。

### 3.3 可选方式：其他本机 MySQL 8

如果已经安装 MySQL Server 8 和 MySQL Client，可直接检查：

```powershell
mysql --version
```

本机安装方式需确保：

- MySQL Server 主版本为 8；
- 记得 root 密码；
- MySQL 服务已经启动；
- `mysql` 命令已加入 `PATH`。

后续建表 SQL 对 Docker 和本机 MySQL 完全相同。

## 4. 启动 MySQL

### 4.1 在 Ubuntu 22.04 安装并启动

更新软件索引并安装服务器与客户端：

```bash
sudo apt update
sudo apt install -y mysql-server mysql-client
```

启动服务并设置开机自动启动：

```bash
sudo systemctl enable --now mysql
sudo systemctl status mysql --no-pager
```

状态应为 `active (running)`。检查版本：

```bash
mysql --version
sudo mysql -e "SELECT VERSION();"
```

设置服务器时区。若该服务器本来就应使用上海时区，可执行：

```bash
sudo timedatectl set-timezone Asia/Shanghai
timedatectl
```

编辑 MySQL 配置：

```bash
sudo nano /etc/mysql/mysql.conf.d/mysqld.cnf
```

在已有的 `[mysqld]` 段内增加或确认以下配置，不要创建第二个 `[mysqld]` 段：

```ini
character-set-server = utf8mb4
collation-server = utf8mb4_0900_ai_ci
default-time-zone = '+08:00'
bind-address = 127.0.0.1
```

`bind-address = 127.0.0.1` 表示只允许本机连接，适合数据库和后端部署在同一台 Ubuntu 服务器的方案。保存后检查配置并重启：

```bash
sudo mysqld --validate-config
sudo systemctl restart mysql
sudo systemctl status mysql --no-pager
```

Ubuntu 默认通常允许系统 root 通过 Unix socket 管理 MySQL，因此使用以下命令进入，无需给数据库 root 开放远程密码登录：

```bash
sudo mysql
```

进入后提示符应为 `mysql>`。

可选执行 MySQL 安全初始化：

```bash
sudo mysql_secure_installation
```

课程服务器至少应禁用匿名账户和测试数据库。不要为了远程管理而开放 root 登录。

### 4.2 使用 Docker 启动

先为数据库数据创建持久化 volume：

```powershell
docker volume create transit-mysql-data
```

设置一个仅对当前 PowerShell 会话有效的 root 密码。请替换示例值，不要使用真实项目密码以外的公共弱密码：

```powershell
$env:TRANSIT_MYSQL_ROOT_PASSWORD = "请替换为强密码"
```

启动 MySQL 8.0 容器：

```powershell
docker run --name transit-mysql `
  -e MYSQL_ROOT_PASSWORD=$env:TRANSIT_MYSQL_ROOT_PASSWORD `
  -e TZ=Asia/Shanghai `
  -p 3306:3306 `
  -v transit-mysql-data:/var/lib/mysql `
  -d mysql:8.0 `
  --character-set-server=utf8mb4 `
  --collation-server=utf8mb4_0900_ai_ci
```

检查容器：

```powershell
docker ps --filter "name=transit-mysql"
docker logs transit-mysql --tail 30
```

日志出现 `ready for connections` 后继续。首次初始化通常需要几十秒。

以后启停数据库使用：

```powershell
docker stop transit-mysql
docker start transit-mysql
```

不要重复执行 `docker run` 创建同名容器。

### 4.3 连接 Docker 中的 MySQL

```powershell
docker exec -it transit-mysql mysql -uroot -p
```

随后输入第 4.2 节设置的 root 密码。使用交互提示可以避免特殊字符在命令行中被错误解释。进入后提示符应变为：

```text
mysql>
```

### 4.4 连接其他本机 MySQL

```powershell
mysql -h 127.0.0.1 -P 3306 -uroot -p
```

随后交互输入 root 密码。

## 5. 创建数据库和应用账户

以下命令在 `mysql>` 中执行。先确认版本和时区：

```sql
SELECT VERSION();
SELECT @@global.time_zone, @@session.time_zone, NOW(3);
```

创建数据库：

```sql
CREATE DATABASE IF NOT EXISTS transit_system
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_0900_ai_ci;
```

创建后端专用账户。请把示例密码替换为新的强密码：

```sql
CREATE USER IF NOT EXISTS 'transit_app'@'%'
  IDENTIFIED BY '114514';

ALTER USER 'transit_app'@'%'
  IDENTIFIED BY '114514';

GRANT SELECT, INSERT, UPDATE, DELETE,
      CREATE, ALTER, INDEX, DROP, REFERENCES
ON transit_system.*
TO 'transit_app'@'%';

FLUSH PRIVILEGES;
```

说明：

- `root` 只用于数据库管理，不提供给 FastAPI；
- `transit_app` 是数据库账户，与业务表 `users` 中的乘客/分析师/管理员不是同一种用户；
- 开发阶段授予了迁移所需的 DDL 权限；正式部署后可为运行时另建一个只有增删改查权限的账户；
- 密码不得写入 Git 仓库，后续放入后端 `.env`。

检查数据库：

```sql
SHOW CREATE DATABASE transit_system;
SHOW GRANTS FOR 'transit_app'@'%';
```

## 6. 创建全部表

在同一个 `mysql>` 会话执行以下完整 SQL。若某条语句失败，应停止，先解决错误，不要跳过后继续。

```sql
USE transit_system;

SET NAMES utf8mb4;
SET time_zone = '+08:00';

CREATE TABLE users (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    username VARCHAR(64) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role ENUM('passenger', 'analyst', 'admin') NOT NULL
        DEFAULT 'passenger',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    updated_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3)
        ON UPDATE CURRENT_TIMESTAMP(3),
    PRIMARY KEY (id),
    UNIQUE KEY uq_users_username (username)
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `lines` (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    line_name VARCHAR(100) NOT NULL,
    direction TINYINT UNSIGNED NOT NULL,
    line_type TINYINT UNSIGNED NULL,
    shanghai_line_id VARCHAR(32) NULL,
    amap_line_id VARCHAR(32) NULL,
    first_departure_time TIME NULL,
    last_departure_time TIME NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    updated_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3)
        ON UPDATE CURRENT_TIMESTAMP(3),
    PRIMARY KEY (id),
    UNIQUE KEY uq_lines_amap_id (amap_line_id),
    UNIQUE KEY uq_lines_shanghai_direction
        (shanghai_line_id, direction),
    KEY idx_lines_name_active (line_name, is_active),
    CONSTRAINT chk_lines_direction CHECK (direction IN (0, 1)),
    CONSTRAINT chk_lines_type CHECK (
        line_type IS NULL OR line_type IN (1, 2, 3)
    )
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE stops (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    stop_name VARCHAR(150) NOT NULL,
    amap_stop_id VARCHAR(32) NULL,
    longitude DECIMAL(10,7) NOT NULL,
    latitude DECIMAL(10,7) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    updated_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3)
        ON UPDATE CURRENT_TIMESTAMP(3),
    PRIMARY KEY (id),
    UNIQUE KEY uq_stops_amap_id (amap_stop_id),
    KEY idx_stops_location (longitude, latitude),
    KEY idx_stops_name_active (stop_name, is_active),
    CONSTRAINT chk_stops_longitude CHECK (
        longitude BETWEEN -180 AND 180
    ),
    CONSTRAINT chk_stops_latitude CHECK (
        latitude BETWEEN -90 AND 90
    )
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE line_routes (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    line_id BIGINT UNSIGNED NOT NULL,
    stop_id BIGINT UNSIGNED NOT NULL,
    sequence_no SMALLINT UNSIGNED NOT NULL,
    shanghai_stop_id VARCHAR(32) NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_line_routes_line_sequence
        (line_id, sequence_no),
    UNIQUE KEY uq_line_routes_shanghai_stop
        (line_id, shanghai_stop_id),
    KEY idx_line_routes_stop (stop_id),
    KEY idx_line_routes_line_stop (line_id, stop_id),
    CONSTRAINT fk_line_routes_line
        FOREIGN KEY (line_id) REFERENCES `lines` (id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT fk_line_routes_stop
        FOREIGN KEY (stop_id) REFERENCES stops (id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT chk_line_routes_sequence CHECK (sequence_no >= 1)
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE favorite_stops (
    user_id BIGINT UNSIGNED NOT NULL,
    stop_id BIGINT UNSIGNED NOT NULL,
    created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    PRIMARY KEY (user_id, stop_id),
    KEY idx_favorite_stops_stop (stop_id),
    CONSTRAINT fk_favorite_stops_user
        FOREIGN KEY (user_id) REFERENCES users (id)
        ON UPDATE RESTRICT ON DELETE CASCADE,
    CONSTRAINT fk_favorite_stops_stop
        FOREIGN KEY (stop_id) REFERENCES stops (id)
        ON UPDATE RESTRICT ON DELETE RESTRICT
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE query_logs (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    user_id BIGINT UNSIGNED NULL,
    stop_id BIGINT UNSIGNED NOT NULL,
    queried_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    PRIMARY KEY (id),
    KEY idx_query_logs_stop_time (stop_id, queried_at),
    KEY idx_query_logs_user_time (user_id, queried_at),
    KEY idx_query_logs_time (queried_at),
    CONSTRAINT fk_query_logs_user
        FOREIGN KEY (user_id) REFERENCES users (id)
        ON UPDATE RESTRICT ON DELETE SET NULL,
    CONSTRAINT fk_query_logs_stop
        FOREIGN KEY (stop_id) REFERENCES stops (id)
        ON UPDATE RESTRICT ON DELETE RESTRICT
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE ingestion_runs (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    source ENUM('shanghai', 'amap') NOT NULL,
    task_type VARCHAR(50) NOT NULL,
    trigger_type ENUM('scheduled', 'manual', 'user_request') NOT NULL,
    request_key VARCHAR(255) NULL,
    started_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    finished_at DATETIME(3) NULL,
    status ENUM('running', 'success', 'partial', 'failed') NOT NULL
        DEFAULT 'running',
    received_count INT UNSIGNED NOT NULL DEFAULT 0,
    inserted_count INT UNSIGNED NOT NULL DEFAULT 0,
    updated_count INT UNSIGNED NOT NULL DEFAULT 0,
    skipped_count INT UNSIGNED NOT NULL DEFAULT 0,
    failed_count INT UNSIGNED NOT NULL DEFAULT 0,
    error_message TEXT NULL,
    PRIMARY KEY (id),
    KEY idx_ingestion_runs_status_started (status, started_at),
    KEY idx_ingestion_runs_source_task_started
        (source, task_type, started_at),
    KEY idx_ingestion_runs_started (started_at)
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE arrival_infos (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    ingestion_run_id BIGINT UNSIGNED NOT NULL,
    line_id BIGINT UNSIGNED NOT NULL,
    stop_id BIGINT UNSIGNED NOT NULL,
    source_up_down TINYINT UNSIGNED NULL,
    collected_at DATETIME(3) NOT NULL,
    current_bus_distance_m INT UNSIGNED NULL,
    current_bus_arrival_min INT UNSIGNED NULL,
    current_bus_comfort TINYINT UNSIGNED NULL,
    current_bus_stop_count SMALLINT UNSIGNED NULL,
    current_license_plate VARCHAR(64) NULL,
    current_barrier_free BOOLEAN NULL,
    next_bus_distance_m INT UNSIGNED NULL,
    next_bus_arrival_min INT UNSIGNED NULL,
    next_bus_stop_count SMALLINT UNSIGNED NULL,
    next_license_plate VARCHAR(64) NULL,
    next_barrier_free BOOLEAN NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_arrival_run_line_stop
        (ingestion_run_id, line_id, stop_id),
    KEY idx_arrival_realtime
        (line_id, stop_id, collected_at),
    KEY idx_arrival_stop_time (stop_id, collected_at DESC),
    KEY idx_arrival_line_time (line_id, collected_at),
    KEY idx_arrival_time (collected_at),
    CONSTRAINT fk_arrival_ingestion_run
        FOREIGN KEY (ingestion_run_id) REFERENCES ingestion_runs (id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT fk_arrival_line
        FOREIGN KEY (line_id) REFERENCES `lines` (id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT fk_arrival_stop
        FOREIGN KEY (stop_id) REFERENCES stops (id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT chk_arrival_source_direction CHECK (
        source_up_down IS NULL OR source_up_down IN (0, 1)
    ),
    CONSTRAINT chk_arrival_comfort CHECK (
        current_bus_comfort IS NULL
        OR current_bus_comfort IN (0, 1, 2, 3)
    )
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE dispatch_schedules (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    ingestion_run_id BIGINT UNSIGNED NOT NULL,
    line_id BIGINT UNSIGNED NOT NULL,
    collected_at DATETIME(3) NOT NULL,
    schedule_code SMALLINT NULL,
    message_default VARCHAR(255) NULL,
    message_short VARCHAR(255) NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_dispatch_schedule_run_line
        (ingestion_run_id, line_id),
    KEY idx_dispatch_schedule_line_time
        (line_id, collected_at),
    KEY idx_dispatch_schedule_time (collected_at),
    CONSTRAINT fk_dispatch_schedule_ingestion_run
        FOREIGN KEY (ingestion_run_id) REFERENCES ingestion_runs (id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT fk_dispatch_schedule_line
        FOREIGN KEY (line_id) REFERENCES `lines` (id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT chk_dispatch_schedule_code CHECK (
        schedule_code IS NULL OR schedule_code IN (-1, 0, 1)
    )
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE dispatch_cars (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    schedule_id BIGINT UNSIGNED NOT NULL,
    sequence_no TINYINT UNSIGNED NOT NULL,
    vehicle_text VARCHAR(64) NULL,
    is_barrier_free BOOLEAN NULL,
    planned_departure_at DATETIME(3) NULL,
    countdown_text VARCHAR(64) NULL,
    countdown_seconds INT UNSIGNED NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_dispatch_cars_schedule_sequence
        (schedule_id, sequence_no),
    KEY idx_dispatch_cars_departure (planned_departure_at),
    CONSTRAINT fk_dispatch_cars_schedule
        FOREIGN KEY (schedule_id) REFERENCES dispatch_schedules (id)
        ON UPDATE RESTRICT ON DELETE CASCADE,
    CONSTRAINT chk_dispatch_cars_sequence CHECK (sequence_no >= 1)
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_0900_ai_ci;
```

预期结果是每条 `CREATE TABLE` 均显示：

```text
Query OK, 0 rows affected
```

如果中途断开，可以重新进入 MySQL，执行 `USE transit_system;`，再从失败的表开始。已经成功建立的表再次执行会报“表已存在”，不要因此删除整个数据库。

## 7. 验证数据库结构

### 7.1 验证表数量

```sql
USE transit_system;
SHOW TABLES;

SELECT COUNT(*) AS table_count
FROM information_schema.tables
WHERE table_schema = 'transit_system'
  AND table_type = 'BASE TABLE';
```

`table_count` 必须为 `10`。

### 7.2 验证字符集

```sql
SELECT table_name, engine, table_collation
FROM information_schema.tables
WHERE table_schema = 'transit_system'
ORDER BY table_name;
```

所有表应使用 `InnoDB` 和 `utf8mb4_0900_ai_ci`。

### 7.3 验证外键

```sql
SELECT table_name,
       constraint_name,
       referenced_table_name,
       delete_rule,
       update_rule
FROM information_schema.referential_constraints
WHERE constraint_schema = 'transit_system'
ORDER BY table_name, constraint_name;
```

重点检查：

- `favorite_stops.user_id` 为 `ON DELETE CASCADE`；
- `query_logs.user_id` 为 `ON DELETE SET NULL`；
- `dispatch_cars.schedule_id` 为 `ON DELETE CASCADE`；
- 线路、站点、快照和采集运行关联为 `ON DELETE RESTRICT`。

### 7.4 验证索引

```sql
SHOW INDEX FROM stops;
SHOW INDEX FROM line_routes;
SHOW INDEX FROM arrival_infos;
SHOW INDEX FROM dispatch_schedules;
SHOW INDEX FROM query_logs;
```

重点确认：

- `line_routes` 存在普通索引 `idx_line_routes_line_stop (line_id, stop_id)`，但它不是唯一索引；
- `uq_arrival_run_line_stop (ingestion_run_id, line_id, stop_id)` 负责同一采集批次内的到站快照幂等；
- `idx_arrival_realtime (line_id, stop_id, collected_at)` 支持最新到站查询；
- `arrival_infos` 存在 `idx_arrival_line_time (line_id, collected_at)`；
- `uq_dispatch_schedule_run_line (ingestion_run_id, line_id)` 负责同一采集批次内的调度快照幂等；
- `idx_dispatch_schedule_line_time (line_id, collected_at)` 支持最新调度和线路历史查询。

也可以一次查看全部索引：

```sql
SELECT table_name,
       index_name,
       non_unique,
       seq_in_index,
       column_name,
       collation
FROM information_schema.statistics
WHERE table_schema = 'transit_system'
ORDER BY table_name, index_name, seq_in_index;
```

### 7.5 保存建表结果

逐表查看 MySQL 实际采用的结构：

```sql
SHOW CREATE TABLE users\G
SHOW CREATE TABLE `lines`\G
SHOW CREATE TABLE stops\G
SHOW CREATE TABLE line_routes\G
SHOW CREATE TABLE favorite_stops\G
SHOW CREATE TABLE query_logs\G
SHOW CREATE TABLE ingestion_runs\G
SHOW CREATE TABLE arrival_infos\G
SHOW CREATE TABLE dispatch_schedules\G
SHOW CREATE TABLE dispatch_cars\G
```

后续编写 SQLAlchemy 模型和 Alembic 初始迁移时，应与这些结果逐项对照。

## 8. 执行事务回滚式冒烟测试

下面的测试会临时插入用户、线路、站点、站序、采集记录和快照，验证中文、外键和基本关系。末尾执行 `ROLLBACK`，不会留下测试数据。

```sql
USE transit_system;
START TRANSACTION;

INSERT INTO users
    (username, password_hash, role)
VALUES
    ('数据库测试用户', 'not-a-real-password-hash', 'passenger');
SET @test_user_id = LAST_INSERT_ID();

INSERT INTO `lines`
    (line_name, direction, line_type,
     shanghai_line_id, amap_line_id,
     first_departure_time, last_departure_time)
VALUES
    ('980路', 0, 1, '10468', '310100015144', '05:30', '22:30');
SET @test_line_id = LAST_INSERT_ID();

INSERT INTO stops
    (stop_name, amap_stop_id, longitude, latitude)
VALUES
    ('海阳路上南路', 'BV10029479', 121.4993680, 31.1567830);
SET @test_stop_id = LAST_INSERT_ID();

INSERT INTO line_routes
    (line_id, stop_id, sequence_no, shanghai_stop_id)
VALUES
    (@test_line_id, @test_stop_id, 1, '687C0003');

INSERT INTO favorite_stops (user_id, stop_id)
VALUES (@test_user_id, @test_stop_id);

INSERT INTO query_logs (user_id, stop_id)
VALUES (@test_user_id, @test_stop_id);

INSERT INTO ingestion_runs
    (source, task_type, trigger_type, request_key, status)
VALUES
    ('shanghai', 'nearby_realtime', 'manual',
     '121.499368,31.156783', 'running');
SET @test_run_id = LAST_INSERT_ID();

SET @test_collected_at = NOW(3);

INSERT INTO arrival_infos
    (ingestion_run_id, line_id, stop_id, source_up_down,
     collected_at, current_bus_distance_m,
     current_bus_arrival_min, current_license_plate,
     current_barrier_free)
VALUES
    (@test_run_id, @test_line_id, @test_stop_id, 0,
     @test_collected_at, 0, 0, '沪A51786D无障碍', TRUE);

INSERT INTO dispatch_schedules
    (ingestion_run_id, line_id, collected_at,
     schedule_code, message_default, message_short)
VALUES
    (@test_run_id, @test_line_id, @test_collected_at,
     1, '等待首站发车', '即将发车');
SET @test_schedule_id = LAST_INSERT_ID();

INSERT INTO dispatch_cars
    (schedule_id, sequence_no, vehicle_text,
     is_barrier_free, planned_departure_at,
     countdown_text, countdown_seconds)
VALUES
    (@test_schedule_id, 1, '沪A04998D无障碍', TRUE,
     TIMESTAMP(CURRENT_DATE, '23:50:00'), '即将发车', 0);

UPDATE ingestion_runs
SET status = 'success',
    finished_at = NOW(3),
    received_count = 1,
    inserted_count = 3
WHERE id = @test_run_id;

SELECT l.line_name,
       l.direction,
       s.stop_name,
       lr.sequence_no,
       ai.current_license_plate,
       ai.current_barrier_free
FROM arrival_infos AS ai
JOIN `lines` AS l ON l.id = ai.line_id
JOIN stops AS s ON s.id = ai.stop_id
JOIN line_routes AS lr
  ON lr.line_id = ai.line_id
 AND lr.stop_id = ai.stop_id
WHERE ai.ingestion_run_id = @test_run_id;

SELECT COUNT(*) AS favorite_count
FROM favorite_stops
WHERE user_id = @test_user_id;

ROLLBACK;
```

预期结果：

- `USE` 和 `START TRANSACTION` 执行成功；
- 每条 `INSERT` 均显示 `Query OK, 1 row affected`；
- `UPDATE ingestion_runs` 显示 `Rows matched: 1  Changed: 1`；
- 关联查询返回 1 行，关键列应为：

```text
+-----------+-----------+--------------------+-------------+-------------------------+----------------------+
| line_name | direction | stop_name          | sequence_no | current_license_plate   | current_barrier_free |
+-----------+-----------+--------------------+-------------+-------------------------+----------------------+
| 980路     |         0 | 海阳路上南路         |           1 | 沪A51786D无障碍         |                    1 |
+-----------+-----------+--------------------+-------------+-------------------------+----------------------+
1 row in set
```

- 收藏查询返回 `favorite_count = 1`；
- `ROLLBACK` 显示 `Query OK, 0 rows affected`，上述临时数据全部撤销。

回滚后确认表为空：

```sql
SELECT COUNT(*) FROM users;
SELECT COUNT(*) FROM `lines`;
SELECT COUNT(*) FROM stops;
SELECT COUNT(*) FROM ingestion_runs;
```

预期结果：在一个全新数据库中，四条查询的 `COUNT(*)` 都应为 `0`。如果表中原本已有数据，回滚后的计数应与测试前完全一致。

## 9. 验证关键约束

以下测试建议一次只执行一组，并在测试后 `ROLLBACK`。

### 9.1 验证线路方向唯一性

同一个市政府 `lineId` 可以存在两个方向：

```sql
START TRANSACTION;

INSERT INTO `lines`
    (line_name, direction, shanghai_line_id)
VALUES
    ('测试线路', 0, 'TEST-LINE'),
    ('测试线路', 1, 'TEST-LINE');

SELECT id, line_name, direction, shanghai_line_id
FROM `lines`
WHERE shanghai_line_id = 'TEST-LINE';

INSERT INTO `lines`
    (line_name, direction, shanghai_line_id)
VALUES
    ('重复方向测试', 0, 'TEST-LINE');

ROLLBACK;
```

预期结果：

- 第一条 `INSERT` 显示 `Query OK, 2 rows affected`；
- `SELECT` 返回 2 行，`direction` 分别为 `0` 和 `1`；
- 第二条 `INSERT` 失败，返回 `ERROR 1062 (23000)`，并指向唯一键 `uq_lines_shanghai_direction`；
- `ROLLBACK` 成功，不保留两条测试线路。

### 9.2 验证重复快照被拒绝

`arrival_infos` 的 `(ingestion_run_id, line_id, stop_id)` 必须唯一。执行：

```sql
START TRANSACTION;

INSERT INTO `lines` (line_name, direction)
VALUES ('重复快照测试线路', 0);
SET @dup_line_id = LAST_INSERT_ID();

INSERT INTO stops (stop_name, longitude, latitude)
VALUES ('重复快照测试站', 121.5000000, 31.2000000);
SET @dup_stop_id = LAST_INSERT_ID();

INSERT INTO ingestion_runs
    (source, task_type, trigger_type, status)
VALUES
    ('shanghai', 'duplicate_snapshot_test', 'manual', 'running');
SET @dup_run_id = LAST_INSERT_ID();

INSERT INTO arrival_infos
    (ingestion_run_id, line_id, stop_id, collected_at)
VALUES
    (@dup_run_id, @dup_line_id, @dup_stop_id, NOW(3));

INSERT INTO arrival_infos
    (ingestion_run_id, line_id, stop_id, collected_at)
VALUES
    (@dup_run_id, @dup_line_id, @dup_stop_id,
     NOW(3) + INTERVAL 1 SECOND);

ROLLBACK;
```

预期结果：

- 前四条 `INSERT` 均成功，每条影响 1 行；
- 第二次写入 `arrival_infos` 时返回 `ERROR 1062 (23000)`，并指向 `uq_arrival_run_line_stop`；
- 即使两条快照的 `collected_at` 不同，也不允许同一采集批次重复写入同一线路站点；
- `ROLLBACK` 成功，不保留任何测试数据。

实际后端使用 `ON DUPLICATE KEY` 时可幂等跳过；这里故意使用普通 `INSERT` 验证唯一约束。

### 9.3 验证用户删除策略

```sql
START TRANSACTION;

INSERT INTO users (username, password_hash, role)
VALUES ('删除策略测试用户', 'not-a-real-password-hash', 'passenger');
SET @delete_user_id = LAST_INSERT_ID();

INSERT INTO stops (stop_name, longitude, latitude)
VALUES ('删除策略测试站', 121.5100000, 31.2100000);
SET @delete_stop_id = LAST_INSERT_ID();

INSERT INTO favorite_stops (user_id, stop_id)
VALUES (@delete_user_id, @delete_stop_id);

INSERT INTO query_logs (user_id, stop_id)
VALUES (@delete_user_id, @delete_stop_id);
SET @delete_query_log_id = LAST_INSERT_ID();

DELETE FROM users WHERE id = @delete_user_id;

SELECT COUNT(*) AS favorite_count
FROM favorite_stops
WHERE user_id = @delete_user_id;

SELECT id, user_id, stop_id
FROM query_logs
WHERE id = @delete_query_log_id;

ROLLBACK;
```

预期结果：

- 四条 `INSERT` 均成功，`DELETE FROM users` 显示 `1 row affected`；
- 收藏查询返回 `favorite_count = 0`，证明 `ON DELETE CASCADE` 生效；
- 日志查询仍返回 1 行，其 `id` 与 `stop_id` 保留，`user_id` 为 `NULL`，证明 `ON DELETE SET NULL` 生效；
- `ROLLBACK` 成功，用户、站点、收藏和日志的测试变更均被撤销。

后端常规管理只停用用户；该测试用于证明数据库约束正确。

### 9.4 验证线路和站点不能误删

当 `line_routes` 仍引用线路和站点时，验证物理删除被拒绝，但逻辑停用可以成功：

```sql
START TRANSACTION;

INSERT INTO `lines` (line_name, direction)
VALUES ('外键限制测试线路', 0);
SET @restrict_line_id = LAST_INSERT_ID();

INSERT INTO stops (stop_name, longitude, latitude)
VALUES ('外键限制测试站', 121.5200000, 31.2200000);
SET @restrict_stop_id = LAST_INSERT_ID();

INSERT INTO line_routes (line_id, stop_id, sequence_no)
VALUES (@restrict_line_id, @restrict_stop_id, 1);

DELETE FROM `lines` WHERE id = @restrict_line_id;
DELETE FROM stops WHERE id = @restrict_stop_id;

UPDATE `lines`
SET is_active = FALSE
WHERE id = @restrict_line_id;

UPDATE stops
SET is_active = FALSE
WHERE id = @restrict_stop_id;

SELECT l.is_active AS line_active,
       s.is_active AS stop_active
FROM `lines` AS l
JOIN stops AS s ON s.id = @restrict_stop_id
WHERE l.id = @restrict_line_id;

ROLLBACK;
```

预期结果：

- 三条 `INSERT` 均成功；
- ``DELETE FROM `lines``` 返回 `ERROR 1451 (23000)`，并指向外键 `fk_line_routes_line`；
- `DELETE FROM stops` 返回 `ERROR 1451 (23000)`，并指向外键 `fk_line_routes_stop`；
- 两条 `UPDATE` 均显示 `1 row affected`；
- 最后的 `SELECT` 返回 1 行，`line_active = 0` 且 `stop_active = 0`；
- `ROLLBACK` 成功，不保留测试线路、站点和站序。

## 10. 建立后端连接参数

后续 FastAPI 使用以下信息：

```text
数据库类型：MySQL 8
主机：127.0.0.1
端口：3306
数据库：transit_system
用户：transit_app
密码：创建应用账户时设置的密码
字符集：utf8mb4
时区：Asia/Shanghai / +08:00
```

SQLAlchemy 异步连接 URL 形式为：

```text
mysql+asyncmy://transit_app:经过URL编码的密码@127.0.0.1:3306/transit_system?charset=utf8mb4
```

不要现在把真实密码写进项目文件。后端阶段会创建 `.env` 和 `.env.example`，其中只有 `.env.example` 可以提交版本管理。

可以先从宿主机验证应用账户。如果使用 Docker 且本机安装了 MySQL Client：

```powershell
mysql -h 127.0.0.1 -P 3306 -utransit_app -p transit_system
```

连接后检查：

```sql
SELECT CURRENT_USER(), DATABASE(), NOW(3);
SHOW TABLES;
```

## 11. 备份与恢复

### 11.1 Ubuntu 环境备份

创建只允许当前系统用户访问的备份目录：

```bash
mkdir -p "$HOME/transit-db-backups"
chmod 700 "$HOME/transit-db-backups"
```

使用 root 的本地 socket 身份执行一致性备份：

```bash
sudo mysqldump \
  --single-transaction \
  --triggers \
  --set-gtid-purged=OFF \
  transit_system \
  > "$HOME/transit-db-backups/transit_system_$(date +%F_%H%M%S).sql"
```

检查备份：

```bash
ls -lh "$HOME/transit-db-backups"
head -n 20 "$HOME"/transit-db-backups/transit_system_*.sql
```

备份文件包含业务数据，不能提交到 Git，也不应放在网站可访问目录中。

### 11.2 Docker 环境备份

在 PowerShell 中执行。命令使用容器内部已有的 root 环境变量，不会把密码写入备份文件：

```powershell
docker exec transit-mysql sh -c `
  'exec mysqldump -uroot -p"$MYSQL_ROOT_PASSWORD" --single-transaction --triggers transit_system' `
  > transit_system_backup.sql
```

若 PowerShell 的交互重定向表现异常，可使用本机安装的 `mysqldump`：

```powershell
mysqldump -h 127.0.0.1 -P 3306 `
  -utransit_app -p `
  --single-transaction `
  --triggers `
  transit_system > transit_system_backup.sql
```

检查备份文件不是空文件：

```powershell
Get-Item -LiteralPath '.\transit_system_backup.sql'
```

### 11.3 恢复

恢复会修改数据库内容，执行前先确认目标数据库。推荐恢复到新的测试数据库，而不是覆盖当前开发库：

```sql
CREATE DATABASE transit_system_restore_test
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_0900_ai_ci;
```

PowerShell 不可靠地支持 MySQL 常用的 `<` 输入重定向。请打开 Windows“命令提示符（cmd）”，切换到备份文件目录后执行：

```bat
mysql -h 127.0.0.1 -P 3306 -uroot -p `
  transit_system_restore_test < transit_system_backup.sql
```

在 `cmd` 中不要输入行尾反引号；实际应写成一行：

```bat
mysql -h 127.0.0.1 -P 3306 -uroot -p transit_system_restore_test < transit_system_backup.sql
```

Ubuntu 上恢复到测试数据库：

```bash
sudo mysql transit_system_restore_test \
  < "$HOME/transit-db-backups/具体备份文件.sql"
```

恢复后验证 10 张表和关键记录数量，确认成功后再决定是否保留测试数据库。

## 12. 日常操作

查看数据库占用：

```sql
SELECT table_name,
       table_rows,
       ROUND(data_length / 1024 / 1024, 2) AS data_mb,
       ROUND(index_length / 1024 / 1024, 2) AS index_mb
FROM information_schema.tables
WHERE table_schema = 'transit_system'
ORDER BY data_length + index_length DESC;
```

查看当前连接：

```sql
SHOW PROCESSLIST;
```

查看最近采集运行：

```sql
SELECT id,
       source,
       task_type,
       trigger_type,
       status,
       started_at,
       finished_at,
       received_count,
       inserted_count,
       failed_count
FROM ingestion_runs
ORDER BY started_at DESC
LIMIT 20;
```

检查表：

```sql
CHECK TABLE users,
            `lines`,
            stops,
            line_routes,
            favorite_stops,
            query_logs,
            ingestion_runs,
            arrival_infos,
            dispatch_schedules,
            dispatch_cars;
```

## 13. 常见问题

### 13.1 端口 3306 已被占用

Ubuntu 查看占用：

```bash
sudo ss -lntp | grep ':3306'
```

Windows PowerShell 查看占用：

```powershell
Get-NetTCPConnection -LocalPort 3306 -ErrorAction SilentlyContinue
```

如果本机已有需要保留的 MySQL，不要停止或删除它。Docker 启动时可改为：

```powershell
-p 3307:3306
```

此时后端连接端口也改为 `3307`。

### 13.2 容器名称已存在

```powershell
docker ps -a --filter "name=transit-mysql"
```

若是之前创建的正确容器，执行：

```powershell
docker start transit-mysql
```

不要为了消除报错直接删除容器或 volume。

### 13.3 中文显示乱码

依次检查：

```sql
SHOW VARIABLES LIKE 'character_set%';
SHOW VARIABLES LIKE 'collation%';
SHOW CREATE DATABASE transit_system;
```

客户端连接和后端连接 URL 都应声明 `utf8mb4`。不要使用 `utf8` 或 `latin1`。

### 13.4 时区错误

检查：

```sql
SELECT @@global.time_zone, @@session.time_zone, NOW(3);
```

应用每次创建连接后应把会话时区设为 `+08:00`。本项目所有采集时间按上海时间解释。

### 13.5 `CHECK` 约束创建失败

首先确认不是旧版 MySQL：

```sql
SELECT VERSION();
```

本项目要求 MySQL 8。不要为了兼容旧版本静默删除检查约束。

### 13.6 外键创建失败

常见原因：

- 父表还没有创建；
- 父子字段一个是 `BIGINT UNSIGNED`，另一个不是；
- 表没有使用 InnoDB；
- 引用列不是主键或唯一索引；
- 约束名称重复。

查看最近的 InnoDB 错误：

```sql
SHOW ENGINE INNODB STATUS\G
```

### 13.7 唯一外部 ID 允许多个空值

MySQL 唯一索引允许存在多条 `NULL`。因此 `amap_line_id`、`amap_stop_id`、`shanghai_line_id` 或 `shanghai_stop_id` 尚未匹配时可以留空，不会互相冲突。空字符串 `''` 不等于 `NULL`，解析器必须把缺失 ID 写成真正的 `NULL`。

## 14. 不应执行的操作

- 不要使用 root 账户运行后端；
- 不要把数据库密码提交到仓库；
- 不要通过关闭 `FOREIGN_KEY_CHECKS` 绕过正常导入错误；
- 不要把外部 API ID 改成整数，前导零和字母必须保留；
- 不要物理删除仍有历史数据的线路或站点；
- 不要把市政府 `stopId` 保存为物理站点的全局唯一 ID；
- 不要在没有备份的情况下执行 `DROP DATABASE`、`DROP TABLE` 或批量 `DELETE`；
- 不要手工修改已经由 Alembic 接管后的正式表结构；后端阶段开始后，结构变化必须通过迁移完成。

## 15. 本阶段交付记录

完成后填写以下信息，供后端阶段使用：

```text
完成日期：
部署方式：Docker / 本机 MySQL
MySQL 版本：
数据库主机：
数据库端口：
数据库名称：transit_system
应用数据库用户：transit_app
表数量：10
结构验证：通过 / 未通过
冒烟测试：通过 / 未通过
备份测试：通过 / 未通过
待解决问题：
```

真实密码不要填写在此记录中。


## 补充： Linux上完成的备份数据库流程

当前 MySQL 版本不支持通过 `@@session.in_transaction` 读取该状态。可以直接执行：

```sql
ROLLBACK;
```

即使当前没有事务，`ROLLBACK` 也是安全的，通常返回：

```text
Query OK, 0 rows affected
```

然后确认版本：

```sql
SELECT VERSION(), @@version_comment;
```

退出客户端：

```sql
EXIT;
```

再在系统终端执行备份命令：

```bash
mkdir -p ~/transit-db-backups
chmod 700 ~/transit-db-backups

backup_file=~/transit-db-backups/transit_system_$(date +%F_%H%M%S).sql

sudo mysqldump \
  --single-transaction \
  --triggers \
  --set-gtid-purged=OFF \
  --no-tablespaces \
  transit_system > "$backup_file"

chmod 600 "$backup_file"
ls -lh "$backup_file"
grep -c '^CREATE TABLE' "$backup_file"
```

最后的表数量预期为：

```text
10
```

直接在备份前执行一次 `ROLLBACK`，比依赖不同版本支持情况不一致的事务状态变量更稳妥。