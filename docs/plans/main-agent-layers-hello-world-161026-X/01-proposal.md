# Agent Layers: Prompts, LLMs, Tools + Hello-World Pipeline Check

> "Nothing says 'production-ready AI platform' like spending a day proving the robot can press a button that returns a random number."
> - El Barto

## Overview

**Request**: Create the prompts, LLMs and tools layers following `bryan-duarte/hackathon-anonymous-oct`. Add two first prompts (email analysis, hello world), configure Haiku as the provider model, add dummy tools, and expose a test endpoint that proves the whole agent pipeline is connected end to end.

**Created**: 2026-10-16

## What

- **Prompts layer.** Class-based prompts with a registry. Each prompt is a `Prompt` subclass with an `id`, an optional `response_schema` class attribute, and a `get_text_prompt(**variables)` method. The three existing string prompts (main agent, payment agent, invoice extraction) are migrated to classes. Two new ones are added: `EmailTriagePrompt` (templated with the email) and `HelloWorldPrompt`.
- **LLM layer.** `llm_gateway` switches from `ChatOpenAI` to `BearerAuthChatAnthropic`, which calls OpenRouter's Anthropic-compatible endpoint, as in the reference repo. A single default model `anthropic/claude-haiku-5.5` applies everywhere, with optional per-kind overrides.
- **Tools layer.** The stub `modules/tools` gets two dummy `@tool`s: `get_random_token` (random token + timestamp) and `get_system_profile` (a fixed schema).
- **Pipeline check.** `POST /diagnostics/hello-world` (public) runs `OrchestratorService.hello_world()`. It builds a deep agent with the hello-world prompt, the dummy tools and `ToolStrategy(HelloWorldReport)`, then returns the agent's structured report. The report includes the token the tool returned.

## Why

Agents, prompts and models are currently wired ad hoc: string constants, an OpenAI-compatible client and no tool registry. Before building real features such as email triage, we need:
- one consistent pattern for each layer;
- a cheap, repeatable way to confirm that the model, tool calling and structured output all work against the real provider.

## Impact

- `backend/modules/prompts`, `backend/modules/llm_gateway` and `backend/modules/tools` are rewritten or filled in.
- New contracts are added: `contracts/prompts.py` and `contracts/tools.py`. New clients are added: `clients/prompts.py`; `clients/tools.py` is filled in.
- The orchestrator, payments agent and invoice ingestor now read prompts through `PromptsClient`.
- Dependencies: `langchain-anthropic` is added and `langchain-openai` is removed. The `LlmSettings` fields change, and `.env.example` changes with them.
- New public router: `/diagnostics/hello-world`.

## Flow

```
curl POST /diagnostics/hello-world
        │
        ▼
diagnostics_router ──► clients.orchestrator.hello_world()
                               │
                               ▼
                 OrchestratorService.hello_world()
                   ├─ prompts.get_text_prompt(HELLO_WORLD)      ─► task text
                   ├─ prompts.get_response_schema(HELLO_WORLD)  ─► HelloWorldReport
                   ├─ tools.hello_world_tools()                 ─► [get_random_token, get_system_profile]
                   └─ llm.default_model()                       ─► BearerAuthChatAnthropic(haiku-5.5)
                               │
                               ▼
              create_deep_agent(... response_format=ToolStrategy(HelloWorldReport))
                               │  agent calls both tools via OpenRouter
                               ▼
              final_state["structured_response"]  ──► HelloWorldReport (JSON 200)
```
