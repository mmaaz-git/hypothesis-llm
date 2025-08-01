from utils import get_functions_from_module, get_function_info
import suggest
import asyncio
import write
import review
import improve
import json

functions = get_functions_from_module("statistics")

function_info = get_function_info("statistics", functions)

print(function_info["count"])

print(asyncio.run(write._write_single_function_test("statistics", "count", [
    {
        "property": "count is a function that returns the number of elements in a list",
        "reasoning": "count is a function that returns the number of elements in a list",
        "confidence": "certain"
    }
])))

print(asyncio.run(write._write_multi_function_test(
    module_name="statistics",
    property_dict={
        "property": "the mean of a list is the sum of the elements divided by the count of the elements",
        "reasoning": "this is the mathematical definition of the mean",
        "confidence": "certain",
        "functions_involved": ["mean", "count"]
    }
)))

# Test the _review_single_test function directly
print("=" * 50)
print("Testing _review_single_test function")
print("=" * 50)

# Let's test with the test_mode_properties function that should be split
test_mode_properties_code = '''@given(st.data())
def test_mode_properties(data):
    """Test various properties of the mode function."""
    import pytest
    from collections import Counter

    # Test 1: Empty data should raise StatisticsError
    with pytest.raises(StatisticsError):
        mode([])

    # Test 2: Single element should return that element
    single_element = data.draw(st.integers())
    assert mode([single_element]) == single_element

    # Test 3: Mode should be in the data
    test_list = data.draw(st.lists(st.integers(), min_size=1))
    mode_val = mode(test_list)
    assert mode_val in test_list

    # Test 4: Mode should have maximum frequency
    counter = Counter(test_list)
    assert counter[mode_val] == max(counter.values())'''

# Simulate a pytest failure result
pytest_result = {
    'status': 'fail',
    'falsifying_example': 'data=...',
    'error_message': 'Test failed due to st.data() usage issues'
}

test_info = {
    'name': 'test_mode_properties',
    'source_code': test_mode_properties_code
}

review_result = asyncio.run(review._review_single_test(test_info, pytest_result))
print("Review result:")
print(json.dumps(review_result, indent=2))

# Test the _improve_single_test function directly
print("=" * 50)
print("Testing _improve_single_test function")
print("=" * 50)

# Use the review result we just got to test the improve function
improve_result = asyncio.run(improve._improve_single_test(test_info, review_result))
print("Improve result:")
print("=" * 30)
print(improve_result)
print("=" * 30)