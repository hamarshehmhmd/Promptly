# -*- coding: utf-8 -*-
"""
/***************************************************************************
 Promptly
                                 A QGIS plugin
 Execute LLM-generated code for QGIS processing
***************************************************************************/
"""

import os
import json
import traceback
import time
import threading
import io
import sys
from contextlib import redirect_stdout, redirect_stderr

from qgis.PyQt import uic
from qgis.PyQt.QtWidgets import QDialog, QMessageBox, QProgressBar
from qgis.PyQt.QtCore import Qt, QTimer, QObject, pyqtSignal
from qgis.PyQt.QtGui import QColor
from qgis.core import QgsMessageLog, Qgis

# This loads your .ui file so that PyQt can populate your plugin with the elements from Qt Designer
FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'qgis_prompt_executor_dialog_base.ui'))


# Worker class for thread-safe signals
class WorkerSignals(QObject):
    """Defines the signals available from a running worker thread."""
    status = pyqtSignal(str, str)  # (message, status_type)
    result = pyqtSignal(str, str)  # (full_response, code)
    error = pyqtSignal(str)
    finished = pyqtSignal()
    error_log = pyqtSignal(str)  # For updating the error log tab


class QGISPromptExecutorDialog(QDialog, FORM_CLASS):
    def __init__(self, parent=None):
        """Constructor."""
        super(QGISPromptExecutorDialog, self).__init__(parent)
        # Set up the user interface from Designer through FORM_CLASS.
        # After self.setupUi() you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots
        self.setupUi(self)
        
        # Connect signals
        self.pushButtonSend.clicked.connect(self.send_to_llm)
        self.pushButtonExecute.clicked.connect(self.execute_code)
        self.pushButtonFixCode.clicked.connect(self.fix_code)
        self.comboBoxProvider.currentIndexChanged.connect(self.on_provider_changed)
        
        # Disable fix button initially (until there's an error)
        self.pushButtonFixCode.setEnabled(False)
        
        # Store the last error for code fixing
        self.last_error = ""
        self.last_code = ""
        
        # Create progress timer for animated status messages
        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self.update_progress_status)
        self.progress_dots = 0
        self.current_operation = ""
        
        # Initialize default provider settings
        self.provider_endpoints = {
            "Ollama": "http://localhost:11434/api/generate",
            "OpenAI": "https://api.openai.com/v1/chat/completions",
            "OpenRouter": "https://openrouter.ai/api/v1/chat/completions",
            "Anthropic": "https://api.anthropic.com/v1/messages",
            "Custom": ""
        }
        
        self.provider_default_models = {
            "Ollama": "qwen2.5-coder:32b-instruct-q5_K_M",
            "OpenAI": "gpt-4o",
            "OpenRouter": "openai/gpt-4o",
            "Anthropic": "claude-3-opus-20240229",
            "Custom": ""
        }
        
        # Initialize UI with default provider
        self.on_provider_changed(0)  # Ollama is index 0
        
        # Clear response fields
        self.plainTextEditFullResponse.setPlainText("")
        self.plainTextEditCode.setPlainText("")
        self.plainTextEditErrorLog.setPlainText("")
        
        # Set initial status
        self.set_status("Ready", "normal")
        
    def update_progress_status(self):
        """Update the animated dots in the status message during operations."""
        self.progress_dots = (self.progress_dots + 1) % 4
        dots = "." * self.progress_dots
        self.labelStatus.setText(f"⏳ {self.current_operation}{dots}")
        
    def set_status(self, message, status_type="normal"):
        """
        Set the status message with proper formatting.
        
        Args:
            message (str): Message to display
            status_type (str): Type of status - "normal", "success", "error", "warning", "progress"
        """
        # Stop any running progress timer
        self.status_timer.stop()
        
        # Format status message based on type
        if status_type == "success":
            self.labelStatus.setText(f"✅ {message}")
            self.labelStatus.setStyleSheet("color: green; font-weight: bold;")
        elif status_type == "error":
            self.labelStatus.setText(f"❌ {message}")
            self.labelStatus.setStyleSheet("color: red; font-weight: bold;")
        elif status_type == "warning":
            self.labelStatus.setText(f"⚠️ {message}")
            self.labelStatus.setStyleSheet("color: orange; font-weight: bold;")
        elif status_type == "progress":
            # Start animated progress indicator
            self.current_operation = message
            self.progress_dots = 0
            self.labelStatus.setText(f"⏳ {message}")
            self.labelStatus.setStyleSheet("color: blue; font-weight: bold;")
            self.status_timer.start(500)  # Update every 500ms
        else:  # normal
            self.labelStatus.setText(f"ℹ️ {message}")
            self.labelStatus.setStyleSheet("")
        
    def on_provider_changed(self, index):
        """Handle provider selection changes."""
        provider = self.comboBoxProvider.currentText()
        
        # Update endpoint and model based on provider
        self.lineEditServer.setText(self.provider_endpoints.get(provider, ""))
        self.lineEditModel.setText(self.provider_default_models.get(provider, ""))
        
        # Show/hide API key field based on provider
        if provider == "Ollama":
            self.lineEditApiKey.setEnabled(False)
            self.lineEditApiKey.setPlaceholderText("Not required for Ollama")
        else:
            self.lineEditApiKey.setEnabled(True)
            self.lineEditApiKey.setPlaceholderText(f"Required for {provider}")
        
        self.set_status(f"Provider changed to {provider}", "normal")
        
    def _format_prompt_for_provider(self, provider, prompt):
        """Format the prompt based on the provider requirements."""
        if provider == "OpenAI" or provider == "OpenRouter":
            return [{"role": "user", "content": prompt}]
        elif provider == "Anthropic":
            return {"role": "user", "content": prompt}
        else:  # Ollama and custom
            return prompt
    
    def send_to_llm(self, is_error_fix=False, fix_prompt=None):
        """
        Send the prompt to the selected LLM provider and retrieve the generated code.
        
        Args:
            is_error_fix (bool): Whether this is a code-fixing request
            fix_prompt (str): Optional custom prompt for error fixing
        """
        # Disable send button to prevent multiple requests
        self.pushButtonSend.setEnabled(False)
        if is_error_fix:
            self.pushButtonFixCode.setEnabled(False)
        
        # Clear previous responses if not fixing an error
        if not is_error_fix:
            self.plainTextEditFullResponse.setPlainText("")
            self.plainTextEditCode.setPlainText("")
        
        # Get provider and values from UI
        provider = self.comboBoxProvider.currentText()
        api_endpoint = self.lineEditServer.text()
        api_key = self.lineEditApiKey.text()
        model = self.lineEditModel.text()
        
        # Use the provided fix prompt or get the prompt from the UI
        if is_error_fix and fix_prompt:
            prompt = fix_prompt
        else:
            prompt = self.plainTextEditPrompt.toPlainText()
            
        temperature = self.doubleSpinBoxTemperature.value()
        max_tokens = self.spinBoxMaxTokens.value()
        
        if not prompt:
            self.set_status("No prompt entered - please type a prompt first", "error")
            self.pushButtonSend.setEnabled(True)
            if is_error_fix:
                self.pushButtonFixCode.setEnabled(True)
            return
        
        if provider != "Ollama" and not api_key:
            self.set_status(f"API key is required for {provider}", "error")
            self.pushButtonSend.setEnabled(True)
            if is_error_fix:
                self.pushButtonFixCode.setEnabled(True)
            return
        
        # Set initial status
        operation_name = "fixing code" if is_error_fix else "sending request"
        self.set_status(f"{operation_name.capitalize()} to {provider} ({model})", "progress")
            
        try:
            import requests
            import re
            
            # Format prompt based on provider
            formatted_prompt = self._format_prompt_for_provider(provider, prompt)
            
            # Create payload based on provider
            headers = {}
            payload = {}
            
            if provider == "Ollama":
                payload = {
                    "model": model,
                    "prompt": formatted_prompt,
                    "stream": False
                }
            elif provider == "OpenAI":
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "model": model,
                    "messages": formatted_prompt,
                    "temperature": temperature,
                    "max_tokens": max_tokens
                }
            elif provider == "OpenRouter":
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://qgis.org/",  # Required by OpenRouter
                    "X-Title": "Promptly"  # Helps with attribution
                }
                payload = {
                    "model": model,
                    "messages": formatted_prompt,
                    "temperature": temperature,
                    "max_tokens": max_tokens
                }
            elif provider == "Anthropic":
                headers = {
                    "x-api-key": api_key,
                    "content-type": "application/json",
                    "anthropic-version": "2023-06-01"
                }
                payload = {
                    "model": model,
                    "messages": [formatted_prompt],
                    "max_tokens": max_tokens,
                    "temperature": temperature
                }
            elif provider == "Custom":
                # For custom provider, we'll need to parse the API key as a JSON of headers
                try:
                    if api_key:
                        headers = json.loads(api_key)
                except json.JSONDecodeError:
                    headers = {"Authorization": f"Bearer {api_key}"}
                
                payload = {
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": temperature,
                    "max_tokens": max_tokens
                }
            
            # Log details for debugging
            QgsMessageLog.logMessage(f"Sending request to {api_endpoint} with payload: {json.dumps(payload)[:500]}...", 
                                   level=Qgis.Info)
            
            # Create a worker with signals for thread-safe communication
            worker_signals = WorkerSignals()
            
            # Connect signals to handlers
            worker_signals.status.connect(self.handle_status_update)
            worker_signals.result.connect(
                lambda full, code: self.handle_result(full, code, is_error_fix)
            )
            worker_signals.error.connect(self.handle_error)
            worker_signals.error_log.connect(self.handle_error_log)
            
            if is_error_fix:
                worker_signals.finished.connect(lambda: self.pushButtonFixCode.setEnabled(True))
            else:
                worker_signals.finished.connect(lambda: self.pushButtonSend.setEnabled(True))
            
            # Define the worker function
            def worker_function():
                """Worker function that runs in a separate thread"""
                try:
                    # Send request to the API
                    response = requests.post(api_endpoint, headers=headers, json=payload, timeout=120)
                    
                    # Process response based on provider
                    llm_output = ""
                    raw_response = ""
                    
                    if response.status_code == 200:
                        # Signal processing status
                        worker_signals.status.emit(f"Processing response from {provider}", "progress")
                        
                        # Log the raw response for debugging
                        raw_response = response.text
                        QgsMessageLog.logMessage(f"Raw response: {raw_response[:500]}...", level=Qgis.Info)
                        
                        response_json = response.json()
                        
                        if provider == "Ollama":
                            llm_output = response_json.get("response", "")
                        elif provider == "OpenAI" or provider == "OpenRouter":
                            llm_output = response_json.get("choices", [{}])[0].get("message", {}).get("content", "")
                        elif provider == "Anthropic":
                            try:
                                llm_output = response_json.get("content", [{}])[0].get("text", "")
                            except (KeyError, IndexError):
                                # Alternative format
                                llm_output = response_json.get("content", "")
                                if not llm_output and isinstance(response_json.get("content"), list):
                                    contents = response_json.get("content", [])
                                    llm_output = "\n".join([item.get("text", "") for item in contents if item.get("text")])
                        else:  # Custom provider - attempt to extract response
                            try:
                                # Try common response formats
                                if "choices" in response_json:
                                    llm_output = response_json.get("choices", [{}])[0].get("message", {}).get("content", "")
                                elif "response" in response_json:
                                    llm_output = response_json.get("response", "")
                                else:
                                    llm_output = str(response_json)
                            except:
                                llm_output = response.text
                        
                        # If we still don't have output, try to use the raw response
                        if not llm_output.strip():
                            llm_output = f"Response received but couldn't extract text. Raw response:\n\n{raw_response}"
                            worker_signals.status.emit("Response format issue - check details in response", "warning")
                            QgsMessageLog.logMessage(f"Couldn't extract text from response: {raw_response}", level=Qgis.Warning)
                        
                        # Function to extract Python code from response
                        def extract_python_code(llm_response):
                            code_pattern = r"```python(.*?)```"  # Extracts Python code blocks
                            matches = re.findall(code_pattern, llm_response, re.DOTALL)
                            if matches:
                                return matches[0].strip()  # Return first code block found
                            return None  # No valid Python code found
                        
                        # Extract Python code
                        python_code = extract_python_code(llm_output)
                        
                        # Signal result with both the full response and the extracted code
                        worker_signals.result.emit(llm_output, python_code or "")
                        
                        # Signal appropriate status
                        if python_code:
                            if is_error_fix:
                                worker_signals.status.emit("Fixed code received - ready to execute", "success")
                            else:
                                worker_signals.status.emit("Code found in response - ready to execute", "success")
                        else:
                            worker_signals.status.emit(
                                "Response received, but no Python code block found. See Full Response tab.", 
                                "warning")
                    else:
                        error_message = f"Error {response.status_code}"
                        try:
                            error_details = response.json()
                            error_message += f" - {json.dumps(error_details)}"
                        except:
                            error_message += f" - {response.text}"
                        
                        worker_signals.error.emit(f"Error from {provider}:\n\n{error_message}")
                        worker_signals.status.emit(f"API Error: {response.status_code}", "error")
                        QgsMessageLog.logMessage(f"API Error: {error_message}", level=Qgis.Critical)
                
                except requests.exceptions.Timeout:
                    error_msg = f"Request to {provider} timed out. Check your connection or the server status."
                    worker_signals.error.emit(error_msg)
                    worker_signals.status.emit("Request timed out", "error")
                    QgsMessageLog.logMessage(error_msg, level=Qgis.Critical)
                    
                except Exception as e:
                    error_msg = f"Error: {str(e)}"
                    worker_signals.error.emit(f"An error occurred while processing your request:\n\n{error_msg}\n\n{traceback.format_exc()}")
                    worker_signals.status.emit(f"Error: {str(e)[:50]}...", "error")
                    QgsMessageLog.logMessage(f"Error in send_to_llm: {str(e)}\n{traceback.format_exc()}", level=Qgis.Critical)
                
                finally:
                    # Signal that the worker is done
                    worker_signals.finished.emit()
            
            # Run the worker function in a separate thread
            thread = threading.Thread(target=worker_function, daemon=True)
            thread.start()
            
        except Exception as e:
            error_msg = f"Error: {str(e)}"
            self.set_status(f"Error: {str(e)[:50]}...", "error")
            self.plainTextEditFullResponse.setPlainText(f"An error occurred while starting the request:\n\n{error_msg}\n\n{traceback.format_exc()}")
            QgsMessageLog.logMessage(f"Error in send_to_llm: {str(e)}\n{traceback.format_exc()}", level=Qgis.Critical)
            self.pushButtonSend.setEnabled(True)
            if is_error_fix:
                self.pushButtonFixCode.setEnabled(True)
    
    def fix_code(self):
        """Send the error and current code to the LLM to get a fix."""
        if not self.last_error or not self.last_code:
            self.set_status("No error to fix", "warning")
            return
            
        # Create a specialized prompt for code fixing
        fix_prompt = f"""I need help fixing an error in this QGIS Python code:

```python
{self.last_code}
```

The error I encountered is:
```
{self.last_error}
```

Please provide a corrected version of the code that fixes this error.
Only return the corrected code in a Python code block (enclosed in ```python and ```).
"""
        
        # Send the fix prompt to the LLM
        self.send_to_llm(is_error_fix=True, fix_prompt=fix_prompt)
    
    def handle_status_update(self, message, status_type):
        """Handle status updates from the worker thread"""
        self.set_status(message, status_type)
        
    def handle_result(self, full_response, code, is_error_fix=False):
        """
        Handle results from the worker thread
        
        Args:
            full_response (str): Complete response from the LLM
            code (str): Extracted Python code
            is_error_fix (bool): Whether this is a result from error fixing
        """
        self.plainTextEditFullResponse.setPlainText(full_response)
        
        if code:
            self.plainTextEditCode.setPlainText(code)
            self.last_code = code  # Save for potential error fixing
            
            # Switch to the appropriate tab
            if is_error_fix:
                # For error fix results, show the code tab
                self.tabWidgetResponse.setCurrentIndex(1)  # Code tab
            else:
                self.tabWidgetResponse.setCurrentIndex(1)  # Code tab
        else:
            if not is_error_fix:
                # Only clear the code if this is not an error fix
                self.plainTextEditCode.setPlainText("")
                
            # Switch to the full response tab
            self.tabWidgetResponse.setCurrentIndex(0)  # Full response tab
            
    def handle_error(self, error_message):
        """Handle errors from the worker thread"""
        self.plainTextEditFullResponse.setPlainText(error_message)
        self.tabWidgetResponse.setCurrentIndex(0)  # Show full response tab
    
    def handle_error_log(self, error_log):
        """Update the error log tab with new error information"""
        self.plainTextEditErrorLog.setPlainText(error_log)
        self.last_error = error_log  # Save for potential error fixing
        self.pushButtonFixCode.setEnabled(True)  # Enable the fix button
        self.tabWidgetResponse.setCurrentIndex(2)  # Switch to error log tab
            
    def execute_code(self):
        """Execute the Python code in the QGIS environment."""
        code = self.plainTextEditCode.toPlainText()
        
        if not code:
            self.set_status("No code to execute", "error")
            return
            
        try:
            self.set_status("Executing code...", "progress")
            
            # Disable button during execution
            self.pushButtonExecute.setEnabled(False)
            
            # Save the code for potential error fixing
            self.last_code = code
            
            # Clear previous error log
            self.plainTextEditErrorLog.setPlainText("")
            self.last_error = ""
            self.pushButtonFixCode.setEnabled(False)
            
            # Capture stdout and stderr
            stdout_buffer = io.StringIO()
            stderr_buffer = io.StringIO()
            
            # Execute with output capturing
            try:
                with redirect_stdout(stdout_buffer), redirect_stderr(stderr_buffer):
                    exec(code)
                
                stdout_output = stdout_buffer.getvalue()
                stderr_output = stderr_buffer.getvalue()
                
                # Check for any stderr output
                if stderr_output:
                    # If there's stderr, consider it an error
                    self.set_status("Code executed with errors", "warning")
                    error_log = f"STDERR Output:\n{stderr_output}\n\nSTDOUT Output:\n{stdout_output}"
                    self.plainTextEditErrorLog.setPlainText(error_log)
                    self.last_error = error_log
                    self.pushButtonFixCode.setEnabled(True)
                    self.tabWidgetResponse.setCurrentIndex(2)  # Switch to error log tab
                    QMessageBox.warning(self, "Execution Warning", "Code executed with warnings or errors. See Error Log tab.")
                else:
                    # If stdout has content, show it in the error log tab as information
                    if stdout_output:
                        self.plainTextEditErrorLog.setPlainText(f"Code executed successfully.\n\nOutput:\n{stdout_output}")
                        self.tabWidgetResponse.setCurrentIndex(2)  # Switch to error log tab
                    
                    self.set_status("Code executed successfully", "success")
                    QMessageBox.information(self, "Success", "Code executed successfully!")
            
            except Exception as e:
                error_msg = f"Error executing code: {str(e)}"
                tb_str = traceback.format_exc()
                error_log = f"{error_msg}\n\n{tb_str}\n\nSTDOUT Output:\n{stdout_buffer.getvalue()}"
                
                # Update error log and switch to it
                self.plainTextEditErrorLog.setPlainText(error_log)
                self.last_error = error_log
                self.pushButtonFixCode.setEnabled(True)
                self.tabWidgetResponse.setCurrentIndex(2)  # Switch to error log tab
                
                self.set_status(error_msg, "error")
                QgsMessageLog.logMessage(f"{error_msg}\n{tb_str}", level=Qgis.Critical)
                QMessageBox.critical(self, "Error", error_msg)
        
        finally:
            # Re-enable button
            self.pushButtonExecute.setEnabled(True) 