import argparse
import json
from suggest import suggest
from write import write
from review import review
from improve import improve
import subprocess
from constants import DEFAULT_MODEL, DEFAULT_MAX_CONCURRENT_REQUESTS

def main():
    parser = argparse.ArgumentParser(
        prog="hypothesis-llm",
        description="Generate property-based test suggestions using LLMs"
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Suggest subcommand
    suggest_parser = subparsers.add_parser(
        "suggest",
        help="Suggest properties for functions in a module"
    )
    suggest_parser.add_argument(
        "module",
        type=str,
        help="Module to analyze (e.g., 'math', 'statistics')"
    )
    suggest_parser.add_argument(
        "--functions", "-f",
        type=str,
        help="Comma-separated list of specific functions to analyze (e.g., 'sin,cos,sqrt'). If not provided, all functions from the module will be analyzed."
    )
    suggest_parser.add_argument(
        "--max-concurrent",
        type=int,
        default=DEFAULT_MAX_CONCURRENT_REQUESTS,
        help="Maximum number of concurrent API requests (default: 10)"
    )
    suggest_parser.add_argument(
        "--output", "-o",
        type=str,
        help="Output file to save results (default: print to stdout)"
    )
    suggest_parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Suppress progress output"
    )
    suggest_parser.add_argument(
        "--model", "-m",
        type=str,
        default=DEFAULT_MODEL,
        help="LLM model to use (default: claude-4-sonnet)"
    )

    # Write subcommand
    write_parser = subparsers.add_parser(
        "write",
        help="Generate test code from property suggestions"
    )
    write_parser.add_argument(
        "properties_input",
        type=str,
        help="JSON file path or JSON string with property suggestions"
    )
    write_parser.add_argument(
        "--output", "-o",
        type=str,
        help="Output file for generated tests (default: print to stdout)"
    )
    write_parser.add_argument(
        "--model", "-m",
        type=str,
        default=DEFAULT_MODEL,
        help="LLM model to use (default: claude-4-sonnet)"
    )
    write_parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Suppress progress output"
    )
    write_parser.add_argument(
        "--max-concurrent",
        type=int,
        default=DEFAULT_MAX_CONCURRENT_REQUESTS,
        help="Maximum number of concurrent API requests (default: 10)"
    )

    # Review subcommand
    review_parser = subparsers.add_parser(
        "review",
        help="Review existing test files and suggest improvements"
    )
    review_parser.add_argument(
        "test_file",
        type=str,
        help="Test file to review (will run pytest automatically)"
    )
    review_parser.add_argument(
        "--output", "-o",
        type=str,
        help="Output file for review results (default: print to stdout)"
    )
    review_parser.add_argument(
        "--model", "-m",
        type=str,
        default=DEFAULT_MODEL,
        help="LLM model to use (default: claude-4-sonnet)"
    )
    review_parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Suppress progress output"
    )
    review_parser.add_argument(
        "--max-concurrent",
        type=int,
        default=DEFAULT_MAX_CONCURRENT_REQUESTS,
        help="Maximum number of concurrent API requests (default: 10)"
    )

    # Improve subcommand
    improve_parser = subparsers.add_parser(
        "improve",
        help="Fix test functions based on review feedback"
    )
    improve_parser.add_argument(
        "test_file",
        type=str,
        help="Test file to improve"
    )
    improve_parser.add_argument(
        "reviews_input",
        type=str,
        help="JSON file path or JSON string with review results"
    )
    improve_parser.add_argument(
        "--output", "-o",
        type=str,
        help="Output file for improved tests (default: print to stdout)"
    )
    improve_parser.add_argument(
        "--model", "-m",
        type=str,
        default=DEFAULT_MODEL,
        help="LLM model to use (default: claude-4-sonnet)"
    )
    improve_parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Suppress progress output"
    )
    improve_parser.add_argument(
        "--max-concurrent",
        type=int,
        default=DEFAULT_MAX_CONCURRENT_REQUESTS,
        help="Maximum number of concurrent API requests (default: 10)"
    )

    args = parser.parse_args()

    if args.command == "suggest":
        try:
            # Parse functions list if provided
            functions_list = None
            if args.functions:
                functions_list = [f.strip() for f in args.functions.split(',')]

            result = suggest(
                module_name=args.module,
                functions=functions_list,
                max_concurrent_requests=args.max_concurrent,
                model_name=args.model,
                quiet=args.quiet
            )

            if args.output:
                with open(args.output, 'w') as f:
                    json.dump(result, f, indent=2)
                if not args.quiet:
                    print(f"Results saved to {args.output}")
            else:
                print(json.dumps(result, indent=2))
        except ImportError as e:
            print(f"Error: {e}")
            return 1
        except ValueError as e:
            print(f"Error: {e}")
            return 1
        except Exception as e:
            print(f"Unexpected error: {e}")
            return 1
    elif args.command == "write":
        try:
            # Try to parse as JSON string first
            try:
                properties_data = json.loads(args.properties_input)
                input_source = "JSON string"
            except json.JSONDecodeError:
                # If that fails, treat as file path
                with open(args.properties_input, "r") as f:
                    properties_data = json.load(f)
                input_source = args.properties_input

            result = write(
                properties_data=properties_data,
                model_name=args.model,
                quiet=args.quiet,
                max_concurrent_requests=args.max_concurrent
            )

            # Handle output
            if args.output:
                with open(args.output, 'w') as f:
                    f.write(result)
                if not args.quiet:
                    print(f"Generated tests saved to {args.output}")
            else:
                print(result)

        except FileNotFoundError as e:
            print(f"Error: Properties file not found: {e}")
            return 1
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON: {e}")
            return 1
        except Exception as e:
            print(f"Unexpected error: {e}")
            return 1
    elif args.command == "review":
        try:
            result = review(
                test_file=args.test_file,
                model_name=args.model,
                quiet=args.quiet,
                max_concurrent_requests=args.max_concurrent
            )

            # Handle output
            if args.output:
                with open(args.output, 'w') as f:
                    json.dump(result, f, indent=2)
                if not args.quiet:
                    print(f"Review results saved to {args.output}")
            else:
                print(json.dumps(result, indent=2))

        except FileNotFoundError as e:
            print(f"Error: Test file not found: {e}")
            return 1
        except subprocess.SubprocessError as e:
            print(f"Error running pytest: {e}")
            return 1
        except Exception as e:
            print(f"Unexpected error: {e}")
            return 1
    elif args.command == "improve":
        try:
            # Try to parse reviews as JSON string first
            try:
                reviews_data = json.loads(args.reviews_input)
                input_source = "JSON string"
            except json.JSONDecodeError:
                # If that fails, treat as file path
                with open(args.reviews_input, "r") as f:
                    reviews_data = json.load(f)
                input_source = args.reviews_input

            result = improve(
                test_file=args.test_file,
                reviews=reviews_data,
                model_name=args.model,
                quiet=args.quiet,
                max_concurrent_requests=args.max_concurrent
            )

            # Handle output
            if args.output:
                with open(args.output, 'w') as f:
                    f.write(result)
                if not args.quiet:
                    print(f"Improved tests saved to {args.output}")
            else:
                print(result)

        except FileNotFoundError as e:
            print(f"Error: File not found: {e}")
            return 1
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON in reviews: {e}")
            return 1
        except Exception as e:
            print(f"Unexpected error: {e}")
            return 1
    else:
        parser.print_help()

if __name__ == "__main__":
    main()