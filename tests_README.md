# Tests for Promptly QGIS Plugin

This directory contains automated tests for the Promptly QGIS plugin to verify that:
1. Buttons are correctly re-enabled after LLM requests
2. SQL database selection and schema extraction works properly

## How to Run the Tests

### Running All Tests
To run all tests at once, execute:
```bash
python run_tests.py
```

### Running Individual Tests
You can also run specific tests:
```bash
python test_button_fix.py        # Test for button re-enabling
python test_database_feature.py  # Test for database functionality
python test_integration.py       # Integration test of the whole workflow
```

## Test Descriptions

### Button Re-enabling Test
This test verifies that the Send and Fix buttons are properly re-enabled after:
- Successful LLM responses
- Error responses
- Error log updates

### Database Feature Test
This test checks:
- The SQL database dropdown correctly populates with available database connections
- The refresh button works to update the list
- The database schema is correctly extracted
- The formatted prompt includes the database schema when a database is selected

### Integration Test
This test simulates an end-to-end workflow:
1. Selecting a database
2. Entering a prompt
3. Sending it to the LLM (simulated)
4. Verifying the response handling
5. Checking that buttons are re-enabled

## Manual Testing Steps

After running the automated tests, you should also do these quick manual tests in QGIS:

1. **Button Blocking Test**:
   - Open the plugin
   - Enter a prompt and click "Send to LLM"
   - Verify that after receiving a response, you can click "Send to LLM" again
   - Try executing the code, then verify you can click "Send to LLM" again
   - Cause an execution error, then verify you can click "Fix Code with LLM"

2. **Database Feature Test**:
   - Open the plugin
   - Click the refresh button next to the database dropdown
   - Select a database (if available) and enter a SQL-related prompt
   - Send to LLM and check if the response references your database schema 