#!/usr/bin/env node
/**
 * KDNA E2E Coaching Demo — RFC schema-valid wire format
 *
 * Demonstrates the full protocol chain in wire (snake_case) format:
 *   KDNA load → Pipeline (3 stages) → ArtifactEnvelope → FidelityResult
 *
 * All pure data flow — no LLM calls, no external dependencies.
 * Deterministic fixture scores — reproducible on every run.
 * Writes schema-valid JSON outputs to examples/e2e-coaching/outputs/.
 *
 * Runs with: node demo.mjs
 * Validate with: kdna protocol validate outputs/artifact-envelope.json
 */

import { writeFileSync, mkdirSync } from "fs";
import { fileURLToPath } from "url";
import { dirname, join } from "path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const outDir = join(__dirname, "outputs");
mkdirSync(outDir, { recursive: true });

// ─── Stage 1: Simulate KDNA domain loading ───
const loadedKdna = {
  name: "@aikdna/writing",
  version: "0.7.2",
  judgment_version: "2026.05",
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
  banned_terms: [
    { term: "polish", why: "Implies cosmetic-only changes", replace_with: "refine" },
    { term: "good writing", why: "Too vague for actionable feedback", replace_with: "specific structural strengths" },
  ],
  self_checks: [
    "Is the diagnosis structural or cosmetic?",
    "Is the reader defined before prose recommendations?",
    "Are claims backed by specific evidence from the content?",
  ],
};

console.log("✓ Stage 1: KDNA domain loaded —", loadedKdna.name, loadedKdna.version);
console.log("  Axioms:", loadedKdna.axioms.length);
console.log("  Misunderstandings:", loadedKdna.misunderstandings.length);
console.log("  Self-checks:", loadedKdna.self_checks.length);

// ─── Stage 2: ArtifactEnvelope (RFC-0009 wire format) ───
const now = "2026-06-08T10:30:00Z";

const artifactEnvelope = {
  artifact_id: "art_20260608_001",
  artifact_type: "daily_letter",
  schema_version: "1.0.0",
  content_schema_version: "0.1.0",
  created_at: now,
  generator: { engine: "daily-letter-engine", version: "0.1.0", run_id: "run_001" },
  source_kdna: [{ name: loadedKdna.name, version: loadedKdna.version, role: loadedKdna.role }],
  source_artifacts: [],
  stage: { stage_id: "generate-letter", stage_name: "Generate Daily Letter", stage_order: 2, stage_attempt: 1, stage_status: "completed" },
  content: {
    title: "When Surface Fixes Hide the Real Problem",
    sections: [
      { type: "diagnosis", text: "Your article has a strong premise but the argument structure collapses in section 3. Before refining language, we need to rebuild the logical bridge between sections 2 and 4." },
      { type: "structural_analysis", text: "Section 2 establishes a clear need. Section 4 offers a solution. But section 3 skips the mechanism — it tells the reader WHAT changed without explaining HOW." },
      { type: "prescription", text: "Add a transition paragraph between sections 2 and 4. Start with 'The mechanism that connects this need to the solution is...' and provide one concrete example." },
    ],
    audience_defined: true,
    diagnostic_first: true,
    evidence_backed: true,
  },
  content_digest: "sha256:d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2",
  quality: {
    gate_results: [
      { gate_id: "schema_valid", gate_type: "schema_validation", result: "pass" },
      { gate_id: "axioms_applied", gate_type: "kdna_compliance", result: "pass", score: 0.92 },
      { gate_id: "human_reviewed", gate_type: "human_review", result: "pass" },
    ],
    overall_result: "pass",
  },
  trace_refs: [
    { trace_id: "trace_route_001", trace_type: "route" },
    { trace_id: "trace_generation_001", trace_type: "generation" },
    { trace_id: "trace_postvalidate_001", trace_type: "postvalidate" },
  ],
  review: { status: "approved", reviewed_by: "coach-expert-001", reviewed_at: now },
  metadata: { tags: ["daily-coaching", "conflict-domain"], environment: "staging" },
};

console.log("\n✓ Stage 2: Pipeline completed — 3 stages");
console.log("  Artifact:", artifactEnvelope.artifact_id, "(" + artifactEnvelope.artifact_type + ")");
console.log("  Quality gates:", artifactEnvelope.quality.gate_results.filter((g) => g.result === "pass").length + "/" + artifactEnvelope.quality.gate_results.length, "passed");
console.log("  Review:", artifactEnvelope.review.status);

writeFileSync(join(outDir, "artifact-envelope.json"), JSON.stringify(artifactEnvelope, null, 2));

// ─── Stage 3: FidelityResult (RFC-0010 wire format) ───

// Deterministic per-axiom scores — no Math.random()
const perAxiomFixtures = {
  diagnose_before_polish: { score: 0.92, transfer_level: "operationalized", evidence: "Artifact opens with diagnosis section before any prescriptive content" },
  audience_before_prose: { score: 0.84, transfer_level: "operationalized", evidence: "Audience analysis present before prose recommendations" },
  evidence_density_matters: { score: 0.79, transfer_level: "referenced", evidence: "Each claim in prescription section cites specific content evidence" },
};

const per_axiom = loadedKdna.axioms.map((ax) => ({
  axiom_id: ax.id,
  domain: loadedKdna.name,
  score: perAxiomFixtures[ax.id]?.score ?? 0.80,
  transfer_level: perAxiomFixtures[ax.id]?.transfer_level ?? "referenced",
  evidence: perAxiomFixtures[ax.id]?.evidence ?? "N/A",
}));

// Deterministic task results
const task_results = [
  { transfer_gap: 0.82, convergence_score: 0.88, task_type: "core_scenario", task_prompt: "Review an article with weak argument structure" },
  { transfer_gap: 0.78, convergence_score: 0.85, task_type: "boundary_scenario", task_prompt: "Grammar-only check request" },
  { transfer_gap: 0.85, convergence_score: 0.90, task_type: "novel_scenario", task_prompt: "Technical documentation with structural issues" },
];

function computeStats(results) {
  const n = results.length;
  if (n === 0) return { mean: 0, std_dev: 0, ci95_lower: 0, ci95_upper: 0 };
  const mean = results.reduce((s, r) => s + r.transfer_gap, 0) / n;
  const variance = n > 1 ? results.reduce((s, r) => s + (r.transfer_gap - mean) ** 2, 0) / (n - 1) : 0;
  const stdDev = Math.sqrt(variance);
  const se = stdDev / Math.sqrt(n);
  return { mean, std_dev: stdDev, ci95_lower: mean - 1.96 * se, ci95_upper: mean + 1.96 * se };
}

function classifyVerdict(metrics) {
  if (metrics.naive_drift < 0.1 && metrics.transfer_gap < 0.1) return "common_sense";
  if (metrics.gap_width < 0.05) return "inconclusive";
  if (metrics.transfer_gap >= 0.5) return "strong_transfer";
  if (metrics.transfer_gap >= 0.25) return "partial_transfer";
  if (metrics.transfer_gap >= 0.1) return "weak_transfer";
  return "no_transfer";
}

const stats = computeStats(task_results);
const overall_score = +stats.mean.toFixed(4);
const blind_delta = +(stats.mean - 0.62).toFixed(4);
const verdict = classifyVerdict({ transfer_gap: stats.mean, naive_drift: 0.25, gap_width: stats.mean + 0.1 });

const fidelityResult = {
  fidelity_id: "fid_20260608_001",
  protocol_version: "1.0.0",
  target_artifact: { artifact_id: artifactEnvelope.artifact_id, artifact_type: artifactEnvelope.artifact_type, content_digest: artifactEnvelope.content_digest },
  source_kdna: [{ name: loadedKdna.name, version: loadedKdna.version, role: loadedKdna.role }],
  overall_score: overall_score,
  pass_threshold: 0.70,
  passed: overall_score >= 0.70,
  dimensions: [
    { dimension_id: "judgment_activation", dimension_name: "Judgment Activation", score: 0.90, weight: 0.35, evidence: [{ claim: "Axioms triggered in generation trace", verdict: "confirmed", detail: "All 3 axioms detected in trace" }] },
    { dimension_id: "judgment_differentiation", dimension_name: "Judgment Differentiation", score: 0.82, weight: 0.35, evidence: [{ claim: "KDNA output differs from best_prompt", verdict: "confirmed", detail: "Blind evaluator identified difference in 3/3 tasks" }] },
    { dimension_id: "judgment_artifact_presence", dimension_name: "Artifact Presence", score: 0.83, weight: 0.30, evidence: [{ claim: "Banned terms avoided in artifact", verdict: "confirmed", detail: "'polish' replaced with 'refine'" }] },
  ],
  per_axiom: per_axiom,
  comparison: {
    conditions: [
      { condition_id: "A", condition_type: "no_kdna", model: "claude-sonnet-4-5", score: 0.35 },
      { condition_id: "B", condition_type: "best_prompt", model: "claude-sonnet-4-5", score: 0.62 },
      { condition_id: "C", condition_type: "kdna_loaded", model: "claude-sonnet-4-5", score: overall_score, judgment_delta: +(overall_score - 0.35).toFixed(4) },
    ],
    blind_delta: blind_delta,
    blind_design: "a_b_c_shuffled",
    evaluator_model: "gpt-4o",
    evaluator_rubric: "Rate each output on: (1) diagnostic depth, (2) structural awareness, (3) evidence orientation.",
  },
  calibration: {
    positive_anchor: { expected_score_min: 0.80, actual_score: 0.88, passed: true },
    negative_anchor: { expected_score_max: 0.30, actual_score: 0.15, passed: true },
    calibration_valid: true,
  },
  tasks: task_results.map((t) => ({ task_id: "task_" + t.task_type, task_type: t.task_type, input_summary: t.task_prompt, task_score: t.transfer_gap })),
  trace_refs: artifactEnvelope.trace_refs,
  completed_at: now,
  measurement_duration_ms: 3420,
  evaluator: { engine: "fidelity-engine", version: "0.1.0" },
};

console.log("\n✓ Stage 3: Fidelity measured");
console.log("  Overall score:", fidelityResult.overall_score, fidelityResult.passed ? "(PASS)" : "(FAIL)");
console.log("  Blind delta (vs best prompt):", fidelityResult.comparison.blind_delta);
console.log("  Verdict:", verdict);
console.log("  Calibration valid:", fidelityResult.calibration.calibration_valid);
console.log("  Per-axiom transfer:");
fidelityResult.per_axiom.forEach((ax) => {
  console.log("    " + ax.axiom_id + ": " + ax.score + " (" + ax.transfer_level + ")");
});
console.log("  CI95: [" + stats.ci95_lower.toFixed(4) + ", " + stats.ci95_upper.toFixed(4) + "]");

writeFileSync(join(outDir, "fidelity-result.json"), JSON.stringify(fidelityResult, null, 2));

// ─── Summary ───
console.log("\n═══════════════════════════════════════════");
console.log("  KDNA E2E Coaching Demo — Complete");
console.log("═══════════════════════════════════════════");
console.log("  Protocol chain verified (wire format):");
console.log("  1. KDNA load  ✓  " + loadedKdna.axioms.length + " axioms, " + loadedKdna.self_checks.length + " self-checks");
console.log("  2. Pipeline    ✓  3 stages → " + artifactEnvelope.artifact_type);
console.log("  3. Envelope    ✓  " + artifactEnvelope.quality.gate_results.length + " quality gates, review: " + artifactEnvelope.review.status);
console.log("  4. Fidelity    ✓  score " + fidelityResult.overall_score + ", verdict: " + verdict);
console.log("\n  Schema-valid outputs written to:");
console.log("    " + join(outDir, "artifact-envelope.json"));
console.log("    " + join(outDir, "fidelity-result.json"));
console.log("═══════════════════════════════════════════");
