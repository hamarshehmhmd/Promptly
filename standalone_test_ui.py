#!/usr/bin/env python3
"""
Standalone test version of Promptly dialog for testing without QGIS.
This mocks QGIS dependencies and creates a simplified interface for testing.
"""

import sys
import os
import json
import traceback
import time
import threading
import io
from contextlib import redirect_stdout, redirect_stderr

try:
    from PyQt5.QtWidgets import (QApplication, QDialog, QVBoxLayout, QHBoxLayout, 
                                QTabWidget, QWidget, QPushButton, QPlainTextEdit,
                                QLabel, QComboBox, QLineEdit, QGroupBox, QGridLayout,
                                QSplitter, QMessageBox, QProgressBar, QSpacerItem,
                                QSizePolicy)
    from PyQt5.QtCore import Qt, QTimer, QObject, pyqtSignal
    from PyQt5.QtGui import QColor, QPixmap, QIcon
    from PyQt5 import uic
except ImportError:
    try:
        from PySide2.QtWidgets import (QApplication, QDialog, QVBoxLayout, QHBoxLayout,
                                      QTabWidget, QWidget, QPushButton, QPlainTextEdit,
                                      QLabel, QComboBox, QLineEdit, QGroupBox, QGridLayout,
                                      QSplitter, QMessageBox, QProgressBar, QSpacerItem,
                                      QSizePolicy)
        from PySide2.QtCore import Qt, QTimer, QObject, Signal as pyqtSignal
        from PySide2.QtGui import QColor, QPixmap, QIcon
    except ImportError:
        print("Neither PyQt5 nor PySide2 is installed. Please install one of them:")
        print("pip install PyQt5")
        print("or")
        print("pip install PySide2")
        sys.exit(1)

# Mock QGIS modules and classes
class MockQgis:
    Info = "Info"
    Warning = "Warning"
    Critical = "Critical"

class MockQgsMessageLog:
    @staticmethod
    def logMessage(message, tag, level):
        print(f"[{level}] {tag}: {message}")

class MockQgsProject:
    @staticmethod
    def instance():
        return MockQgsProject()
    
    def addMapLayer(self, layer):
        print(f"Mock: Adding layer to project")

class MockQgsVectorLayer:
    def __init__(self, uri, name, provider):
        self.uri = uri
        self.name = name
        self.provider = provider
    
    def isValid(self):
        return True

class MockIface:
    def mainWindow(self):
        return None

# Create mock modules
import types

qgis_core = types.ModuleType('qgis.core')
qgis_core.QgsMessageLog = MockQgsMessageLog
qgis_core.Qgis = MockQgis
qgis_core.QgsProject = MockQgsProject
qgis_core.QgsVectorLayer = MockQgsVectorLayer
qgis_core.QgsProviderRegistry = type('MockQgsProviderRegistry', (), {'instance': lambda: None})()
qgis_core.QgsProviderMetadata = type('MockQgsProviderMetadata', (), {})()
qgis_core.QgsDataSourceUri = type('MockQgsDataSourceUri', (), {})()
qgis_core.QgsApplication = type('MockQgsApplication', (), {})()
qgis_core.QgsRasterLayer = type('MockQgsRasterLayer', (), {})()
qgis_core.QgsFeature = type('MockQgsFeature', (), {})()

qgis_utils = types.ModuleType('qgis.utils')
qgis_utils.iface = MockIface()
qgis_utils.qgsfunction = lambda x: x
qgis_utils.plugins = {}

# Add to sys.modules so imports work
sys.modules['qgis'] = types.ModuleType('qgis')
sys.modules['qgis.core'] = qgis_core
sys.modules['qgis.utils'] = qgis_utils
sys.modules['qgis.PyQt'] = types.ModuleType('qgis.PyQt')
sys.modules['qgis.PyQt.QtWidgets'] = types.ModuleType('qgis.PyQt.QtWidgets')
sys.modules['qgis.PyQt.QtCore'] = types.ModuleType('qgis.PyQt.QtCore')
sys.modules['qgis.PyQt.QtGui'] = types.ModuleType('qgis.PyQt.QtGui')

# Mock uic.loadUiType
def mock_loadUiType(ui_file):
    # Create a base dialog class
    class MockFormClass(QDialog):
        def setupUi(self, dialog):
            dialog.setWindowTitle("Promptly - Standalone Test")
            dialog.setMinimumSize(900, 800)
            dialog.resize(900, 800)
            
            # Main layout
            main_layout = QVBoxLayout(dialog)
            main_layout.setSpacing(10)
            main_layout.setContentsMargins(12, 12, 12, 12)
            
            # Header
            header_layout = QHBoxLayout()
            
            # Logo (mock)
            logo_label = QLabel()
            logo_label.setText("🔧")  # Using emoji as placeholder
            logo_label.setMaximumSize(32, 32)
            header_layout.addWidget(logo_label)
            
            # Title
            title_label = QLabel("Promptly")
            title_label.setStyleSheet("font-size: 14pt; font-weight: bold;")
            header_layout.addWidget(title_label)
            
            header_layout.addStretch()
            main_layout.addLayout(header_layout)
            
            # Splitter for main content
            splitter = QSplitter(Qt.Vertical)
            main_layout.addWidget(splitter)
            
            # Top widget with tabs
            top_widget = QWidget()
            top_layout = QVBoxLayout(top_widget)
            
            # Settings tabs
            settings_tabs = QTabWidget()
            dialog.settingsTabs = settings_tabs
            
            # LLM Settings tab
            llm_tab = QWidget()
            llm_layout = QVBoxLayout(llm_tab)
            
            # Provider settings grid
            grid_layout = QGridLayout()
            
            # Provider
            grid_layout.addWidget(QLabel("LLM Provider:"), 0, 0)
            provider_combo = QComboBox()
            provider_combo.addItems(["Ollama", "OpenAI", "OpenRouter", "Anthropic", "Custom"])
            dialog.comboBoxProvider = provider_combo
            grid_layout.addWidget(provider_combo, 0, 1, 1, 3)
            
            # Server
            grid_layout.addWidget(QLabel("Server:"), 1, 0)
            server_edit = QLineEdit()
            dialog.lineEditServer = server_edit
            grid_layout.addWidget(server_edit, 1, 1, 1, 3)
            
            # Model
            grid_layout.addWidget(QLabel("Model:"), 2, 0)
            model_edit = QLineEdit()
            dialog.lineEditModel = model_edit
            grid_layout.addWidget(model_edit, 2, 1, 1, 3)
            
            # API Key
            grid_layout.addWidget(QLabel("API Key:"), 3, 0)
            api_key_edit = QLineEdit()
            api_key_edit.setEchoMode(QLineEdit.Password)
            dialog.lineEditApiKey = api_key_edit
            grid_layout.addWidget(api_key_edit, 3, 1, 1, 3)
            
            llm_layout.addLayout(grid_layout)
            llm_layout.addStretch()
            settings_tabs.addTab(llm_tab, "LLM Settings")
            
            # Data Context tab
            data_tab = QWidget()
            data_layout = QVBoxLayout(data_tab)
            
            # Database section
            db_group = QGroupBox("Database Reference")
            db_layout = QVBoxLayout(db_group)
            
            db_combo_layout = QHBoxLayout()
            db_combo_layout.addWidget(QLabel("Database:"))
            sql_db_combo = QComboBox()
            sql_db_combo.addItem("None")
            dialog.comboBoxSqlDatabase = sql_db_combo
            db_combo_layout.addWidget(sql_db_combo)
            
            refresh_db_btn = QPushButton("Refresh")
            dialog.pushButtonRefreshDatabases = refresh_db_btn
            db_combo_layout.addWidget(refresh_db_btn)
            
            db_layout.addLayout(db_combo_layout)
            data_layout.addWidget(db_group)
            
            # Layer section
            layer_group = QGroupBox("Layer Reference")
            layer_layout = QVBoxLayout(layer_group)
            
            layer_combo_layout = QHBoxLayout()
            layer_combo_layout.addWidget(QLabel("Layer:"))
            layer_combo = QComboBox()
            layer_combo.addItem("None")
            dialog.comboBoxLayer = layer_combo
            layer_combo_layout.addWidget(layer_combo)
            
            refresh_layer_btn = QPushButton("Refresh")
            dialog.pushButtonRefreshLayers = refresh_layer_btn
            layer_combo_layout.addWidget(refresh_layer_btn)
            
            layer_layout.addLayout(layer_combo_layout)
            data_layout.addWidget(layer_group)
            
            data_layout.addStretch()
            settings_tabs.addTab(data_tab, "Data Context")
            
            top_layout.addWidget(settings_tabs)
            
            # Prompt section
            prompt_group = QGroupBox("Prompt")
            prompt_layout = QVBoxLayout(prompt_group)
            
            prompt_edit = QPlainTextEdit()
            prompt_edit.setPlaceholderText("Enter your prompt here...")
            dialog.plainTextEditPrompt = prompt_edit
            prompt_layout.addWidget(prompt_edit)
            
            # Buttons
            button_layout = QHBoxLayout()
            
            send_btn = QPushButton("Send to LLM")
            dialog.pushButtonSend = send_btn
            button_layout.addWidget(send_btn)
            
            cancel_btn = QPushButton("Cancel")
            dialog.pushButtonCancel = cancel_btn
            button_layout.addWidget(cancel_btn)
            
            button_layout.addStretch()
            prompt_layout.addLayout(button_layout)
            
            top_layout.addWidget(prompt_group)
            splitter.addWidget(top_widget)
            
            # Bottom widget with response tabs
            bottom_widget = QWidget()
            bottom_layout = QVBoxLayout(bottom_widget)
            
            response_tabs = QTabWidget()
            
            # Full Response tab
            response_tab = QWidget()
            response_layout = QVBoxLayout(response_tab)
            
            response_edit = QPlainTextEdit()
            response_edit.setReadOnly(True)
            dialog.plainTextEditFullResponse = response_edit
            response_layout.addWidget(response_edit)
            response_tabs.addTab(response_tab, "Full Response")
            
            # Code tab
            code_tab = QWidget()
            code_layout = QVBoxLayout(code_tab)
            
            code_edit = QPlainTextEdit()
            code_edit.setReadOnly(True)
            dialog.plainTextEditCode = code_edit
            code_layout.addWidget(code_edit)
            
            # Code buttons
            code_button_layout = QHBoxLayout()
            
            execute_btn = QPushButton("Execute Code")
            dialog.pushButtonExecute = execute_btn
            code_button_layout.addWidget(execute_btn)
            
            fix_btn = QPushButton("Fix Code")
            fix_btn.setEnabled(False)
            dialog.pushButtonFixCode = fix_btn
            code_button_layout.addWidget(fix_btn)
            
            code_button_layout.addStretch()
            code_layout.addLayout(code_button_layout)
            response_tabs.addTab(code_tab, "Generated Code")
            
            # Error Log tab
            error_tab = QWidget()
            error_layout = QVBoxLayout(error_tab)
            
            error_edit = QPlainTextEdit()
            error_edit.setReadOnly(True)
            dialog.plainTextEditErrorLog = error_edit
            error_layout.addWidget(error_edit)
            response_tabs.addTab(error_tab, "Error Log")
            
            bottom_layout.addWidget(response_tabs)
            splitter.addWidget(bottom_widget)
            
            # Status bar
            status_label = QLabel("Ready")
            dialog.labelStatus = status_label
            main_layout.addWidget(status_label)
            
            # Set splitter proportions
            splitter.setSizes([400, 400])
    
    return MockFormClass, type('MockBase', (), {})

# Mock the uic module
uic_module = types.ModuleType('uic')
uic_module.loadUiType = mock_loadUiType
sys.modules['qgis.PyQt.uic'] = uic_module


# Worker class for thread-safe signals
class WorkerSignals(QObject):
    """Defines the signals available from a running worker thread."""
    status = pyqtSignal(str, str)  # (message, status_type)
    result = pyqtSignal(str, str)  # (full_response, code)
    error = pyqtSignal(str)
    finished = pyqtSignal()
    error_log = pyqtSignal(str)  # For updating the error log tab


class StandalonePromptlyDialog(QDialog):
    def __init__(self, parent=None):
        """Constructor."""
        super(StandalonePromptlyDialog, self).__init__(parent)
        
        # Set up the user interface using mock UI
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
        self.set_status("Ready (Standalone Mode)", "normal")
        
        # Apply some basic styling
        self.setStyleSheet("""
            QGroupBox {
                border: 1px solid #b8b8b8;
                border-radius: 6px;
                margin-top: 12px;
                font-weight: bold;
                background-color: #fafafa;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
            QPushButton {
                background-color: #2d8bca;
                color: white;
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #3498db;
            }
            QPushButton:pressed {
                background-color: #2980b9;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
    
    def setupUi(self, dialog):
        """Setup UI using mock form class"""
        form_class, _ = mock_loadUiType("")
        form_instance = form_class()
        form_instance.setupUi(dialog)
        
        # Copy widgets to self
        for attr_name in dir(form_instance):
            if not attr_name.startswith('_'):
                attr_value = getattr(form_instance, attr_name)
                if hasattr(attr_value, 'objectName'):  # It's a widget
                    setattr(self, attr_name, attr_value)
    
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
    
    def send_to_llm(self):
        """Mock LLM request - simulates sending to LLM."""
        prompt = self.plainTextEditPrompt.toPlainText().strip()
        
        if not prompt:
            QMessageBox.warning(self, "Warning", "Please enter a prompt first.")
            return
        
        self.set_status("Sending request to LLM (simulated)", "progress")
        self.pushButtonSend.setEnabled(False)
        self.pushButtonCancel.setEnabled(True)
        
        # Simulate a response after 2 seconds
        QTimer.singleShot(2000, self.simulate_llm_response)
    
    def simulate_llm_response(self):
        """Simulate an LLM response."""
        # Mock response
        mock_response = f"""I'll help you with that request.

Here's a Python code solution:

```python
# Generated QGIS code for your request
from qgis.core import QgsProject, QgsVectorLayer
from qgis.utils import iface

# Create a sample layer
layer = QgsVectorLayer("Point?crs=EPSG:4326", "Sample Layer", "memory")

# Add to project
QgsProject.instance().addMapLayer(layer)

print("Layer created and added to project!")
```

This code creates a sample vector layer and adds it to your QGIS project.
"""
        
        # Extract code (simple regex for demo)
        import re
        code_pattern = r'```python\n(.*?)\n```'
        code_match = re.search(code_pattern, mock_response, re.DOTALL)
        code = code_match.group(1) if code_match else ""
        
        # Update UI
        self.plainTextEditFullResponse.setPlainText(mock_response)
        self.plainTextEditCode.setPlainText(code)
        
        # Re-enable buttons
        self.pushButtonSend.setEnabled(True)
        self.pushButtonCancel.setEnabled(False)
        
        self.set_status("Response received (simulated)", "success")
    
    def cancel_request(self):
        """Cancel the current request."""
        self.pushButtonSend.setEnabled(True)
        self.pushButtonCancel.setEnabled(False)
        self.set_status("Request canceled", "warning")
    
    def execute_code(self):
        """Execute the generated code."""
        code = self.plainTextEditCode.toPlainText().strip()
        
        if not code:
            QMessageBox.warning(self, "Warning", "No code to execute.")
            return
        
        self.set_status("Executing code (simulated)", "progress")
        
        try:
            # In standalone mode, we'll just show what would be executed
            QMessageBox.information(self, "Code Execution", 
                                  f"In a real QGIS environment, this code would be executed:\n\n{code[:200]}...")
            self.set_status("Code execution simulated", "success")
            
        except Exception as e:
            error_msg = str(e)
            self.plainTextEditErrorLog.setPlainText(error_msg)
            self.last_error = error_msg
            self.last_code = code
            self.pushButtonFixCode.setEnabled(True)
            self.set_status("Code execution failed", "error")
    
    def fix_code(self):
        """Fix the code based on the last error."""
        if not self.last_error:
            QMessageBox.warning(self, "Warning", "No error to fix.")
            return
        
        self.set_status("Requesting code fix (simulated)", "progress")
        
        # Simulate fix after delay
        QTimer.singleShot(1500, self.simulate_code_fix)
    
    def simulate_code_fix(self):
        """Simulate a code fix response."""
        fixed_code = """# Fixed version of the code
from qgis.core import QgsProject, QgsVectorLayer
from qgis.utils import iface

try:
    # Create a sample layer with proper error handling
    layer = QgsVectorLayer("Point?crs=EPSG:4326", "Sample Layer", "memory")
    
    if layer.isValid():
        # Add to project
        QgsProject.instance().addMapLayer(layer)
        print("Layer created and added to project successfully!")
    else:
        print("Failed to create layer")
        
except Exception as e:
    print(f"Error: {e}")
"""
        
        self.plainTextEditCode.setPlainText(fixed_code)
        self.set_status("Code fix received (simulated)", "success")
    
    def refresh_databases(self):
        """Refresh the database list."""
        self.comboBoxSqlDatabase.clear()
        self.comboBoxSqlDatabase.addItem("None")
        
        # Add mock databases
        mock_databases = ["PostgreSQL - localhost:5432/gis", "SpatiaLite - sample.db"]
        for db in mock_databases:
            self.comboBoxSqlDatabase.addItem(db)
        
        self.set_status("Database list refreshed (mock data)", "success")
    
    def refresh_layers(self):
        """Refresh the layer list."""
        self.comboBoxLayer.clear()
        self.comboBoxLayer.addItem("None")
        
        # Add mock layers
        mock_layers = ["Countries", "Cities", "Roads", "Boundaries"]
        for layer in mock_layers:
            self.comboBoxLayer.addItem(layer)
        
        self.set_status("Layer list refreshed (mock data)", "success")


def main():
    """Main function to run the standalone dialog."""
    app = QApplication(sys.argv)
    
    # Set application properties
    app.setApplicationName("Promptly - Standalone Test")
    app.setApplicationVersion("1.0")
    
    # Create and show dialog
    dialog = StandalonePromptlyDialog()
    dialog.show()
    
    # Run the application
    sys.exit(app.exec_())


if __name__ == "__main__":
    main() 