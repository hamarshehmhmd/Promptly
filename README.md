# Promptly

A QGIS plugin that provides a simple interface to send prompts to various LLM providers and execute the generated Python code in QGIS.

## Features

- Send custom prompts to multiple LLM providers:
  - Ollama (local)
  - OpenAI (GPT models)
  - OpenRouter (access to multiple models)
  - Anthropic (Claude models)
  - Custom API endpoints
- View both full LLM responses and automatically extracted code in a tabbed interface
- Edit the generated code before execution
- Execute the code directly within QGIS
- Simple and lightweight UI

## Requirements

- QGIS 3.x
- Python 3.x
- `requests` Python package
- For Ollama: [Ollama](https://github.com/jmorganca/ollama) running locally or on a remote server
- For other providers: Valid API key

## Installation

1. Download or clone this repository
2. Copy the `QGISPromptExecutor` folder to your QGIS plugins directory:
   - Windows: `C:\Users\{username}\AppData\Roaming\QGIS\QGIS3\profiles\default\python\plugins`
   - Linux: `~/.local/share/QGIS/QGIS3\profiles\default/python/plugins`
   - macOS: `~/Library/Application Support/QGIS/QGIS3\profiles\default/python/plugins`
3. Enable the plugin in QGIS:
   - Open QGIS
   - Go to Plugins > Manage and Install Plugins
   - Find "Promptly" in the list and check the box to enable it

## Usage

1. Click the Promptly icon in the toolbar or go to Plugins > Promptly
2. Select your preferred LLM provider from the dropdown menu
3. Configure the provider settings:
   - API Key (required for all providers except Ollama)
   - API Endpoint (pre-filled with the default for each provider)
   - Model (pre-filled with a recommended model for each provider)
   - Temperature and Max Tokens (adjust as needed)
4. Enter your prompt in the text area
5. Click "Send to LLM" to submit your prompt
6. View results in two tabs:
   - "Full Response" tab shows the complete response from the LLM
   - "Executable Code" tab shows only the extracted Python code
7. Review and edit the code if necessary
8. Click "Execute Code" to run the code in QGIS

## Provider-Specific Settings

### Ollama
- API Endpoint: `http://localhost:11434/api/generate` (adjust if running on a different port or server)
- Model: depends on what models you have pulled locally (e.g., `qwen2.5-coder:32b-instruct-q5_K_M`)
- API Key: Not required

### OpenAI
- API Endpoint: `https://api.openai.com/v1/chat/completions`
- Model: `gpt-4o`, `gpt-4-turbo`, `gpt-3.5-turbo`, etc.
- API Key: Your OpenAI API key

### OpenRouter
- API Endpoint: `https://openrouter.ai/api/v1/chat/completions`
- Model: 
  - OpenAI models: `openai/gpt-4o`, `openai/gpt-4-turbo`
  - Anthropic models: `anthropic/claude-3-opus`, `anthropic/claude-3-sonnet`
  - Other models: Check [OpenRouter's models page](https://openrouter.ai/models)
- API Key: Your OpenRouter API key

### Anthropic
- API Endpoint: `https://api.anthropic.com/v1/messages`
- Model: `claude-3-opus-20240229`, `claude-3-sonnet-20240229`, etc.
- API Key: Your Anthropic API key

### Custom
- API Endpoint: URL of your custom LLM provider's API
- Model: The model identifier accepted by your provider
- API Key: You can either:
  - Enter a simple API key which will be used as `Bearer [key]`
  - Enter a JSON object containing custom headers, e.g., `{"Authorization": "Bearer abc123", "Custom-Header": "value"}`

## Examples

Example prompts:
- "Calculate the area of layer 'buildings' and add it as a new field named 'area_sqm'"
- "Create a buffer of 100 meters around layer 'rivers' and save it as a new layer"
- "Change the style of layer 'roads' to show different colors based on the 'type' attribute"

## Troubleshooting

- **API Key Issues**: Make sure your API key is valid and has not expired
- **Model Selection**: Ensure the model you selected is available with your account/subscription
- **Network Issues**: Check your network connection and firewall settings
- **Response Format**: If you get a response but no code is extracted, check if the LLM is generating code in the expected format (with ```python code blocks)

## License

This plugin is licensed under the [MIT License](LICENSE). 