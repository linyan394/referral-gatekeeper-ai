"""科室推荐引擎 - 基于多维度评分推荐最适合的转诊科室"""

import logging
from typing import Optional

import config
from core.analyzer import AnalysisResult
from models.schemas import (
    DepartmentRecommendation, PatientInfo, UrgencyLevel
)

logger = logging.getLogger(__name__)


class DepartmentRecommender:
    """科室推荐引擎：多维度评分（症状匹配、病史相关性、紧急程度、年龄因素）"""

    def recommend(
        self,
        patient: PatientInfo,
        analysis: AnalysisResult,
        knowledge_base,
        target_hospital_depts: Optional[list[str]] = None,
    ) -> list[DepartmentRecommendation]:
        """生成科室推荐列表

        Args:
            patient: 患者信息
            analysis: 病情分析结果
            knowledge_base: 知识库
            target_hospital_depts: 目标医院科室列表

        Returns:
            按评分降序排列的科室推荐列表
        """
        target_hospital_depts = target_hospital_depts or []
        scores: list[dict] = []

        for dept in knowledge_base.departments:
            dept_name = dept["name"]
            score_detail = self._score_department(
                patient, analysis, dept, target_hospital_depts
            )
            if score_detail["total"] >= config.MIN_SCORE_THRESHOLD:
                scores.append({
                    "department": dept,
                    "score_detail": score_detail,
                })

        # 按总分降序排序
        scores.sort(key=lambda x: x["score_detail"]["total"], reverse=True)

        # 截取前N个
        scores = scores[: config.MAX_RECOMMENDATIONS]

        # 构建推荐结果
        recommendations = []
        for item in scores:
            dept = item["department"]
            detail = item["score_detail"]
            rec = self._build_recommendation(
                dept, detail, analysis, patient, target_hospital_depts
            )
            recommendations.append(rec)

        # 如果目标医院缺少推荐科室，添加提示
        for rec in recommendations:
            if not rec.available_at_target:
                logger.warning(
                    f"目标医院缺少推荐科室: {rec.department}"
                )

        return recommendations

    def _score_department(
        self,
        patient: PatientInfo,
        analysis: AnalysisResult,
        dept: dict,
        target_depts: list[str],
    ) -> dict:
        """计算单个科室的综合评分"""
        # 1. 症状匹配分
        symptom_score, matched_symptoms = self._match_keywords(
            analysis.extracted_symptoms, dept.get("symptom_keywords", [])
        )

        # 2. 病史匹配分
        history_score, matched_history = self._match_keywords(
            analysis.extracted_history, dept.get("history_keywords", [])
        )

        # 3. 疾病匹配分（直接诊断加分）
        disease_score, matched_diseases = self._match_keywords(
            analysis.extracted_diseases, dept.get("diseases", [])
        )

        # 4. 紧急程度分
        urgency_score = self._urgency_score(analysis, dept)

        # 5. 年龄/性别适配分
        age_gender_score = self._age_gender_score(patient, dept)

        # 加权计算
        symptom_weighted = symptom_score * config.SYMPTOM_WEIGHT
        history_weighted = (
            (history_score * 0.5 + disease_score * 0.5) * config.HISTORY_WEIGHT
        )
        urgency_weighted = urgency_score * config.URGENCY_WEIGHT
        age_weighted = age_gender_score * config.AGE_FACTOR_WEIGHT

        total = min(
            symptom_weighted + history_weighted + urgency_weighted + age_weighted,
            1.0,
        )

        return {
            "total": round(total, 3),
            "symptom_score": round(symptom_score, 3),
            "history_score": round(history_score, 3),
            "disease_score": round(disease_score, 3),
            "urgency_score": round(urgency_score, 3),
            "age_gender_score": round(age_gender_score, 3),
            "matched_symptoms": matched_symptoms,
            "matched_history": matched_history,
            "matched_diseases": matched_diseases,
        }

    def _match_keywords(
        self, extracted: list[str], dept_keywords: list[str]
    ) -> tuple[float, list[str]]:
        """计算关键词匹配分

        Returns:
            (匹配分0-1, 匹配到的关键词列表)
        """
        if not extracted or not dept_keywords:
            return 0.0, []
        matched = [kw for kw in extracted if kw in dept_keywords]
        if not matched:
            return 0.0, []
        # 匹配率 = 匹配数 / 该科室关键词数，同时考虑匹配绝对数
        ratio = len(matched) / len(dept_keywords)
        coverage = len(matched) / len(extracted)
        # 取两者加权，保证多匹配多得分
        score = min(ratio * 2 + coverage * 0.5, 1.0)
        return score, matched

    def _urgency_score(self, analysis: AnalysisResult, dept: dict) -> float:
        """紧急程度评分"""
        score = 0.0
        # 危急关键词出现在该科室的emergency_keywords中，加分
        dept_emergency_kw = dept.get("emergency_keywords", [])
        for found in analysis.emergency_keywords_found:
            for dept_kw in dept_emergency_kw:
                if found in dept_kw or dept_kw in found:
                    score += 0.5
        # 生命体征异常时，急诊科加分
        if analysis.abnormal_vitals:
            if dept["name"] == "急诊科":
                score += 0.5
        return min(score, 1.0)

    def _age_gender_score(self, patient: PatientInfo, dept: dict) -> float:
        """年龄/性别适配评分"""
        score = 0.0
        age = patient.age

        # 年龄范围检查
        age_range = dept.get("age_range", [0, 120])
        if age_range[0] <= age <= age_range[1]:
            score += 0.3
        else:
            return 0.0  # 不在年龄范围内，直接0分

        # 儿科特殊规则
        if age <= 14 and dept["name"] == "儿科":
            score += 0.5

        # 老年科特殊规则
        if age >= 65 and dept["name"] == "老年医学科":
            score += 0.3

        # 性别规则
        gender = dept.get("gender")
        if gender:
            if patient.gender.value == gender:
                score += 0.4
            else:
                return 0.0  # 性别不符，0分

        return min(score, 1.0)

    def _build_recommendation(
        self,
        dept: dict,
        detail: dict,
        analysis: AnalysisResult,
        patient: PatientInfo,
        target_depts: list[str],
    ) -> DepartmentRecommendation:
        """构建科室推荐对象"""
        dept_name = dept["name"]
        score = detail["total"]

        # 确定置信度
        if score >= 0.6:
            confidence = "高"
        elif score >= 0.35:
            confidence = "中"
        else:
            confidence = "低"

        # 构建推荐理由
        reasons = []
        if detail["matched_symptoms"]:
            reasons.append(
                f"症状匹配：{', '.join(detail['matched_symptoms'][:5])}"
            )
        if detail["matched_history"]:
            reasons.append(
                f"病史相关：{', '.join(detail['matched_history'][:3])}"
            )
        if detail["matched_diseases"]:
            reasons.append(
                f"诊断相关：{', '.join(detail['matched_diseases'][:3])}"
            )
        if detail["urgency_score"] > 0:
            reasons.append(
                f"紧急程度提示：{dept.get('urgency_hint', '需紧急评估')}"
            )
        if patient.age <= 14 and dept_name == "儿科":
            reasons.append("患者为儿童，优先儿科就诊")
        if patient.age >= 65 and dept_name == "老年医学科":
            reasons.append("患者为老年，可综合评估多病共存问题")

        # 判断目标医院是否有该科室
        available = True
        if target_depts:
            all_names = set(target_depts)
            # 也检查别名
            available = (
                dept_name in all_names
                or any(a in all_names for a in dept.get("aliases", []))
                or any(dept_name in td or td in dept_name for td in target_depts)
            )

        # 确定建议紧急程度
        urgency = UrgencyLevel.ROUTINE
        if analysis.has_emergency_signals and detail["urgency_score"] > 0.3:
            urgency = UrgencyLevel.EMERGENCY
        elif detail["urgency_score"] > 0.2:
            urgency = UrgencyLevel.URGENT

        return DepartmentRecommendation(
            department=dept_name,
            score=score,
            confidence=confidence,
            reasons=reasons,
            matched_symptoms=detail["matched_symptoms"],
            matched_history=detail["matched_history"],
            urgency=urgency,
            available_at_target=available,
        )