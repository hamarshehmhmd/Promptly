# Run all tests for the Promptly plugin
import os
import sys
import traceback

def run_all_tests():
    """Run all test scripts and report results"""
    print("Running all tests for Promptly plugin...")
    print("=" * 60)
    
    # List of test modules
    test_modules = [
        "test_button_fix",
        "test_database_feature",
        "test_integration"
    ]
    
    # Run each test and track results
    passed = []
    failed = []
    
    for test in test_modules:
        print(f"\nRunning {test}...")
        print("-" * 60)
        try:
            # Import and run the test
            module = __import__(test)
            
            # Find and run the main test function
            for attr_name in dir(module):
                if attr_name.startswith('test_') and callable(getattr(module, attr_name)):
                    test_func = getattr(module, attr_name)
                    test_func()
                    break
            
            passed.append(test)
            print(f"{test} PASSED")
        except Exception as e:
            failed.append(test)
            print(f"{test} FAILED: {str(e)}")
            print(traceback.format_exc())
    
    # Report summary
    print("\n" + "=" * 60)
    print(f"Test Summary: {len(passed)} passed, {len(failed)} failed")
    
    if failed:
        print("\nFailed tests:")
        for test in failed:
            print(f"  - {test}")
    
    if len(passed) == len(test_modules):
        print("\nAll tests PASSED! The plugin should work correctly.")
        return True
    else:
        print("\nSome tests FAILED. Please fix the issues before using the plugin.")
        return False

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1) 