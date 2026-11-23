FROM python:3.12-slim

# Hugging Face Spaces 标准配置：非root用户
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user
WORKDIR $HOME/app

COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

COPY --chown=user . .

# Railway 等平台注入 PORT 环境变量，config.py 自动读取（优先级 GATEKEEPER_PORT > PORT > 8080）
EXPOSE 8080

CMD ["python", "main.py"]