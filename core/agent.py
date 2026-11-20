"""转诊守门人智能体 - 核心编排模块

职责：在医生做出转诊决定之前，完成三项校验：
1. 该不该转（转诊决策评估）
2. 往哪里转（科室推荐）
3. 转之前必须排除什么（转诊前必查项）

最终决策权和医疗责任始终归属于医生。
"""

import logging
import uuid
from datetime import datetime

from core.analyzer import ConditionAnalyzer
from core.recommender import DepartmentRecommender
from core.validator import ReferralValidator
from knowledge.loader import get_knowledge_base
from models.schemas import ReferralRequest, ReferralReport

logger = logging.getLogger(__name__)


class ReferralGatekeeperAgent:
    """转诊守门人AI智能体

    工作流程：
    1. 接收转诊请求（患者病情 + 目标医院）
    2. 病情分析：提取症状、病史、危急信号
    3. 转诊决策校验：该不该转
    4. 科室推荐：往哪里转（多维度评分）
    5. 转诊前校验：转之前必须排除什么
    6. 生成结构化转诊建议报告
    """

    def __init__(self):
        self.knowledge_base = get_knowledge_base()
        self.analyzer = ConditionAnalyzer()
        self.recommender = DepartmentRecommender()
        self.validator = ReferralValidator()

    def evaluate(self, request: ReferralRequest) -> ReferralReport:
        """执行完整的转诊评估流程

        Args:
            request: 转诊请求（含患者信息和目标医院）

        Returns:
            结构化转诊建议报告
        """
        request_id = self._generate_request_id()

        logger.info(
            f"[{request_id}] 开始转诊评估: "
            f"患者{request.patient.age}岁, "
            f"目标医院={request.target_hospital}"
        )

        # Step 1: 病情分析
        analysis = self.analyzer.analyze(
            request.patient, self.knowledge_base
        )

        # Step 2: 转诊决策评估（该不该转）
        decision = self.validator.evaluate_decision(
            request.patient, analysis, self.knowledge_base
        )

        # Step 3: 查找目标医院信息
        hospital = self.knowledge_base.find_hospital(
            request.target_hospital
        )
        target_depts = hospital.get("departments", []) if hospital else []

        # Step 4: 科室推荐（往哪里转）
        recommendations = self.recommender.recommend(
            request.patient, analysis, self.knowledge_base, target_depts
        )

        # Step 5: 目标医院校验
        hospital_validation = self.validator.validate_target_hospital(
            request.target_hospital, recommendations, self.knowledge_base
        )

        # Step 6: 转诊前必查项（转之前必须排除什么）
        pre_checks = self.validator.get_pre_referral_checks(
            analysis, self.knowledge_base
        )

        # Step 7: 生成综合摘要
        summary = self._generate_summary(
            request, decision, recommendations, hospital_validation, pre_checks
        )

        report = ReferralReport(
            request_id=request_id,
            decision=decision,
            recommendations=recommendations,
            pre_referral_checks=pre_checks,
            target_hospital_departments=target_depts,
            summary=summary,
        )

        logger.info(
            f"[{request_id}] 转诊评估完成: "
            f"建议转诊={decision.should_refer}, "
            f"紧急程度={decision.urgency_level.value}, "
            f"推荐科室数={len(recommendations)}"
        )

        return report

    def _generate_request_id(self) -> str:
        """生成请求编号"""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        short_uuid = uuid.uuid4().hex[:8]
        return f"REF-{timestamp}-{short_uuid}"

    def _generate_summary(
        self,
        request: ReferralRequest,
        decision,
        recommendations: list,
        hospital_validation: dict,
        pre_checks: list,
    ) -> str:
        """生成综合建议摘要"""
        parts = []

        # 转诊决策
        if decision.urgency_level.value == "emergency":
            parts.append(
                "【急诊转诊】患者存在危急情况，建议立即通过120转运至目标医院急诊科，"
                "转运前确保生命体征稳定。"
            )
        elif decision.should_refer:
            parts.append(
                "【建议转诊】患者病情需要专科评估，建议尽快转诊至目标医院。"
            )
        else:
            parts.append(
                "【可基层处理】当前病情未发现危急信号，可在基层观察处理，"
                "如有转诊指征可择期转诊。"
            )

        # 推荐科室
        if recommendations:
            top_rec = recommendations[0]
            dept_desc = f"首选推荐科室：{top_rec.department}（匹配度{top_rec.score:.0%}，置信度{top_rec.confidence}）"
            if len(recommendations) > 1:
                others = "、".join(r.department for r in recommendations[1:3])
                dept_desc += f"；备选：{others}"
            parts.append(dept_desc)

        # 目标医院校验
        if hospital_validation["found"]:
            if hospital_validation["missing_departments"]:
                parts.append(
                    f"注意：目标医院缺少部分推荐科室（{', '.join(hospital_validation['missing_departments'])}），"
                    "请核实或考虑调整。"
                )
        else:
            parts.append(hospital_validation["message"])

        # 转诊前必查
        high_checks = [c for c in pre_checks if c.severity == "high"]
        if high_checks:
            check_names = "、".join(c.item for c in high_checks[:3])
            parts.append(
                f"转诊前必须完成的高优先级检查：{check_names}。"
            )

        parts.append("最终转诊决策请由临床医生综合判断。")

        return " ".join(parts)