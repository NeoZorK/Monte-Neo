#!/usr/bin/env python3
"""
OpenCode Adapter - Code Completion & Analysis
Code completion, bug detection, refactoring suggestions, test generation
100% LOCAL - NO CLOUD
"""

from typing import Dict, List, Any
import logging
import json


class CodeAnalyzer:
    """Local code analysis without cloud dependencies"""

    def __init__(self, client):
        self.client = client
        self.logger = logging.getLogger("CodeAnalyzer")
        self.logger.info("✅ Code analyzer initialized (local)")

    def analyze_code(self, code: str, language: str = "python") -> Dict[str, Any]:
        """Analyze code for issues (local analysis)"""
        self.logger.info(f"🔍 Analyzing {language} code ({len(code)} chars)...")

        prompt = f"""
        Analyze this {language} code and identify:
        1. Potential bugs
        2. Security vulnerabilities
        3. Performance issues
        4. Code style violations

        Format response as JSON with these fields:
        - bugs: list of bug descriptions
        - security: list of security issues
        - performance: list of performance issues
        - style: list of style violations

        Code to analyze:
        ```{language}
        {code}
        ```
        """

        result = self.client.query("qwen3:8b", prompt)

        if not result.get("success"):
            return {"success": False, "error": result.get("error")}

        try:
            # Try to parse JSON response
            analysis = json.loads(result.get("output", "{}"))
            return {
                "success": True,
                "analysis": analysis,
                "language": language
            }
        except json.JSONDecodeError:
            # Fallback: return raw analysis
            return {
                "success": True,
                "analysis": {"raw": result.get("output", "")},
                "language": language
            }

    def suggest_refactoring(self, code: str, language: str = "python") -> Dict[str, Any]:
        """Suggest refactoring improvements (local)"""
        self.logger.info(f"💡 Suggesting refactoring for {language} code...")

        prompt = f"""
        Suggest refactoring improvements for this {language} code:

        1. Extract functions/methods
        2. Reduce complexity
        3. Improve readability
        4. Follow {language} best practices

        Format response as JSON:
        - suggestions: list of improvements
        - examples: code examples of suggestions

        Code:
        ```{language}
        {code}
        ```
        """

        result = self.client.query("qwen2.5-coder:7b", prompt)

        if not result.get("success"):
            return {"success": False, "error": result.get("error")}

        try:
            suggestions = json.loads(result.get("output", "{}"))
            return {
                "success": True,
                "suggestions": suggestions,
                "language": language
            }
        except json.JSONDecodeError:
            return {
                "success": True,
                "suggestions": {"raw": result.get("output", "")},
                "language": language
            }


class CodeCompletion:
    """Code completion engine (local)"""

    def __init__(self, client):
        self.client = client
        self.logger = logging.getLogger("CodeCompletion")
        self.logger.info("✅ Code completion initialized (local)")

    def complete_code(self, code_prefix: str, language: str = "python",
                     context_lines: int = 5) -> Dict[str, Any]:
        """Generate code completion (local)"""
        self.logger.info(f"📝 Generating code completion for {language}...")

        prompt = f"""
        Complete this {language} code. Provide multiple completion options (top 3).

        Incomplete code:
        ```{language}
        {code_prefix}
        ```

        Provide JSON with:
        - completions: list of 3 completion options
        - confidence: confidence score (0-1) for each
        - explanation: why each completion makes sense
        """

        result = self.client.query("qwen2.5-coder:7b", prompt)

        if not result.get("success"):
            return {"success": False, "error": result.get("error")}

        try:
            completions = json.loads(result.get("output", "{}"))
            return {
                "success": True,
                "completions": completions,
                "language": language
            }
        except json.JSONDecodeError:
            # Parse raw response
            output = result.get("output", "")
            return {
                "success": True,
                "completions": {"raw": output},
                "language": language
            }

    def function_signature_completion(self, partial_signature: str,
                                       language: str = "python") -> Dict[str, Any]:
        """Complete function signature (local)"""
        self.logger.info(f"🔧 Completing function signature ({language})...")

        prompt = f"""
        Complete this {language} function signature:

        {partial_signature}

        Provide:
        1. Complete signature with proper type hints
        2. Docstring template
        3. Implementation skeleton

        Format as JSON with: signature, docstring, skeleton
        """

        result = self.client.query("qwen2.5-coder:7b", prompt)

        if not result.get("success"):
            return {"success": False, "error": result.get("error")}

        try:
            completion = json.loads(result.get("output", "{}"))
            return {
                "success": True,
                "completion": completion,
                "language": language
            }
        except json.JSONDecodeError:
            return {
                "success": True,
                "completion": {"raw": result.get("output", "")},
                "language": language
            }


class TestGenerator:
    """Generate unit tests (local)"""

    def __init__(self, client):
        self.client = client
        self.logger = logging.getLogger("TestGenerator")
        self.logger.info("✅ Test generator initialized (local)")

    def generate_tests(self, code: str, language: str = "python",
                      test_framework: str = "pytest") -> Dict[str, Any]:
        """Generate unit tests for code (local)"""
        self.logger.info(f"🧪 Generating {test_framework} tests for {language}...")

        prompt = f"""
        Generate comprehensive unit tests for this {language} code using {test_framework}.

        Include:
        1. Happy path tests
        2. Edge case tests
        3. Error condition tests
        4. Mock external dependencies

        Code:
        ```{language}
        {code}
        ```

        Provide complete test code that runs immediately.
        """

        result = self.client.query("qwen2.5-coder:7b", prompt)

        if not result.get("success"):
            return {"success": False, "error": result.get("error")}

        return {
            "success": True,
            "tests": result.get("output", ""),
            "language": language,
            "framework": test_framework
        }

    def generate_integration_tests(self, code: str, language: str = "python") -> Dict[str, Any]:
        """Generate integration tests (local)"""
        self.logger.info(f"🔗 Generating integration tests for {language}...")

        prompt = f"""
        Generate integration tests for this {language} module.

        Include:
        1. Module interaction tests
        2. External service mocking
        3. Database tests (if applicable)
        4. End-to-end flow tests

        Code:
        ```{language}
        {code}
        ```

        Provide complete integration tests.
        """

        result = self.client.query("qwen2.5-coder:7b", prompt)

        if not result.get("success"):
            return {"success": False, "error": result.get("error")}

        return {
            "success": True,
            "tests": result.get("output", ""),
            "language": language,
            "type": "integration"
        }


class DocumentationGenerator:
    """Generate documentation (local)"""

    def __init__(self, client):
        self.client = client
        self.logger = logging.getLogger("DocumentationGenerator")
        self.logger.info("✅ Documentation generator initialized (local)")

    def generate_docstring(self, code: str, language: str = "python") -> Dict[str, Any]:
        """Generate docstring for code (local)"""
        self.logger.info(f"📚 Generating docstring for {language}...")

        prompt = f"""
        Generate a comprehensive docstring for this {language} function/class.

        Include:
        1. Description
        2. Parameters with types
        3. Return value
        4. Raises (exceptions)
        5. Examples
        6. Notes (if applicable)

        Code:
        ```{language}
        {code}
        ```

        Format docstring in standard {language} style.
        """

        result = self.client.query("qwen2.5-coder:7b", prompt)

        if not result.get("success"):
            return {"success": False, "error": result.get("error")}

        return {
            "success": True,
            "docstring": result.get("output", ""),
            "language": language
        }

    def generate_readme(self, project_files: List[str], description: str) -> Dict[str, Any]:
        """Generate README documentation (local)"""
        self.logger.info("📖 Generating README...")

        files_text = "\n".join(project_files)

        prompt = f"""
        Generate a comprehensive README.md for this project:

        Description: {description}

        Project files:
        {files_text}

        Include:
        1. Project overview
        2. Installation instructions
        3. Usage examples
        4. API documentation
        5. Configuration
        6. Troubleshooting
        7. Contributing
        8. License

        Format as Markdown.
        """

        result = self.client.query("qwen3:8b", prompt)

        if not result.get("success"):
            return {"success": False, "error": result.get("error")}

        return {
            "success": True,
            "readme": result.get("output", "")
        }

    def generate_api_docs(self, code: str, language: str = "python") -> Dict[str, Any]:
        """Generate API documentation (local)"""
        self.logger.info(f"🔌 Generating API docs for {language}...")

        prompt = f"""
        Generate API documentation for this {language} code.

        Include:
        1. Class/function signatures
        2. Parameters documentation
        3. Return values
        4. Exception documentation
        5. Usage examples
        6. Type hints

        Code:
        ```{language}
        {code}
        ```

        Format as Markdown suitable for API documentation.
        """

        result = self.client.query("qwen2.5-coder:7b", prompt)

        if not result.get("success"):
            return {"success": False, "error": result.get("error")}

        return {
            "success": True,
            "api_docs": result.get("output", ""),
            "language": language
        }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("\n🧪 OPENCODE ADAPTER TESTING")
    print("=" * 60)
    print("Components:")
    print("  1. Code Analysis (bugs, security, performance)")
    print("  2. Code Completion (function/line completion)")
    print("  3. Test Generation (unit + integration)")
    print("  4. Documentation (docstrings, README, API docs)")
    print("=" * 60)
    print("All local, no cloud dependencies!")
    print("=" * 60)
