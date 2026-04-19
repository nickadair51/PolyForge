"""Synthesis Layer — blind evaluation of provider solutions.

Receives solutions labeled with anonymous SolutionKeys so the evaluating
LLM cannot be biased by provider identity. The Orchestrator maps keys
back to provider names after synthesis returns.
"""

import json
from polyforge.models import (
    SolutionKey, LLMResponse, ExecutionResult, SynthesisResult, LLMRequest,
)
from polyforge.providers.LLMProvider import LLMProvider

SYNTHESIS_SYSTEM_PROMPT = (
    "You are a code review assistant. You are given multiple candidate solutions "
    "to the same coding question. Each solution is labeled with a blind key "
    "(Solution A, Solution B, etc.). You do not know which tool produced each solution.\n\n"
    "Evaluate each solution on:\n"
    "1. Correctness — does the test output show all tests passing?\n"
    "2. Code quality — is the implementation clean, readable, and maintainable?\n"
    "3. Completeness — does it fully address the original question?\n"
    "4. Minimality — does it make only the changes necessary, without unnecessary modifications?\n\n"
    "Respond ONLY with a JSON object:\n"
    "{\n"
    '  "recommended_solution": "<Solution A | Solution B | ...>",\n'
    '  "justification": "<why this solution is best>",\n'
    '  "quality_warnings": ["<any concerns about the recommended solution>"],\n'
    '  "failure_analysis": "<if no solution passes tests, explain why — otherwise null>",\n'
    '  "closest_solution": "<if all failed, which came closest — otherwise null>",\n'
    '  "solution_rankings": ["<ordered best to worst>"]\n'
    "}"
)

# Maps provider index (order they appear) to a blind key
_KEY_ORDER = [SolutionKey.SOLUTION_A, SolutionKey.SOLUTION_B, SolutionKey.SOLUTION_C]


class SynthesisLayer:
    def __init__(self, provider: LLMProvider):
        self._provider = provider

    async def synthesize(
        self,
        question: str,
        llm_responses: list[LLMResponse],
        execution_results: list[ExecutionResult],
        query_id: str,
    ) -> tuple[SynthesisResult, dict[str, str]]:
        """Run blind synthesis and return (result, key_to_provider mapping).

        The key_to_provider dict lets the Orchestrator decode blind keys
        back to real provider names.
        """
        # Pair responses with execution results by provider
        exec_by_provider = {er.provider: er for er in execution_results}

        # Assign blind keys and build the mapping
        key_to_provider: dict[str, str] = {}
        sections: list[str] = []

        for i, llm_resp in enumerate(llm_responses):
            key = _KEY_ORDER[i]
            key_to_provider[key.value] = llm_resp.provider
            exec_result = exec_by_provider.get(llm_resp.provider)
            sections.append(self._build_solution_section(key, llm_resp, exec_result))

        user_message = f"### Original Question\n{question}\n\n" + "\n\n".join(sections)

        request = LLMRequest(
            query_id=query_id,
            provider="synthesis",
            system_prompt=SYNTHESIS_SYSTEM_PROMPT,
            file_contents={},
            question=user_message,
        )

        response = await self._provider.query_llm(request)
        return self._parse_synthesis(response, key_to_provider), key_to_provider

    def _build_solution_section(
        self, key: SolutionKey, llm_resp: LLMResponse, exec_result: ExecutionResult | None
    ) -> str:
        parts = [f"### {key.value}"]

        # Modified files
        parts.append("#### Modified Files")
        for filename, content in llm_resp.modified_files.items():
            parts.append(f"--- {filename} ---\n```\n{content}\n```")

        # Test results
        if exec_result:
            parts.append("#### Test Results")
            parts.append(
                f"Exit code: {exec_result.exit_code}\n"
                f"Tests passed: {exec_result.tests_passed} | "
                f"Failed: {exec_result.tests_failed} | "
                f"Errors: {exec_result.tests_errored}"
            )
            parts.append("#### Test Output")
            if exec_result.stderr:
                parts.append(exec_result.stderr)
            if exec_result.stdout:
                parts.append(exec_result.stdout)
        else:
            parts.append("#### Test Results\nNo execution result — provider failed before Docker stage.")

        return "\n\n".join(parts)

    def _parse_synthesis(
        self, response: LLMResponse, key_to_provider: dict[str, str]
    ) -> SynthesisResult:
        """Parse the synthesis LLM response and decode blind keys back to provider names."""
        cost = response.cost if hasattr(response, 'cost') else 0.0

        if not response.success:
            return SynthesisResult(
                recommended_provider=None,
                justification=f"Synthesis call failed: {response.error}",
                quality_warnings=[],
                failure_analysis="Synthesis LLM did not return a valid response.",
                closest_provider=None,
                solution_rankings=[],
                synthesis_cost=cost,
            )

        try:
            raw = response.raw_text.strip()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                fence_start = raw.find("```")
                if fence_start == -1:
                    raise ValueError("No JSON found in synthesis response")
                content_start = raw.index("\n", fence_start) + 1
                fence_end = raw.find("```", content_start)
                if fence_end == -1:
                    raise ValueError("Unclosed code fence in synthesis response")
                data = json.loads(raw[content_start:fence_end].strip())

            # Decode blind keys → provider names
            rec_key = data.get("recommended_solution")
            recommended = key_to_provider.get(rec_key) if rec_key else None

            closest_key = data.get("closest_solution")
            closest = key_to_provider.get(closest_key) if closest_key else None

            raw_rankings = data.get("solution_rankings", [])
            rankings = [key_to_provider[k] for k in raw_rankings if k in key_to_provider]

            return SynthesisResult(
                recommended_provider=recommended,
                justification=data.get("justification", ""),
                quality_warnings=data.get("quality_warnings", []),
                failure_analysis=data.get("failure_analysis"),
                closest_provider=closest,
                solution_rankings=rankings,
                synthesis_cost=cost,
            )
        except Exception as e:
            return SynthesisResult(
                recommended_provider=None,
                justification=f"Failed to parse synthesis response: {e}",
                quality_warnings=[],
                failure_analysis=str(e),
                closest_provider=None,
                solution_rankings=[],
                synthesis_cost=cost,
            )
