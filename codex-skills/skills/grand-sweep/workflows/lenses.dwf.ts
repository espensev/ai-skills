/* zcode-workflow
description: Run one lens set of a grand-sweep campaign, one read-only auditor per lens.
args:
  campaign:
    type: string
    required: true
    description: Absolute forward-slash campaign directory (build/kit snapshot owner).
  crewPy:
    type: string
    required: true
    description: Absolute path of the frozen scripts/crew.py to run.
  set:
    type: string
    required: true
    description: Lens set name; reads build/lenses-<set>.json from the campaign.
  limit:
    type: number
    default: 0
    description: Run at most N lenses (0 means all pending lenses).
*/

interface LensRecord {
  /** Slug of the lens; becomes the subagent name and verdict file name. */
  name: string;
  /** Human title of the lens. */
  title: string;
  /** What this lens audits. */
  brief: string;
  /** Repo-relative paths the lens should read. */
  inputs: string[];
}

interface LensList {
  campaign: string;
  /** Frozen source root every input path resolves under. */
  root: string;
  /** Commit of the frozen root. */
  commit: string;
  lenses: LensRecord[];
}

interface ProbeResult {
  /** True only when the probe file round-tripped through staging. */
  ok: boolean;
  /** What the probe did and saw. */
  detail: string;
}

interface Candidate {
  /** low, medium or high. */
  severity: "low" | "medium" | "high";
  /** path:line of the issue. */
  where: string;
  /** One sentence: what is wrong. */
  what: string;
  /** Quoted lines or command+output that shows it. */
  evidence: string;
}

interface LensVerdict {
  /** The slug of this lens. */
  lens: string;
  /** completed or failed, as recorded in the verdict file. */
  status?: string;
  /** Issues found, each cited path:line with evidence. */
  candidates: Candidate[];
  /** Areas checked and found consistent. */
  clean: string[];
  /** What this lens could not check and why. */
  notCovered: string[];
  /** One-sentence verdict summary. */
  summary?: string;
}

interface LensAggLine {
  set: string;
  lenses: number;
  withVerdict: number;
  candidates: number;
  bySeverity: { low: number; medium: number; high: number };
}

interface WorkflowReport {
  conclusion: string;
  findings: Candidate[];
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
const set = requireString("set");
const limit = typeof args.limit === "number" && args.limit > 0 ? Math.floor(args.limit) : 0;

phase("Load the lens list for the set");
const loadRes = await world.run(
  "python",
  ["-I", crewPy, campaign, "lenses", set, "--pending",
   ...(limit > 0 ? ["--limit", String(limit)] : [])],
  { timeoutMs: 120000 },
);
if (loadRes.exitCode !== 0) {
  throw new Error("crew.py lenses " + set + " exited " + loadRes.exitCode + ": " + loadRes.stderr);
}
const listing = JSON.parse(loadRes.stdout) as LensList;
if (typeof listing.root !== "string" || typeof listing.commit !== "string" ||
    !Array.isArray(listing.lenses)) {
  throw new Error("crew.py lenses " + set + " did not return a lens list object");
}
for (const lens of listing.lenses) {
  if (typeof lens.name !== "string" || typeof lens.title !== "string" ||
      typeof lens.brief !== "string" || !Array.isArray(lens.inputs) ||
      !lens.inputs.every((p) => typeof p === "string")) {
    throw new Error("malformed lens record: " + JSON.stringify(lens));
  }
  if (!/^[a-z0-9]+(-[a-z0-9]+)*$/.test(lens.name) || lens.name.length > 28) {
    throw new Error("lens name is not filename-safe: " + lens.name);
  }
}
const lensNames = listing.lenses.map((lens) => lens.name);
if (new Set(lensNames).size !== lensNames.length) {
  throw new Error("duplicate lens names in set " + set);
}
const auditorNames = listing.lenses.map((lens) => "lens-" + lens.name);
if (new Set(auditorNames).size !== auditorNames.length) {
  throw new Error("lens auditor subagent names would collide in set " + set);
}
log("Loaded " + listing.lenses.length + " pending lenses for set " + set +
    (limit > 0 ? " (limit " + limit + ")" : ""));

function verdictPathOf(lensName: string): string {
  return campaign + "/staging/lens/" + set + "/" + lensName + ".json";
}

function lensAsk(lens: LensRecord): string {
  return "You are a read-only seam auditor: lens " + lens.name + " (" + lens.title +
    ") of set " + set + ".\n" +
    "Brief: " + lens.brief + "\n" +
    "Frozen source root: " + listing.root + " (commit " + listing.commit +
    "). Resolve every repo-relative input path under that root and read only files there; " +
    "do not read the shared main checkout.\n" +
    (lens.inputs.length > 0
      ? "Inputs (repo-relative):\n" +
        lens.inputs.map((p) => "- " + p).join("\n") + "\n"
      : "") +
    "Read real files on disk and cite path:line for every claim; do not report a check you did not run; " +
    "style opinions are not findings. Severity: high = data loss, crash, wrong result or security exposure; " +
    "medium = real defect with a workaround; low = hygiene. If key or secret material is involved, name the " +
    "kind and location only, never print the value.\n" +
    "Escape every backslash when writing JSON (or use forward slashes) so the file stays valid JSON.\n" +
    "Resume check: if your verdict file at " + verdictPathOf(lens.name) +
    " already exists and parses as JSON with lens " + lens.name +
    " and status completed, return that object as your answer without redoing the work.\n" +
    "You are READ-ONLY: do not edit, create, move or delete any file except your own verdict file.\n" +
    "Write your verdict JSON to " + verdictPathOf(lens.name) +
    " with keys lens, status, candidates (each with severity, where, what, evidence), clean, notCovered, summary. " +
    "Then return the same object as your typed answer (lens, candidates, clean, notCovered).\n" +
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

let verdicts: LensVerdict[] = [];

if (listing.lenses.length > 0) {
  const first = listing.lenses[0];
  const dynamicParts = [first.name, first.title, first.brief, ...first.inputs];
  gateAsk(lensAsk(first), verdictPathOf(first.name), first.name, dynamicParts);

  phase("Probe a staging round-trip before any lens runs");
  const probe = await agent("probe-" + set).ask<ProbeResult>(
    "Pre-flight probe for lens set " + set + ".\n" +
    "Write the single line probe-ok to " + campaign + "/staging/lens/" + set + "/probe.txt, " +
    "then read that file back and confirm it says probe-ok.\n" +
    "Escape every backslash when writing files or JSON. The only file you may write is the probe file. " +
    "No machine-sensitive commands and no machine identity verifier runs. Return {ok, detail}.",
  );
  if (!probe.ok) {
    throw new Error("probe failed for lens set " + set + ": " + probe.detail);
  }
  log("Probe ok: " + probe.detail);

  phase("Run every lens in parallel, one read-only auditor per lens");
  const settled = await Promise.all(
    listing.lenses.map(async (lens) => {
      let verdict: LensVerdict;
      try {
        verdict = await agent("lens-" + lens.name).ask<LensVerdict>(lensAsk(lens));
      } catch (err: unknown) {
        const message = err instanceof Error ? err.message : String(err);
        verdict = { lens: lens.name, candidates: [], clean: [],
                   notCovered: ["ask rejected: " + message] };
      }
      report({ lens: lens.name, candidates: verdict.candidates.length,
               clean: verdict.clean.length });
      return verdict;
    }),
  );
  verdicts = settled;
  log("Lenses done this run: " + settled.length);
}

phase("Aggregate the lens verdicts and publish");
const aggRes = await world.run(
  "python", ["-I", crewPy, campaign, "lensagg", set],
  { timeoutMs: 120000 },
);
if (aggRes.exitCode !== 0) {
  throw new Error("crew.py lensagg " + set + " exited " + aggRes.exitCode + ": " + aggRes.stderr);
}
const agg = JSON.parse(aggRes.stdout) as LensAggLine;
log("Set " + set + ": " + agg.withVerdict + "/" + agg.lenses + " lenses with verdicts, " +
    agg.candidates + " candidates");

const candidates = verdicts.flatMap((v) => v.candidates);
const notable = candidates.filter(
  (c) => c.severity === "medium" || c.severity === "high");
const header = [
  "# Lens sweep - set " + set,
  "",
  "- Lenses with verdict: " + agg.withVerdict + " of " + agg.lenses,
  "- Candidates on disk: " + agg.candidates + " (" + agg.bySeverity.low + " low, " +
    agg.bySeverity.medium + " medium, " + agg.bySeverity.high + " high)",
  "",
  "## Candidates from this run",
  "",
];
const footer = ["", "Full detail in build/" + set + "-coverage.json."];
const blocks = verdicts.flatMap((v) => [
  ...v.candidates.map((c) =>
    "- **" + c.severity + "** " + c.where + " - " + c.what +
    "\n  > " + c.evidence.slice(0, 500).split("\n").join("\n  > ")),
]);

let markdown = header.concat(blocks.length > 0 ? blocks : ["None."], footer).join("\n");
while (utf8Bytes(markdown) > MARKDOWN_CAP_BYTES && blocks.length > 0) {
  blocks.pop();
  markdown = header.concat(blocks, footer).join("\n");
}

try {
  await artifact.markdown("lens-report", markdown, {
    title: "Lens sweep: " + set,
    description: "Lens verdicts and candidates for set " + set + ".",
    primary: true,
  });
} catch (err: unknown) {
  const message = err instanceof Error ? err.message : String(err);
  log("markdown publish rejected: " + message);
  await artifact.markdown("lens-report", [
    "# Lens sweep - set " + set,
    "",
    "The full report could not be published; see build/" + set + "-coverage.json",
  ].join("\n"), { title: "Lens sweep: " + set, primary: true });
}

const reportOut: WorkflowReport = {
  conclusion: "Lens set " + set + ": " + agg.withVerdict + " of " + agg.lenses +
    " lenses have verdicts with " + agg.candidates + " candidates on disk (" +
    agg.bySeverity.medium + " medium, " + agg.bySeverity.high + " high).",
  findings: notable,
  verified: [
    "Ask-content gate checked the first ask before any fan-out.",
    "Pre-flight probe verified a staging round-trip before any lens ran.",
    "Every verdict reconciled by crew.py lensagg " + set + " into build/" + set + "-coverage.json.",
  ],
  notCovered: [
    ...verdicts.flatMap((v) => v.notCovered.map((n) => v.lens + ": " + n)),
    "Candidates are lens proposals only; confirmation is the confirm tier's job.",
    ...(limit > 0
      ? ["limit " + limit + " truncated this run's lens list; lenses beyond it stayed pending."]
      : []),
  ],
};
return reportOut;
