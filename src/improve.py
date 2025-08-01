import llm
import json
import asyncio
from utils import run_async_with_progress, parse_python_code
from review import parse_test_functions
from prompts import IMPROVE_SINGLE_TEST_PROMPT
from constants import DEFAULT_MODEL, DEFAULT_MAX_CONCURRENT_REQUESTS


async def _improve_single_test(func_info: dict, review: dict, model_name: str = DEFAULT_MODEL) -> str:
    """
    Rewrite a single test function based on review feedback.

    Args:
        func_info: Dict with function name and source code
        review: Dict with issue and fix from review
        model_name: LLM model to use

    Returns:
        Improved function code as string
    """
    model = llm.get_async_model(model_name)

    issue = review.get('issue', '')
    fix = review.get('fix', '')

    prompt = IMPROVE_SINGLE_TEST_PROMPT.format(
        test_source_code=func_info['source_code'],
        issue=issue,
        fix=fix)

    response = await model.prompt(prompt)
    raw_response = await response.text()
    return parse_python_code(raw_response)


def improve(test_file: str,
            reviews: dict,
            model_name: str = DEFAULT_MODEL,
            max_concurrent_requests: int = DEFAULT_MAX_CONCURRENT_REQUESTS,
            quiet: bool = False) -> str:
    """
    Improve a test file by fixing functions marked as problematic in reviews.

    Args:
        test_file: Path to the test file to improve
        reviews: Dict from review() with function analyses
        model_name: LLM model to use for improvements
        quiet: Whether to suppress progress output

    Returns:
        Improved test file content as string
    """
    # Parse existing test functions
    test_functions = parse_test_functions(test_file)

    if not quiet:
        print(f"Analyzing {len(test_functions)} test functions...")

    # Separate functions that need improvement vs those that are okay
    functions_to_improve = []
    functions_to_keep = []

    for func in test_functions:
        func_name = func['name']
        review = reviews.get('reviews', {}).get(func_name)

        if review is None:
            # Function not in reviews dict, skip it entirely
            continue
        elif review.get('okay', True):
            # Function is okay, keep as-is
            functions_to_keep.append(func)
        else:
            # Function needs improvement
            functions_to_improve.append((func, review))

    if not functions_to_improve:
        if not quiet:
            print("No functions need improvement!")
        # Return original file content
        with open(test_file, 'r') as f:
            return f.read()

    if not quiet:
        print(f"Identified {len(functions_to_improve)} functions to fix")

    # Improve functions that need fixing
    async def run_improvement(item):
        func_info, review = item
        return await _improve_single_test(func_info, review, model_name)

    improved_functions = asyncio.run(run_async_with_progress(
        items=functions_to_improve,
        async_processor=run_improvement,
        max_concurrent=max_concurrent_requests,
        quiet=quiet,
        get_item_name=lambda item: f"{item[0]['name']}()"
    ))

    # Combine kept functions and improved functions
    all_functions = []

    # Add kept functions (in original order)
    for func in functions_to_keep:
        all_functions.append(func['source_code'])

    # Add improved functions
    for improved_code in improved_functions:
        if improved_code.strip():  # Only add non-empty improvements
            all_functions.append(improved_code)

    # Extract imports/header from original file (everything before first function/class)
    # (hacky)
    with open(test_file, 'r') as f:
        lines = f.readlines()

    header_lines = []
    for line in lines:
        stripped = line.strip()
        # Stop when we hit any function/class definition or decorator
        if (stripped.startswith('def ') or
            stripped.startswith('async def ') or
            stripped.startswith('class ') or
            stripped.startswith('@')):  # Decorators usually precede functions
            break
        header_lines.append(line)

    # Use the original header (includes all imports, comments, etc.)
    imports = ''.join(header_lines).rstrip() + '\n'

    improved_file = imports + '\n\n' + '\n\n'.join(all_functions)

    return improved_file