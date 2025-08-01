# how to write good tests
# used for write and improve

WRITING_TEST_GUIDELINES = """
In order to write good tests, you must follow these stylistic guidelines:

1. Use `@given` decorators with appropriate hypothesis strategies. Infer types from the function signature or docstring.
2. Make assertions that directly test the stated properties.
3. Add clear comments or docstrings explaining the properties being tested so that a human can review your work.
4. Handle edge cases and potential exceptions appropriately.
5. Use descriptive test method names that describe the property being tested.

You must write precise and robust tests. Here are some bad practices and their good alternatives:
| Bad Practice | Good Alternative |
|--------------|------------------|
| `st.data()` | Use a proper strategy. Only use `st.data()` if it is necessary for a complex strategy. |
| `assume()` | Use a proper strategy, or chain it with .filter() or .map() |
| `st.floats()` if you are generating floats that will be compared | Use `st.floats(allow_nan=False, allow_infinity=False)` because, by default, `nan` is not equal to itself and `inf` may overflow. |
| Use exact equality when comparing floats | Use `numpy.isclose()` or `numpy.allclose()` or `math.isclose()` |
"""

# prompts for suggesting properties

SUGGEST_SINGLE_FUNCTION_PROPERTIES = f"""
Identify the most important properties to test this function's correctness.

Function: {{function_name}}
Signature: {{function_signature}}
Docstring: {{function_docstring}}

Source code:
{{function_source}}

Please identify properties this function should satisfy. For each property:
1. Express it clearly (using mathematical notation when appropriate)
2. Explain your reasoning for why this property should hold
3. Rate your confidence as: certain, high, medium, low, or uncertain

Examples of properties:
- Mathematical relationships (commutativity, associativity, etc.)
- Invariants (bounds, constraints)
- Identity properties
- Monotonicity
- Edge case behaviors

It is NOT necessary to list all properties. Focus on the MOST IMPORTANT properties that would catch bugs.

Be specific and testable in your property descriptions.

Also output confidence level as:
- "certain" only for mathematical definitions
- "high" for well-established patterns
- "medium" for likely but not guaranteed properties
- "low" for speculative properties
- "uncertain" when you're unsure
"""

SUGGEST_MULTI_FUNCTION_PROPERTIES = f"""
Analyze these functions together and identify mathematical/logical properties that involve relationships between multiple functions.

Functions:
{{function_infos}}

Please identify properties that involve relationships between these functions. For each property:
1. Express it clearly (using mathematical notation when appropriate)
2. Explain your reasoning for why this property should hold
3. List which functions are involved in this property
4. Rate your confidence as: certain, high, medium, low, or uncertain

Focus on multi-function relationships like:
- Inverse relationships (f(g(x)) = x)
- Compositional properties
- Algebraic relationships (f(x) + g(x), f(x) * g(x))
- Domain/range relationships
- Symmetry relationships
- Functional equations involving multiple functions

Only include properties that genuinely involve multiple functions working together. Ignore single-function properties.

Be specific and testable in your property descriptions.
Also output confidence level as:
- "certain" only for mathematical definitions
- "high" for well-established patterns
- "medium" for likely but not guaranteed properties
- "low" for speculative properties
- "uncertain" when you're unsure.
"""


# prompts for writing tests (from scratch)

WRITING_SINGLE_FUNCTION_PROPERTIES = f"""
Generate `hypothesis` test code for testing these properties of {{function_name}} from {{module_name}}.

# Function Information:
Name: {{function_name}}
Signature: {{function_signature}}
Docstring: {{function_docstring}}

Source code:
{{function_source}}

# Properties to test:
{{properties}}

# Guidelines for good test code:
{WRITING_TEST_GUIDELINES}

# Other instructions:
Assume these imports are already available:
```python
import hypothesis
from hypothesis import given, strategies as st
```
and the function itself.
If you need to import something else, you MUST import it in the test function.
For example, if you need to use `math.isclose` to compare floats, you must import it yourself.
Generate ONLY the test function code.
"""

WRITING_MULTI_FUNCTION_PROPERTIES = f"""
Generate `hypothesis` test code for testing this multi-function property from the {{module_name}} module.

# Property: {{property}} (confidence: {{confidence}})
# Reasoning: {{reasoning}}

# Functions involved:
{{functions_involved}}

# Guidelines for good test code:
{WRITING_TEST_GUIDELINES}

# Other instructions:
Assume these imports are already available:
```python
import hypothesis
from hypothesis import given, strategies as st
```
and the functions involved.
If you need to import something else, you MUST import it in the test function.
For example, if you need to use `math.isclose` to compare floats, you must import it yourself.
Generate ONLY the test function code.
"""

# prompts for reviewing tests

REVIEW_SINGLE_TEST_PROMPT = f"""
Review this Hypothesis property-based test:

```python
{{test_source_code}}
```

Test Results:
{{pytest_results}}

Analyze this test result carefully:

If the test PASSED:
- Mark okay=false if you see ANY of these issues:
  * Uses exact equality (==) for floating-point comparisons
  * Missing @given decorators or strategy definitions
  * Uses random.shuffle() or other non-deterministic operations
  * Missing imports inside test functions
  * Tests incorrect mathematical properties
  * Not actually property-based (just hardcoded values)
- Mark okay=true ONLY if test is genuinely well-written with proper tolerances

If the test FAILED or ERROR:
- Consider if this might be a GENUINE BUG in the code being tested (mark okay=true, explain in issue)
- Or if there's a problem with the TEST ITSELF (mark okay=false, suggest fix)

Common TEST problems to look for:
- Uses == instead of math.isclose() for floating-point comparisons
- Strategy generates invalid values (overflow, NaN, undefined names)
- Assertion tolerance too strict/loose for floating point
- Missing imports or syntax errors
- Missing @given decorators
- Uses random.shuffle() instead of deterministic alternatives
- Incorrect property logic

Common signs of GENUINE BUGS:
- Test logic looks correct but implementation doesn't match expected behavior
- Property should mathematically hold but fails on valid inputs
- Error messages suggest implementation issues

You may assume that the following imports are available:
```python
import hypothesis
from hypothesis import given, strategies as st
```
and the function(s) being tested.

# Guidelines for good test code:
{WRITING_TEST_GUIDELINES}
"""

# prompts for improving tests

IMPROVE_SINGLE_TEST_PROMPT = f"""
Fix this Hypothesis property-based test function:

```python
{{test_source_code}}
```

Problem identified: {{issue}}

Specific fix suggested: {{fix}}

You may assume that the following imports are available:
```python
import hypothesis
from hypothesis import given, strategies as st
```
and the function(s) being tested. For example, if you are testing `mean`, you may assume that `from statistics import mean` is available.

Apply the specific fix suggested above. Requirements:
1. Keep the same function name
2. If you need imports, put them at the TOP of your output
3. Apply ONLY the fix described - don't make other changes

Return ONLY the fixed function code:"""