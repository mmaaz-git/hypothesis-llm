from utils import get_functions_from_module, get_function_info
import suggest
import asyncio
import write

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