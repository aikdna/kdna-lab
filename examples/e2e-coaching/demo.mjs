#!/usr/bin/env node
/**
 * KDNA E2E Coaching Demo
 *
 * Demonstrates the full protocol chain:
 *   KDNA load → Pipeline (3 stages) → ArtifactEnvelope → Fidelity Measure → FidelityResult
 *
 * All pure data flow — no LLM calls, no external dependencies.
 * Runs with: node demo.mjs
 */

// ─── Stage 1: Simulate KDNA domain loading ───
const loadedKdna = {
  name: "@aikdna/writing",
  version: "0.7.2",
  judgmentVersion: "2026.05",
  role: "primary",
  axioms: [
    {
      id: "diagnose_before_polish",
      oneSentence: "Diagnose before polishing.",
      fullStatement: "When reviewing content, diagnose structure before language.",
      appliesWhen: ["User asks to review content"],
      doesNotApplyWhen: ["User explicitly asks for grammar check only"],
      failureRisk: "Surface polishing on structurally weak content wastes effort.",
    },
    {
      id: "audience_before_prose",
      oneSentence: "Define audience before writing.",
      fullStatement: "Before evaluating prose quality, verify the intended audience is defined.",
      appliesWhen: ["Content targets an unspecified reader"],
      doesNotApplyWhen: ["Audience is explicitly stated in the brief"],
      failureRisk: "Well-written content can still miss the target audience.",
    },
    {
      id: "evidence_density_matters",
      oneSentence: "Claims need support.",
      fullStatement: "Every claim in the output should be traceable to specific evidence in the input.",
      appliesWhen: ["Output makes assertions about the content"],
      doesNotApplyWhen: ["Output is purely structural or formatting advice"],
      failureRisk: "Confident-sounding advice without evidence undermines trust.",
    },
  ],
  misunderstandings: [
    {
      id: "polish_is_sufficient",
      wrong: "Making the text flow better fixes the content.",
      correct: "Flow improvements are cosmetic; structural problems require structural fixes.",
    },
  ],
  bannedTerms: [
    { term: "polish", why: "Implies cosmetic-only changes", replaceWith: "refine" },
    { term: "good writing", why: "Too vague for actionable feedback", replaceWith: "specific structural strengths" },
  ],
  selfChecks: [
    "Is the diagnosis structural or cosmetic?",
    "Is the reader defined before prose recommendations?",
    "Are claims backed by specific evidence from the content?",
  ],
};

console.log("✓ Stage 1: KDNA domain loaded —", loadedKdna.name, loadedKdna.version);
console.log("  Axioms:", loadedKdna.axioms.length);
console.log("  Misunderstandings:", loadedKdna.misunderstandings.length);
console.log("  Self-checks:", loadedKdna.selfChecks.length);

// ─── Stage 2: Simulate generation pipeline ───
const pipelineStages = [
  { stageId: "load-domain", stageName: "Load KDNA Domain", stageOrder: 1 },
  { stageId: "generate-letter", stageName: "Generate Daily Letter", stageOrder: 2 },
  { stageId: "measure-fidelity", stageName: "Measure Fidelity", stageOrder: 3 },
];

const artifact = {
  artifactId: "art_20260608_001",
  artifactType: "daily_letter",
  schemaVersion: "1.0.0",
  createdAt: new Date().toISOString(),
  generator: { engine: "daily-letter-engine", version: "0.1.0", runId: "run_001" },
  sourceKdna: [{ name: loadedKdna.name, version: loadedKdna.version, role: loadedKdna.role }],
  sourceArtifacts: [],
  stage: { stageId: "generate-letter", stageName: "Generate Daily Letter", stageOrder: 2, stageStatus: "completed" },
  content: {
    title: "When Surface Fixes Hide the Real Problem",
    sections: [
      { type: "diagnosis", text: "Your article has a strong premise but the argument structure collapses in section 3. Before refining language, we need to rebuild the logical bridge between sections 2 and 4." },
      { type: "structural_analysis", text: "Section 2 establishes a clear need. Section 4 offers a solution. But section 3 skips the mechanism — it tells the reader WHAT changed without explaining HOW." },
      { type: "prescription", text: "Add a transition paragraph between sections 2 and 4. Start with 'The mechanism that connects this need to the solution is...' and provide one concrete example." },
    ],
    audienceDefined: true,
    diagnosticFirst: true,
    evidenceBacked: true,
  },
  contentDigest: "sha256:d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2",
  quality: {
    gateResults: [
      { gateId: "schema_valid", gateType: "schema_validation", result: "pass" },
      { gateId: "axioms_applied", gateType: "kdna_compliance", result: "pass", score: 0.92 },
      { gateId: "human_reviewed", gateType: "human_review", result: "pass" },
    ],
    overallResult: "pass",
  },
  traceRefs: [
    { traceId: "trace_route_001", traceType: "route" },
    { traceId: "trace_generation_001", traceType: "generation" },
    { traceId: "trace_postvalidate_001", traceType: "postvalidate" },
  ],
  review: { status: "approved", reviewedBy: "coach-expert-001", reviewedAt: new Date().toISOString() },
  metadata: { tags: ["daily-coaching", "conflict-domain"], environment: "staging" },
};

console.log("\n✓ Stage 2: Pipeline completed —", pipelineStages.length, "stages");
console.log("  Artifact:", artifact.artifactId, "(" + artifact.artifactType + ")");
console.log("  Quality gates:", artifact.quality.gateResults.filter((g) => g.result === "pass").length + "/" + artifact.quality.gateResults.length, "passed");
console.log("  Review:", artifact.review.status);

// ─── Stage 3: Fidelity measurement ───
function classifyVerdict(metrics) {
  if (metrics.naiveDrift < 0.1 && metrics.transferGap < 0.1) return "common_sense";
  if (metrics.gapWidth < 0.05) return "inconclusive";
  if (metrics.transferGap >= 0.5) return "strong_transfer";
  if (metrics.transferGap >= 0.25) return "partial_transfer";
  if (metrics.transferGap >= 0.1) return "weak_transfer";
  return "no_transfer";
}

function computeStats(results) {
  const n = results.length;
  if (n === 0) return { mean: 0, stdDev: 0, ci95Lower: 0, ci95Upper: 0 };
  const mean = results.reduce((s, r) => s + r.transferGap, 0) / n;
  const variance = n > 1 ? results.reduce((s, r) => s + (r.transferGap - mean) ** 2, 0) / (n - 1) : 0;
  const stdDev = Math.sqrt(variance);
  const se = stdDev / Math.sqrt(n);
  return { mean, stdDev, ci95Lower: mean - 1.96 * se, ci95Upper: mean + 1.96 * se };
}

const perAxiomResults = loadedKdna.axioms.map((ax) => {
  const score = Math.random() * 0.3 + 0.7; // simulate 0.70–1.00 range
  return {
    axiomId: ax.id,
    domain: loadedKdna.name,
    score: +score.toFixed(2),
    transferLevel: score >= 0.80 ? "operationalized" : "referenced",
    evidence: `Artifact ${ax.id === "diagnose_before_polish" ? "opens with diagnosis section before any prescriptive content" : ax.id === "audience_before_prose" ? "audience analysis present before prose recommendations" : "each claim in prescription section cites specific content evidence"}`,
  };
});

const taskResults = [
  { transferGap: 0.82, convergenceScore: 0.88, taskType: "core_scenario", taskPrompt: "Review an article with weak argument structure" },
  { transferGap: 0.78, convergenceScore: 0.85, taskType: "boundary_scenario", taskPrompt: "Grammar-only check request" },
  { transferGap: 0.85, convergenceScore: 0.90, taskType: "novel_scenario", taskPrompt: "Technical documentation with structural issues" },
];

const stats = computeStats(taskResults);
const verdict = classifyVerdict({ transferGap: stats.mean, naiveDrift: 0.25, gapWidth: stats.mean + 0.1, oldNewDivergence: "", naiveSimilarity: "" });

const fidelityResult = {
  fidelityId: "fid_20260608_001",
  protocolVersion: "1.0.0",
  targetArtifact: { artifactId: artifact.artifactId, artifactType: artifact.artifactType, contentDigest: artifact.contentDigest },
  sourceKdna: [{ name: loadedKdna.name, version: loadedKdna.version, role: "primary" }],
  overallScore: +stats.mean.toFixed(2),
  passThreshold: 0.70,
  passed: stats.mean >= 0.70,
  dimensions: [
    { dimensionId: "judgment_activation", dimensionName: "Judgment Activation", score: 0.90, weight: 0.35, evidence: [{ claim: "Axioms triggered in generation trace", verdict: "confirmed", detail: "All 3 axioms detected in trace" }] },
    { dimensionId: "judgment_differentiation", dimensionName: "Judgment Differentiation", score: 0.82, weight: 0.35, evidence: [{ claim: "KDNA output differs from best_prompt", verdict: "confirmed", detail: "Blind evaluator identified difference in 3/3 tasks" }] },
    { dimensionId: "judgment_artifact_presence", dimensionName: "Artifact Presence", score: 0.83, weight: 0.30, evidence: [{ claim: "Banned terms avoided in artifact", verdict: "confirmed", detail: "'polish' replaced with 'refine'" }] },
  ],
  perAxiom: perAxiomResults,
  comparison: {
    conditions: [
      { conditionId: "A", conditionType: "no_kdna", model: "claude-sonnet-4-5", score: 0.35 },
      { conditionId: "B", conditionType: "best_prompt", model: "claude-sonnet-4-5", score: 0.62 },
      { conditionId: "C", conditionType: "kdna_loaded", model: "claude-sonnet-4-5", score: stats.mean, judgmentDelta: +(stats.mean - 0.35).toFixed(2) },
    ],
    blindDelta: +(stats.mean - 0.62).toFixed(2),
    blindDesign: "a_b_c_shuffled",
    evaluatorModel: "gpt-4o",
  },
  calibration: {
    positiveAnchor: { expectedScoreMin: 0.80, actualScore: 0.88, passed: true },
    negativeAnchor: { expectedScoreMax: 0.30, actualScore: 0.15, passed: true },
    calibrationValid: true,
  },
  tasks: taskResults.map((t) => ({ taskId: "task_" + t.taskType, taskType: t.taskType, inputSummary: t.taskPrompt, taskScore: t.transferGap })),
  traceRefs: artifact.traceRefs,
  completedAt: new Date().toISOString(),
  evaluator: { engine: "fidelity-engine", version: "0.1.0" },
};

console.log("\n✓ Stage 3: Fidelity measured");
console.log("  Overall score:", fidelityResult.overallScore, fidelityResult.passed ? "(PASS)" : "(FAIL)");
console.log("  Blind delta (vs best prompt):", fidelityResult.comparison.blindDelta);
console.log("  Verdict:", verdict);
console.log("  Calibration valid:", fidelityResult.calibration.calibrationValid);
console.log("  Per-axiom transfer:");
fidelityResult.perAxiom.forEach((ax) => {
  console.log("    " + ax.axiomId + ": " + ax.score + " (" + ax.transferLevel + ")");
});
console.log("  CI95: [" + stats.ci95Lower.toFixed(2) + ", " + stats.ci95Upper.toFixed(2) + "]");

// ─── Summary ───
console.log("\n═══════════════════════════════════════════");
console.log("  KDNA E2E Coaching Demo — Complete");
console.log("═══════════════════════════════════════════");
console.log("  Protocol chain verified:");
console.log("  1. KDNA load  ✓  " + loadedKdna.axioms.length + " axioms, " + loadedKdna.selfChecks.length + " self-checks");
console.log("  2. Pipeline    ✓  " + pipelineStages.length + " stages → " + artifact.artifactType);
console.log("  3. Envelope    ✓  " + artifact.quality.gateResults.length + " quality gates, review: " + artifact.review.status);
console.log("  4. Fidelity    ✓  score " + fidelityResult.overallScore + ", verdict: " + verdict);
console.log("═══════════════════════════════════════════");
