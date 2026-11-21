FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# DevCloud 仅路由容器 8080 端口
EXPOSE 8080

# 绑定 0.0.0.0:8080，生产模式无 reload
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]