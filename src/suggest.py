import llm
import inspect
import importlib
import json
import asyncio
from utils import get_functions_from_module, get_function_info, run_async_with_progress
from prompts import SUGGEST_SINGLE_FUNCTION_PROPERTIES, SUGGEST_MULTI_FUNCTION_PROPERTIES
from constants import DEFAULT_MODEL, DEFAULT_MAX_CONCURRENT_REQUESTS

async def _one_function(function_info: dict, model_name: str = DEFAULT_MODEL) -> list[dict]:
    """
    Suggest properties for a single function.

    Args:
        function_info: Dictionary with function name, signature, docstring, source
        model_name: Name of the model to use for analysis

    Returns:
        List of dicts with property, reasoning, confidence
    """
    model = llm.get_async_model(model_name)

    prompt = SUGGEST_SINGLE_FUNCTION_PROPERTIES.format(
        function_name=function_info['name'],
        function_signature=function_info['signature'],
        function_docstring=function_info['docstring'],
        function_source=function_info['source'])

    schema = {
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "property": {"type": "string"},
                        "reasoning": {"type": "string"},
                        "confidence": {"type": "string", "enum": ["certain", "high", "medium", "low", "uncertain"]}
                    },
                    "required": ["property", "reasoning", "confidence"]
                }
            }
        },
        "required": ["items"]
    }

    response = await model.prompt(prompt, schema=schema)
    properties = json.loads(await response.text())

    return properties.get("items", [])

def _multi_function(function_infos: list[dict], model_name: str = DEFAULT_MODEL) -> list[dict]:
    """
    Suggest properties that involve relationships between multiple functions.

    Args:
        function_infos: List of function info dictionaries
        model_name: Name of the model to use for analysis

    Returns:
        List of dicts with property, reasoning, confidence, functions_involved
    """
    if len(function_infos) < 2:
        return []  # Need at least 2 functions for multi-function analysis

    model = llm.get_model(model_name) # don't need async here bc one request

    # Build function descriptions
    func_descriptions = []
    for i, func_info in enumerate(function_infos, 1):
        func_descriptions.append(f"""Function {i}: {func_info['name']}
Signature: {func_info['signature']}
Docstring: {func_info['docstring']}
Source: {func_info['source']}""")

    functions_text = "\n\n".join(func_descriptions)
    func_names = [f['name'] for f in function_infos]

    prompt = SUGGEST_MULTI_FUNCTION_PROPERTIES.format(
        function_infos=functions_text)

    schema = {
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "property": {"type": "string"},
                        "reasoning": {"type": "string"},
                        "functions_involved": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of function names involved in this property"
                        },
                        "confidence": {"type": "string", "enum": ["certain", "high", "medium", "low", "uncertain"]}
                    },
                    "required": ["property", "reasoning", "functions_involved", "confidence"]
                }
            }
        },
        "required": ["items"]
    }

    response = model.prompt(prompt, schema=schema)
    properties = json.loads(response.text())

    return properties.get("items", [])

def suggest(module_name: str,
            functions: str | list[str] | None = None,
            max_concurrent_requests: int = DEFAULT_MAX_CONCURRENT_REQUESTS,
            model_name: str = DEFAULT_MODEL,
            quiet: bool = False) -> dict:
    """
    Suggest property-based tests for functions.

    Args:
        module_name: Name of the module
        functions: Name of the function or list of function names. If not provided, all functions from the module will be analyzed.
        max_concurrent_requests: Maximum number of concurrent API requests
        model_name: LLM model to use for analysis
        quiet: Whether to suppress progress output

    Returns:
        Dictionary with analysis results
    """
    if functions is None:
        functions = get_functions_from_module(module_name)

    function_info = get_function_info(module_name, functions)

    if not function_info:
        raise ValueError("No functions found to analyze")

    if not quiet:
        print(f"Analyzing {len(function_info)} function(s) from module '{module_name}'")

    # to return
    result = {"module_name": module_name,
            "single_function_properties": {},
            "multi_function_properties": {}}

    # async run over each function for single function analysis
    async def _run(func_info): return await _one_function(func_info, model_name)
    results = asyncio.run(run_async_with_progress(
        items=list(function_info.values()),
        async_processor=_run,
        max_concurrent=max_concurrent_requests,
        quiet=quiet,
        get_item_name=lambda func: f"{func['name']}()"
    ))

    for func_name, properties in zip(function_info.keys(), results):
        result["single_function_properties"][func_name] = properties or []

    # do multi function analysis
    if len(function_info) >= 2:
        if not quiet:
            print("Performing multi-function analysis...")

        multi_result = _multi_function(list(function_info.values()), model_name)
        result["multi_function_properties"] = multi_result or []
    else:
        result["multi_function_properties"] = []

    return result
