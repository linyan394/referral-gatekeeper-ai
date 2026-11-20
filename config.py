"""转诊守门人AI智能体 - 全局配置"""

import os
from pathlib import Path

# 项目根目录
BASE_DIR = Path(__file__).resolve().parent

# 知识库目录
KNOWLEDGE_DIR = BASE_DIR / "knowledge"

# 知识库文件路径
DEPARTMENT_MAP_PATH = KNOWLEDGE_DIR / "department_map.json"
HOSPITAL_REGISTRY_PATH = KNOWLEDGE_DIR / "hospital_registry.json"
TRIAGE_RULES_PATH = KNOWLEDGE_DIR / "triage_rules.json"

# API服务配置
# 云平台（Render/Railway等）会注入PORT环境变量，优先级：GATEKEEPER_PORT > PORT > 8080
API_HOST = os.getenv("GATEKEEPER_HOST", "0.0.0.0")
API_PORT = int(os.getenv("GATEKEEPER_PORT", os.getenv("PORT", "8080")))

# 推荐引擎配置
MAX_RECOMMENDATIONS = 5        # 最多返回的推荐科室数量
MIN_SCORE_THRESHOLD = 0.15     # 最低推荐分数阈值
URGENCY_WEIGHT = 0.30          # 紧急程度权重
SYMPTOM_WEIGHT = 0.35          # 症状匹配权重
HISTORY_WEIGHT = 0.20          # 病史相关性权重
AGE_FACTOR_WEIGHT = 0.15       # 年龄因素权重

# 转诊校验配置
CRITICAL_KEYWORDS = [          # 危急重症关键词（需立即转诊）
    "休克", "昏迷", "呼吸衰竭", "心衰", "大出血",
    "主动脉夹层", "肺栓塞", "脑疝", "心脏骤停", "窒息",
]

# 日志配置
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")