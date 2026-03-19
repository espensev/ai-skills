# Gemini Context-Native Skills

While the initial focus of `gemini-skills` is to map the generic skill set (Discover, Planner, Manager, QA, Ship, Loop, Loop Master), Gemini's massive context window enables a new class of skills that are not feasible on other runtimes.

The following concepts represent "Context-Native" skills designed specifically to leverage Gemini's ability to ingest massive amounts of data at once:

## 1. The "Repo-Scale Refactoring" Skill (`epic-refactor`)

*   **The Concept:** A skill designed for massive, cross-cutting architectural changes (e.g., "Migrate our entire data layer from REST to GraphQL" or "Upgrade from React 15 to 19").
*   **The Gemini Advantage:** Claude and GPT will hallucinate or lose the thread halfway through a 300-file migration. Gemini can ingest the entire project, build a topological map of the dependencies, and systematically rewrite it while holding the entire migration state in context.

## 2. The "Mega-Log Analyzer" Skill (`forensic-debugger`)

*   **The Concept:** A skill that ingests raw, unparsed production logs, memory dumps, or network PCAP files.
*   **The Gemini Advantage:** If you have a 500MB server log from a production crash, GPT and Claude require you to write scripts to filter it down first. Gemini can ingest the entire raw log file, cross-reference the exact timestamps with your application code, and pinpoint the microservice that caused the cascade failure.

## 3. The "Visual-to-Component" CI Skill (`ui-test-engineer`)

*   **The Concept:** A skill that integrates with Playwright or Cypress. When a test fails, it captures a video of the test run and screenshots of the failure.
*   **The Gemini Advantage:** Gemini can watch the video of the failing end-to-end test, look at the DOM snapshot, read the Cypress test code, and read your frontend components all at once to fix the visual regression.

## 4. The "Living Documentation" Synchronizer (`doc-weaver`)

*   **The Concept:** A skill that enforces the "Planning Contracts" mentioned in your `.gemini.md` file. It continuously reads your entire codebase and cross-references it with your architecture Wiki/Markdown files.
*   **The Gemini Advantage:** If a developer changes a core database schema, Gemini can automatically detect that it invalidates an architectural diagram in a Markdown file 5 folders away and rewrite the documentation to match the new code, because it has both the code and the docs in its massive context window.

## Impact on Campaign Planning

Gemini's massive context window transforms how multi-agent campaigns (Discover, Planner, Manager, QA, Ship) are structured and executed. By leveraging context-native skills, campaign planning can evolve in the following ways:

*   **Zero-Shot Discovery & Graphing:** The `Discover` and `Planner` agents no longer need to sequentially crawl a codebase. They can ingest the entire repository at once to instantly draft the "Graph" and "Integration" sections of the 13-element Planning Contract, eliminating discovery latency.
*   **Holistic Verification:** The `QA` agent can validate the "Verification" and "Exit Criteria" steps of a contract by analyzing the proposed changes against massive datasets—such as full production logs or comprehensive UI test recordings—in a single evaluation pass.
*   **Continuous Synchronization:** The `doc-weaver` concept allows the `Loop Master` to maintain the "Docs" and "Schema" sections of the Planning Contract effortlessly. It can diff the entire codebase against the entire documentation suite simultaneously, spawning `Loop` agents only when structural drifts are detected.
*   **Massive Refactoring Campaigns:** A `Manager` agent orchestrating an `epic-refactor` campaign can safely assign parallel tasks to `Loop` agents. Because the "Conflicts" and "Ownership" elements of the contract are informed by a global context map, the risk of breaking distant dependencies is practically eliminated.

## Taming Massive Context: The "Lens" Strategy

More context equals more power, but it also increases the risk of the model "losing the plot" or making unauthorized, out-of-scope changes. We channel Gemini's capabilities by using its massive window for *perfect comprehension*, while strictly limiting its *execution* through the **13-element Planning Contract**.

This is how Gemini natively executes the `Plan -> Run -> Verify` lifecycle:

### 1. Plan: The Ground Truth Baseline (`codebase_investigator` & `enter_plan_mode`)
*   **The Mechanism:** Instead of a separate `Planner` agent crawling the code sequentially, Gemini uses tools like `codebase_investigator` or `enter_plan_mode` to ingest the repository and map its architecture instantly.
*   **The Guardrail:** The output of this phase is *strictly* the 13-element Planning Contract. By forcing Gemini to distill massive context down into a rigid Markdown contract (focusing heavily on `Graph`, `Ownership`, and `Exit Criteria`), we compress the global view into a deterministic, human-readable boundary box.

### 2. Run: The Focused Worker (Read-All, Write-Scoped)
*   **The Mechanism:** There is no need to spin up isolated `Loop` agents for most tasks. Gemini CLI executes the changes directly using its native tools (`replace`, `write_file`).
*   **The Guardrail:** The contract's `Ownership` section acts as "The Lens." Even though Gemini has the entire codebase loaded to prevent breaking distant dependencies, its write access is strictly logically scoped to the current contract task. If a change falls outside the task's defined scope, it must be rejected or added to a new contract.

### 3. Verify: Holistic, Context-Aware QA
*   **The Mechanism:** Instead of a separate `QA` agent running isolated unit tests, Gemini CLI uses `run_shell_command` to execute tests natively.
*   **The Guardrail:** The massive context window is weaponized for defense. Because Gemini holds the whole project, it acts as a semantic compiler. When a test fails or a log is produced, it instantly cross-references the error against the entire proposed git diff and the `Conflicts` section of the contract to detect unintended "butterfly effects" before the code is merged.

## Actionable Next Steps

To operationalize this strategy and move from theory to execution, the immediate priority for the `gemini-skills` adapter is to:

1.  **Draft the Epic Refactor Proof-of-Concept:** Scaffold the `.gemini/commands/epic-refactor.toml` wrapper and its underlying instruction set to provide a working example of a context-native skill.
2.  **Define Context Bounds:** Explicitly map out how `epic-refactor` relies on the `docs/planning-contract.md` to prevent massive hallucinations during a repo-wide rewrite.