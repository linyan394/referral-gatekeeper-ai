"""演示：用转诊守门人智能体处理一个真实案例"""
from core.agent import ReferralGatekeeperAgent
from models.schemas import PatientInfo, ReferralRequest


def main():
    agent = ReferralGatekeeperAgent()

    # 用户实际症状：22岁，受凉后嗓子疼、轻微流鼻涕，无发烧，精神好
    patient = PatientInfo(
        age=22,
        gender="unknown",
        chief_complaint="受凉后咽痛1天，伴轻微流涕",
        present_illness="昨天受凉后出现嗓子疼，轻微流鼻涕，无发烧，精神状态良好",
        past_history="既往体健",
        vital_signs={
            "temperature": 36.5,
            "systolic_bp": 118,
            "diastolic_bp": 76,
            "heart_rate": 78,
            "respiratory_rate": 16,
            "oxygen_saturation": 98
        }
    )

    request = ReferralRequest(
        patient=patient,
        target_hospital="县人民医院",
        referring_institution="社区卫生服务中心",
        notes="受凉后咽痛、流涕1天，无发热，精神状态良好"
    )

    report = agent.evaluate(request)

    print("=" * 60)
    print("         转诊守门人AI智能体 — 评估报告")
    print("=" * 60)
    print(f"\n请求编号: {report.request_id}")
    d = report.decision
    print(f"\n🏥 转诊决策: {'建议转诊' if d.should_refer else '可基层处理'} "
          f"(紧急度: {d.urgency_level.value})")
    print(f"   决策依据: {d.rationale}")
    print(f"   可基层处理: {'是' if d.local_manageable else '否'}")

    print("\n📋 推荐科室 (Top 3):")
    for i, rec in enumerate(report.recommendations[:3], 1):
        print(f"  {i}. {rec.department} (评分 {rec.score:.2f}, 置信度: {rec.confidence})")
        for reason in rec.reasons:
            print(f"     - {reason}")

    print("\n✅ 转诊前必查项:")
    if report.pre_referral_checks:
        for c in report.pre_referral_checks:
            print(f"  - [{c.severity}] {c.item}: {c.reason}")
    else:
        print("  无特殊必查项")

    print(f"\n💬 综合建议:\n{report.summary}")
    print(f"\n⚠️ 免责声明:\n{report.disclaimer}")


if __name__ == "__main__":
    main()