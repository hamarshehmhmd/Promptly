# Test script for verifying button re-enabling after LLM requests
from qgis.PyQt.QtCore import QTimer
from qgis_prompt_executor_dialog import QGISPromptExecutorDialog

def test_button_reenabling():
    """Test that buttons are correctly re-enabled after requests"""
    print("Testing button re-enabling after LLM requests...")
    
    # Create dialog instance
    dialog = QGISPromptExecutorDialog()
    
    # Verify initial button states
    assert dialog.pushButtonSend.isEnabled(), "Send button should be enabled initially"
    assert not dialog.pushButtonFixCode.isEnabled(), "Fix button should be disabled initially"
    
    # Manually trigger the result handlers to simulate responses
    
    # 1. Test the handle_result method
    print("Testing handle_result...")
    dialog.pushButtonSend.setEnabled(False)  # Manually disable the button
    dialog.handle_result("Test response", "print('Test code')", False)
    assert dialog.pushButtonSend.isEnabled(), "Send button should be re-enabled after handle_result"
    
    # 2. Test the handle_error method
    print("Testing handle_error...")
    dialog.pushButtonSend.setEnabled(False)  # Manually disable the button
    dialog.handle_error("Test error message")
    assert dialog.pushButtonSend.isEnabled(), "Send button should be re-enabled after handle_error"
    assert dialog.pushButtonFixCode.isEnabled(), "Fix button should be enabled after handle_error"
    
    # 3. Test the handle_error_log method
    print("Testing handle_error_log...")
    dialog.pushButtonSend.setEnabled(False)  # Manually disable the button
    dialog.handle_error_log("Test error log")
    assert dialog.pushButtonSend.isEnabled(), "Send button should be re-enabled after handle_error_log"
    assert dialog.pushButtonFixCode.isEnabled(), "Fix button should be enabled after handle_error_log"
    
    print("All button re-enabling tests passed!")

if __name__ == "__main__":
    test_button_reenabling() 