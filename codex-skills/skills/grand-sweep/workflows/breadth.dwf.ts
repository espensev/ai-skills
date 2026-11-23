/* zcode-workflow
description: Breadth review of one lane's pending units for a grand-sweep campaign.
args:
  campaign:
    type: string
    required: true
    description: Absolute forward-slash campaign directory (build/kit snapshot owner).
  crewPy:
    type: string
    required: true
    description: Absolute path of the frozen scripts/crew.py to run.
  lane:
    type: string
    required: true
    description: Lane name as frozen in manifest.json.
  pendingOnly:
    type: boolean
    default: true
    description: Load only units that are neither adopted nor terminal.
  limit:
    type: number
    default: 0
    description: Review at most N units (0 means all loaded units).
  focus:
    type: string
    default: ""
    description: Extra lane focus text appended to every audit ask.
*/

/** One file in a unit, as crew.py emits it: [rel, sha256, bytes, kind]. */
type UnitFile = [string, string, number, string];

interface Unit {
  /** Unit id, e.g. ps-00042. */
  id: string;
  /** Absolute forward-slash repo root. */
  root: string;
  /** Repo-relative directory the unit covers. */
  dir: string;
  /** Total bytes of the unit. */
  bytes: number;
  /** True when a single huge file forms the unit. */
  oversize: boolean;
  /** The files to review. */
  files: UnitFile[];
}

interface ProbeResult {
  /** True only when the probe file round-tripped through staging. */
  ok: boolean;
  /** What the probe did and saw. */
  detail: string;
}

interface VerdictFinding {
  /** low, medium or high. */
  severity: "low" | "medium" | "high";
  /** path:line of the defect. */
  where: string;
  /** One sentence: what is wrong. */
  what: string;
  /** Quoted lines or command+output that shows it. */
  evidence: string;
}

interface UnitVerdict {
  /** completed when every file was reviewed, failed otherwise. */
  status: "completed" | "failed";
  /** Unit id the verdict file names. */
  unitId?: string;
  /** Reviewer name recorded in the verdict file. */
  reviewer?: string;
  /** Failed-attempt count recorded in the verdict file. */
  attempts?: number;
  /** Findings cited path:line with evidence. */
  findings: VerdictFinding[];
  /** Path of the verdict JSON the reviewer wrote. */
  verdictPath: string;
  /** One or two sentences. */
  summary: string;
  /** Covered ranges, e.g. path:first-last. */
  covered?: string[];
}

interface AggLine {
  lane: string;
  units: number;
  completed: number;
  failed: number;
  pending: number;
  terminalFailed: number;
  low: number;
  medium: number;
  high: number;
}

interface WorkflowReport {
  conclusion: string;
  findings: VerdictFinding[];
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
const lane = requireString("lane");
const pendingOnly = typeof args.pendingOnly === "boolean" ? args.pendingOnly : true;
const limit = typeof args.limit === "number" && args.limit > 0 ? Math.floor(args.limit) : 0;
const focus = typeof args.focus === "string" ? args.focus : "";

phase("Load the frozen unit list for the lane");
const loadRes = await world.run(
  "python",
  [
    "-I", crewPy, campaign, "units", lane,
    ...(pendingOnly ? ["--pending"] : []),
    ...(limit > 0 ? ["--limit", String(limit)] : []),
  ],
  { timeoutMs: 120000 },
);
if (loadRes.exitCode !== 0) {
  throw new Error("crew.py units " + lane + " exited " + loadRes.exitCode + ": " + loadRes.stderr);
}
const units = JSON.parse(loadRes.stdout) as Unit[];
if (!Array.isArray(units)) {
  throw new Error("crew.py units " + lane + " did not return an array");
}
for (const unit of units) {
  if (typeof unit.id !== "string" || typeof unit.root !== "string" ||
      !Array.isArray(unit.files) || unit.files.length === 0) {
    throw new Error("malformed unit record: " + JSON.stringify(unit));
  }
  for (const entry of unit.files) {
    if (!Array.isArray(entry) || entry.length < 4 || typeof entry[0] !== "string" ||
        typeof entry[1] !== "string" || !/^[0-9a-f]{64}$/.test(entry[1]) ||
        typeof entry[2] !== "number") {
      throw new Error("unit " + unit.id + " has a malformed file entry: " + JSON.stringify(entry));
    }
  }
}
const unitIds = units.map((unit) => unit.id);
if (new Set(unitIds).size !== unitIds.length) {
  throw new Error("crew.py returned duplicate unit ids for lane " + lane);
}
const reviewerNames = units.map((unit) => "rev-" + unit.id);
if (new Set(reviewerNames).size !== reviewerNames.length) {
  throw new Error("reviewer subagent names would collide for lane " + lane);
}
log("Loaded " + units.length + " units for lane " + lane +
    (limit > 0 ? " (limit " + limit + ")" : ""));

function verdictPathOf(unitId: string): string {
  return campaign + "/staging/breadth/" + lane + "/" + unitId + ".json";
}

function unitAsk(unit: Unit): string {
  return "Unit " + unit.id + " of lane " + lane + ", repo root " + unit.root + ".\n" +
    "Files to review (repo-relative path and expected sha256):\n" +
    unit.files.map((entry) => "- " + entry[0] + "  sha256=" + entry[1]).join("\n") + "\n" +
    (unit.oversize
      ? "This unit is oversize: read the file in sections and state which line ranges you covered.\n"
      : "") +
    "Steps:\n" +
    "(1) Read every listed file in full.\n" +
    "(2) Verify each file's sha256 first; if any differs from the expected value, do not review that file: write status failed with reason input-changed.\n" +
    "(3) Audit for correctness bugs, broken or dangling references, security issues (secrets, injection, unsafe shell), docs-vs-code drift, dead or contradicting instructions, copy-paste errors. " +
    "Severity: high = data loss, crash, wrong result or security exposure; medium = real defect with a workaround; low = hygiene." +
    (focus.length > 0 ? " Lane focus: " + focus + "\n" : "\n") +
    "(4) Every finding must cite path:line and quote the evidence; do not report a check you did not run; style opinions are not findings.\n" +
    "(5) Do not edit, create, move or delete any file except your one verdict file.\n" +
    "(6) Escape every backslash when writing JSON (or use forward slashes) so the file stays valid JSON.\n" +
    "(7) Resume check: if your verdict file at " + verdictPathOf(unit.id) +
    " already exists and parses as JSON with unitId " + unit.id +
    " and status completed, return that object as your answer without redoing the work; " +
    "if a failed verdict file exists there, increment its attempts field by one in the file you write (attempts defaults to 1).\n" +
    "(8) Write your verdict JSON to " + verdictPathOf(unit.id) +
    " with keys unitId, status, reviewer, attempts, findings (each with severity, where, what, evidence), summary, covered. " +
    "Do not restate file content in summary. Then return the same object as your typed answer.\n" +
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

let collectedFindings: VerdictFinding[] = [];

if (units.length > 0) {
  const firstUnit = units[0];
  const dynamicParts = [
    firstUnit.id, firstUnit.root, firstUnit.dir, focus,
    ...firstUnit.files.flatMap((entry) => entry.map((field) => String(field))),
  ];
  gateAsk(unitAsk(firstUnit), firstUnit.files[0][0], firstUnit.files[0][1], dynamicParts);

  phase("Probe one file and a staging round-trip before any fan-out");
  const firstFile = firstUnit.files[0];
  const probe = await agent("probe-" + lane).ask<ProbeResult>(
    "Pre-flight probe for the breadth sweep of lane " + lane + ".\n" +
    "1. Read the file " + firstUnit.root + "/" + firstFile[0] + " (first few KB is enough).\n" +
    "2. Verify its sha256; it must equal " + firstFile[1] + ".\n" +
    "3. Write the single line probe-ok to " + campaign + "/staging/breadth/" + lane + "/probe.txt, " +
    "then read that file back and confirm it says probe-ok.\n" +
    "Escape every backslash when writing files or JSON. The only file you may write is the probe file. " +
    "No machine-sensitive commands and no machine identity verifier runs. Return {ok, detail}.",
  );
  if (!probe.ok) {
    throw new Error("probe failed for lane " + lane + ": " + probe.detail);
  }
  log("Probe ok: " + probe.detail);

  phase("Review every unit in parallel, one read-only auditor per unit");
  const verdicts = await Promise.all(
    units.map(async (unit) => {
      let verdict: UnitVerdict;
      try {
        verdict = await agent("rev-" + unit.id).ask<UnitVerdict>(unitAsk(unit));
      } catch (err: unknown) {
        const message = err instanceof Error ? err.message : String(err);
        verdict = {
          status: "failed",
          findings: [],
          verdictPath: verdictPathOf(unit.id),
          summary: "ask rejected: " + message,
        };
      }
      report({ unit: unit.id, status: verdict.status, findings: verdict.findings });
      return verdict;
    }),
  );
  collectedFindings = verdicts.flatMap((v) => v.findings);
  const completedCount = verdicts.filter((v) => v.status === "completed").length;
  log("Reviewed " + units.length + " units: " + completedCount + " completed, " +
      (units.length - completedCount) + " failed");
}

phase("Re-check input identities, aggregate and publish");
const checkRes = await world.run(
  "python", ["-I", crewPy, campaign, "check", lane],
  { timeoutMs: 600000 },
);
if (checkRes.exitCode !== 0) {
  throw new Error("crew.py check " + lane + " exited " + checkRes.exitCode + ": " + checkRes.stderr);
}
const check = JSON.parse(checkRes.stdout) as { files: number; changed: number; missing: number };

const aggRes = await world.run(
  "python", ["-I", crewPy, campaign, "agg", lane],
  { timeoutMs: 120000 },
);
if (aggRes.exitCode !== 0) {
  throw new Error("crew.py agg " + lane + " exited " + aggRes.exitCode + ": " + aggRes.stderr);
}
const agg = JSON.parse(aggRes.stdout) as AggLine;
log("Coverage: " + agg.completed + "/" + agg.units + " completed, " + agg.failed +
    " failed, " + agg.pending + " pending, " + agg.terminalFailed + " terminal-failed");

const notable = collectedFindings.filter(
  (finding) => finding.severity === "medium" || finding.severity === "high");
const header = [
  "# Breadth sweep - lane " + lane,
  "",
  "- Units: " + agg.units + " (completed " + agg.completed + ", failed " + agg.failed +
    ", pending " + agg.pending + ", terminal-failed " + agg.terminalFailed + ")",
  "- Findings this run: " + notable.length + " medium/high of " + collectedFindings.length +
    " total (unconfirmed candidates)",
  "- Identity check after review: " + check.changed + " changed, " + check.missing +
    " missing of " + check.files + " files",
  "",
  "## Medium and high findings from this run (unconfirmed candidates)",
  "",
];
const footer = [
  "",
  "Failed, terminal and pending units are listed in build/breadth-coverage-" + lane + ".json.",
];
const blocks = notable.map((finding) =>
  "- **" + finding.severity + "** " + finding.where + " - " + finding.what +
  "\n  > " + finding.evidence.slice(0, 500).split("\n").join("\n  > "));

let markdown = header.concat(blocks.length > 0 ? blocks : ["None."], footer).join("\n");
while (utf8Bytes(markdown) > MARKDOWN_CAP_BYTES && blocks.length > 0) {
  blocks.pop();
  markdown = header.concat(blocks, footer).join("\n");
}

try {
  await artifact.markdown("breadth-report", markdown, {
    title: "Breadth sweep: " + lane,
    description: "Coverage counts and notable findings for lane " + lane + ".",
    primary: true,
  });
} catch (err: unknown) {
  const message = err instanceof Error ? err.message : String(err);
  log("markdown publish rejected: " + message);
  await artifact.markdown("breadth-report", [
    "# Breadth sweep - lane " + lane,
    "",
    "The full report could not be published; see build/breadth-coverage-" + lane + ".json",
  ].join("\n"), { title: "Breadth sweep: " + lane, primary: true });
}

const reportOut: WorkflowReport = {
  conclusion: "Breadth sweep of lane " + lane + ": " + agg.completed + " of " + agg.units +
    " units completed with " + agg.medium + " medium and " + agg.high +
    " high unconfirmed candidates on disk; " + agg.failed + " failed, " + agg.terminalFailed +
    " terminal-failed. Identity check: " + check.changed + " changed, " + check.missing +
    " missing of " + check.files + ".",
  findings: notable,
  verified: [
    "Ask-content gate checked the first ask before any fan-out.",
    "Pre-flight probe verified one file's sha256 and a staging round-trip before fan-out.",
    "Coverage reconciled from on-disk verdicts by crew.py agg " + lane + ".",
    "Input identities re-hashed by crew.py check " + lane + " after review.",
  ],
  notCovered: [
    "Findings are reviewer candidates only; confirmation is the confirm tier's job.",
    "Files excluded from the manifest (binary, secret, oversize, sampled out).",
    "Units still pending or failed; see build/breadth-coverage-" + lane + ".json.",
    ...(limit > 0
      ? ["limit " + limit + " truncated this run's record list; records beyond it stayed pending (" +
         agg.pending + " pending now)."]
      : []),
  ],
};
return reportOut;
