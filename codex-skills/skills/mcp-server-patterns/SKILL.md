---
name: mcp-server-patterns
description: "Build and maintain MCP servers with current SDK semantics, schema validation, and clear transport choices. Use when implementing tools, resources, prompts, stdio servers, or HTTP-based MCP services."
---

# MCP Server Patterns

Build MCP servers from the current SDK and protocol surface, not from stale
examples.

## Dependencies

- Required: none
- Optional: Context7 or official MCP documentation sources
- Fallback: official MCP docs and the current SDK README or release notes

## Workflow

1. Confirm the SDK and version already in the repo.
2. Verify the current registration API before writing code:
   - tool or registerTool
   - resource or registerResource
   - prompt registration shape
   - transport setup
3. Keep domain logic separate from transport wiring.
4. Define schemas first:
   - validate tool input
   - keep return shapes consistent
   - prefer explicit error payloads over raw stack traces
5. Choose transport deliberately:
   - stdio for local clients
   - streamable HTTP for remote clients
   - support legacy transports only when compatibility requires them
6. Keep tools idempotent when practical and document cost or rate-limit risks.
7. Test registration and one happy-path invocation before calling the work done.

## Design Rules

- Prefer small tools with narrow input contracts.
- Keep resources read-oriented and predictable.
- Avoid transport-specific logic in core business functions.
- Pin SDK versions when the server is intended to be stable.
- Re-check signatures when upgrading the SDK.

## Output

When implementing or reviewing an MCP server, produce:

1. chosen transport and why
2. tool or resource contract summary
3. validation approach
4. minimal working example or patch
5. verification step
