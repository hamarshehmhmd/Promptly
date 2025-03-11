# Test script for verifying SQL database functionality
from qgis.PyQt.QtCore import QTimer
from qgis_prompt_executor_dialog import QGISPromptExecutorDialog
import json

def test_database_functionality():
    """Test that the SQL database dropdown and schema extraction work correctly"""
    print("Testing SQL database dropdown and schema functionality...")
    
    # Create dialog instance
    dialog = QGISPromptExecutorDialog()
    
    # Verify database dropdown has at least the 'None' option
    assert dialog.comboBoxSqlDatabase.count() >= 1, "Database dropdown should have at least 'None' option"
    assert dialog.comboBoxSqlDatabase.itemText(0) == "None", "First item should be 'None'"
    
    # Test refresh button functionality
    print("Testing database refresh...")
    dialog.refresh_databases()
    
    # Get available database count
    db_count = dialog.comboBoxSqlDatabase.count()
    print(f"Found {db_count-1} database connections")
    
    # If there are databases, test the schema extraction (optional test)
    if db_count > 1:
        print("Testing schema extraction with the first available database...")
        # Select the first available database (index 1, since 0 is "None")
        dialog.comboBoxSqlDatabase.setCurrentIndex(1)
        selected_db = dialog.comboBoxSqlDatabase.currentText()
        
        # Test schema extraction
        schema = dialog.get_database_schema(selected_db)
        if schema:
            print(f"Successfully extracted schema from {selected_db}")
            print(f"Schema has {len(schema['tables'])} tables")
            # Print first table details if available
            if len(schema['tables']) > 0:
                print(f"First table info: {json.dumps(schema['tables'][0], indent=2)}")
        else:
            print(f"No schema extracted from {selected_db} or an error occurred")
    else:
        print("No databases available to test schema extraction")
    
    # Test prompt formatting with database
    print("Testing prompt formatting with database reference...")
    test_prompt = "Create a query to get all features"
    
    # Format prompt with database if available
    if db_count > 1:
        dialog.comboBoxSqlDatabase.setCurrentIndex(1)
        formatted = dialog._format_prompt_for_provider("Ollama", test_prompt)
        
        # Check if database info is included
        if selected_db != "None" and selected_db in formatted:
            print("Database schema successfully included in the formatted prompt")
        else:
            print("Database schema was not included in the formatted prompt")
    else:
        # Test with "None" selected
        dialog.comboBoxSqlDatabase.setCurrentIndex(0)
        formatted = dialog._format_prompt_for_provider("Ollama", test_prompt)
        assert formatted == test_prompt, "Prompt shouldn't be modified if no database is selected"
        print("Prompt correctly unchanged with 'None' database selected")
    
    print("Database functionality tests completed!")

if __name__ == "__main__":
    test_database_functionality() 