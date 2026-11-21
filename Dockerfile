FROM python:3.12-slim

# Hugging Face Spaces 标准配置：非root用户
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user
WORKDIR $HOME/app

COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

COPY --chown=user . .

# HF Spaces 要求监听 7860 端口（config.py 优先读取 GATEKEEPER_PORT）
ENV GATEKEEPER_PORT=7860
EXPOSE 7860

CMD ["python", "main.py"]