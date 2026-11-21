FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# DevCloud 仅路由容器 8080 端口
EXPOSE 8080

# Railway 等平台会注入 PORT 环境变量，config.py 中已有 PORT > 8080 的回退逻辑
CMD ["python", "main.py"]