# Hosted model configuration

The default model is OpenRouter's `openrouter/free` router at `https://openrouter.ai/api/v1`. It selects a free model that fits the request and routes only to free models. Current free model availability can change; the router avoids hard-coding a model that may later disappear.

The OpenRouter free tier is rate limited. OpenRouter documents 20 requests per minute and 50 per day for `:free` variants, and says free model variants do not require purchasing credits. The router is designed to remain free-only; do not add paid model fallbacks if zero-cost use is required. See [OpenRouter free models](https://openrouter.ai/collections/free-models) and the [`:free` routing guide](https://openrouter.ai/docs/guides/routing/model-variants/free).

Set `OPENROUTER_API_KEY` locally. Do not commit or share the key. `MODEL_ID` and `MODEL_BASE_URL` remain configurable. A Gemini-branded model is not the default because OpenRouter's current Google free offerings include Gemma rather than Gemini; the free router can choose among currently eligible free models.

Model output is JSON parsed and validated by the application; it cannot call tools or modify authoritative farm records directly. The provider receives the evidence included in each prompt, so use only records authorized for hosted processing.
