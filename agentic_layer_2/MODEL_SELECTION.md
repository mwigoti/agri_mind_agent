# Hosted model comparison

**Current selection:** `Qwen/Qwen2.5-7B-Instruct` via Hugging Face Inference Providers' OpenAI-compatible chat completions route (`MODEL_BASE_URL=https://router.huggingface.co/v1`). This is a provisional implementation default, selected for Apache-2.0 licensing and ecosystem fit. It does not establish that this exact model/provider supports reliable native tool calls or has passed AgriMind tasks. This implementation asks for constrained JSON; model outputs never execute tools directly.

| Candidate | Open-weights / license | Hosting and interaction | Assessment |
|---|---|---|---|
| Qwen2.5-7B-Instruct | Hub card lists Apache-2.0 | Inference Providers exposes chat completions; provider-specific tool/JSON support varies | Default, moderate footprint and Qwen-aligned. Must test actual tool choice, schema adherence, latency, and cost. |
| Qwen3-4B-Instruct-2507 | Apache-2.0 | Listed in Inference Providers documentation | Smaller alternative for lower latency/cost; no task run performed. |
| Llama-3.1-8B-Instruct | Llama 3.1 Community License | Provider availability/access conditions vary | Plausible instruction model, but license is less permissive than Apache-2.0 and adds review obligations. |

Hugging Face documents routed provider billing, configurable providers, and a small monthly credit amount for free users that may change. It also documents function calling at the routed API layer; this is not proof that each model/provider pairing honors tool calls. No live model request was possible in this implementation session, so price, rate limits, exact endpoint availability, and AgriMind task performance remain unverified. See the official [Qwen model card](https://huggingface.co/Qwen/Qwen2.5-7B-Instruct), [Qwen3 license](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507/blob/main/LICENSE), [Llama model card](https://huggingface.co/meta-llama/Llama-3.1-8B-Instruct), [Hugging Face function calling guide](https://huggingface.co/docs/inference-providers/en/guides/function-calling), and [provider pricing](https://huggingface.co/docs/inference-providers/pricing).

Hosted inference transmits request contents to an external provider. Use only synthetic records for the demo; obtain appropriate authorization before sending personal or household data. No weights are downloaded locally and no sovereignty guarantee is made.
