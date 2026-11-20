"""病情分析器 - 从医生输入中提取关键临床信息"""

import re
import logging
from dataclasses import dataclass, field

from models.schemas import PatientInfo

logger = logging.getLogger(__name__)


@dataclass
class AnalysisResult:
    """病情分析结果"""
    # 提取的症状关键词
    extracted_symptoms: list[str] = field(default_factory=list)
    # 提取的病史关键词
    extracted_history: list[str] = field(default_factory=list)
    # 提取的疾病关键词
    extracted_diseases: list[str] = field(default_factory=list)
    # 是否检测到危急重症信号
    has_emergency_signals: bool = False
    # 检测到的危急关键词
    emergency_keywords_found: list[str] = field(default_factory=list)
    # 生命体征异常
    abnormal_vitals: list[str] = field(default_factory=list)
    # 综合文本（用于匹配）
    full_text: str = ""


class ConditionAnalyzer:
    """病情分析器：解析患者病情文本，提取结构化关键信息"""

    # 生命体征异常阈值
    VITAL_THRESHOLDS = {
        "收缩压高": ("收缩压", 180),
        "收缩压低": ("收缩压", 90),
        "舒张压高": ("舒张压", 110),
        "心率过快": ("心率", 120),
        "心率过慢": ("心率", 50),
        "血氧低": ("血氧饱和度", 90),
        "体温高": ("体温", 38.5),
        "血糖高": ("血糖", 20),
        "血糖低": ("血糖", 3.0),
    }

    def analyze(self, patient: PatientInfo, knowledge_base) -> AnalysisResult:
        """分析患者病情，提取关键信息

        Args:
            patient: 患者信息
            knowledge_base: 知识库实例

        Returns:
            分析结果
        """
        # 拼接所有文本字段用于关键词匹配
        text_parts = [
            patient.chief_complaint,
            patient.present_illness,
            patient.past_history,
            patient.examination_findings,
            patient.current_diagnosis,
        ]
        full_text = " ".join(p for p in text_parts if p)

        result = AnalysisResult(full_text=full_text)

        # 遍历知识库中所有科室，提取匹配的关键词
        for dept in knowledge_base.departments:
            # 匹配症状关键词
            for kw in dept.get("symptom_keywords", []):
                if kw in full_text and kw not in result.extracted_symptoms:
                    result.extracted_symptoms.append(kw)

            # 匹配病史关键词
            for kw in dept.get("history_keywords", []):
                if kw in full_text and kw not in result.extracted_history:
                    result.extracted_history.append(kw)

            # 匹配疾病关键词
            for kw in dept.get("diseases", []):
                if kw in full_text and kw not in result.extracted_diseases:
                    result.extracted_diseases.append(kw)

            # 检测危急重症信号
            for kw in dept.get("emergency_keywords", []):
                if kw in full_text and kw not in result.emergency_keywords_found:
                    result.emergency_keywords_found.append(kw)

        # 全局危急关键词检测
        from config import CRITICAL_KEYWORDS
        for kw in CRITICAL_KEYWORDS:
            if kw in full_text and kw not in result.emergency_keywords_found:
                result.emergency_keywords_found.append(kw)

        result.has_emergency_signals = len(result.emergency_keywords_found) > 0

        # 检测生命体征异常
        result.abnormal_vitals = self._check_vitals(patient.vital_signs)

        if result.abnormal_vitals:
            result.has_emergency_signals = True

        logger.info(
            f"病情分析完成: 症状={len(result.extracted_symptoms)}, "
            f"病史={len(result.extracted_history)}, "
            f"危急信号={result.has_emergency_signals}"
        )
        return result

    def _check_vitals(self, vitals: dict) -> list[str]:
        """检测生命体征异常"""
        abnormal = []
        for label, (key, threshold) in self.VITAL_THRESHOLDS.items():
            if key in vitals:
                try:
                    value = float(vitals[key])
                    if "低" in label or "慢" in label:
                        if value < threshold:
                            abnormal.append(f"{key}{value}（{label}，阈值{threshold}）")
                    else:
                        if value > threshold:
                            abnormal.append(f"{key}{value}（{label}，阈值{threshold}）")
                except (ValueError, TypeError):
                    continue
        return abnormal

    def extract_numbers_from_text(self, text: str) -> dict:
        """从文本中提取数字指标（如血压160/100）"""
        vitals = {}
        # 血压模式: 160/100 或 收缩压160
        bp_match = re.search(r"血压\s*(\d{2,3})\s*/\s*(\d{2,3})", text)
        if bp_match:
            vitals["收缩压"] = int(bp_match.group(1))
            vitals["舒张压"] = int(bp_match.group(2))
        # 心率
        hr_match = re.search(r"心率\s*(\d{2,3})", text)
        if hr_match:
            vitals["心率"] = int(hr_match.group(1))
        # 体温
        temp_match = re.search(r"体温\s*(\d{2}\.\d)", text)
        if temp_match:
            vitals["体温"] = float(temp_match.group(1))
        return vitals