# Interview Practice App — 部署指南

> **目标架构：** Vercel 前端 + 阿里云裸机后端 (FastAPI + PostgreSQL)
> **服务器：** 阿里云轻量 `139.196.242.143` (2C2G/40GB)
> **关键决策：不用 Docker，裸机部署 PostgreSQL + systemd 管理后端，最小化内存占用**
> **代码策略：同一份代码，双环境兼容，通过 `.env` 配置开关切换**
> **前置条件：** 已在 GitHub 创建仓库，代码已推送

---

## 目录

0. [代码双兼容架构说明](#0-代码双兼容架构说明)
1. [代码准备 (本地 Windows)](#1-代码准备本地-windows)
2. [服务器环境准备](#2-服务器环境准备)
3. [PostgreSQL 裸机安装](#3-postgresql-裸机安装)
4. [后端部署 (systemd)](#4-后端部署-systemd)
5. [Vercel 前端部署](#5-vercel-前端部署)
6. [验证 & 排错](#6-验证--排错)
7. [后续可选优化](#7-后续可选优化)

---

## 0. 代码双兼容架构说明

### 核心原则

**同一份代码，通过 `.env` 配置决定运行模式，无需修改业务代码。**

### 已实现的 Graceful Degradation

| 组件 | 禁用时的行为 | 对业务的影响 |
|---|---|---|
| **Redis** | 所有缓存操作返回空/False，不抛异常 | 无缓存，性能略降，功能完全正常 |
| **RabbitMQ** | `publish_to_queue` 返回 False，消息不发 | 异步任务（简历解析等）不执行，核心功能正常 |
| **Kafka** | Event Publisher 使用 in-memory 后端 | 事件流不持久化，不影响核心流程 |

### 本地 vs 云端配置对比

| 配置项 | 本地开发 | 阿里云部署 |
|---|---|---|
| `DATABASE_URL` | `localhost:5432` | `localhost:5432` |
| `REDIS_ENABLED` | `true` | `false` |
| `RABBITMQ_ENABLED` | `true` | `false` |
| `KAFKA_ENABLED` | `false` | `false` |
| `EMBEDDING_PROVIDER` | `dashscope` | `dashscope` |
| `DEBUG` | `true` | `false` |

### Agent 操作提示

部署 Agent 只需做一件事：**根据目标环境写对 `.env` 文件**。

```bash
# 本地开发环境
REDIS_ENABLED=true
RABBITMQ_ENABLED=true
DEBUG=true

# 阿里云生产环境
REDIS_ENABLED=false
RABBITMQ_ENABLED=false
DEBUG=false
```

其余代码不变。中间件初始化已在 `main.py` 中按开关条件执行，缓存和队列操作已内置空值回退。

---

## 1. 代码准备 (本地 Windows)

### 1.1 确认 .gitignore 已包含敏感文件

`.env` 已在 `.gitignore` 中，确保不会被提交。

### 1.2 提交当前代码改动

```powershell
cd D:\AI_Project\Surprise\Interview-Practice-App

# 提交核心代码（backend、web、docker-compose、readme）
git add backend/ web/ docker-compose.yml readme/

# 忽略开发中间文件
git reset -- .claude-done.md .claude-prompt.txt .claude-task.md .claude/ .cursorrules
git reset -- bug1-explain-stream.txt create_tables.sql openapi_tmp.json
git reset -- run-claude.bat run-claude2.bat task-bugfix.txt tasks.txt
git reset -- web/smoke-questions.png web/test-results/ web/playwright-report/

git commit -m "deploy: prepare for production - CORS middleware, DashScope embedding, Vercel-ready frontend"
```

### 1.3 创建 GitHub 仓库并推送

```powershell
# 先在 GitHub 创建空仓库（私有或公开均可）
# 然后执行：
git remote add origin https://github.com/你的用户名/interview-practice-app.git
git push -u origin master
```

---

## 2. 服务器环境准备

### 2.1 SSH 登录

```bash
ssh root@139.196.242.143
```

### 2.2 确认系统信息

```bash
# 查看操作系统版本
cat /etc/os-release

# 查看内存
free -h

# 查看 Python 版本
python3 --version
# 如果版本低于 3.10，需要升级：
# yum install -y python3.10 python3.10-devel python3.10-pip
```

### 2.3 安装基础依赖

```bash
# Alibaba Cloud Linux / CentOS
yum install -y gcc make python3-devel libffi-devel openssl-devel

# 如果是 Ubuntu/Debian：
# apt install -y gcc make python3-dev libffi-dev libssl-dev pkg-config
```

### 2.4 开放端口（阿里云控制台）

进入 **阿里云控制台 → 轻量应用服务器 → 防火墙**，添加规则：

| 端口 | 协议 | 说明 |
|------|------|------|
| 8000 | TCP | 后端 API 服务（Vercel 前端需要访问） |
| 80 | TCP | HTTP（可选，后续配 Nginx 用） |
| 443 | TCP | HTTPS（可选，后续配 SSL 用） |

⚠️ **不要开放 5432 端口！** 数据库只监听 localhost，本地访问即可。

---

## 3. PostgreSQL 裸机安装

### 3.1 安装 PostgreSQL

```bash
# Alibaba Cloud Linux / CentOS 8+
# 先添加 PostgreSQL 官方 yum 源
yum install -y https://download.postgresql.org/pub/repos/yum/reporpms/EL-8-x86_64/pgdg-redhat-repo-latest.noarch.rpm

# 安装 PostgreSQL 15
yum install -y postgresql15-server postgresql15

# 如果是 Alibaba Cloud Linux 2 (CentOS 7 兼容)：
# yum install -y https://download.postgresql.org/pub/repos/yum/reporpms/EL-7-x86_64/pgdg-redhat-repo-latest.noarch.rpm
# yum install -y postgresql15-server postgresql15

# 如果是 Ubuntu：
# apt install -y postgresql postgresql-client
```

### 3.2 初始化并启动

```bash
# CentOS/Alibaba Cloud Linux
/usr/pgsql-15/bin/postgresql-15-setup initdb
systemctl enable postgresql-15 --now

# Ubuntu (systemd 自动初始化了)：
# systemctl enable postgresql --now
```

### 3.3 创建数据库和用户

```bash
# 切换 postgres 用户
su - postgres

# 创建数据库
psql << 'PSQLEOF'
CREATE DATABASE interview_practice;
ALTER USER postgres WITH PASSWORD '在此替换为随机密码';
\q
PSQLEOF

exit
```

### 3.4 确认数据库可用

```bash
# 测试本地连接
PGPASSWORD='你的密码' psql -U postgres -h localhost -d interview_practice -c "SELECT version();"
# 应该输出 PostgreSQL 版本信息

# 检查监听地址（应该是 127.0.0.1，不是 0.0.0.0）
cat /var/lib/pgsql/15/data/postgresql.conf | grep listen_addresses
# 应该显示: listen_addresses = 'localhost'
```

### 3.5 执行数据库迁移

```bash
# 方式一：如果有 Alembic 迁移文件
cd /opt/interview-app/backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
alembic upgrade head

# 方式二：如果有 SQL 文件
PGPASSWORD='你的密码' psql -U postgres -h localhost -d interview_practice -f create_tables.sql
```

### 3.6 内存优化（可选但推荐）

```bash
# 编辑 PostgreSQL 配置，限制内存使用
vi /var/lib/pgsql/15/data/postgresql.conf

# 修改以下参数：
# shared_buffers = 64MB         # 默认 128MB，2GB 服务器降低
# effective_cache_size = 256MB  # 默认 4GB，大幅降低
# work_mem = 4MB                # 默认 4MB，保持
# max_connections = 20          # 默认 100，降低（我们的 app 用不了那么多）

# 重启生效
systemctl restart postgresql-15

# 验证生效
PGPASSWORD='你的密码' psql -U postgres -h localhost -d interview_practice -c "SHOW shared_buffers;"
```

---

## 4. 后端部署 (systemd)

### 4.1 拉取代码

```bash
mkdir -p /opt/interview-app
cd /opt/interview-app

# 拉取代码
git clone --depth 1 https://github.com/你的用户名/interview-practice-app.git .
```

### 4.2 创建生产环境 .env

```bash
cat > .env << 'ENVEOF'
# ── Application ──────────────────────────────────────────────
APP_NAME=Interview Practice App
DEBUG=false
API_V1_PREFIX=/api/v1

# ── Database (本地 PostgreSQL，裸机安装) ─────────────────────
DATABASE_URL=postgresql+asyncpg://postgres:你的数据库密码@localhost:5432/interview_practice

# ── LLM Provider ─────────────────────────────────────────────
LLM_PROVIDER=dashscope
LLM_BASE_URL=https://coding.dashscope.aliyuncs.com/v1
LLM_API_KEY=sk-6103f6d575894d5aa02a20fb236f61fc
LLM_MODEL_NAME=qwen3.6-plus
LLM_MAX_RETRIES=3
LLM_TIMEOUT=60

# ── Embedding (DashScope API) ───────────────────────────────
EMBEDDING_PROVIDER=dashscope
EMBEDDING_MODEL_PATH=text-embedding-v4
EMBEDDING_DIMENSION=1024

# ── Auth & Access Control ───────────────────────────────────
AUTH_ENABLED=false
PUBLIC_MODE=true
JWT_SECRET_KEY=用 openssl rand -hex 32 生成一个
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# ── File Storage ─────────────────────────────────────────────
UPLOAD_DIR=uploads
MAX_UPLOAD_SIZE_MB=50

# ── Vector Store ─────────────────────────────────────────────
VECTOR_STORE_TYPE=pgvector

# ── 禁用不需要的中间件（省内存） ────────────────────────────
REDIS_ENABLED=false
RABBITMQ_ENABLED=false
ENVEOF

# 生成 JWT_SECRET_KEY 并替换
SECRET=$(openssl rand -hex 32)
sed -i "s/用 openssl rand -hex 32 生成一个/$SECRET/" .env

# 替换数据库密码
DB_PASS='你的实际密码'
sed -i "s/你的数据库密码/$DB_PASS/g" .env
```

### 4.3 安装 Python 依赖

```bash
cd /opt/interview-app/backend

# 创建虚拟环境
python3 -m venv /opt/interview-app/backend/venv
source /opt/interview-app/backend/venv/bin/activate

# 安装依赖
pip install --upgrade pip
pip install -r requirements.txt

# 安装 pgvector 扩展（Python 包）
pip install pgvector

# 验证安装
uvicorn --version
python -c "import fastapi; print('FastAPI OK')"
python -c "import asyncpg; print('asyncpg OK')"
python -c "import pgvector; print('pgvector OK')"

deactivate
```

### 4.4 确保上传目录存在

```bash
mkdir -p /opt/interview-app/backend/uploads
```

### 4.5 创建 systemd 服务

```bash
cat > /etc/systemd/system/interview-backend.service << 'EOF'
[Unit]
Description=Interview Practice Backend API
After=network.target postgresql-15.service
Wants=postgresql-15.service

[Service]
Type=simple
User=root
WorkingDirectory=/opt/interview-app/backend
EnvironmentFile=/opt/interview-app/.env
Environment=PYTHONUNBUFFERED=1

ExecStart=/opt/interview-app/backend/venv/bin/uvicorn app.main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --workers 1 \
  --log-level info

Restart=always
RestartSec=5
# 限制内存使用，防止 OOM
MemoryMax=512M

# 标准输出到 journal
StandardOutput=journal
StandardError=journal
SyslogIdentifier=interview-backend

[Install]
WantedBy=multi-user.target
EOF

# 重新加载 systemd
systemctl daemon-reload

# 启动服务
systemctl enable --now interview-backend

# 查看状态
systemctl status interview-backend
```

### 4.6 运行数据库迁移

```bash
cd /opt/interview-app/backend
source venv/bin/activate

# 方式一：Alembic 迁移
alembic upgrade head

# 方式二：如果有 SQL 脚本
# PGPASSWORD='你的密码' psql -U postgres -h localhost -d interview_practice -f create_tables.sql

deactivate
```

### 4.7 验证后端启动

```bash
# 检查服务状态
systemctl status interview-backend

# 查看实时日志
journalctl -u interview-backend -f

# 测试健康检查
curl http://localhost:8000/health

# 测试 API 文档
curl http://localhost:8000/docs

# 从外网测试（确认端口已开放）
curl http://139.196.242.143:8000/health
```

---

## 5. Vercel 前端部署

### 5.1 连接 Vercel

1. 登录 [vercel.com](https://vercel.com)
2. 点击 **Add New... → Project**
3. Import 你的 GitHub 仓库 `interview-practice-app`

### 5.2 配置构建设置

| 设置项 | 值 |
|---|---|
| **Framework Preset** | Next.js |
| **Root Directory** | `web` |
| **Build Command** | `next build` |
| **Output Directory** | `.next` |
| **Install Command** | `npm install` |

### 5.3 设置环境变量

在 **Settings → Environment Variables** 中添加：

| 变量名 | 值 | 作用域 |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | `http://139.196.242.143:8000` | All Environments |

### 5.4 部署

点击 **Deploy**，等待自动构建（约 2-3 分钟）。

部署成功后，Vercel 会给你一个域名：
```
https://interview-practice-xxx.vercel.app
```

---

## 6. 验证 & 排错

### 6.1 基础检查清单

- [ ] 后端健康检查：`curl http://139.196.242.143:8000/health` 返回 `{"status": "ok"}`
- [ ] Vercel 前端能打开，页面正常渲染
- [ ] 前端能调用后端 API（打开浏览器 DevTools → Network，检查请求）
- [ ] 数据库连接正常（后端日志无数据库连接错误）
- [ ] LLM 调用正常（尝试发起一次面试/提问功能）

### 6.2 常见问题

**问题 1：Vercel 前端请求后端 CORS 错误**

```bash
# 检查后端 CORS 是否已配置
grep -A 6 "CORSMiddleware" /opt/interview-app/backend/app/main.py

# 如果没配置，说明代码没更新，重新拉代码：
cd /opt/interview-app
git pull
systemctl restart interview-backend
```

**问题 2：后端服务启动失败**

```bash
# 查看详细错误
journalctl -u interview-backend --no-pager -n 100

# 常见原因：
# 1. Python 依赖没装全 → source venv/bin/activate && pip install -r requirements.txt
# 2. 端口 8000 被占用 → netstat -tlnp | grep 8000
# 3. .env 文件路径不对 → 检查 EnvironmentFile 路径
# 4. 数据库连接失败 → 检查 DATABASE_URL 中的密码是否正确
```

**问题 3：数据库连接失败**

```bash
# 确认 PostgreSQL 在运行
systemctl status postgresql-15

# 手动测试数据库连接
PGPASSWORD='你的密码' psql -U postgres -h localhost -d interview_practice -c "SELECT 1;"

# 检查 pg_hba.conf 是否允许密码认证
cat /var/lib/pgsql/15/data/pg_hba.conf | grep -v "^#" | grep -v "^$"
# 应该有类似这样的行：
# host    all    all    127.0.0.1/32    scram-sha-256
# 或
# host    all    all    127.0.0.1/32    md5
```

**问题 4：阿里云安全组拦截**

- 去控制台确认 8000 端口已放行
- 测试：`curl -v http://139.196.242.143:8000/health`
- 如果超时（不是返回错误），说明是网络层面被拦截

**问题 5：Vercel 部署失败**

- 查看 Vercel 构建日志
- 常见原因：`NEXT_PUBLIC_API_URL` 环境变量未设置、`web/` 目录下 `package.json` 路径不对

**问题 6：内存不够**

```bash
# 查看内存使用
free -h

# 查看哪个进程最吃内存
ps aux --sort=-%mem | head -10

# 如果 OpenClaw 占太多，可以限制或暂时停止
systemctl stop openclaw   # 如果需要的话

# PostgreSQL 内存优化见 3.6 节
```

### 6.3 关键日志位置

```bash
# 后端日志
journalctl -u interview-backend -f           # 实时
journalctl -u interview-backend --no-pager -n 200  # 最近 200 行

# PostgreSQL 日志
journalctl -u postgresql-15 -f

# 内存监控
watch -n 2 'free -h && echo "---" && ps aux --sort=-%mem | head -5'
```

---

## 7. 后续可选优化

### 7.1 域名 + HTTPS + Nginx

购买域名后，用 Nginx 反向代理：

```bash
# 安装 Nginx
yum install -y nginx

# 安装 Certbot（免费 SSL）
yum install -y certbot python3-certbot-nginx  # 或 epel-release + certbot

# 配置 Nginx
cat > /etc/nginx/conf.d/interview.conf << 'NGINX'
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        # 保持 SSE/流式连接
        proxy_buffering off;
        proxy_cache off;
        # 保持长连接
        proxy_read_timeout 300s;
        proxy_connect_timeout 75s;
    }
}
NGINX

nginx -t && systemctl reload nginx

# 申请 SSL 证书
certbot --nginx -d your-domain.com
```

然后更新 Vercel 环境变量：
```
NEXT_PUBLIC_API_URL=https://your-domain.com
```

### 7.2 内存优化总结

| 组件 | 预估内存 |
|---|---|
| PostgreSQL (裸机) | ~100-120 MB |
| FastAPI + uvicorn (单进程) | ~200 MB |
| **总计** | **~300-350 MB** |
| 峰值（OCR 加载时） | ~500-600 MB |

如果内存仍然紧张：
- 从 `requirements.txt` 移除 `pymupdf`、`paddleocr`（如果不用简历解析功能）
- 降低 PostgreSQL `max_connections` 到 10
- 降低 `shared_buffers` 到 32MB

### 7.3 自动更新脚本

```bash
cat > /opt/interview-app/update.sh << 'EOF'
#!/bin/bash
set -e

echo "=== 拉取最新代码 ==="
cd /opt/interview-app
git pull

echo "=== 安装新依赖（如果有）==="
source /opt/interview-app/backend/venv/bin/activate
pip install -r /opt/interview-app/backend/requirements.txt
deactivate

echo "=== 运行数据库迁移 ==="
cd /opt/interview-app/backend
source venv/bin/activate
alembic upgrade head
deactivate

echo "=== 重启后端服务 ==="
systemctl restart interview-backend

echo "=== 清理 systemd 日志 ==="
journalctl --vacuum-size=50M

echo "=== 完成 ==="
systemctl status interview-backend --no-pager
EOF

chmod +x /opt/interview-app/update.sh

# 以后更新只需：
/opt/interview-app/update.sh
```

### 7.4 监控 & 告警（可选）

```bash
# 简单的内存监控脚本
cat > /opt/interview-app/monitor.sh << 'EOF'
#!/bin/bash
MEM_USED=$(free -m | awk '/^Mem:/ {printf "%.0f", $3/$2*100}')
echo "$(date): 内存使用率 ${MEM_USED}%"

if [ "$MEM_USED" -gt 85 ]; then
    echo "⚠️ 内存使用率超过 85%！"
    ps aux --sort=-%mem | head -5
    journalctl -u interview-backend --no-pager -n 50
fi
EOF

chmod +x /opt/interview-app/monitor.sh

# 加到 crontab，每 5 分钟检查一次
crontab -l 2>/dev/null; echo "*/5 * * * * /opt/interview-app/monitor.sh >> /var/log/interview-monitor.log 2>&1" | crontab -
```

---

## 附录：关键配置速查

### 环境变量清单

| 变量 | 开发环境 | 生产环境 |
|---|---|---|
| `DEBUG` | `true` | `false` |
| `DATABASE_URL` | `localhost:5432` | `localhost:5432` (裸机) |
| `LLM_API_KEY` | `sk-6103...` | `sk-6103...` |
| `EMBEDDING_PROVIDER` | `dashscope` | `dashscope` |
| `EMBEDDING_MODEL_PATH` | `text-embedding-v4` | `text-embedding-v4` |
| `EMBEDDING_DIMENSION` | `1024` | `1024` |
| `AUTH_ENABLED` | `false` | `false` |
| `REDIS_ENABLED` | `false` | `false` |
| `RABBITMQ_ENABLED` | `false` | `false` |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | `http://139.196.242.143:8000` |

### 端口清单

| 端口 | 服务 | 暴露范围 |
|---|---|---|
| 8000 | FastAPI 后端 | 公网（Vercel 需要访问） |
| 5432 | PostgreSQL | 仅 localhost（不暴露公网） |
| 3000 | Next.js (开发) | 本地开发用 |

### 常用命令速查

```bash
# 后端服务
systemctl status interview-backend    # 查看状态
systemctl restart interview-backend   # 重启
systemctl stop interview-backend      # 停止
journalctl -u interview-backend -f    # 看日志

# PostgreSQL
systemctl status postgresql-15        # 查看状态
systemctl restart postgresql-15       # 重启
PGPASSWORD='密码' psql -U postgres -h localhost -d interview_practice  # 连接

# 内存检查
free -h
ps aux --sort=-%mem | head -10

# 更新
/opt/interview-app/update.sh
```

---

*部署文档版本: 2.0 (裸机优化版) | 更新日期: 2026-05-26*
