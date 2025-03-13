
<div align="left">
  <img src="icons/icon.png" alt="promptly Logo" width=fit>
  <h1>Promptly</h1>
</div>


A QGIS plugin that provides a simple interface to send prompts to various LLM providers and execute the generated Python code in QGIS.
My Email: hamarshehmhmd@gmail.com



## Features

- Send custom prompts to multiple LLM providers
- View both full LLM responses and extracted code
- Edit and execute code within QGIS
- Lightweight UI

## Requirements

| Requirement | Details |
|------------|---------|
| QGIS | 3.x |
| Python | 3.x |
| Dependencies | `requests` package |
| Ollama | [Ollama](https://github.com/jmorganca/ollama) (local/remote) |
| Other Providers | Valid API key |

## Installation

1. Download or clone this repository.
2. Copy `QGISPromptExecutor` to the QGIS plugins directory:
   - **Windows:** `C:\Users\{username}\AppData\Roaming\QGIS\QGIS3\profiles\default\python\plugins`
   - **Linux:** `~/.local/share/QGIS/QGIS3/profiles/default/python/plugins`
   - **macOS:** `~/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins`
3. Enable the plugin via **Plugins > Manage and Install Plugins**.

### Alternative Installation

1. Download the ZIP file.
2. Install via **Plugins > Manage and Install Plugins > Install from ZIP**.

''' This Plugin Will soon be available on the QGIS plugin store for easier installation'''

## Usage

1. Open **Plugins > Promptly** or click the toolbar icon.
2. Select an LLM provider.
3. Configure settings (API Key, Endpoint, Model, etc.).
4. Enter a prompt and click **Send to LLM**.
5. Review results:
   - **Full Response**: Complete LLM output.
   - **Executable Code**: Extracted Python code.
6. Edit and execute code within QGIS.

## Provider-Specific Settings

| Provider  | API Endpoint | Model | API Key Required? |
|-----------|-------------|-------|------------------|
| **Ollama** | `http://localhost:11434/api/generate` | Depends on local models | No |
| **OpenAI** | `https://api.openai.com/v1/chat/completions` | `gpt-4o`, `gpt-3.5-turbo`, etc. | Yes |
| **OpenRouter** | `https://openrouter.ai/api/v1/chat/completions` | OpenAI, Anthropic, and others | Yes |
| **Anthropic** | `https://api.anthropic.com/v1/messages` | `claude-3-opus`, `claude-3-sonnet` | Yes |
| **Custom** | User-defined | User-defined | Yes (if required) |

## Examples

| Task | Example Prompt |
|------|---------------|
| Calculate area | "Calculate area of 'buildings' layer and add as 'area_sqm'" |
| Buffer creation | "Create 100m buffer around 'rivers' and save as new layer" |
| Style update | "Change 'roads' layer color based on 'type' attribute" |

## Troubleshooting

| Issue | Solution |
|-------|---------|
| **API Key Issues** | Ensure the key is valid and not expired. |
| **Model Selection** | Check model availability in your subscription. |
| **Network Issues** | Verify connection and firewall settings. |
| **Response Format** | Ensure LLM outputs Python code within ```python blocks. |

## License

This plugin is licensed under the [MIT License](LICENSE).

