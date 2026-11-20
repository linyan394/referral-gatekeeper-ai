"""知识库加载器 - 加载并管理医学知识库数据"""

import json
import logging
from functools import lru_cache
from typing import Optional

import config

logger = logging.getLogger(__name__)


def _load_json(path) -> dict:
    """加载JSON文件"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error(f"知识库文件不存在: {path}")
        return {}
    except json.JSONDecodeError as e:
        logger.error(f"知识库文件格式错误: {path}, {e}")
        return {}


class KnowledgeBase:
    """医学知识库管理器"""

    def __init__(self):
        self._department_map = None
        self._hospital_registry = None
        self._triage_rules = None

    @property
    def departments(self) -> list[dict]:
        """获取科室映射列表"""
        if self._department_map is None:
            self._department_map = _load_json(config.DEPARTMENT_MAP_PATH)
        return self._department_map.get("departments", [])

    @property
    def hospitals(self) -> list[dict]:
        """获取医院注册列表"""
        if self._hospital_registry is None:
            self._hospital_registry = _load_json(config.HOSPITAL_REGISTRY_PATH)
        return self._hospital_registry.get("hospitals", [])

    @property
    def triage_rules(self) -> dict:
        """获取分诊规则"""
        if self._triage_rules is None:
            self._triage_rules = _load_json(config.TRIAGE_RULES_PATH)
        return self._triage_rules

    def find_hospital(self, name: str) -> Optional[dict]:
        """根据名称或别名查找医院信息"""
        name = name.strip()
        for hospital in self.hospitals:
            if hospital["name"] == name:
                return hospital
            if name in hospital.get("aliases", []):
                return hospital
            # 模糊匹配：名称包含
            if name in hospital["name"] or hospital["name"] in name:
                return hospital
            for alias in hospital.get("aliases", []):
                if alias in name or name in alias:
                    return hospital
        return None

    def get_department_by_name(self, dept_name: str) -> Optional[dict]:
        """根据科室名或别名查找科室定义"""
        for dept in self.departments:
            if dept["name"] == dept_name:
                return dept
            if dept_name in dept.get("aliases", []):
                return dept
        return None

    def get_pre_referral_checks(self, symptoms: list[str]) -> list[dict]:
        """根据症状获取转诊前必查项"""
        checks = []
        for rule in self.triage_rules.get("pre_referral_checks", []):
            applies = rule.get("applies_to_symptoms", [])
            for symptom in symptoms:
                for trigger in applies:
                    if trigger in symptom or symptom in trigger:
                        for check in rule.get("checks", []):
                            if check not in checks:
                                checks.append(check)
                        break
        return checks

    def get_urgency_rule(self, level: str) -> Optional[dict]:
        """获取指定紧急程度的规则"""
        for rule in self.triage_rules.get("urgency_rules", []):
            if rule["level"] == level:
                return rule
        return None


@lru_cache(maxsize=1)
def get_knowledge_base() -> KnowledgeBase:
    """获取知识库单例"""
    return KnowledgeBase()