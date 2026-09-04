# Repository Audit Matrix — CAREER-OS-V2

Internal audit against **every repository supplied for this project**. Each is
classified: INSPECTED / USED / INTEGRATED / TESTED, with a decision and reason.
No repository is integrated merely to inflate the matrix — the objective is a
coherent production architecture.

## Matrix

| Repository | Purpose | Inspected? | Used? | Integrated? | Where? | Tested? | Decision | Reason if not used |
| ---------- | ------- | ---------- | ----- | ----------- | ------ | ------- | -------- | ------------------ |
| Lourenco-biel/Auto_Jobs_Applier_AIHawk | Standalone Selenium auto-apply bot | ✅ (API+README) | Architecture only | ✅ pattern (portal abstraction; forbidden-bypass discipline) | `execution/flow.py` portal detection; `autoapply/adapter.py` | ✅ (`test_autoapply_chain.py`) | REFERENCE ONLY (patterns) | Standalone app, LLM/resume/schema/secrets bundled; not embeddable as a library; would violate integration rules |
| taoyota/aihawk | Fork reorganizing AIHawk into modules | ✅ (API+README) | Architecture only | ⚠️ partial (module-separation pattern) | `autoapply/` layered layout | ✅ (same tests) | REFERENCE ONLY | Same embeddability limits; no net-new capability |
| vasu-devs/JustHireMe | Local-first Python/React job workbench (AGPL) | ✅ (resolved 2235★) | Architecture only | ✅ pattern (supported-vs-experimental flow model; quality gate) | `execution/flow.py` `supported` flag; approval gate in `execution/state.py` | ✅ | REFERENCE ONLY (AGPL not imported) | AGPL-3.0 + standalone app; the supported/experimental model was adopted, code was not |
| MadsLorentzen/ai-job-search | Claude-Code CLI operator framework | ✅ (API+README) | — | ⚠️ (different execution model) | carried in `autonomy/loop.py` checkpoint model | ✅ (`test_provider_controller.py` etc.) | REFERENCE ONLY | Operator/CLI model; our harness runs as libraries, not Claude Code |
| MaxMiksa/Auto-Company | 24/7 agent harness + dashboard server | ✅ (API+README) | — | ⚠️ (agent-loop pattern only) | `autonomy/` durable loop | ✅ | REFERENCE ONLY | Standalone; the durable loop idea is already native |
| D4Vinci/Scrapling | Adaptive scraping framework | ✅ | ✅ (optional dependency) | ✅ (pre-existing integration) | `discovery/scraper.py` prefers Scrapling when installed, stdlib fallback otherwise | ✅ (existing discovery tests) | OPTIONAL PROVIDER (already integrated when installed) | Scrapling not installed in the sandbox venv; code path exists and is tested via fallback |
| FreeLLMAPI / free-llm-api | Free LLM API catalog (top resolved: `mnfst/awesome-free-llm-apis`, 7.3k★) | ✅ (search + README) | — | — | informs provider config surface only | n/a | REFERENCE ONLY | Catalog (not installable/dev-dep); free providers surface via env-config OpenAI-compatible endpoints, not by importing a catalog |
| diegosouzapw/OmniRoute | MIT free AI gateway, 352 providers / 150+ free, OpenAI-compatible | ✅ (README/API) | Architecture only | ⚠️ optional endpoint target | `providers/routing.py` `HTTPProviderAdapter` (env `CAREER_OS_*_BASE_URL`-compatible) | ✅ (`test_provider_routing.py`) | OPTIONAL PROVIDER | Requires self-hosting a 61k★ gateway + live endpoint; none present in sandbox; the adapter surface exists so it can be pointed at it |
| ollama/ollama | Local-model runtime (MIT) | ✅ (API/README) | Used (adapter) | ✅ (existing adapter) | `providers/routing.py` `OllamaAdapter` via `CAREER_OS_OLLAMA_URL` | ✅ (`test_provider_routing.py` outage/fallback) | OPTIONAL PROVIDER | Ollama not installed/running in sandbox; adapter exists and reports OUTAGE when unreachable; pipeline stays deterministic via offline fallback |
| punkpeye/awesome-mcp-servers | Catalog of MCP servers (94k★) | ✅ (API) | — | — | — | n/a | NOT NEEDED | Career OS has no MCP server host/tool layer; catalog adds no required capability to the current architecture |
| public-apis/public-apis | Collective list of free public APIs (475k★) | ✅ (API) | Used (prior) | ✅ (prior discovery work: PublicJob/ATS APIs) | `discovery/service.py` ATS + PublicJob sources | ✅ | REFERENCE ONLY | Discovery sources are already implemented (ATS/PublicJob/Scrapling); no new API needed for the current scope |
| ripienaar/free-for-dev | Free SaaS/PaaS/IaaS tiers (136k★) | ✅ (API) | — | — | — | n/a | REFERENCE ONLY | Applied where relevant (free provider tiers inform the optional provider config); no infra dependency introduced |
| VoltAgent/awesome-design-md | DESIGN.md collection by brand design systems (114k★) | ✅ (README) | Used (concept) | ✅ (original ARACHNE system) | `DESIGN.md` + motion/states in `dashboard/index.html` | ✅ (JS syntax check; ARACHNE tests) | INTEGRATED (original design, no copied branding) | Produces the ARACHNE DESIGN.md + applied principles; does not copy any external brand |

## Decisions summary

- **INTEGRATED**: ARACHNE design system (`DESIGN.md` + dashboard), auto-apply
  adapter + flow detection (patterns from AIHawk/JustHireMe), provider health
  routing (routing.py), Scrapling (pre-existing optional), Ollama adapter
  (pre-existing optional).
- **OPTIONAL PROVIDER**: OmniRoute, Ollama — reachable through the provider
  adapter surface when a real endpoint/key exists; never assumed available.
- **REFERENCE ONLY**: FreeLLMAPI catalog, ai-job-search, Auto-Company, public-apis,
  free-for-dev.
- **NOT NEEDED**: awesome-mcp-servers (no MCP host in this product).

## Provider capability (no fabricated credentials)

| Provider | Status in this environment | Why |
| -------- | -------------------------- | --- |
| offline (deterministic) | AVAILABLE | Always-on fallback; pipeline is fully operational with zero credentials |
| ollama (local) | OUTAGE / NOT_CONFIGURED | No running Ollama endpoint in the sandbox; adapter probes `CAREER_OS_OLLAMA_URL` |
| http (credentialed, e.g. OmniRoute endpoint) | NOT_CONFIGURED | No API key/base-URL configured; adapter requires `CAREER_OS_*_API_KEY` |
| Free tier providers | NOT_CONFIGURED | Would observe real quota/rate-limit states only after a real credential exists |