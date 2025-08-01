import importlib
import inspect
import asyncio
import ast
import re
import subprocess
import tempfile
import os
from typing import Optional, List, Dict
import xml.etree.ElementTree as ET

from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn

# PARSING UTILS

def parse_test_functions(test_file: str) -> list[dict]:
    """
    Parse test file and extract individual test functions.

    Returns:
        List of dicts with function name and source code
    """
    with open(test_file, 'r') as f:
        content = f.read()

    tree = ast.parse(content)
    test_functions = []
    content_lines = content.split('\n')

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name.startswith('test_'):
            # Use AST to get decorator start line (handles multi-line decorators properly)
            if node.decorator_list:
                # First decorator's line number (1-indexed)
                actual_start_line = node.decorator_list[0].lineno - 1
            else:
                # No decorators, start from function definition
                actual_start_line = node.lineno - 1

            # Look backwards from actual_start_line to include comments/docstrings before decorators
            for i in range(actual_start_line - 1, -1, -1):
                line = content_lines[i].strip()
                if (line.startswith('#') or   # Comments
                    line == '' or            # Empty lines
                    line.startswith('"""') or line.startswith("'''") or  # Docstrings
                    line.endswith('"""') or line.endswith("'''")):     # End of docstrings
                    actual_start_line = i
                elif line:  # Hit non-empty, non-comment line
                    break

            # End of function
            end_line = node.end_lineno if hasattr(node, 'end_lineno') else node.lineno + 10

            source_lines = content_lines[actual_start_line:end_line]
            source_code = '\n'.join(source_lines)

            test_functions.append({
                'name': node.name,
                'source_code': source_code
            })

    return test_functions


def _extract_falsifying_example(text: str) -> Optional[str]:
    """Extract the falsifying example block from a failure message."""
    if "Falsifying example:" not in text:
        return None
    lines = text.splitlines()
    start = next((i for i, line in enumerate(lines) if "Falsifying example:" in line), None)
    if start is None:
        return None

    example_lines = []
    for line in lines[start:]:
        if line.strip() == "":
            break
        example_lines.append(line.strip())

    return "\n".join(example_lines)

def _parse_pytest_junit_xml(path: str) -> List[Dict]:
    tree = ET.parse(path)
    root = tree.getroot()

    results = {}
    for testcase in root.iter("testcase"):
        name = testcase.attrib.get("name")
        failure_node = testcase.find("failure")
        error_node = testcase.find("error")

        if failure_node is not None:
            status = "fail"
            falsifying_example = _extract_falsifying_example(failure_node.text or "")
            error_message = None
        elif error_node is not None:
            status = "error"
            falsifying_example = None
            error_message = (error_node.text or "").strip()
        else:
            status = "pass"
            falsifying_example = None
            error_message = None

        results[name] = {
            "status": status,
            "falsifying_example": falsifying_example,
            "error_message": error_message,
        }

    return results

def pytest_report(file_path: str, return_counts: bool = False):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".xml") as tmp:
        report_path = tmp.name

    try:
        result = subprocess.run(
            [
                "pytest",
                file_path,
                f"--junitxml={report_path}",
                "-q",
            ],
            capture_output=True,
            timeout=90,
        )
    except subprocess.SubprocessError as e:
        return {"FATAL ERROR": str(e)}

    if not os.path.exists(report_path):
        return {"FATAL ERROR": result.stderr.decode()}

    with open(report_path) as f:
        report = _parse_pytest_junit_xml(f)

    os.remove(report_path) # cleanup temp file

    if return_counts:
        counts = {
            "total": len(report),
            "fail": sum(1 for r in report if r["status"] == "fail"),
            "error": sum(1 for r in report if r["status"] == "error"),
            "pass": sum(1 for r in report if r["status"] == "pass"),
        }
        return report, counts

    return report

def parse_python_code(text: str) -> str:
    """
    Parse Python code from LLM response text.

    Tries in order:
    1. Extract from ```python code block
    2. Extract from ``` code block
    3. Return raw text

    Args:
        text: Raw text from LLM response

    Returns:
        Extracted Python code as string
    """
    if not text or not isinstance(text, str):
        return ""

    text = text.strip()

    # First try: Look for ```python code block
    python_pattern = r'```python\s*\n(.*?)\n```'
    match = re.search(python_pattern, text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()

    # Second try: Look for any ``` code block
    code_pattern = r'```\s*\n(.*?)\n```'
    match = re.search(code_pattern, text, re.DOTALL)
    if match:
        return match.group(1).strip()

    # Third try: Look for ``` with language on same line
    inline_pattern = r'```\w*\s*(.*?)\n```'
    match = re.search(inline_pattern, text, re.DOTALL)
    if match:
        return match.group(1).strip()

    # Last resort: Return the raw text
    return text

def get_functions_from_module(module_name: str) -> list:
    """
    Get all functions from a module.

    Returns:
        List of function names
    """
    mod = importlib.import_module(module_name)
    functions = []

    for name, obj in inspect.getmembers(mod, callable):
        # Only include public callables (not private)
        if not name.startswith('_'):
            functions.append(name)

    return functions

def get_function_info(module_name: str, functions: str | list[str]) -> dict:
    """
    Get info about functions from a given module.

    Args:
        module_name: Name of the module
        functions: Function name or list of function names

    Returns:
        Dictionary with function name as key and name, signature, docstring, source as value
    """
    function_info = {}

    try:
        mod = importlib.import_module(module_name)
    except ImportError as e:
        raise ImportError(f"Could not import module '{module_name}': {e}")

    if isinstance(functions, str):
        functions = [functions]

    for func_name in functions:
        if not hasattr(mod, func_name):
            raise ValueError(f"Function '{func_name}' not found in module '{module_name}'")

        func = getattr(mod, func_name)

        if not callable(func):
            raise ValueError(f"'{func_name}' in module '{module_name}' is not callable")

        try:
            source = inspect.getsource(func)
        except (TypeError, OSError):
            source = ""

        try:
            signature = str(inspect.signature(func))
        except (ValueError, TypeError):
            signature = None

        function_info[func_name] = {
            'name': func_name,
            'signature': signature,
            'docstring': inspect.getdoc(func) or "",
            'source': source
        }

    return function_info

# ASYNC UTILS

async def run_async_with_progress(
    items: list,
    async_processor,
    max_concurrent: int = 10,
    quiet: bool = False,
    get_item_name=lambda item: str(item)
) -> list:
    """
    Run an async function on a list of items with optional progress bar.

    Args:
        items: List of items to process
        async_processor: Async function that takes an item and returns a result
        max_concurrent: Maximum number of concurrent tasks
        quiet: Whether to suppress progress bar
        get_item_name: Function to extract display name from item

    Returns:
        List of results in the same order as input items
    """
    semaphore = asyncio.Semaphore(max_concurrent)

    if quiet:
        # No progress bar in quiet mode
        async def runner_with_semaphore(item):
            async with semaphore:
                try:
                    return await async_processor(item)
                except Exception as e:
                    print(f"Error processing {get_item_name(item)}: {e}")
                    return None

        tasks = [runner_with_semaphore(item) for item in items]
        return await asyncio.gather(*tasks)
    else:
        # Use rich progress bar
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("({task.completed}/{task.total})"),
            transient=True,
        ) as progress:
            task = progress.add_task("Starting...", total=len(items))

            async def runner_with_progress(item):
                async with semaphore:
                    item_name = get_item_name(item)
                    progress.update(task, description=f"Processing {item_name}")

                    try:
                        result = await async_processor(item)
                    except Exception as e:
                        print(f"\nError processing {item_name}: {e}")
                        result = None

                    progress.advance(task)
                    return result

            tasks = [runner_with_progress(item) for item in items]
            return await asyncio.gather(*tasks)