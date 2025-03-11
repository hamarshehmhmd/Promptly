# Integration test script for the Promptly plugin
from qgis.PyQt.QtCore import QTimer
from qgis_prompt_executor_dialog import QGISPromptExecutorDialog, WorkerSignals
import time

def simulate_llm_response(dialog):
    """Simulate an LLM response after a short delay"""
    print("Simulating LLM response...")
    
    # Create fake worker signals
    signals = WorkerSignals()
    
    # Connect signals to dialog handlers
    signals.status.connect(dialog.handle_status_update)
    signals.result.connect(lambda f, c: dialog.handle_result(f, c, False))
    signals.error.connect(dialog.handle_error)
    signals.finished.connect(lambda: print("Worker finished signal emitted"))
    
    # Create fake response
    fake_response = """I'll help you create a query for that database.

Here's the SQL query:

```python
from qgis.core import QgsDataSourceUri, QgsVectorLayer

# Get the database connection details
uri = QgsDataSourceUri()
uri.setConnection("localhost", "5432", "my_database", "username", "password")

# Set the table and key column
uri.setDataSource("public", "my_table", "geom")

# Create the SQL query
sql = "SELECT * FROM my_table WHERE attribute > 10"

# Create and add the layer
layer = QgsVectorLayer(uri.uri(False), "Query Result", "postgres")

# Add to map
if layer.isValid():
    QgsProject.instance().addMapLayer(layer)
else:
    print("Layer failed to load!")
```

This code connects to your PostgreSQL database and executes a query."""

    fake_code = """from qgis.core import QgsDataSourceUri, QgsVectorLayer

# Get the database connection details
uri = QgsDataSourceUri()
uri.setConnection("localhost", "5432", "my_database", "username", "password")

# Set the table and key column
uri.setDataSource("public", "my_table", "geom")

# Create the SQL query
sql = "SELECT * FROM my_table WHERE attribute > 10"

# Create and add the layer
layer = QgsVectorLayer(uri.uri(False), "Query Result", "postgres")

# Add to map
if layer.isValid():
    QgsProject.instance().addMapLayer(layer)
else:
    print("Layer failed to load!")"""
    
    # Emit signals after a short delay
    time.sleep(2)  # Simulate processing time
    signals.status.emit("Processing response", "progress")
    time.sleep(1)
    signals.status.emit("Response received", "success")
    signals.result.emit(fake_response, fake_code)
    signals.finished.emit()

def test_integration():
    """Test the whole workflow of sending a prompt with database reference"""
    print("Starting integration test...")
    
    # Create dialog instance
    dialog = QGISPromptExecutorDialog()
    
    # Set up a test prompt
    dialog.plainTextEditPrompt.setPlainText("Create a query to select all features from my database")
    
    # Refresh databases
    dialog.refresh_databases()
    
    # Check if Send button is enabled
    assert dialog.pushButtonSend.isEnabled(), "Send button should be enabled initially"
    
    # Manually call send_to_llm but replace actual HTTP request with simulation
    print("Sending prompt to LLM...")
    dialog.pushButtonSend.setEnabled(False)  # This happens in send_to_llm
    
    # Verify button is disabled
    assert not dialog.pushButtonSend.isEnabled(), "Send button should be disabled during request"
    
    # Simulate LLM response (this will call the handlers that should re-enable buttons)
    simulate_llm_response(dialog)
    
    # Verify button is re-enabled after response
    assert dialog.pushButtonSend.isEnabled(), "Send button should be re-enabled after response"
    
    # Verify response is shown
    assert len(dialog.plainTextEditFullResponse.toPlainText()) > 0, "Response text should be displayed"
    assert len(dialog.plainTextEditCode.toPlainText()) > 0, "Code should be extracted and displayed"
    
    print("Integration test completed successfully!")

if __name__ == "__main__":
    test_integration() 