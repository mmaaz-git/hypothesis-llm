import llm
import json
import asyncio
from prompts import WRITING_SINGLE_FUNCTION_PROPERTIES, WRITING_MULTI_FUNCTION_PROPERTIES
from utils import get_function_info, run_async_with_progress, parse_python_code
from constants import DEFAULT_MODEL, DEFAULT_MAX_CONCURRENT_REQUESTS

async def _write_single_function_test(module_name: str,
                                      function_name: str,
                                      properties: list[dict],
                                      model_name: str = DEFAULT_MODEL) -> str:
    """
    Generate test code for a single function's properties.

    Args:
        module_name: Name of the module (e.g., 'statistics')
        function_name: Name of the function (e.g., 'mean')
        properties: List of property dicts with 'property', 'reasoning', 'confidence'
        model_name: LLM model to use

    Returns:
        Generated test code as string
    """
    if not properties:
        return ""

    # Get function information
    function_info = get_function_info(module_name, function_name)
    func_info = function_info[function_name]

    model = llm.get_async_model(model_name)

    # Build properties text
    properties_text = []
    for i, prop in enumerate(properties, 1):
        properties_text.append(f"{i}. {prop['property']} (confidence: {prop['confidence']})")

    prompt = WRITING_SINGLE_FUNCTION_PROPERTIES.format(
        function_name=function_name,
        module_name=module_name,
        function_signature=func_info['signature'],
        function_docstring=func_info['docstring'],
        function_source=func_info['source'],
        properties=properties_text)

    response = await model.prompt(prompt)
    raw_response = await response.text()
    return parse_python_code(raw_response)


async def _write_multi_function_test(module_name: str,
                                     property_dict: dict,
                                     model_name: str = DEFAULT_MODEL) -> str:
    """
    Generate test code for a multi-function property.

    Args:
        module_name: Name of the module (e.g., 'statistics')
        property_dict: Dict with 'property', 'reasoning', 'confidence', 'functions_involved'
        model_name: LLM model to use

    Returns:
        Generated test code as string
    """
    functions_involved = property_dict['functions_involved']
    if not functions_involved:
        return ""

    # Get function information for all involved functions
    function_infos = {}
    for func_name in functions_involved:
        func_info = get_function_info(module_name, func_name)
        function_infos[func_name] = func_info[func_name]

    model = llm.get_async_model(model_name)

    # Build function descriptions
    func_descriptions = []
    for func_name, func_info in function_infos.items():
        func_descriptions.append(f"""
Function: {func_info['name']} (from {module_name})
Signature: {func_info['signature']}
Docstring: {func_info['docstring']}
Source: {func_info['source']}""")

    functions_text = "\n".join(func_descriptions)

    prompt = WRITING_MULTI_FUNCTION_PROPERTIES.format(
        module_name=module_name,
        property=property_dict['property'],
        reasoning=property_dict['reasoning'],
        confidence=property_dict['confidence'],
        functions_involved=functions_text)

    response = await model.prompt(prompt)
    raw_response = await response.text()
    return parse_python_code(raw_response)


def write(properties_data: dict,
          model_name: str = DEFAULT_MODEL,
          max_concurrent_requests: int = DEFAULT_MAX_CONCURRENT_REQUESTS,
          quiet: bool = False) -> str:
    """
    Generate test code from property suggestions.

    Args:
        properties_data: Dict with property suggestions from suggest command
        model_name: LLM model to use
        quiet: Whether to suppress progress output

    Returns:
        Generated test code as string
    """
    module_name = properties_data['module_name']
    single_function_properties = properties_data['single_function_properties']
    multi_function_properties = properties_data['multi_function_properties']

    if not quiet:
        print(f"Generating tests for {len(single_function_properties)} functions and {len(multi_function_properties)} multi-function properties...")

    # Async all single function properties
    async def run_single_function(item):
        func_name, properties = item
        return await _write_single_function_test(module_name, func_name, properties, model_name)

    single_function_items = list(single_function_properties.items())
    single_function_tests = asyncio.run(run_async_with_progress(
        items=single_function_items,
        async_processor=run_single_function,
        max_concurrent=max_concurrent_requests,
        quiet=quiet,
        get_item_name=lambda item: f"{item[0]}()"
    ))

    # Async all multi-function properties
    multi_function_tests = []
    if multi_function_properties:
        async def run_multi_function(prop_dict):
            return await _write_multi_function_test(module_name, prop_dict, model_name)

        multi_function_tests = asyncio.run(run_async_with_progress(
            items=multi_function_properties,
            async_processor=run_multi_function,
            max_concurrent=max_concurrent_requests,
            quiet=quiet,
            get_item_name=lambda prop: f"multi-function properties"
        ))

    # Collect imports in alphabetical order from all properties
    function_names = set()
    function_names.update(single_function_properties.keys())
    for prop in multi_function_properties:
        if 'functions_involved' in prop:
            function_names.update(prop['functions_involved'])
    sorted_functions = sorted(function_names)

    # Build imports for final test file
    if sorted_functions:
        if len(sorted_functions) == 1:
            function_imports = f"from {module_name} import {sorted_functions[0]}"
        else:
            function_imports = f"from {module_name} import (\n"
            for func in sorted_functions:
                function_imports += f"    {func},\n"
            function_imports = function_imports.rstrip(',\n') + "\n)"
    else:
        function_imports = f"# No functions to import from {module_name}"

    imports = f'''"""Property-based tests for {module_name} module.
Generated by hypothesis-llm.
"""

import hypothesis
from hypothesis import given, strategies as st
{function_imports}
'''

    return imports + '\n\n' + '\n\n'.join(single_function_tests) + '\n\n' + '\n\n'.join(multi_function_tests)