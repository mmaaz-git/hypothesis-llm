# hypothesis-llm

Use large language models (LLMs) to help write property-based tests (PBTs) with [Hypothesis](https://hypothesis.readthedocs.io/).

This is a work in progress!

Basically, you point this at some Python functions, and it tries to figure out what properties they should satisfy, then generates Hypothesis tests for those properties. It can also review your existing tests and suggest fixes. It comes with four commands:
- `suggest`: Analyze functions and suggest properties to test
- `write`: Generate test code from property suggestions
- `review`: Review existing test files and suggest improvements
- `improve`: Fix test functions based on review feedback

## Installation

Clone this repository and then run:

```bash
pip3 install -e .
```

This package relies on the [llm](https://llm.datasette.io/) library for LLM integration. You can install it with:
```bash
pip3 install llm
```

By default, this library supports the OpenAI models. You can add support for Anthropic models (recommended!) with:
```bash
llm install llm-anthropic
```

It also supports other providers and local models. See the [llm](https://llm.datasette.io/) documentation for more details.

You will need to set up API keys for the LLM providers you want to use. You can do this just by exporting:

```bash
export ANTHROPIC_API_KEY="your-key-here"
```

Or whatever your provider requires. The `llm` library also provides a `keys` command to help you manage your keys.

This package uses Claude 4 Sonnet model by default. You can change this with the `--model` option (read on for more details).

## Quick Start

As described above, there are four commands. These can be used by themselves or in a workflow. We go through each of these in turn, then discuss common parameters. In the next section, we discuss how to use these commands in a workflow and more advanced use cases.

### `suggest`

This command analyzes a Python module and suggests properties that the functions in that module should satisfy.

```bash
hypothesis-llm suggest <module>
```

This will output a JSON file with the properties. The JSON will have the following structure:

```json
{
    "module_name": "module_name",
    "single_function_properties": {
        "function_name1": [
            {
            "property": "property_name",
            "reasoning": "reasoning_for_property",
            "confidence": "confidence_level"
        }
    ],
    },
    "multi_function_properties": [
        {
            "property": "property_name",
            "reasoning": "reasoning_for_property",
            "confidence": "confidence_level",
            "functions_involved": ["function_name1", "function_name2", ...]
        }
    ]
}
```

The `single_function_properties` key contains a dictionary of function names to lists of properties. The `multi_function_properties` key contains a list of properties that involve multiple functions.

### `write`

This command generates test code from property suggestions.

```bash
hypothesis-llm write <properties_file>
```

It expects a JSON file with suggested properties as output by the `suggest` command. It then writes a test file based on the properties.

### `review`

This command reviews existing test files and suggests improvements. It only takes a `.py` file as input.

```bash
hypothesis-llm review <test_file>
```

It will output a JSON file with the suggestions. The JSON will have the following structure:

```json
{
    "test_file": "test_file.py",
    "reviews": {
        "test_function_name": {
            "okay": true | false,
            "issue": "reasoning_for_issue",
            "fix": "fix_suggestion"
        }
    }
}
```

The `reviews` key contains a dictionary of test function names to review objects. The `okay` key is a boolean indicating whether the test function is okay. The `issue` key is a string describing the issue with the test function. The `fix` key is a string describing a fix for the test function.

### `improve`

This command improves existing test functions based on review feedback. It takes a test file and a JSON file with reviews as output by the `review` command.

```bash
hypothesis-llm improve <test_file> <reviews_file>
```

It will output a new test file with the improvements implemented.

### Common Parameters

These parameters are common to all commands.

- `--model`: The model to use. Defaults to `claude-4-sonnet`.
- `--max-concurrent-requests`: The maximum number of concurrent requests to make. Defaults to `10`.
- `--output`: The file to write the output to. Defaults to `stdout`.
- `--quiet`: Whether to suppress output. Defaults to `false`.

You can always use `-h` to see the help for a command.

## Python API

All four commands are also available as a Python API. This is useful if you want to use them in a larger workflow.

```python
from hypothesis_llm import suggest, write, review, improve

suggest("mymodule")
```

The inputs and outputs are the same as the CLI commands, as described above.

## Advanced Usage

We can easily chain these commands together to create a complete workflow. For example, here is a complete workflow for a module called `mymodule`:

```bash
hypothesis-llm suggest mymodule -o mymodule_properties.json
hypothesis-llm write mymodule_properties.json -o mymodule_tests.py
hypothesis-llm review mymodule_tests.py -o mymodule_reviews.json
hypothesis-llm improve mymodule_tests.py mymodule_reviews.json -o mymodule_tests_improved.py
```

The `suggest` command optionally takes a list of functions to analyze. For example, if I only want to analyze `foo` and `bar`, I can do:

```bash
hypothesis-llm suggest mymodule --functions foo,bar -o mymodule_properties.json
```

It is also possible to combine them with other tools, like `jq` to filter the output. For example, suppose I already generated properties for all functions in `mymodule` into `mymodule_properties.json`, but now I only want to write single-function tests for `foo` and `bar`. I can do:

```bash
jq '.single_function_properties |= with_entries(select(.key | test("foo|bar")))' mymodule_properties.json > filtered_properties.json
```

And then write tests from the filtered properties:

```bash
hypothesis-llm write filtered_properties.json -o tests_foo_bar.py
```

We can also additionally keep the multi-function properties to only include those that involve both `foo` and `bar` by doing:

```bash
jq '.single_function_properties |= with_entries(select(.key | test("foo|bar"))) | .multi_function_properties |= map(select(.functions_involved | all(test("foo|bar"))))' mymodule_properties.json > filtered_properties.json
```

Or, we may only want the single-function properties and want to drop all the multi-function properties by doing:

```bash
jq '.multi_function_properties = []' mymodule_properties.json > filtered_properties.json
```

We can also use `jq` to filter the output of the `review` command. For example, suppose I want to review only the tests for `foo`, I can do:

```bash
jq '.reviews |= with_entries(select(.key | test("foo")))' mymodule_reviews.json > filtered_reviews.json
```

And then improve the tests by only fixing the issues for `foo`:

```bash
hypothesis-llm improve mymodule_tests.py filtered_reviews.json -o mymodule_tests_foo_improved.py
```

This would only output a new test file for `foo` with the improvements implemented.

You can also of course do this in an "easier" way (depending on your workflow) in the Python API, as you need only filter `dict`s.

## How it works

This section details some of the internals and design choices of the package. One general design choice is that we try to keep each command focused on one thing. This makes it easier to chain them together. We try to keep the prompt context as focused as possible. For example, theoretically, it is possible to send an entire module to the LLM to generate properties, but instead we parse functions one by one and send them to the LLM separately. We try to use parallel calls as much as possible to speed up the process.

### `suggest`

This takes as input a module name (optionally, some functions in the module) and outputs a JSON file with the properties. It does this by:

1. Getting all functions in the module (or, only the functions specified).
2. For each function, it (async) calls the LLM to generate a list of properties that the function should satisfy (single-function properties).
3. It sends all functions in one prompt to the LLM to generate properties across functions (multi-function properties).

The information about functions sent to the LLM is:
- function name
- function signature
- function docstring
- function source code

For some functions, the signature, docstring, or source code may be missing. For example, for a C function, the signature and source code may be missing. We handle this just be using an empty string in that case.

### `write`

This takes as input a JSON file with properties and outputs a test file. It does this by:

1. For single-function properties:
    -  For each _function_, it (async) calls the LLM to generate tests for that function.
2. For multi-function properties:
    - For each _multi-function property_, it (async) calls the LLM to generate tests for the property.
3. Combines these into one test file, adding basic `hypothesis` imports, as well as importing all the functions from the module that were mentioned in the properties.

Note the difference here. For single-function properties, we loop over functions, i.e., sending all properties for that function in one prompt. For multi-function properties, we loop over properties.

The information about functions sent to the LLM is the same as for the `suggest` command. This is possible because `module_name` is available in the properties JSON.

### `review`

This takes as input a test file and outputs a JSON file with the reviews. It does this by:

1. Runs `pytest` on the test file to get the test results.
2. For each test function, it (async) calls the LLM to review the test function, giving it the test function source code, whether the test passed or failed, and the test output.

Note in this step, we do not send information about the original function to the LLM. This is because we don't have the original module and hence the signature, docstring, and source code. We may add this in the future.

The LLM is prompted to review the function, the strategy, the assertions, and the test output. It is prompted to reflect on the failure, and, if it believes the test is not failing for the right reason, it is prompted to suggest a fix.

### `improve`

This takes as input a test file and a JSON file with reviews and outputs a new test file with the improvements implemented. It does this by:

1. Scans through the review file and notes which are okay and not okay.
2. For each test function that is not okay, it (async) calls the LLM to improve the test function, giving it the test function source code and the review.
3. Combines the okay functions with the improved functions, and adds back the original header.

