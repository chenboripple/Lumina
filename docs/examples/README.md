# Examples and Demo Files

This folder contains runnable examples and sample configuration for quick validation.

## Python Demo Scripts

- Incremental processing demo: [demo_incremental.py](../../scripts/demo/demo_incremental.py)
- Quick start script: [quick_start.py](../../scripts/dev/quick_start.py)

## Sample Config

- Separate LLM settings example: [docs/examples/example_config_with_separate_llm.yaml](example_config_with_separate_llm.yaml)
- Local models and domestic API example: [docs/examples/config-with-local-models.yaml](config-with-local-models.yaml)

### Supported LLM Providers

- **Local**: `ollama`, `llamacpp` (no API key needed)
- **Domestic (China)**: `deepseek`, `bailian`, `volcengine`, `kimi`, `glm`
- **International**: `openai`, `anthropic`

## How to Use

1. Read [docs/deployment/config-reference.md](../deployment/config-reference.md).
2. Copy and adapt [docs/examples/example_config_with_separate_llm.yaml](example_config_with_separate_llm.yaml).
3. For local models or domestic APIs, see [docs/examples/config-with-local-models.yaml](config-with-local-models.yaml).
4. Run the demo scripts from repo root.
