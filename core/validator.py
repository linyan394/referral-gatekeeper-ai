"""转诊校验器 - 三项核心校验：该不该转、往哪里转、转之前必须排除什么"""

import logging
from typing import Optional

from core.analyzer import AnalysisResult
from models.schemas import (
    PatientInfo, PreReferralCheckItem, ReferralDecision, UrgencyLevel
)

logger = logging.getLogger(__name__)


class ReferralValidator:
    """转诊校验器：执行转诊前的安全校验"""

    def evaluate_decision(
        self,
        patient: PatientInfo,
        analysis: AnalysisResult,
        knowledge_base,
    ) -> ReferralDecision:
        """评估是否应该转诊（第一项校验：该不该转）

        Returns:
            转诊决策评估
        """
        # 检测危急重症信号 -> 必须转诊
        if analysis.has_emergency_signals:
            urgency = UrgencyLevel.EMERGENCY
            rationale_parts = []
            if analysis.emergency_keywords_found:
                rationale_parts.append(
                    f"检测到危急信号：{', '.join(analysis.emergency_keywords_found[:5])}"
                )
            if analysis.abnormal_vitals:
                rationale_parts.append(
                    f"生命体征异常：{', '.join(analysis.abnormal_vitals[:3])}"
                )
            rationale_parts.append("病情危急，超出基层处理能力，需立即转诊上级医院")

            return ReferralDecision(
                should_refer=True,
                urgency_level=urgency,
                rationale="；".join(rationale_parts),
                risks_if_delayed=self._get_delay_risks(analysis),
                local_manageable=False,
            )

        # 有明确专科症状/病史 -> 建议转诊
        if analysis.extracted_symptoms or analysis.extracted_history:
            has_specialist_need = self._needs_specialist(
                analysis, knowledge_base
            )
            if has_specialist_need:
                return ReferralDecision(
                    should_refer=True,
                    urgency_level=UrgencyLevel.URGENT,
                    rationale=(
                        "患者存在需要专科评估的症状或病史，"
                        "建议转诊至上级医院相应专科进一步诊治"
                    ),
                    risks_if_delayed=["延误诊断", "病情进展风险"],
                    local_manageable=False,
                )

        # 无明确异常 -> 可基层处理，常规转诊可选
        return ReferralDecision(
            should_refer=False,
            urgency_level=UrgencyLevel.ROUTINE,
            rationale=(
                "当前病情未发现危急信号，且症状可在基层医疗机构处理。"
                "如医生判断有转诊必要，可常规转诊。"
            ),
            risks_if_delayed=[],
            local_manageable=True,
        )

    def get_pre_referral_checks(
        self,
        analysis: AnalysisResult,
        knowledge_base,
    ) -> list[PreReferralCheckItem]:
        """获取转诊前必查项（第三项校验：转之前必须排除什么）

        Returns:
            转诊前必查项列表
        """
        checks_data = knowledge_base.get_pre_referral_checks(
            analysis.extracted_symptoms
        )

        checks = []
        seen_items = set()
        for check in checks_data:
            item_name = check["item"]
            if item_name in seen_items:
                continue
            seen_items.add(item_name)
            checks.append(PreReferralCheckItem(
                item=item_name,
                reason=check["reason"],
                severity=check["severity"],
            ))

        # 危急重症额外检查
        if analysis.has_emergency_signals:
            if not any("生命体征" in c.item for c in checks):
                checks.insert(0, PreReferralCheckItem(
                    item="生命体征监测与稳定",
                    reason="转诊前必须确保生命体征相对稳定，必要时先行抢救",
                    severity="high",
                ))

        logger.info(f"生成转诊前必查项: {len(checks)}项")
        return checks

    def validate_target_hospital(
        self,
        hospital_name: str,
        recommendations: list,
        knowledge_base,
    ) -> dict:
        """校验目标医院是否满足转诊需求（第二项校验：往哪里转）

        Returns:
            校验结果，包含医院信息及科室可用性
        """
        hospital = knowledge_base.find_hospital(hospital_name)

        if not hospital:
            return {
                "found": False,
                "hospital": None,
                "departments": [],
                "missing_departments": [],
                "message": f"未在注册表中找到医院：{hospital_name}，请确认医院名称",
            }

        hospital_depts = set(hospital.get("departments", []))
        missing = []

        for rec in recommendations:
            if not rec.available_at_target:
                missing.append(rec.department)

        return {
            "found": True,
            "hospital": hospital,
            "departments": hospital.get("departments", []),
            "missing_departments": missing,
            "message": (
                "目标医院具备所有推荐科室"
                if not missing
                else f"目标医院缺少以下推荐科室：{', '.join(missing)}，建议调整目标医院或科室选择"
            ),
        }

    def _needs_specialist(self, analysis: AnalysisResult, knowledge_base) -> bool:
        """判断是否需要专科处理"""
        # 如果有明确疾病诊断关键词，需要专科
        if analysis.extracted_diseases:
            return True

        # 如果症状关键词数量较多，倾向于转诊
        if len(analysis.extracted_symptoms) >= 2:
            return True

        # 如果有病史关键词，可能需要专科随访
        if analysis.extracted_history:
            return True

        return False

    def _get_delay_risks(self, analysis: AnalysisResult) -> list[str]:
        """根据危急信号生成延误风险提示"""
        risks = []
        emergency_map = {
            "持续胸痛": "急性心肌梗死可致心源性猝死",
            "大咯血": "窒息风险",
            "休克": "多器官功能衰竭",
            "昏迷": "脑疝、呼吸抑制",
            "大出血": "失血性休克",
            "突发偏瘫": "脑卒中时间窗错过将失去溶栓机会",
            "呼吸衰竭": "缺氧性脑损伤",
            "主动脉夹层": "夹层破裂致死",
        }
        for kw in analysis.emergency_keywords_found:
            for risk_kw, risk_desc in emergency_map.items():
                if risk_kw in kw or kw in risk_kw:
                    if risk_desc not in risks:
                        risks.append(risk_desc)
        if not risks:
            risks.append("病情可能迅速恶化，延误转运增加不良预后风险")
        return risks