"""转诊守门人AI智能体 - 数据模型定义"""

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class UrgencyLevel(str, Enum):
    """紧急程度等级"""
    ROUTINE = "routine"          # 常规转诊
    URGENT = "urgent"            # 紧急转诊（24小时内）
    EMERGENCY = "emergency"      # 急诊转诊（立即）


class Gender(str, Enum):
    """性别"""
    MALE = "male"
    FEMALE = "female"
    UNKNOWN = "unknown"


class PatientInfo(BaseModel):
    """患者信息"""
    age: int = Field(..., ge=0, le=150, description="患者年龄")
    gender: Gender = Field(default=Gender.UNKNOWN, description="性别")
    chief_complaint: str = Field(..., min_length=2, description="主诉/主要症状")
    present_illness: str = Field(default="", description="现病史")
    past_history: str = Field(default="", description="既往史")
    examination_findings: str = Field(default="", description="检查所见")
    current_diagnosis: str = Field(default="", description="目前诊断")
    vital_signs: dict = Field(default_factory=dict, description="生命体征")


class ReferralRequest(BaseModel):
    """转诊请求"""
    patient: PatientInfo = Field(..., description="患者信息")
    target_hospital: str = Field(..., min_length=2, description="目标医院名称")
    referring_doctor: str = Field(default="", description="转诊医生姓名")
    referring_institution: str = Field(default="", description="转出机构")
    notes: str = Field(default="", description="备注")


class DepartmentRecommendation(BaseModel):
    """科室推荐结果"""
    department: str = Field(..., description="推荐科室名称")
    score: float = Field(..., ge=0, le=1, description="匹配评分 0-1")
    confidence: str = Field(..., description="置信度描述")
    reasons: list[str] = Field(default_factory=list, description="推荐理由")
    matched_symptoms: list[str] = Field(default_factory=list, description="匹配的症状")
    matched_history: list[str] = Field(default_factory=list, description="匹配的病史")
    urgency: UrgencyLevel = Field(default=UrgencyLevel.ROUTINE, description="建议紧急程度")
    available_at_target: bool = Field(default=True, description="目标医院是否有该科室")


class PreReferralCheckItem(BaseModel):
    """转诊前必查项"""
    item: str = Field(..., description="检查项名称")
    reason: str = Field(..., description="必须排除的原因")
    severity: str = Field(..., description="未排除后果严重程度: high/medium/low")


class ReferralDecision(BaseModel):
    """转诊决策评估"""
    should_refer: bool = Field(..., description="是否建议转诊")
    urgency_level: UrgencyLevel = Field(..., description="紧急程度")
    rationale: str = Field(..., description="决策依据")
    risks_if_delayed: list[str] = Field(default_factory=list, description="延误风险")
    local_manageable: bool = Field(default=False, description="是否可基层处理")


class ReferralReport(BaseModel):
    """转诊建议报告（最终输出）"""
    request_id: str = Field(..., description="请求编号")
    decision: ReferralDecision = Field(..., description="转诊决策评估")
    recommendations: list[DepartmentRecommendation] = Field(
        default_factory=list, description="科室推荐列表"
    )
    pre_referral_checks: list[PreReferralCheckItem] = Field(
        default_factory=list, description="转诊前必查项"
    )
    target_hospital_departments: list[str] = Field(
        default_factory=list, description="目标医院可用科室"
    )
    disclaimer: str = Field(
        default="本建议由AI辅助生成，仅供参考。最终转诊决策与医疗责任由临床医生承担。",
        description="免责声明"
    )
    summary: str = Field(default="", description="综合建议摘要")


class HospitalInfo(BaseModel):
    """医院信息"""
    name: str = Field(..., description="医院名称")
    level: str = Field(default="", description="医院等级")
    departments: list[str] = Field(default_factory=list, description="科室列表")