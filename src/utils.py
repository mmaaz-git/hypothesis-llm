import importlib
import inspect
import asyncio
import ast
import re
import subprocess
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
            # Find decorators by looking backwards from the function definition
            func_start_line = node.lineno - 1  # ast uses 1-based line numbers

            # Look backwards to find decorators/comments that belong to this function
            actual_start_line = func_start_line
            for i in range(func_start_line - 1, -1, -1):
                line = content_lines[i].strip()
                # Include decorators, docstrings, comments, and empty lines
                if (line.startswith('@') or  # Decorators like @given
                    line.startswith('#') or   # Comments
                    line == '' or            # Empty lines
                    line.startswith('"""') or line.startswith("'''") or  # Docstrings
                    line.endswith('"""') or line.endswith("'''")):     # End of docstrings
                    actual_start_line = i
                elif line and not line.startswith(' '):  # Hit another top-level statement
                    break

            # End of function
            end_line = node.end_lineno if hasattr(node, 'end_lineno') else func_start_line + 10

            source_lines = content_lines[actual_start_line:end_line]
            source_code = '\n'.join(source_lines)

            test_functions.append({
                'name': node.name,
                'source_code': source_code
            })

    return test_functions

def run_pytest_and_parse(test_file: str) -> dict:
    """
    Run pytest on test file and parse results per function.

    Returns:
        Dict mapping function names to their results with details
    """
    # Run pytest with detailed output
    result = subprocess.run([
        'pytest', test_file, '-v', '--tb=long', '--no-header', '--no-summary'
    ], capture_output=True, text=True)

    test_results = {}

    # Parse test outcomes from output
    # Look for lines like: test_file.py::test_function_name PASSED/FAILED/ERROR
    outcome_pattern = r'(\w+\.py)::(\w+)\s+(PASSED|FAILED|ERROR)'
    for match in re.finditer(outcome_pattern, result.stdout):
        file_name, func_name, status = match.groups()
        test_results[func_name] = {
            'status': status,
            'failure_message': ''
        }

    # Parse failure details if any failures occurred
    if 'FAILED' in result.stdout or 'ERROR' in result.stdout:
        test_results = parse_failure_details(test_results, result.stdout)

    return test_results

def parse_failure_details(test_results: dict, output: str) -> dict:
    """
    Extract detailed failure information from pytest output.
    """
    lines = output.split('\n')
    current_test = None
    in_failure_section = False
    failure_lines = []

    for i, line in enumerate(lines):
        # Look for failure headers like "_____________ test_function_name _____________"
        if line.startswith('_') and any(test_name in line for test_name in test_results.keys()):
            # Save previous test's failure if any
            if current_test and failure_lines:
                test_results[current_test]['failure_message'] = '\n'.join(failure_lines)
                failure_lines = []

            for test_name in test_results.keys():
                if test_name in line:
                    current_test = test_name
                    in_failure_section = True
                    break

        # Capture all failure content between test headers
        elif current_test and in_failure_section:
            # Don't capture the divider lines
            if not (line.startswith('=') and line.count('=') > 10):
                failure_lines.append(line)

        # Reset when we hit next section
        elif line.startswith('=') and line.count('=') > 10:
            # Save current test's failure
            if current_test and failure_lines:
                test_results[current_test]['failure_message'] = '\n'.join(failure_lines)
                failure_lines = []
            current_test = None
            in_failure_section = False

    # Save final test's failure
    if current_test and failure_lines:
        test_results[current_test]['failure_message'] = '\n'.join(failure_lines)

    return test_results

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