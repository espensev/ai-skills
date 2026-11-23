/* zcode-workflow
description: Independently confirm or refute pending sweep candidates for a campaign.
args:
  campaign:
    type: string
    required: true
    description: Absolute forward-slash campaign directory (build/kit snapshot owner).
  crewPy:
    type: string
    required: true
    description: Absolute path of the frozen scripts/crew.py to run.
  limit:
    type: number
    default: 150
    description: Confirm at most N candidates (0 means all pending).
  minSeverity:
    type: string
    default: medium
    description: Minimum severity to load: low, medium or high.
*/

interface CandidateRecord {
  /** Content-addressed id, C- plus 10 hex characters. */
  id: string;
  /** low, medium or high. */
  severity: "low" | "medium" | "high";
  /** path:line of the reported issue. */
  where: string;
  /** One sentence: what is claimed wrong. */
  what: string;
  /** The reviewer's evidence for the claim. */
  evidence: string;
  /** Units and lenses that raised this candidate. */
  sources: string[];
}

interface ProbeResult {
  /** True only when the probe file round-tripped through staging. */
  ok: boolean;
  /** What the probe did and saw. */
  detail: string;
}

interface ConfirmVerdict {
  /** The candidate id the verdict file names. */
  candidateId?: string;
  /** confirmed, refuted, inconclusive or duplicate. */
  verdict: "confirmed" | "refuted" | "inconclusive" | "duplicate";
  /** Set for verdict duplicate: id of the surviving candidate. */
  duplicateOf?: string;
  /** Why this verdict holds. */
  reasoning: string;
  /** What supported the claim. */
  evidence: string;
  /** What spoke against it. */
  counterevidence: string;
  /** low, medium or high after confirmation. */
  adjustedSeverity: "low" | "medium" | "high";
}

interface ConfirmAggLine {
  candidates: number;
  confirmed: number;
  refuted: number;
  inconclusive: number;
  duplicate: number;
  pending: number;
  invalid: number;
}

interface WorkflowReport {
  conclusion: string;
  findings: Array<{
    where: string;
    what: string;
    evidence: string;
    severity: "low" | "medium" | "high";
    status: "verified" | "unconfirmed";
  }>;
  verified: string[];
  notCovered: string[];
}

function requireString(key: string): string {
  const value = args[key];
  if (typeof value !== "string" || value.length === 0) {
    throw new Error("argument '" + key + "' is required and must be a non-empty string");
  }
  return value;
}

function utf8Bytes(text: string): number {
  let total = 0;
  for (let i = 0; i < text.length; i += 1) {
    const code = text.charCodeAt(i);
    if (code < 0x80) total += 1;
    else if (code < 0x800) total += 2;
    else if (code >= 0xd800 && code <= 0xdbff) {
      total += 4;
      i += 1;
    } else total += 3;
  }
  return total;
}

const MARKDOWN_CAP_BYTES = 240000;

const campaign = requireString("campaign");
const crewPy = requireString("crewPy");
const limit = typeof args.limit === "number" && args.limit >= 0 ? Math.floor(args.limit) : 150;
const minSeverityRaw = typeof args.minSeverity === "string" ? args.minSeverity : "medium";
if (minSeverityRaw !== "low" && minSeverityRaw !== "medium" && minSeverityRaw !== "high") {
  throw new Error("minSeverity must be low, medium or high, got: " + minSeverityRaw);
}
const minSeverity = minSeverityRaw;

phase("Load the pending candidate list");
const loadRes = await world.run(
  "python",
  ["-I", crewPy, campaign, "candidates", "--min-severity", minSeverity,
   "--pending", "--limit", String(limit)],
  { timeoutMs: 120000 },
);
if (loadRes.exitCode !== 0) {
  throw new Error("crew.py candidates exited " + loadRes.exitCode + ": " + loadRes.stderr);
}
const listing = JSON.parse(loadRes.stdout) as {
  campaign: string;
  root: string;
  commit: string;
  candidates: CandidateRecord[];
};
if (typeof listing.root !== "string" || typeof listing.commit !== "string" ||
    !Array.isArray(listing.candidates)) {
  throw new Error("crew.py candidates did not return a candidate list object");
}
const candidates = listing.candidates;
for (const candidate of candidates) {
  if (typeof candidate.id !== "string" || !/^C-[0-9a-f]{10}$/.test(candidate.id) ||
      typeof candidate.where !== "string" || typeof candidate.what !== "string" ||
      typeof candidate.evidence !== "string" ||
      (candidate.severity !== "low" && candidate.severity !== "medium" &&
       candidate.severity !== "high")) {
    throw new Error("malformed candidate record: " + JSON.stringify(candidate));
  }
}
const candidateIds = candidates.map((c) => c.id);
if (new Set(candidateIds).size !== candidateIds.length) {
  throw new Error("crew.py returned duplicate candidate ids");
}
const confirmerNames = candidates.map((c) => "conf-" + c.id);
if (new Set(confirmerNames).size !== confirmerNames.length) {
  throw new Error("confirmer subagent names would collide");
}
log("Loaded " + candidates.length + " pending candidates at " + minSeverity + " or above" +
    (limit > 0 ? " (limit " + limit + ")" : ""));

function verdictPathOf(candidateId: string): string {
  return campaign + "/staging/confirm/" + candidateId + ".json";
}

function confirmAsk(candidate: CandidateRecord): string {
  return "Independently confirm or refute sweep candidate " + candidate.id + ".\n" +
    "Claim (" + candidate.severity + "): " + candidate.where + " - " + candidate.what + "\n" +
    "Reviewer evidence: " + candidate.evidence + "\n" +
    "Raised by: " + candidate.sources.join(", ") + "\n" +
    "The claim's where may be written as path:line.\n" +
    "Frozen source root: " + listing.root + " (commit " + listing.commit +
    "). If the claim's path is repo-relative, resolve it under that root and read the pinned file; " +
    "if it is absolute, read it as given, read-only. Verify independently from the code alone and look for counterevidence.\n" +
    "Steps:\n" +
    "(1) Reproduce the finding from the code alone: read the cited file and its surroundings; " +
    "you may run read-only checks. Never edit any file except your one verdict file. " +
    "Quote the exact lines you read under evidence.\n" +
    "(2) Verdict: confirmed, refuted, inconclusive, or duplicate (set duplicateOf to the surviving candidate id).\n" +
    "(3) Put anything that weakens the claim into counterevidence; if you found none, write the words " +
    "none found plus what you looked at, so the controller can tell looked-and-found-none from did-not-look.\n" +
    "(4) Escape every backslash when writing JSON (or use forward slashes) so the file stays valid JSON.\n" +
    "(5) Resume check: if your verdict file at " + verdictPathOf(candidate.id) +
    " already exists and parses as JSON with candidateId " + candidate.id +
    " and a verdict set, return that object as your answer without redoing the work.\n" +
    "(6) Write your verdict JSON to " + verdictPathOf(candidate.id) +
    " with keys candidateId, verdict, duplicateOf, reasoning, evidence, counterevidence, adjustedSeverity. " +
    "Then return the same object as your typed answer (verdict, duplicateOf, reasoning, evidence, counterevidence, adjustedSeverity).\n" +
    "No machine-sensitive commands and no machine identity verifier runs.";
}

function gateAsk(ask: string, recordPath: string, recordIdentity: string, dynamic: string[]): void {
  const forbidden = ["undefined", "null", "[object", "NaN"];
  for (const value of dynamic) {
    for (const token of forbidden) {
      const pattern = token === "[object" ? /\[object/ : new RegExp("\\b" + token + "\\b");
      if (pattern.test(value)) {
        throw new Error("ask-content gate failed: record data contains '" + token + "': " + value);
      }
    }
  }
  if (!ask.includes(recordPath) || !ask.includes(recordIdentity)) {
    throw new Error("ask-content gate failed: the first ask lacks the first record's path or identity");
  }
}

let verdicts: Array<{ candidate: CandidateRecord; verdict: ConfirmVerdict | string }> = [];

if (candidates.length > 0) {
  const first = candidates[0];
  const dynamicParts = [first.id, first.where, first.what, first.evidence, ...first.sources];
  gateAsk(confirmAsk(first), first.where, first.id, dynamicParts);

  phase("Probe a staging round-trip before any confirmation runs");
  const probe = await agent("probe-confirm").ask<ProbeResult>(
    "Pre-flight probe for the confirm tier.\n" +
    "Write the single line probe-ok to " + campaign + "/staging/confirm/probe.txt, " +
    "then read that file back and confirm it says probe-ok.\n" +
    "Escape every backslash when writing files or JSON. The only file you may write is the probe file. " +
    "No machine-sensitive commands and no machine identity verifier runs. Return {ok, detail}.",
  );
  if (!probe.ok) {
    throw new Error("probe failed for the confirm tier: " + probe.detail);
  }
  log("Probe ok: " + probe.detail);

  phase("Confirm every candidate in parallel, one independent confirmer each");
  const settled = await Promise.all(
    candidates.map(async (candidate) => {
      let verdict: ConfirmVerdict | string;
      try {
        verdict = await agent("conf-" + candidate.id).ask<ConfirmVerdict>(confirmAsk(candidate));
      } catch (err: unknown) {
        const message = err instanceof Error ? err.message : String(err);
        verdict = "ask rejected: " + message;
      }
      const status = typeof verdict === "string" ? verdict : verdict.verdict;
      report({ candidate: candidate.id, where: candidate.where, status });
      return { candidate, verdict };
    }),
  );
  verdicts = settled;
  log("Confirmers done this run: " + settled.length);
}

phase("Aggregate the confirm verdicts and publish");
const aggRes = await world.run(
  "python", ["-I", crewPy, campaign, "confirmagg"],
  { timeoutMs: 120000 },
);
if (aggRes.exitCode !== 0) {
  throw new Error("crew.py confirmagg exited " + aggRes.exitCode + ": " + aggRes.stderr);
}
const agg = JSON.parse(aggRes.stdout) as ConfirmAggLine;
log("Confirm coverage: " + agg.confirmed + " confirmed, " + agg.refuted + " refuted, " +
    agg.inconclusive + " inconclusive, " + agg.duplicate + " duplicate, " +
    agg.pending + " pending");

const confirmedFindings = verdicts
  .filter((entry): entry is { candidate: CandidateRecord; verdict: ConfirmVerdict } =>
    typeof entry.verdict !== "string" && entry.verdict.verdict === "confirmed")
  .map((entry) => ({
    where: entry.candidate.where,
    what: entry.candidate.what,
    evidence: entry.verdict.evidence || entry.candidate.evidence,
    severity: entry.verdict.adjustedSeverity || entry.candidate.severity,
    status: "verified" as const,
  }));

const header = [
  "# Confirm tier - candidate verdicts",
  "",
  "- Candidates on disk: " + agg.candidates,
  "- Confirmed: " + agg.confirmed + ", refuted: " + agg.refuted +
    ", inconclusive: " + agg.inconclusive + ", duplicate: " + agg.duplicate +
    ", pending: " + agg.pending,
  "",
  "## Confirmed this run",
  "",
];
const footer = ["", "Full detail in build/confirm-coverage.json."];
const blocks = confirmedFindings.map((f) =>
  "- **" + f.severity + "** " + f.where + " - " + f.what +
  "\n  > " + f.evidence.slice(0, 500).split("\n").join("\n  > "));

let markdown = header.concat(blocks.length > 0 ? blocks : ["None."], footer).join("\n");
while (utf8Bytes(markdown) > MARKDOWN_CAP_BYTES && blocks.length > 0) {
  blocks.pop();
  markdown = header.concat(blocks, footer).join("\n");
}

try {
  await artifact.markdown("confirm-report", markdown, {
    title: "Confirm tier verdicts",
    description: "Which sweep candidates survived independent confirmation.",
    primary: true,
  });
} catch (err: unknown) {
  const message = err instanceof Error ? err.message : String(err);
  log("markdown publish rejected: " + message);
  await artifact.markdown("confirm-report", [
    "# Confirm tier - candidate verdicts",
    "",
    "The full report could not be published; see build/confirm-coverage.json",
  ].join("\n"), { title: "Confirm tier verdicts", primary: true });
}

const reportOut: WorkflowReport = {
  conclusion: "Confirm tier: " + agg.confirmed + " of " + agg.candidates +
    " candidates are confirmed, " + agg.refuted + " refuted, " + agg.inconclusive +
    " inconclusive, " + agg.duplicate + " duplicate; " + agg.pending + " still pending.",
  findings: confirmedFindings,
  verified: [
    "Ask-content gate checked the first ask before any fan-out.",
    "Pre-flight probe verified a staging round-trip before any confirmation ran.",
    "Verdict counts reconciled by crew.py confirmagg into build/confirm-coverage.json.",
  ],
  notCovered: [
    "Candidates below " + minSeverity + " severity are not confirmed by this run.",
    "Candidates still pending; see build/confirm-coverage.json.",
    ...(limit > 0
      ? ["limit " + limit + " truncated this run's candidate list; candidates beyond it stayed pending."]
      : []),
  ],
};
return reportOut;
