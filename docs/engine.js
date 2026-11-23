// 转诊守门人核心引擎（移植自 core/ 四模块，纯前端实现）
// 三项校验：该不该转 · 往哪里转 · 转之前必须排除什么

// ============ Step 1: 病情分析器（analyzer） ============
function analyze(patient) {
  const fullText = [patient.complaint, patient.history].filter(Boolean).join(" ");
  const result = {
    symptoms: [], history: [], diseases: [],
    emergencyKeywords: [], hasEmergency: false,
    abnormalVitals: [], fullText: fullText
  };
  for (const dept of DEPARTMENTS) {
    for (const kw of (dept.symptom_keywords || []))
      if (fullText.includes(kw) && !result.symptoms.includes(kw)) result.symptoms.push(kw);
    for (const kw of (dept.history_keywords || []))
      if (fullText.includes(kw) && !result.history.includes(kw)) result.history.push(kw);
    for (const kw of (dept.diseases || []))
      if (fullText.includes(kw) && !result.diseases.includes(kw)) result.diseases.push(kw);
    for (const kw of (dept.emergency_keywords || []))
      if (fullText.includes(kw) && !result.emergencyKeywords.includes(kw)) result.emergencyKeywords.push(kw);
  }
  for (const kw of CRITICAL_KEYWORDS)
    if (fullText.includes(kw) && !result.emergencyKeywords.includes(kw)) result.emergencyKeywords.push(kw);
  result.hasEmergency = result.emergencyKeywords.length > 0;

  // 生命体征：从文本提取 + 阈值校验
  const vitals = extractVitals(patient.vitalsText || "");
  for (const t of VITAL_THRESHOLDS) {
    if (vitals[t.key] !== undefined) {
      const v = parseFloat(vitals[t.key]);
      if (isNaN(v)) continue;
      const abnormal = (t.dir === "down") ? (v < t.threshold) : (v > t.threshold);
      if (abnormal) result.abnormalVitals.push(`${t.key}${v}（${t.label}，阈值${t.threshold}）`);
    }
  }
  if (result.abnormalVitals.length > 0) result.hasEmergency = true;
  return result;
}

function extractVitals(text) {
  const vitals = {};
  let m = /血压\s*(\d{2,3})\s*\/\s*(\d{2,3})/.exec(text);
  if (m) { vitals["收缩压"] = +m[1]; vitals["舒张压"] = +m[2]; }
  m = /心率\s*(\d{2,3})/.exec(text);
  if (m) vitals["心率"] = +m[1];
  m = /体温\s*(\d{1,2}\.\d)/.exec(text);
  if (m) vitals["体温"] = +m[1];
  return vitals;
}

// ============ Step 2: 科室推荐引擎（recommender） ============
function recommend(patient, analysis, targetDepts) {
  targetDepts = targetDepts || [];
  const scores = [];
  for (const dept of DEPARTMENTS) {
    const d = scoreDepartment(patient, analysis, dept);
    if (d.total >= CONFIG.MIN_SCORE_THRESHOLD) scores.push({ dept, detail: d });
  }
  scores.sort((a, b) => b.detail.total - a.detail.total);
  return scores.slice(0, CONFIG.MAX_RECOMMENDATIONS).map(item => buildRecommendation(item.dept, item.detail, analysis, patient, targetDepts));
}

function matchKeywords(extracted, deptKeywords) {
  if (!extracted.length || !deptKeywords.length) return [0, []];
  const matched = extracted.filter(kw => deptKeywords.includes(kw));
  if (!matched.length) return [0, []];
  const ratio = matched.length / deptKeywords.length;
  const coverage = matched.length / extracted.length;
  return [Math.min(ratio * 2 + coverage * 0.5, 1.0), matched];
}

function scoreDepartment(patient, analysis, dept) {
  const [symptomScore, matchedSymptoms] = matchKeywords(analysis.symptoms, dept.symptom_keywords || []);
  const [historyScore, matchedHistory] = matchKeywords(analysis.history, dept.history_keywords || []);
  const [diseaseScore, matchedDiseases] = matchKeywords(analysis.diseases, dept.diseases || []);

  // 紧急程度分
  let urgencyScore = 0;
  for (const found of analysis.emergencyKeywords)
    for (const dk of (dept.emergency_keywords || []))
      if (found.includes(dk) || dk.includes(found)) urgencyScore += 0.5;
  if (analysis.abnormalVitals.length && dept.name === "急诊科") urgencyScore += 0.5;
  urgencyScore = Math.min(urgencyScore, 1.0);

  // 年龄/性别适配分
  let ageGenderScore = 0;
  const [lo, hi] = dept.age_range || [0, 120];
  if (patient.age >= lo && patient.age <= hi) ageGenderScore += 0.3;
  else ageGenderScore = 0;
  if (ageGenderScore > 0) {
    if (patient.age <= 14 && dept.name === "儿科") ageGenderScore += 0.5;
    if (patient.age >= 65 && dept.name === "老年医学科") ageGenderScore += 0.3;
    if (dept.gender) {
      if (patient.gender === dept.gender) ageGenderScore += 0.4;
      else ageGenderScore = 0;
    }
    ageGenderScore = Math.min(ageGenderScore, 1.0);
  }

  const total = Math.min(
    symptomScore * CONFIG.SYMPTOM_WEIGHT +
    (historyScore * 0.5 + diseaseScore * 0.5) * CONFIG.HISTORY_WEIGHT +
    urgencyScore * CONFIG.URGENCY_WEIGHT +
    ageGenderScore * CONFIG.AGE_FACTOR_WEIGHT, 1.0);

  return {
    total: Math.round(total * 1000) / 1000, symptomScore, historyScore, diseaseScore,
    urgencyScore, ageGenderScore, matchedSymptoms, matchedHistory, matchedDiseases
  };
}

function buildRecommendation(dept, detail, analysis, patient, targetDepts) {
  const score = detail.total;
  const confidence = score >= 0.6 ? "高" : (score >= 0.35 ? "中" : "低");
  const reasons = [];
  if (detail.matchedSymptoms.length) reasons.push("症状匹配：" + detail.matchedSymptoms.slice(0, 5).join("，"));
  if (detail.matchedHistory.length) reasons.push("病史相关：" + detail.matchedHistory.slice(0, 3).join("，"));
  if (detail.matchedDiseases.length) reasons.push("诊断相关：" + detail.matchedDiseases.slice(0, 3).join("，"));
  if (detail.urgencyScore > 0) reasons.push("紧急程度提示：" + (dept.urgency_hint || "需紧急评估"));
  if (patient.age <= 14 && dept.name === "儿科") reasons.push("患者为儿童，优先儿科就诊");
  if (patient.age >= 65 && dept.name === "老年医学科") reasons.push("患者为老年，可综合评估多病共存问题");

  let available = true;
  if (targetDepts.length) {
    const set = new Set(targetDepts);
    available = set.has(dept.name) ||
      (dept.aliases || []).some(a => set.has(a)) ||
      targetDepts.some(td => dept.name.includes(td) || td.includes(dept.name));
  }

  let urgency = "routine";
  if (analysis.hasEmergency && detail.urgencyScore > 0.3) urgency = "emergency";
  else if (detail.urgencyScore > 0.2) urgency = "urgent";

  return { department: dept.name, score, confidence, reasons, urgency, available };
}

// ============ Step 3: 转诊校验器（validator） ============
function evaluateDecision(analysis) {
  if (analysis.hasEmergency) {
    const parts = [];
    if (analysis.emergencyKeywords.length) parts.push("检测到危急信号：" + analysis.emergencyKeywords.slice(0, 5).join("，"));
    if (analysis.abnormalVitals.length) parts.push("生命体征异常：" + analysis.abnormalVitals.slice(0, 3).join("，"));
    parts.push("病情危急，超出基层处理能力，需立即转诊上级医院");
    return { shouldRefer: true, urgency: "emergency", rationale: parts.join("；"),
             risks: getDelayRisks(analysis), localManageable: false };
  }
  if (analysis.symptoms.length || analysis.history.length) {
    const needSpec = analysis.diseases.length > 0 || analysis.symptoms.length >= 2 || analysis.history.length > 0;
    if (needSpec) {
      return { shouldRefer: true, urgency: "urgent",
        rationale: "患者存在需要专科评估的症状或病史，建议转诊至上级医院相应专科进一步诊治",
        risks: ["延误诊断", "病情进展风险"], localManageable: false };
    }
  }
  return { shouldRefer: false, urgency: "routine",
    rationale: "当前病情未发现危急信号，且症状可在基层医疗机构处理。如医生判断有转诊必要，可常规转诊。",
    risks: [], localManageable: true };
}

function getDelayRisks(analysis) {
  const risks = [];
  for (const kw of analysis.emergencyKeywords)
    for (const [riskKw, desc] of Object.entries(DELAY_RISKS))
      if (riskKw.includes(kw) || kw.includes(riskKw))
        if (!risks.includes(desc)) risks.push(desc);
  if (!risks.length) risks.push("病情可能迅速恶化，延误转运增加不良预后风险");
  return risks;
}

function getPreReferralChecks(analysis) {
  const checks = [];
  const seen = new Set();
  for (const group of PRE_REFERRAL_CHECKS) {
    const hit = analysis.symptoms.some(sym => group.applies_to_symptoms.some(t => t.includes(sym) || sym.includes(t)));
    if (!hit) continue;
    for (const c of group.checks) {
      if (seen.has(c.item)) continue;
      seen.add(c.item);
      checks.push(c);
    }
  }
  if (analysis.hasEmergency && !checks.some(c => c.item.includes("生命体征")))
    checks.unshift({ item: "生命体征监测与稳定", reason: "转诊前必须确保生命体征相对稳定，必要时先行抢救", severity: "high" });
  return checks;
}

function findHospital(name) {
  if (!name) return null;
  const n = name.trim();
  return HOSPITALS.find(h =>
    h.name === n ||
    (h.aliases || []).includes(n) ||
    h.name.includes(n) || n.includes(h.name) ||
    (h.aliases || []).some(a => a.includes(n) || n.includes(a))
  ) || null;
}

function validateTargetHospital(hospitalName, recommendations) {
  const hospital = findHospital(hospitalName);
  if (!hospital) return { found: false, hospital: null, missing: [],
    message: `未在注册表中找到医院：${hospitalName}，请确认医院名称` };
  const missing = recommendations.filter(r => !r.available).map(r => r.department);
  return { found: true, hospital, missing,
    message: missing.length ? `目标医院缺少以下推荐科室：${missing.join("，")}，建议调整目标医院或科室选择` : "目标医院具备所有推荐科室" };
}

// ============ Step 4: 智能体编排（agent） ============
function startEvaluation() {
  const age = parseInt(document.getElementById("age").value);
  if (isNaN(age)) { alert("请填写患者年龄"); return; }
  const complaint = document.getElementById("complaint").value.trim();
  if (!complaint) { alert("请填写主诉与现病史"); return; }
  const patient = {
    age: age,
    gender: document.getElementById("gender").value,
    complaint: complaint,
    history: document.getElementById("history").value.trim(),
    vitalsText: document.getElementById("vitals").value.trim(),
    targetHospital: document.getElementById("hospital").value.trim()
  };

  const analysis = analyze(patient);
  const decision = evaluateDecision(analysis);
  const hospital = findHospital(patient.targetHospital);
  const targetDepts = hospital ? hospital.departments : [];
  const recommendations = recommend(patient, analysis, targetDepts);
  const hospitalCheck = validateTargetHospital(patient.targetHospital, recommendations);
  const preChecks = getPreReferralChecks(analysis);
  const requestId = "REF-" + new Date().toISOString().replace(/[-:TZ.]/g, "").slice(0, 14) + "-" + Math.random().toString(16).slice(2, 10);

  renderReport(requestId, decision, recommendations, hospitalCheck, preChecks, analysis);
  document.getElementById("form-card").style.display = "none";
  document.getElementById("result").style.display = "block";
  window.scrollTo(0, 0);
}

function urgencyTag(level) {
  const map = {
    emergency: ["emergency", "🚨 立即转诊（争分夺秒，120转运）"],
    urgent: ["urgent", "⏰ 24小时内转诊"],
    routine: ["routine", "📅 常规转诊（1-2周内预约）"]
  };
  const [cls, text] = map[level];
  return `<span class="tag ${cls}">${text}</span>`;
}

function renderReport(requestId, decision, recommendations, hospitalCheck, preChecks, analysis) {
  let html = "";
  const highClass = decision.urgency === "emergency" ? "high" : "";

  // 一、该不该转
  html += `<div class="rpt-block ${highClass}"><h3>一、该不该转（转诊决策校验）</h3><ul>
<li>${decision.shouldRefer ? "<b>建议转诊</b>" : "<b>可基层处理</b>"} ${urgencyTag(decision.urgency)}</li>
<li>依据：${decision.rationale}</li>`;
  if (decision.risks.length) html += `<li>延误风险：${decision.risks.join("；")}</li>`;
  html += `</ul></div>`;

  // 二、往哪里转
  html += `<div class="rpt-block"><h3>二、往哪里转（科室推荐）</h3>`;
  if (recommendations.length) {
    recommendations.forEach(r => {
      html += `<div class="dept-item ${r.urgency === "emergency" ? "high" : ""}">
<b>${r.department}</b><span class="score">匹配度 ${(r.score * 100).toFixed(0)}% · 置信度${r.confidence} ${urgencyTag(r.urgency)}</span>
<div class="reason">${r.reasons.join("；") || "综合评估匹配"}</div>
${r.available ? "" : `<div class="reason" style="color:#c62828">⚠ 该目标医院可能缺少此科室，请核实</div>`}
</div>`;
    });
  } else {
    html += `<p>未找到明确匹配的推荐科室，请医生结合临床判断。</p>`;
  }
  if (patient2HospitalMsg(hospitalCheck)) html += `<p style="font-size:.85em">${hospitalCheck.message}</p>`;
  html += `</div>`;

  // 三、转之前必须排除什么
  html += `<div class="rpt-block"><h3>三、转之前必须排除什么（转诊前必查项）</h3>`;
  if (preChecks.length) {
    html += `<ul>`;
    for (const c of preChecks)
      html += `<li>${c.severity === "high" ? "🔴" : "🟡"} <b>${c.item}</b> —— ${c.reason}</li>`;
    html += `</ul>`;
  } else {
    html += `<p>当前症状暂无特定转诊前必查项，请按常规流程准备病历资料转诊。</p>`;
  }
  html += `</div>`;

  // 综合摘要
  html += `<div id="summary"><b>📋 综合建议（报告编号 ${requestId}）</b><br>${generateSummary(decision, recommendations, hospitalCheck, preChecks)}</div>`;

  // 危急警示
  if (decision.urgency === "emergency") {
    html = `<div class="warn">⚠️ <b>危急警示</b>：${analysis.emergencyKeywords.concat(analysis.abnormalVitals).slice(0, 5).join("，")} —— 请立即启动急救流程，先稳定生命体征再转运！</div>` + html;
  }

  document.getElementById("rpt").innerHTML = html;
}

function patient2HospitalMsg(hospitalCheck) {
  return hospitalCheck.message && hospitalCheck.message !== "目标医院具备所有推荐科室";
}

function generateSummary(decision, recommendations, hospitalCheck, preChecks) {
  const parts = [];
  if (decision.urgency === "emergency")
    parts.push("【急诊转诊】患者存在危急情况，建议立即通过120转运至目标医院急诊科，转运前确保生命体征稳定。");
  else if (decision.shouldRefer)
    parts.push("【建议转诊】患者病情需要专科评估，建议尽快转诊至目标医院。");
  else
    parts.push("【可基层处理】当前病情未发现危急信号，可在基层观察处理，如有转诊指征可择期转诊。");
  if (recommendations.length) {
    const top = recommendations[0];
    let desc = `首选推荐科室：${top.department}（匹配度${(top.score * 100).toFixed(0)}%，置信度${top.confidence}）`;
    if (recommendations.length > 1) desc += `；备选：${recommendations.slice(1, 3).map(r => r.department).join("、")}`;
    parts.push(desc);
  }
  if (hospitalCheck.found) {
    if (hospitalCheck.missing.length)
      parts.push(`注意：目标医院缺少部分推荐科室（${hospitalCheck.missing.join("，")}），请核实或考虑调整。`);
  } else {
    parts.push(hospitalCheck.message);
  }
  const highChecks = preChecks.filter(c => c.severity === "high");
  if (highChecks.length)
    parts.push(`转诊前必须完成的高优先级检查：${highChecks.slice(0, 3).map(c => c.item).join("、")}。`);
  parts.push("最终转诊决策请由临床医生综合判断。");
  return parts.join(" ");
}