"""API路由 - 转诊守门人智能体REST接口"""

import logging

from fastapi import APIRouter, HTTPException

from core.agent import ReferralGatekeeperAgent
from models.schemas import (
    HospitalInfo, ReferralReport, ReferralRequest,
)
from knowledge.loader import get_knowledge_base

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["转诊守门人"])

# 全局智能体实例
_agent = ReferralGatekeeperAgent()


@router.post(
    "/referral/evaluate",
    response_model=ReferralReport,
    summary="转诊评估",
    description="医生输入患者病情病史和目标医院，智能体分析最适合转入的科室及原因",
)
async def evaluate_referral(request: ReferralRequest) -> ReferralReport:
    """执行转诊评估，返回结构化转诊建议报告"""
    try:
        report = _agent.evaluate(request)
        return report
    except Exception as e:
        logger.error(f"转诊评估失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"评估失败: {str(e)}")


@router.get(
    "/hospitals",
    response_model=list[HospitalInfo],
    summary="查询已注册医院列表",
)
async def list_hospitals() -> list[HospitalInfo]:
    """获取知识库中所有已注册的医院信息"""
    kb = get_knowledge_base()
    return [
        HospitalInfo(
            name=h["name"],
            level=h.get("level", ""),
            departments=h.get("departments", []),
        )
        for h in kb.hospitals
    ]


@router.get(
    "/hospitals/{hospital_name}",
    response_model=HospitalInfo,
    summary="查询指定医院信息",
)
async def get_hospital(hospital_name: str) -> HospitalInfo:
    """获取指定医院的科室信息"""
    kb = get_knowledge_base()
    hospital = kb.find_hospital(hospital_name)
    if not hospital:
        raise HTTPException(
            status_code=404,
            detail=f"未找到医院: {hospital_name}",
        )
    return HospitalInfo(
        name=hospital["name"],
        level=hospital.get("level", ""),
        departments=hospital.get("departments", []),
    )


@router.get(
    "/departments",
    response_model=list[str],
    summary="查询所有科室列表",
)
async def list_departments() -> list[str]:
    """获取知识库中所有科室名称"""
    kb = get_knowledge_base()
    return [d["name"] for d in kb.departments]


@router.get(
    "/health",
    summary="健康检查",
)
async def health_check() -> dict:
    """服务健康检查"""
    return {
        "status": "ok",
        "service": "转诊守门人AI智能体",
        "knowledge_base_loaded": len(get_knowledge_base().departments) > 0,
    }