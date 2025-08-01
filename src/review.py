import llm
import json
import asyncio
from utils import (
    run_async_with_progress,
    pytest_report,
    parse_test_functions
)
from constants import DEFAULT_MODEL, DEFAULT_MAX_CONCURRENT_REQUESTS
from prompts import REVIEW_SINGLE_TEST_PROMPT

async def _review_single_test(test_info: dict, pytest_result: dict, model_name: str = DEFAULT_MODEL) -> dict:
    """
    Review a single test function with its pytest results.

    Returns:
        Dict with {"okay": bool, "issue": str, "fix": str}
    """
    model = llm.get_async_model(model_name)

    prompt = REVIEW_SINGLE_TEST_PROMPT.format(
        test_source_code=test_info['source_code'],
        test_status=pytest_result.get('status', 'UNKNOWN'),
        falsifying_example=pytest_result.get('falsifying_example', ''),
        error_message=pytest_result.get('error_message', ''))

    schema = {
        "type": "object",
        "properties": {
            "okay": {"type": "boolean"},
            "issue": {"type": "string"},
            "fix": {"type": "string"}
        },
        "required": ["okay", "issue", "fix"]
    }

    response = await model.prompt(prompt, schema=schema)
    result = json.loads(await response.text())
    return result


def review(test_file: str,
           model_name: str = DEFAULT_MODEL,
           max_concurrent_requests: int = DEFAULT_MAX_CONCURRENT_REQUESTS,
           quiet: bool = False) -> dict:
    """
    Review a test file by running pytest and analyzing each test function.

    Args:
        test_file: Path to the test file to review
        model_name: LLM model to use for analysis
        quiet: Whether to suppress progress output

    Returns:
        Dict with test_file and reviews for each function
    """
    if not quiet:
        print(f"Running pytest on {test_file}...")

    # Run pytest and get results
    report, counts = pytest_report(test_file, return_counts=True)

    if not quiet:
        print(f"Pytest results: {counts['pass']} passed, {counts['fail']} failed, {counts['error']} errors")

    # Parse test functions from file
    test_functions = parse_test_functions(test_file)

    if not quiet:
        print(f"Reviewing {len(test_functions)} test functions...")

    # Review each test function with its pytest result
    async def run_review(test_info):
        func_name = test_info['name']
        pytest_result = report.get(func_name, {'status': 'UNKNOWN'})
        return await _review_single_test(test_info, pytest_result, model_name)

    reviews_list = asyncio.run(run_async_with_progress(
        items=test_functions,
        async_processor=run_review,
        max_concurrent=max_concurrent_requests,
        quiet=quiet,
        get_item_name=lambda test: f"{test['name']}()"
    ))

    # Build final result
    reviews = {}
    for test_func, review_result in zip(test_functions, reviews_list):
        reviews[test_func['name']] = review_result

    return {
        "test_file": test_file,
        "reviews": reviews
    }