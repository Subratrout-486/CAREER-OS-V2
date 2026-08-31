# Automation Adapter Plan

## Goal
Provide a local, auditable execution layer that an agent can call for approved LinkedIn operations.

## Recommended boundary

```text
Agent / Career OS
      |
      v
Policy + approval gate
      |
      +--> Official LinkedIn API adapter (preferred)
      |
      +--> Local browser adapter (only where appropriate/permitted)
      |
      v
Action result + audit log
```

## Candidate open-source patterns researched

1. MCP + Playwright: `joaovaleri/linkedin-mcp`
2. OAuth/CLI agent interface: `mudrii/golink`
3. LinkedIn analytics/content MCP: `southleft/linkedin-mcp`
4. Local browser MCP: `BrowserMCP/mcp`
5. Human-in-the-loop engagement: `dancolta/linkedin-engage`

## Requirements for our implementation

- dry-run mode
- explicit action policy
- action audit log
- retry and failure states
- screenshot capture on browser failure
- no credentials in repository
- no CAPTCHA bypass
- no anti-detection/evasion logic
- configurable daily action limits
- human approval for identity-bearing actions by default

## First implementation target

Build the deterministic content queue and audit layer first. Then attach an authenticated LinkedIn adapter. The adapter should expose narrow operations such as `get_profile`, `create_post`, `add_comment`, and `get_post_metrics`, subject to whatever official or permitted interface is available at runtime.
