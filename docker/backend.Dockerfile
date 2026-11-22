FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# 先装依赖再拷源码，改代码时不必重装依赖
COPY backend/pyproject.toml /app/pyproject.toml
COPY backend/src /app/src
RUN pip install --no-cache-dir -e .

COPY backend/ /app/

EXPOSE 8000

# 单进程：插件运行时状态在进程内存，多 worker 会让插件启停与菜单同步各自为政
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
