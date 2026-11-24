# Discovery — grand-sweep campaign kit (2026-11-23)

Context: `grand-sweep` worked as a method (high verdict quality, review gates
held) but every campaign re-authored ~1,000 lines of script, and the
2026-11-21 `.audit/` + `.zcode/` cleanup destroyed a live campaign's
receipts, saved workflows and journals. Two prepared campaigns (18 Nov) were
never launched; rate-window stalls falsified the old "quota is not a
constraint" claim; the 2026-11-23 probe passed on access while every ask
said `undefined`; runs launched from a campaign directory were invisible from
the repository root because journals key on the launching session's cwd.

Decision (kit spec v1/v2, campaign `ps-shell-sweep-20261123-4522`): ship the
method as a versioned kit inside the skill — `scripts/crew.py`
(freeze/lanes/units/agg/check/subset/lenses/lensagg/candidates/confirmagg/status/close),
three generic workflow drivers, a deterministic freeze with kit snapshot
under `build/kit/`, `build/runs.json` as the run ledger, and a tender prompt
for a recurring automation that resumes and pauses itself. Re-authoring stays
the documented fallback.

ZCode projection: the installed `~/.zcode/skills/grand-sweep` copy
(2026-11-10) was older than this canonical file and shadowed it, and
`Install-AgentSkills.ps1` accepts only `Both|Codex|Claude`. Rather than add a
provider to the installer (its retirement/parity machinery is provider-shaped
and the single-skill need is narrow), a dedicated
`scripts/Sync-GrandSweepZCode.ps1` projects exactly the canonical
`grand-sweep` directory into the ZCode user-scope skills root: default
(check) mode reports drift and exits non-zero, `-Apply` replaces only that
one skill directory, unsafe names and in-package targets are refused, and its
Pester contract test is wired into `Test-ReleaseReadiness.ps1`. After
review, apply mode no longer deletes recursively: it copies the canonical
files, removes only the computed extras, and drops empty directories; it
refuses a target that is a file or a reparse point. Running
`scripts/tests/*.Tests.ps1` requires Pester 5+ (the gate uses the DevHome
runtime, which provides Pester 6.2.0 — the tests there run 11/11); bare
`pwsh -NoProfile` on this machine only sees Pester 3.4.0 and cannot run
them.

## Review record

- Spec review (APPROVE-WITH-CHANGES, adopted): freeze determinism vs
  timestamps in the manifest; unconsumed subsets; unbounded retry of failing
  units (→ attempts, terminal-failed at 3); lossy candidate ids (→
  content-addressed ids); undefined lens schema (→
  `build/lenses-<set>.json` shape); markdown cap counted in chars (→ bytes);
  missing `timeoutMs` values.
- Controller driver review: gate false positive on "null" (→ word-boundary
  gate over dynamic fields and focus/brief only); self-skipping probe (→
  probes carry no resume check and always perform the real read/hash/write/
  read-back); mutated container; missing frozen root and commit in lens and
  confirm asks. All fixed test-first.
- Independent kit review (REJECT): ANSI-code-page stdout corrupting non-ASCII
  lens briefs; `freeze` overwriting the snapshot before refusing. Both fixed
  test-first.
- First live use: campaign `ps-shell-sweep-20261123-4522`, revision 2,
  132 units, 5 breadth lanes + 2 lens sets launched 2026-11-23.

## First live use: outcome

Campaign `ps-shell-sweep-20261123-4522`, measured 2026-11-23/24: 460 files
frozen into 132 units at `928abd4`; 132 of 132 units and 24 of 24 lenses
completed; 285 de-duplicated candidates; about 124M tokens in the campaign
tiers (83M in workflow runs, 41M in native lanes). Three review rounds before
launch each found a real defect (recorded above). Retiring the pinned worktree
after close made `check` report every file missing, so `check`/`close` gained
`--repository <checkout>` to re-verify identities from the frozen commit.

Confirmation calibrated severity both ways. Of 56 medium/high candidates, 50
were confirmed (0 high, 33 medium, 17 downgraded to low), 5 refuted, and 1
duplicate. Both reviewer-rated "high" candidates did not survive: one was
downgraded to medium (report noise), one was refuted against the verification
gate log. A verification-gate log from the same tree was given to confirmers
as primary evidence and settled several claims.

Eval: `grand-sweep-basic-001` keeps its original tokens and gains kit checks
(`crew.py`, `freeze`, `lifecycle`, `build/kit`, `repository root`); the mock
response and committed snapshot still score 35/35 offline.
