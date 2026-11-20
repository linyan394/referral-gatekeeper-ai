"""转诊守门人AI智能体 - 测试用例"""

import sys
import os

# 确保项目根目录在sys.path中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.agent import ReferralGatekeeperAgent
from core.analyzer import ConditionAnalyzer
from core.recommender import DepartmentRecommender
from core.validator import ReferralValidator
from knowledge.loader import get_knowledge_base
from models.schemas import (
    Gender, PatientInfo, ReferralRequest, UrgencyLevel,
)


# ==================== 测试辅助 ====================

def make_patient(
    age=50,
    gender=Gender.MALE,
    chief_complaint="",
    present_illness="",
    past_history="",
    examination_findings="",
    current_diagnosis="",
    vital_signs=None,
) -> PatientInfo:
    """快速构建患者信息"""
    return PatientInfo(
        age=age,
        gender=gender,
        chief_complaint=chief_complaint,
        present_illness=present_illness,
        past_history=past_history,
        examination_findings=examination_findings,
        current_diagnosis=current_diagnosis,
        vital_signs=vital_signs or {},
    )


def make_request(patient: PatientInfo, hospital="省人民医院") -> ReferralRequest:
    """快速构建转诊请求"""
    return ReferralRequest(
        patient=patient,
        target_hospital=hospital,
        referring_doctor="测试医生",
        referring_institution="测试社区卫生服务中心",
    )


# ==================== 知识库测试 ====================

class TestKnowledgeBase:
    """知识库加载测试"""

    def test_departments_loaded(self):
        kb = get_knowledge_base()
        assert len(kb.departments) >= 20, "科室知识库应包含至少20个科室"

    def test_hospitals_loaded(self):
        kb = get_knowledge_base()
        assert len(kb.hospitals) >= 5, "医院注册表应包含至少5家医院"

    def test_triage_rules_loaded(self):
        kb = get_knowledge_base()
        rules = kb.triage_rules
        assert "urgency_rules" in rules
        assert "pre_referral_checks" in rules

    def test_find_hospital_by_name(self):
        kb = get_knowledge_base()
        hospital = kb.find_hospital("北京协和医院")
        assert hospital is not None
        assert hospital["level"] == "三级甲等"

    def test_find_hospital_by_alias(self):
        kb = get_knowledge_base()
        hospital = kb.find_hospital("协和")
        assert hospital is not None
        assert "协和" in hospital["name"]

    def test_find_hospital_not_found(self):
        kb = get_knowledge_base()
        hospital = kb.find_hospital("不存在的医院")
        assert hospital is None


# ==================== 病情分析器测试 ====================

class TestConditionAnalyzer:
    """病情分析器测试"""

    def test_extract_cardiac_symptoms(self):
        analyzer = ConditionAnalyzer()
        kb = get_knowledge_base()
        patient = make_patient(
            chief_complaint="反复胸痛3天，伴胸闷、心悸",
            past_history="高血压病史10年",
        )
        result = analyzer.analyze(patient, kb)
        assert "胸痛" in result.extracted_symptoms
        assert "胸闷" in result.extracted_symptoms
        assert "心悸" in result.extracted_symptoms
        assert "高血压" in result.extracted_history

    def test_detect_emergency_signal(self):
        analyzer = ConditionAnalyzer()
        kb = get_knowledge_base()
        patient = make_patient(
            chief_complaint="突发剧烈胸痛伴大汗2小时",
            present_illness="持续胸痛不缓解，有濒死感",
        )
        result = analyzer.analyze(patient, kb)
        assert result.has_emergency_signals is True
        assert len(result.emergency_keywords_found) > 0

    def test_abnormal_vitals_detection(self):
        analyzer = ConditionAnalyzer()
        kb = get_knowledge_base()
        patient = make_patient(
            chief_complaint="头晕",
            vital_signs={"收缩压": 200, "舒张压": 120, "心率": 130},
        )
        result = analyzer.analyze(patient, kb)
        assert len(result.abnormal_vitals) >= 2

    def test_no_symptoms_matched(self):
        analyzer = ConditionAnalyzer()
        kb = get_knowledge_base()
        patient = make_patient(chief_complaint="感觉不太舒服")
        result = analyzer.analyze(patient, kb)
        assert len(result.extracted_symptoms) == 0
        assert result.has_emergency_signals is False


# ==================== 科室推荐引擎测试 ====================

class TestDepartmentRecommender:
    """科室推荐引擎测试"""

    def test_cardiac_recommendation(self):
        analyzer = ConditionAnalyzer()
        recommender = DepartmentRecommender()
        kb = get_knowledge_base()
        patient = make_patient(
            age=60,
            chief_complaint="反复胸痛、胸闷1周",
            past_history="高血压、冠心病",
        )
        analysis = analyzer.analyze(patient, kb)
        recs = recommender.recommend(patient, analysis, kb)
        assert len(recs) > 0
        assert recs[0].department == "心血管内科"
        assert recs[0].score > 0.3

    def test_pediatric_priority(self):
        analyzer = ConditionAnalyzer()
        recommender = DepartmentRecommender()
        kb = get_knowledge_base()
        patient = make_patient(
            age=5,
            chief_complaint="小儿发热、咳嗽3天",
        )
        analysis = analyzer.analyze(patient, kb)
        recs = recommender.recommend(patient, analysis, kb)
        assert recs[0].department == "儿科"

    def test_gynecology_gender_filter(self):
        analyzer = ConditionAnalyzer()
        recommender = DepartmentRecommender()
        kb = get_knowledge_base()
        patient = make_patient(
            age=30,
            gender=Gender.FEMALE,
            chief_complaint="停经后腹痛伴阴道出血",
        )
        analysis = analyzer.analyze(patient, kb)
        recs = recommender.recommend(patient, analysis, kb)
        dept_names = [r.department for r in recs]
        assert "妇产科" in dept_names

    def test_target_hospital_availability(self):
        analyzer = ConditionAnalyzer()
        recommender = DepartmentRecommender()
        kb = get_knowledge_base()
        patient = make_patient(
            age=60,
            chief_complaint="胸痛、心悸",
        )
        analysis = analyzer.analyze(patient, kb)
        # 县医院没有心胸外科等科室
        county_depts = kb.find_hospital("县人民医院")["departments"]
        recs = recommender.recommend(patient, analysis, kb, county_depts)
        for rec in recs:
            if rec.department not in county_depts:
                assert rec.available_at_target is False


# ==================== 转诊校验器测试 ====================

class TestReferralValidator:
    """转诊校验器测试"""

    def test_emergency_decision(self):
        analyzer = ConditionAnalyzer()
        validator = ReferralValidator()
        kb = get_knowledge_base()
        patient = make_patient(
            chief_complaint="突发意识障碍、大汗",
            vital_signs={"收缩压": 70},
        )
        analysis = analyzer.analyze(patient, kb)
        decision = validator.evaluate_decision(patient, analysis, kb)
        assert decision.should_refer is True
        assert decision.urgency_level == UrgencyLevel.EMERGENCY

    def test_routine_decision(self):
        analyzer = ConditionAnalyzer()
        validator = ReferralValidator()
        kb = get_knowledge_base()
        patient = make_patient(
            chief_complaint="偶尔感觉有点累",
        )
        analysis = analyzer.analyze(patient, kb)
        decision = validator.evaluate_decision(patient, analysis, kb)
        assert decision.local_manageable is True

    def test_pre_referral_checks_for_chest_pain(self):
        analyzer = ConditionAnalyzer()
        validator = ReferralValidator()
        kb = get_knowledge_base()
        patient = make_patient(chief_complaint="胸痛、胸闷")
        analysis = analyzer.analyze(patient, kb)
        checks = validator.get_pre_referral_checks(analysis, kb)
        check_items = [c.item for c in checks]
        assert "心电图" in check_items
        assert "心肌酶谱/肌钙蛋白" in check_items

    def test_hospital_validation(self):
        validator = ReferralValidator()
        kb = get_knowledge_base()
        result = validator.validate_target_hospital("协和医院", [], kb)
        assert result["found"] is True


# ==================== 智能体集成测试 ====================

class TestReferralGatekeeperAgent:
    """智能体端到端集成测试"""

    def test_full_evaluation_cardiac(self):
        """测试心血管内科场景的完整评估"""
        agent = ReferralGatekeeperAgent()
        request = make_request(
            make_patient(
                age=65,
                gender=Gender.MALE,
                chief_complaint="反复胸痛1周，加重伴大汗2小时",
                present_illness="胸骨后压榨感，向左肩放射，持续不缓解",
                past_history="高血压15年，吸烟史30年",
                examination_findings="心电图示ST段抬高",
                vital_signs={"收缩压": 160, "舒张压": 95, "心率": 100},
            ),
            hospital="北京协和医院",
        )
        report = agent.evaluate(request)
        assert report.request_id.startswith("REF-")
        assert report.decision.should_refer is True
        assert report.decision.urgency_level in [
            UrgencyLevel.EMERGENCY, UrgencyLevel.URGENT
        ]
        assert len(report.recommendations) > 0
        assert report.recommendations[0].department == "心血管内科"
        assert len(report.recommendations[0].reasons) > 0
        assert "心电图" in [c.item for c in report.pre_referral_checks]
        assert len(report.target_hospital_departments) > 0
        assert "最终" in report.summary or "建议" in report.summary

    def test_full_evaluation_stroke(self):
        """测试脑卒中场景"""
        agent = ReferralGatekeeperAgent()
        request = make_request(
            make_patient(
                age=70,
                chief_complaint="突发右侧肢体无力、言语不清2小时",
                past_history="房颤病史",
            ),
            hospital="华西医院",
        )
        report = agent.evaluate(request)
        assert report.decision.should_refer is True
        dept_names = [r.department for r in report.recommendations]
        assert "神经内科" in dept_names

    def test_full_evaluation_pediatric(self):
        """测试儿科场景"""
        agent = ReferralGatekeeperAgent()
        request = make_request(
            make_patient(
                age=3,
                chief_complaint="小儿发热3天，咳嗽加重",
                present_illness="体温最高39.5度，精神差",
            ),
            hospital="省人民医院",
        )
        report = agent.evaluate(request)
        assert report.recommendations[0].department == "儿科"

    def test_full_evaluation_routine(self):
        """测试常规轻症场景"""
        agent = ReferralGatekeeperAgent()
        request = make_request(
            make_patient(
                age=30,
                chief_complaint="最近有点乏力",
            ),
            hospital="市中心医院",
        )
        report = agent.evaluate(request)
        assert report.decision.local_manageable is True

    def test_unknown_hospital(self):
        """测试未知医院场景"""
        agent = ReferralGatekeeperAgent()
        request = make_request(
            make_patient(
                age=50,
                chief_complaint="胸痛",
            ),
            hospital="某未知医院",
        )
        report = agent.evaluate(request)
        assert report.request_id  # 仍然能生成报告
        assert len(report.target_hospital_departments) == 0


if __name__ == "__main__":
    # 简单运行器
    import traceback
    test_classes = [
        TestKnowledgeBase, TestConditionAnalyzer, TestDepartmentRecommender,
        TestReferralValidator, TestReferralGatekeeperAgent,
    ]
    total = 0
    passed = 0
    for test_class in test_classes:
        instance = test_class()
        methods = [m for m in dir(instance) if m.startswith("test_")]
        for method_name in methods:
            total += 1
            try:
                getattr(instance, method_name)()
                passed += 1
                print(f"  PASS: {test_class.__name__}.{method_name}")
            except Exception as e:
                print(f"  FAIL: {test_class.__name__}.{method_name}: {e}")
                traceback.print_exc()
    print(f"\n结果: {passed}/{total} 通过")