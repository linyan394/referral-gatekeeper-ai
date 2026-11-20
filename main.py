"""转诊守门人AI智能体 - 主入口

启动FastAPI服务:
    python main.py
或:
    uvicorn main:app --host 0.0.0.0 --port 8080 --reload
"""

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

import config
from api.routes import router

# 配置日志
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# 创建FastAPI应用
app = FastAPI(
    title="转诊守门人AI智能体",
    description=(
        "嵌入基层医疗转诊决策节点的安全校验智能体。"
        "医生输入患者病情病史和目标医院，"
        "智能体完成三项校验：该不该转、往哪里转、转之前必须排除什么。"
        "最终决策权和医疗责任始终归属于医生。"
    ),
    version="1.0.0",
)

# 注册路由
app.include_router(router)


@app.on_event("startup")
async def startup_event():
    """服务启动事件"""
    logger.info("转诊守门人AI智能体服务启动中...")
    logger.info(f"监听地址: {config.API_HOST}:{config.API_PORT}")


@app.get("/", summary="智能体界面", response_class=HTMLResponse)
async def root():
    """返回智能体网页界面"""
    html_path = Path(__file__).parent / "static" / "index.html"
    if html_path.exists():
        return HTMLResponse(content=html_path.read_text(encoding="utf-8"))
    return HTMLResponse(
        content="<h1>转诊守门人AI智能体</h1><p>界面文件缺失，请访问 <a href='/docs'>/docs</a> 使用API文档界面</p>",
        status_code=200,
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=config.API_HOST,
        port=config.API_PORT,
        reload=False,
    )