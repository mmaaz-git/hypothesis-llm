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
You are an expert property-based tester.

# Task

Propose the **most important, testable properties** for the function below.

# Rules
- Base every property on behaviour evident from the source / docstring.
- No probabilistic, statistical, or domain-external claims.
- Prioritise definitions, edge-cases, invariants, and algebraic laws.
- Do not propose properties that are based on esoteric theoretical domain-specific properties.
- Rate confidence as: certain | high | medium | low | uncertain.

# Important single-function properties
- **Idempotence**: `set(set(xs)) == set(xs)`
- **Double reverse**: `reverse(reverse(xs)) == xs`
- **Length invariant**: `len(sorted(xs)) == len(xs)`
- **Bounded output**: `min(xs) ≤ median(xs) ≤ max(xs)`
- **Monotonicity**: for positive `x < y`, `log(x) < log(y)`
- **Commutativity**: `gcd(a, b) == gcd(b, a)`
- **Associativity**: `max(max(a, b), c) == max(a, max(b, c))`
- **Neutral element**: `max(a, -inf) == a`
- **Error condition**: `sqrt(x)` raises `ValueError` when `x < 0`

# Function: {{function_name}}

Signature: {{function_signature}}
Docstring: {{function_docstring}}
Source code:
```python
{{function_source}}
"""

SUGGEST_MULTI_FUNCTION_PROPERTIES = """
You are an expert property-based tester.

Task: propose up to **6 key, testable properties** that relate two or more of the functions below.

# Rules
- Each property must reference **≥ 2 distinct functions**.
- Use behaviour evident from the source / docstrings only.
- No probabilistic, statistical, or deep domain-specific claims.
- Prioritise inverses, composition, shared invariants, algebraic or symmetry relations, and domain/range consistency.
- Rate confidence as: certain | high | medium | low | uncertain.

# Important multi-function properties
- **Round-trip**: `parse_json(dumps_json(x)) == x`
- **Equivalent paths**: `f(g(x)) == g(f(x))`

Functions provided:
{function_infos}

Return the properties in the required schema only—no extra text.
"""

# prompts for writing tests (from scratch)

WRITING_SINGLE_FUNCTION_PROPERTIES = f"""
Generate `hypothesis` test code for testing these properties of {{function_name}} from {{module_name}}.

# Function Information

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

# Test Results

Status: {{test_status}}
Falsifying example:
{{falsifying_example}}
Error message:
{{error_message}}

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
- REFLECT on if this demonstrates a genuine bug in the code in the code being tested (mark okay=true, explain in issue)
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

Make the MINIMAL fix needed. Rules:
1. Keep same function name and exact structure
2. If fixing floating-point comparison: ONLY change == to math.isclose()
3. If fixing random.shuffle(): ONLY replace with deterministic alternative
4. If fixing missing import: ONLY add the missing import
5. Don't change anything else - no "improvements" or refactoring
6. One change at a time - if fix suggests multiple things, pick one

Return ONLY the fixed function code:"""