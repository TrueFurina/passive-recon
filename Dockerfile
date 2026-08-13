# ============================================================
# Passive Recon — 企业级被动 OSINT/EASM/CTEM 平台
# 多阶段构建：轻量运行镜像
# ============================================================

# ---- 构建阶段 ----
FROM python:3.11-slim AS builder

WORKDIR /build

# 安装依赖（先复制 requirements 利用 Docker 层缓存）
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ---- 运行阶段 ----
FROM python:3.11-slim AS runtime

# 元数据
LABEL org.opencontainers.image.title="passive-recon" \
      org.opencontainers.image.description="Purely passive OSINT/EASM/CTEM platform" \
      org.opencontainers.image.source="https://github.com/TrueFurina/passive-recon"

# 非 root 运行（安全）
RUN groupadd -r recon && useradd -r -g recon recon

WORKDIR /app

# 从构建阶段复制依赖
COPY --from=builder /install /usr/local

# 复制应用代码
COPY . .

# 运行期数据目录（挂载卷）
RUN mkdir -p /app/data && chown -R recon:recon /app/data

# 默认端口
EXPOSE 8000

USER recon

# 默认启动 Web 面板
CMD ["uvicorn", "passive_agent.main:app", "--host", "0.0.0.0", "--port", "8000"]