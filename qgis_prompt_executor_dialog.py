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
from qgis.core import QgsMessageLog, Qgis, QgsProviderRegistry, QgsProviderMetadata, QgsDataSourceUri
from qgis.utils import iface, qgsfunction, plugins
from qgis.core import QgsProject, QgsApplication, QgsVectorLayer, QgsRasterLayer, QgsFeature
from PyQt5.QtWidgets import QMessageBox

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


class PromptlyDialog(QDialog, FORM_CLASS):
    def __init__(self, parent=None):
        """Constructor."""
        super(PromptlyDialog, self).__init__(parent)
        # Set up the user interface from Designer through FORM_CLASS.
        # After self.setupUi() you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots
        self.setupUi(self)
        
        # Connect signals
        self.pushButtonSend.clicked.connect(self.send_to_llm)
        self.pushButtonExecute.clicked.connect(self.execute_code)
        self.pushButtonFixCode.clicked.connect(self.fix_code)
        self.comboBoxProvider.currentIndexChanged.connect(self.on_provider_changed)
        self.pushButtonCancel.clicked.connect(self.cancel_request)
        
        # Connect database-related signals
        self.pushButtonRefreshDatabases.clicked.connect(self.refresh_databases)
        
        # Connect layer-related signals
        self.pushButtonRefreshLayers.clicked.connect(self.refresh_layers)
        
        # Disable fix button initially (until there's an error)
        self.pushButtonFixCode.setEnabled(False)
        
        # Store the last error for code fixing
        self.last_error = ""
        self.last_code = ""
        
        # Add variables to track request status
        self.current_thread = None
        self.request_canceled = False
        
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
        
        # Initialize database list
        self.refresh_databases()
        
        # Initialize layer list
        self.refresh_layers()
        
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
        """Format the prompt based on the provider's expected format"""
        # Check if a database is selected and add schema information
        db_selection = self.comboBoxSqlDatabase.currentText()
        db_schema = None
        
        if db_selection != "None":
            self.set_status(f"Getting schema for {db_selection}...", "progress")
            db_schema = self.get_database_schema(db_selection)
            
            if db_schema:
                # Add database schema info to the prompt
                prompt += f"\n\nReference database schema ({db_selection}):\n```json\n{json.dumps(db_schema, indent=2)}\n```\nPlease use this database schema as a reference for any SQL queries."

        # Check if a layer is selected and add metadata information
        layer_selection = self.comboBoxLayer.currentText()
        layer_metadata = None
        
        if layer_selection != "None":
            self.set_status(f"Getting metadata for {layer_selection}...", "progress")
            layer_metadata = self.get_layer_metadata(layer_selection)
            
            if layer_metadata:
                # Add layer metadata info to the prompt
                prompt += f"\n\nReference layer metadata ({layer_selection}):\n```json\n{json.dumps(layer_metadata, indent=2)}\n```\nPlease use this layer as a reference for your QGIS code. The user has selected this specific layer to work with."

        # Add QGIS-specific context and coding guidance
        qgis_context = """
Please follow these guidelines when generating QGIS code:

1. Always include necessary QGIS imports at the top of your code (note the correct locations):
   - from qgis.core import QgsProject, QgsVectorLayer, QgsCoordinateReferenceSystem, Qgis
   - from qgis.utils import iface
   - from PyQt5.QtCore import Qt, QVariant
   - from PyQt5.QtGui import QColor
   - from PyQt5.QtWidgets import QMessageBox, QInputDialog, QDialog, QComboBox

2. IMPORTANT IMPORT RULES:
   - Qgis (with the enums like Qgis.Info) is imported from qgis.core, NOT from PyQt5
   - Message bars are accessed through iface.messageBar(), NOT through a QgsMessageBar class

3. When your code involves modifying the map canvas or project:
   - Reference the current project with QgsProject.instance()
   - Use iface for user interface operations
   - Always call refresh operations like iface.mapCanvas().refresh() when making visual changes
   
4. For adding layers to the map:
   - Use QgsProject.instance().addMapLayer(layer) or addMapLayers([layers])
   - Ensure layers have proper CRS settings
   
5. For user notifications:
   - Use iface.messageBar().pushMessage("Title", "Message", level=Qgis.Info)
   - Do NOT use QgsMessageBar directly
   
6. For USER INTERACTION and LAYER SELECTION:
   - If a specific layer has been pre-selected in the dropdown, use that layer directly
   - For additional layer selection needs, allow the user to select a layer using:
     ```python
     layer_names = [layer.name() for layer in QgsProject.instance().mapLayers().values()]
     layer_name, ok = QInputDialog.getItem(None, "Select Layer", "Choose a layer:", layer_names, 0, False)
     if ok and layer_name:
         selected_layer = next((layer for layer in QgsProject.instance().mapLayers().values() if layer.name() == layer_name), None)
         if selected_layer:
             # Proceed with the selected layer
     ```
   
7. USING THE SELECTED LAYER:
   - If a layer has been pre-selected in the dropdown, access it directly with:
     ```python
     # Get the selected layer by name
     layer_name = "LAYER_NAME_HERE"  # Replace with the name from the metadata
     selected_layer = None
     for lyr in QgsProject.instance().mapLayers().values():
         if lyr.name() == layer_name:
             selected_layer = lyr
             break
             
     if selected_layer:
         # Work with the selected layer
         # Example: count features, process attributes, etc.
     else:
         iface.messageBar().pushMessage("Error", f"Layer '{layer_name}' not found", level=Qgis.Warning)
     ```
   
8. When executing complex operations:
   - Consider wrapping in try/except blocks
   - Add progress messages for user feedback
   
Provide complete, self-contained code that will run in the QGIS Python environment.
"""
        prompt += "\n\n" + qgis_context
        
        # Format the prompt based on provider
        if provider == "Ollama":
            return prompt
        elif provider in ["OpenAI", "OpenRouter"]:
            return [{"role": "user", "content": prompt}]
        elif provider == "Anthropic":
            return {"role": "user", "content": prompt}
        elif provider == "Custom":
            return {"role": "user", "content": prompt}
        else:
            return prompt
    
    def send_to_llm(self, is_error_fix=False, fix_prompt=None):
        """
        Send the prompt to the selected LLM provider and retrieve the generated code.
        
        Args:
            is_error_fix (bool): Whether this is a code-fixing request
            fix_prompt (str): Optional custom prompt for error fixing
        """
        # Reset cancel flag
        self.request_canceled = False
        
        # Disable send button and enable cancel button
        self.pushButtonSend.setEnabled(False)
        self.pushButtonCancel.setEnabled(True)
        
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
            self.pushButtonCancel.setEnabled(False)
            if is_error_fix:
                self.pushButtonFixCode.setEnabled(True)
            return
        
        if provider != "Ollama" and not api_key:
            self.set_status(f"API key is required for {provider}", "error")
            self.pushButtonSend.setEnabled(True)
            self.pushButtonCancel.setEnabled(False)
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
                worker_signals.finished.connect(lambda: self.handle_request_finished(True))
            else:
                worker_signals.finished.connect(lambda: self.handle_request_finished(False))
            
            # Store reference to current thread for cancellation
            self.current_thread = None
            
            # Define the worker function
            def worker_function():
                """Worker function that runs in a separate thread"""
                # Check if canceled before making the request
                if self.request_canceled:
                    worker_signals.status.emit("Request canceled", "warning")
                    worker_signals.finished.emit()
                    return
                    
                try:
                    # Send request to the API
                    response = requests.post(api_endpoint, headers=headers, json=payload, timeout=120)
                    
                    # Process response based on provider
                    llm_output = ""
                    raw_response = ""
                    
                    # Check if canceled after the request but before processing
                    if self.request_canceled:
                        worker_signals.status.emit("Request canceled", "warning")
                        worker_signals.finished.emit()
                        return
                    
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
                        
                        # Final cancel check before finalizing result
                        if self.request_canceled:
                            worker_signals.status.emit("Request canceled", "warning")
                            worker_signals.finished.emit()
                            return
                        
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
            self.current_thread = thread
            thread.start()
            
        except Exception as e:
            error_msg = f"Error: {str(e)}"
            self.set_status(f"Error: {str(e)[:50]}...", "error")
            self.plainTextEditFullResponse.setPlainText(f"An error occurred while starting the request:\n\n{error_msg}\n\n{traceback.format_exc()}")
            QgsMessageLog.logMessage(f"Error in send_to_llm: {str(e)}\n{traceback.format_exc()}", level=Qgis.Critical)
            self.handle_request_finished(is_error_fix)
    
    def cancel_request(self):
        """Cancel the current LLM request"""
        if self.current_thread and self.current_thread.is_alive():
            self.request_canceled = True
            self.set_status("Canceling request...", "warning")
            QgsMessageLog.logMessage("User canceled LLM request", level=Qgis.Info)
    
    def handle_request_finished(self, is_error_fix=False):
        """Handle cleanup when request is finished (success or canceled)"""
        # Re-enable send button and disable cancel button
        self.pushButtonSend.setEnabled(True)
        self.pushButtonCancel.setEnabled(False)
        
        if is_error_fix:
            self.pushButtonFixCode.setEnabled(True)
        
        # Clear thread reference
        self.current_thread = None
    
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
            
            # Create a clean namespace for execution
            # First include standard modules that might be needed
            execution_namespace = {
                '__builtins__': __builtins__,
                'os': os,
                'sys': sys,
                'json': json,
                'time': time,
                'io': io,
                'traceback': traceback,
            }
            
            # Add QGIS-specific modules and objects with proper imports
            from qgis.utils import iface, qgsfunction, plugins
            from qgis.core import (QgsProject, QgsApplication, QgsVectorLayer, QgsRasterLayer, 
                                  QgsFeature, QgsGeometry, QgsCoordinateReferenceSystem, 
                                  QgsCoordinateTransform, QgsField, QgsFields, Qgis)
            from qgis.PyQt.QtCore import Qt, QVariant
            from qgis.PyQt.QtWidgets import QMessageBox, QInputDialog, QDialog, QComboBox
            from qgis.PyQt.QtGui import QColor
            
            # Add all these imports to the namespace
            execution_namespace.update({
                # Core QGIS modules
                'QgsProject': QgsProject,
                'QgsApplication': QgsApplication,
                'QgsVectorLayer': QgsVectorLayer,
                'QgsRasterLayer': QgsRasterLayer,
                'QgsFeature': QgsFeature,
                'QgsGeometry': QgsGeometry,
                'QgsCoordinateReferenceSystem': QgsCoordinateReferenceSystem,
                'QgsCoordinateTransform': QgsCoordinateTransform,
                'QgsField': QgsField,
                'QgsFields': QgsFields,
                'Qgis': Qgis,  # Important for message levels like Qgis.Info, Qgis.Warning
                
                # Main QGIS interfaces
                'iface': iface,
                'project': QgsProject.instance(),
                'plugins': plugins,
                
                # Qt classes
                'Qt': Qt,
                'QVariant': QVariant,
                'QColor': QColor,
                'QMessageBox': QMessageBox,
                'QInputDialog': QInputDialog,  # For layer selection
                'QDialog': QDialog,
                'QComboBox': QComboBox,
                
                # Common helper functions
                'getLayerByName': lambda name: next((l for l in QgsProject.instance().mapLayers().values() if l.name() == name), None),
                'getActiveLayer': lambda: iface.activeLayer(),
                'addLayer': lambda layer: QgsProject.instance().addMapLayer(layer),
                'removeLayer': lambda layer: QgsProject.instance().removeMapLayer(layer),
                'refresh': lambda: iface.mapCanvas().refresh(),
                'message': lambda title, msg="", level=Qgis.Info: iface.messageBar().pushMessage(title, msg, level=level),
                'getAllLayers': lambda: list(QgsProject.instance().mapLayers().values()),
                'getAllLayerNames': lambda: [layer.name() for layer in QgsProject.instance().mapLayers().values()],
                'selectLayerByName': lambda title="Select Layer", prompt="Choose a layer:": _select_layer_from_list(title, prompt)
            })
            
            # Helper function for layer selection
            def _select_layer_from_list(title="Select Layer", prompt="Choose a layer:"):
                """Allow the user to select a layer from the current project"""
                layer_names = [layer.name() for layer in QgsProject.instance().mapLayers().values()]
                if not layer_names:
                    return None
                    
                layer_name, ok = QInputDialog.getItem(None, title, prompt, layer_names, 0, False)
                if ok and layer_name:
                    return next((layer for layer in QgsProject.instance().mapLayers().values() 
                                 if layer.name() == layer_name), None)
                return None
                
            # Add the helper function to the namespace
            execution_namespace['_select_layer_from_list'] = _select_layer_from_list
            
            # Also add proper module imports to make import statements work
            execution_namespace.update({
                'qgis': __import__('qgis'),
                'qgis.core': __import__('qgis.core'),
                'qgis.utils': __import__('qgis.utils'),
                'qgis.PyQt': __import__('qgis.PyQt'),
                'PyQt5': __import__('PyQt5'),
                'PyQt5.QtCore': __import__('PyQt5.QtCore'),
                'PyQt5.QtGui': __import__('PyQt5.QtGui'),
                'PyQt5.QtWidgets': __import__('PyQt5.QtWidgets'),
            })
            
            # Capture stdout and stderr
            stdout_buffer = io.StringIO()
            stderr_buffer = io.StringIO()
            
            # Execute with output capturing
            try:
                with redirect_stdout(stdout_buffer), redirect_stderr(stderr_buffer):
                    # Execute the code with the custom namespace
                    exec(code, execution_namespace)
                
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
                    
                    # Force refresh of the QGIS canvas to show any changes
                    iface.mapCanvas().refresh()
            
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
            
            # Force refresh of the canvas to show any changes
            try:
                iface.mapCanvas().refresh()
            except:
                pass
                
    def refresh_databases(self):
        """Fetch and populate the database dropdown with available SQL databases"""
        try:
            self.set_status("Refreshing database list...", "progress")
            
            # Clear the database dropdown (keeping only the 'None' option at index 0)
            while self.comboBoxSqlDatabase.count() > 1:
                self.comboBoxSqlDatabase.removeItem(1)
            
            # Get available database connections
            # Check for spatialite/sqlite databases
            spatialite_provider = QgsProviderRegistry.instance().providerMetadata('spatialite')
            if spatialite_provider:
                for conn_name in spatialite_provider.connections():
                    self.comboBoxSqlDatabase.addItem(f"SpatiaLite: {conn_name}")
            
            # Check for PostgreSQL/PostGIS databases
            postgres_provider = QgsProviderRegistry.instance().providerMetadata('postgres')
            if postgres_provider:
                for conn_name in postgres_provider.connections():
                    self.comboBoxSqlDatabase.addItem(f"PostgreSQL: {conn_name}")
            
            # Check for MSSQL databases
            mssql_provider = QgsProviderRegistry.instance().providerMetadata('mssql')
            if mssql_provider:
                for conn_name in mssql_provider.connections():
                    self.comboBoxSqlDatabase.addItem(f"MSSQL: {conn_name}")
            
            # Check for OGR (for various other DB types)
            ogr_provider = QgsProviderRegistry.instance().providerMetadata('ogr')
            if ogr_provider:
                for conn_name in ogr_provider.connections():
                    if 'sqlite' in conn_name.lower():
                        self.comboBoxSqlDatabase.addItem(f"SQLite: {conn_name}")
            
            self.set_status("Database list refreshed", "success")
            
        except Exception as e:
            QgsMessageLog.logMessage(f"Error refreshing databases: {str(e)}\n{traceback.format_exc()}", 
                                    level=Qgis.Critical)
            self.set_status(f"Error refreshing databases: {str(e)[:50]}...", "error")
    
    def refresh_layers(self):
        """Fetch and populate the layer dropdown with available layers from the current project"""
        try:
            self.set_status("Refreshing layer list...", "progress")
            
            # Clear the layer dropdown (keeping only the 'None' option at index 0)
            while self.comboBoxLayer.count() > 1:
                self.comboBoxLayer.removeItem(1)
            
            # Get layers from current project
            project = QgsProject.instance()
            layers = project.mapLayers().values()
            
            # Add vector layers first (grouped by geometry type)
            vector_layers = {}
            for layer in layers:
                if layer.type() == QgsVectorLayer.VectorLayer:
                    # Get the geometry type name
                    if hasattr(layer, 'geometryType'):
                        geom_type = layer.geometryType()
                        geom_name = "Unknown"
                        
                        if geom_type == 0:
                            geom_name = "Point"
                        elif geom_type == 1:
                            geom_name = "Line"
                        elif geom_type == 2:
                            geom_name = "Polygon"
                        elif geom_type == 3:
                            geom_name = "NoGeometry"
                        elif geom_type == 4:
                            geom_name = "Multi"
                            
                        if geom_name not in vector_layers:
                            vector_layers[geom_name] = []
                        
                        vector_layers[geom_name].append(layer)
            
            # Add vector layers grouped by geometry type
            for geom_name, layers_list in vector_layers.items():
                for layer in layers_list:
                    self.comboBoxLayer.addItem(f"{geom_name}: {layer.name()}")
            
            # Add raster layers
            for layer in layers:
                if layer.type() == QgsRasterLayer.RasterLayer:
                    self.comboBoxLayer.addItem(f"Raster: {layer.name()}")
            
            self.set_status("Layer list refreshed", "success")
            
        except Exception as e:
            QgsMessageLog.logMessage(f"Error refreshing layers: {str(e)}\n{traceback.format_exc()}", 
                                    level=Qgis.Critical)
            self.set_status(f"Error refreshing layers: {str(e)[:50]}...", "error")
    
    def get_database_schema(self, db_selection):
        """Get schema information from the selected database"""
        if db_selection == "None":
            return None
        
        try:
            # Parse the database selection (format is "Provider: connection_name")
            provider_type, conn_name = db_selection.split(": ", 1)
            
            schema_info = {"tables": [], "database_type": provider_type}
            
            if provider_type == "PostgreSQL":
                provider = QgsProviderRegistry.instance().providerMetadata('postgres')
                connection = provider.findConnection(conn_name)
                if connection:
                    # Get list of schemas
                    schemas = connection.schemas()
                    
                    # For each schema, get the tables
                    for schema in schemas:
                        tables = connection.tables(schema)
                        for table in tables:
                            # Get table columns (fields)
                            uri = QgsDataSourceUri(connection.uri())
                            uri.setSchema(schema)
                            uri.setTable(table)
                            
                            conn = provider.createConnection(uri.uri(), {})
                            fields = conn.fields(schema, table)
                            
                            columns = []
                            for field in fields:
                                columns.append({
                                    "name": field.name(),
                                    "type": field.typeName()
                                })
                            
                            schema_info["tables"].append({
                                "schema": schema,
                                "name": table,
                                "columns": columns
                            })
            
            elif provider_type == "SpatiaLite" or provider_type == "SQLite":
                provider_key = 'spatialite' if provider_type == "SpatiaLite" else 'ogr'
                provider = QgsProviderRegistry.instance().providerMetadata(provider_key)
                connection = provider.findConnection(conn_name)
                
                if connection:
                    # SpatiaLite/SQLite doesn't have schemas, so we use "" as schema name
                    tables = connection.tables("")
                    
                    for table in tables:
                        # Get table columns
                        fields = connection.fields("", table)
                        
                        columns = []
                        for field in fields:
                            columns.append({
                                "name": field.name(),
                                "type": field.typeName()
                            })
                        
                        schema_info["tables"].append({
                            "schema": "",
                            "name": table,
                            "columns": columns
                        })
            
            elif provider_type == "MSSQL":
                provider = QgsProviderRegistry.instance().providerMetadata('mssql')
                connection = provider.findConnection(conn_name)
                
                if connection:
                    # Get list of schemas
                    schemas = connection.schemas()
                    
                    # For each schema, get the tables
                    for schema in schemas:
                        tables = connection.tables(schema)
                        for table in tables:
                            # Get table columns
                            fields = connection.fields(schema, table)
                            
                            columns = []
                            for field in fields:
                                columns.append({
                                    "name": field.name(),
                                    "type": field.typeName()
                                })
                            
                            schema_info["tables"].append({
                                "schema": schema,
                                "name": table,
                                "columns": columns
                            })
            
            return schema_info
            
        except Exception as e:
            QgsMessageLog.logMessage(f"Error getting database schema: {str(e)}\n{traceback.format_exc()}", 
                                    level=Qgis.Critical)
            self.set_status(f"Error extracting database schema: {str(e)[:50]}...", "error")
            return None

    def get_layer_metadata(self, layer_selection):
        """Get metadata information from the selected layer"""
        try:
            if layer_selection == "None":
                return None
            
            self.set_status(f"Getting metadata for {layer_selection}...", "progress")
            
            # Parse the layer selection (Format: "GeometryType: LayerName")
            parts = layer_selection.split(":", 1)
            if len(parts) != 2:
                return None
                
            layer_type = parts[0].strip()
            layer_name = parts[1].strip()
            
            # Find the layer in the project
            project = QgsProject.instance()
            layer = None
            
            for lyr in project.mapLayers().values():
                if lyr.name() == layer_name:
                    layer = lyr
                    break
            
            if not layer:
                return None
            
            # Create metadata object
            metadata = {
                "name": layer.name(),
                "type": layer_type,
                "crs": layer.crs().authid() if hasattr(layer, 'crs') else "Unknown",
                "provider": layer.providerType() if hasattr(layer, 'providerType') else "Unknown"
            }
            
            # Get feature count and fields for vector layers
            if layer.type() == QgsVectorLayer.VectorLayer:
                metadata["featureCount"] = layer.featureCount()
                
                # Get fields information
                fields = []
                for field in layer.fields():
                    field_info = {
                        "name": field.name(),
                        "type": field.typeName()
                    }
                    fields.append(field_info)
                
                metadata["fields"] = fields
                
                # Get extent
                if layer.extent():
                    extent = layer.extent()
                    metadata["extent"] = {
                        "xMin": extent.xMinimum(),
                        "yMin": extent.yMinimum(),
                        "xMax": extent.xMaximum(),
                        "yMax": extent.yMaximum()
                    }
            
            # For raster layers
            elif layer.type() == QgsRasterLayer.RasterLayer:
                # Get band count and data type
                metadata["bandCount"] = layer.bandCount() if hasattr(layer, 'bandCount') else 0
                metadata["dataType"] = layer.dataType(1) if hasattr(layer, 'dataType') else 0
                
                # Get extent
                if layer.extent():
                    extent = layer.extent()
                    metadata["extent"] = {
                        "xMin": extent.xMinimum(),
                        "yMin": extent.yMinimum(),
                        "xMax": extent.xMaximum(),
                        "yMax": extent.yMaximum()
                    }
            
            self.set_status(f"Layer metadata extracted", "success")
            return metadata
            
        except Exception as e:
            QgsMessageLog.logMessage(f"Error getting layer metadata: {str(e)}\n{traceback.format_exc()}", 
                                    level=Qgis.Critical)
            self.set_status(f"Error extracting layer metadata: {str(e)[:50]}...", "error")
            return None

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
        
        # Make sure buttons are re-enabled
        self.pushButtonSend.setEnabled(True)
        if is_error_fix:
            self.pushButtonFixCode.setEnabled(True)
            
    def handle_error(self, error_message):
        """Handle errors from the worker thread"""
        self.plainTextEditFullResponse.setPlainText(error_message)
        self.tabWidgetResponse.setCurrentIndex(0)  # Show full response tab
        
        # Make sure buttons are re-enabled
        self.pushButtonSend.setEnabled(True)
        self.pushButtonFixCode.setEnabled(True)
    
    def handle_error_log(self, error_log):
        """Update the error log tab with new error information"""
        self.plainTextEditErrorLog.setPlainText(error_log)
        self.last_error = error_log  # Save for potential error fixing
        self.pushButtonFixCode.setEnabled(True)  # Enable the fix button
        self.tabWidgetResponse.setCurrentIndex(2)  # Switch to error log tab
        
        # Make sure send button is re-enabled
        self.pushButtonSend.setEnabled(True)
