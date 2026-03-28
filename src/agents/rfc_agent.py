from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from langchain_core.messages import AIMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

import src.config.settings as cfg
from src.core.state import AgentState
from src.tools.rfc_tools import add_rfc, check_rfc_status, search_rfc_knowledge


class SkillLoader:
    """Load skill documents lazily so each phase only sees the guidance it needs."""

    def __init__(self, skill_root: Path):
        self.skill_root = skill_root
        self._cache: dict[str, str] = {}
        self.load_history: list[str] = []

    def load(self, *stages: str) -> str:
        docs: list[str] = []
        for stage in stages:
            if stage not in self._cache:
                skill_path = self._resolve_skill_path(stage)
                try:
                    self._cache[stage] = skill_path.read_text(encoding="utf-8")
                except FileNotFoundError:
                    self._cache[stage] = f"# Missing skill\nSkill file `{skill_path.name}` was not found."
                self.load_history.append(stage)
            docs.append(self._cache[stage])
        return "\n\n".join(docs)

    def _resolve_skill_path(self, stage: str) -> Path:
        if stage == "skill":
            return self.skill_root / "SKILL.md"
        return self.skill_root / f"{stage}.md"


class RFCExpertAgentRuntime:
    """Skill-driven RFC agent with a stable `ainvoke` interface."""

    def __init__(self):
        self.llm = ChatOpenAI(
            base_url=cfg.OPENROUTER_BASE_URL,
            api_key=cfg.OPENROUTER_API_KEY,
            model=cfg.DEFAULT_MODEL,
            temperature=0,
        )
        skill_root = Path(__file__).resolve().parent.parent / "skills" / "rfc_agent"
        self.skill_loader = SkillLoader(skill_root)

    async def ainvoke(self, initial_state: AgentState) -> dict[str, Any]:
        messages = initial_state.get("messages", [])
        if not messages:
            return {"messages": [AIMessage(content="I need a question before I can look up RFC details.")]}

        question = messages[-1].content
        intent = await self._run_intent(question)
        plan = await self._run_planning(question, intent)
        retrieval = await self._run_retrieval(plan)
        answer = await self._run_answer(question, plan, retrieval)

        return {
            "messages": [AIMessage(content=answer)],
            "rfc_id": plan.get("rfc_id"),
            "query": plan.get("query"),
            "context": retrieval.get("context"),
            "next_step": "answer",
        }

    async def _run_intent(self, question: str) -> dict[str, Any]:
        skills_doc = self.skill_loader.load("skill", "base", "intent")
        system = f"""You are the intent stage of an RFC expert agent.

Use the loaded skills to classify the user request before any retrieval step.

Loaded skills:
{skills_doc}

Return only one JSON object. Do not emit XML, markdown fences, tool calls, or extra commentary.

Return JSON with:
- "request_type": one of "specific_rfc", "protocol_topic", "technical_detail", "general_networking"
- "mentions_rfc": boolean
- "confidence": number between 0 and 1
- "topic": short English topic summary
- "user_goal": short explanation of what the user wants
"""
        prompt = ChatPromptTemplate.from_messages(
            [("system", system), ("human", "{question}")]
        )
        return self._invoke_json_prompt(
            prompt,
            {"question": question},
            fallback={
                "request_type": "technical_detail",
                "mentions_rfc": False,
                "confidence": 0.3,
                "topic": question[:80],
                "user_goal": "Need RFC-related technical guidance.",
            },
        )

    async def _run_planning(self, question: str, intent: dict[str, Any]) -> dict[str, Any]:
        skills_doc = self.skill_loader.load("planning")
        intent_json = json.dumps(intent, ensure_ascii=False, sort_keys=True)
        system = f"""You are the planning stage of an RFC expert agent.

Use the loaded skills to decide retrieval strategy and produce a single search query in English.

Loaded skills:
{skills_doc}

Return only one JSON object. Do not emit XML, markdown fences, tool calls, or extra commentary.

Return JSON with:
- "rfc_id": RFC number as digits only, or null
- "query": an English retrieval query tailored for RFC text search
- "needs_rfc_content": boolean
- "should_check_local": boolean
- "answer_strategy": short phrase describing how the answer should be framed
"""
        prompt = ChatPromptTemplate.from_messages(
            [("system", system), ("human", "Question: {question}\nIntent result JSON: {intent_json}")]
        )
        result = self._invoke_json_prompt(
            prompt,
            {"question": question, "intent_json": intent_json},
            fallback={
                "rfc_id": self._normalize_rfc_id(intent.get("rfc_id")),
                "query": question,
                "needs_rfc_content": bool(intent.get("mentions_rfc")),
                "should_check_local": bool(intent.get("mentions_rfc")),
                "answer_strategy": "Use RFC retrieval when available.",
            },
        )
        result["rfc_id"] = self._normalize_rfc_id(result.get("rfc_id"))
        return result

    async def _run_retrieval(self, plan: dict[str, Any]) -> dict[str, Any]:
        self.skill_loader.load("retrieval")

        rfc_id = self._normalize_rfc_id(plan.get("rfc_id"))
        query = plan.get("query")
        needs_rfc_content = bool(plan.get("needs_rfc_content"))
        should_check_local = bool(plan.get("should_check_local", bool(rfc_id and needs_rfc_content)))

        context_parts: list[str] = []
        retrieval_notes: list[str] = []

        if rfc_id and needs_rfc_content and should_check_local:
            exists = await check_rfc_status.ainvoke(rfc_id)
            retrieval_notes.append(f"Local RFC {rfc_id} indexed: {exists}.")
            if not exists:
                try:
                    download_result = await add_rfc.ainvoke(rfc_id)
                except Exception as exc:
                    download_result = f"Failed to download RFC {rfc_id}: {exc}"

                retrieval_notes.append(download_result)
                if self._is_tool_error(download_result):
                    return {
                        "context": "",
                        "retrieval_notes": "\n".join(retrieval_notes),
                        "download_failed": True,
                        "search_failed": False,
                        "search_empty": False,
                    }

        if query:
            try:
                search_result = await search_rfc_knowledge.ainvoke(query)
            except Exception as exc:
                search_result = f"Search failed: {exc}"

            if self._is_search_error(search_result):
                retrieval_notes.append(search_result)
                return {
                    "context": "",
                    "retrieval_notes": "\n".join(retrieval_notes),
                    "download_failed": False,
                    "search_failed": True,
                    "search_empty": False,
                }

            if self._is_empty_search(search_result):
                retrieval_notes.append(search_result)
                return {
                    "context": "",
                    "retrieval_notes": "\n".join(retrieval_notes),
                    "download_failed": False,
                    "search_failed": False,
                    "search_empty": True,
                }

            context_parts.append(search_result)
            retrieval_notes.append("Knowledge base search succeeded.")

        return {
            "context": "\n\n".join(context_parts),
            "retrieval_notes": "\n".join(retrieval_notes),
            "download_failed": False,
            "search_failed": False,
            "search_empty": not bool(context_parts),
        }

    async def _run_answer(
        self, question: str, plan: dict[str, Any], retrieval: dict[str, Any]
    ) -> str:
        skills_doc = self.skill_loader.load("answering")
        plan_json = json.dumps(plan, ensure_ascii=False, sort_keys=True)
        system = f"""You are the answering stage of an RFC expert agent.

Use the loaded skills to answer conservatively and clearly.

Loaded skills:
{skills_doc}

Rules:
- Prefer RFC-backed statements from the provided context.
- If retrieval failed or context is empty, explicitly say what is missing.
- You may add brief general networking knowledge, but label it as general knowledge rather than RFC-backed evidence.
- If the user asked about a specific RFC and it could not be retrieved, say that directly.
"""
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", system),
                (
                    "human",
                    "Question: {question}\n\nPlan JSON: {plan_json}\n\nRetrieval notes:\n{retrieval_notes}\n\nContext:\n{context}",
                ),
            ]
        )
        chain = prompt | self.llm | StrOutputParser()
        return chain.invoke(
            {
                "question": question,
                "plan_json": plan_json,
                "retrieval_notes": retrieval.get("retrieval_notes", ""),
                "context": retrieval.get("context", ""),
            }
        )

    @staticmethod
    def _normalize_rfc_id(value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip().lower().replace("rfc", "")
        digits = "".join(ch for ch in text if ch.isdigit())
        return digits or None

    @staticmethod
    def _is_tool_error(result: Any) -> bool:
        if not isinstance(result, str):
            return False
        lowered = result.lower()
        return lowered.startswith("error ") or lowered.startswith("error:") or "failed to download rfc" in lowered

    @staticmethod
    def _is_search_error(result: Any) -> bool:
        if not isinstance(result, str):
            return False
        lowered = result.lower()
        return lowered.startswith("search failed:") or lowered.startswith("error querying knowledge base:")

    @staticmethod
    def _is_empty_search(result: Any) -> bool:
        if not isinstance(result, str):
            return False
        return result.strip() == "No relevant information found in the knowledge base."

    def _invoke_json_prompt(
        self,
        prompt: ChatPromptTemplate,
        variables: dict[str, Any],
        fallback: dict[str, Any],
    ) -> dict[str, Any]:
        chain = prompt | self.llm | StrOutputParser()
        raw_output = chain.invoke(variables)
        return self._parse_structured_output(raw_output, fallback)

    def _parse_structured_output(self, raw_output: str, fallback: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(raw_output, str):
            if isinstance(raw_output, dict):
                return {**fallback, **raw_output}
            raise ValueError(f"Unexpected structured output type: {type(raw_output).__name__}")

        cleaned = raw_output.strip()
        for candidate in (cleaned, self._extract_json_block(cleaned)):
            if candidate:
                try:
                    parsed = json.loads(candidate)
                except json.JSONDecodeError:
                    continue
                if isinstance(parsed, dict):
                    return {**fallback, **parsed}

        tool_call_result = self._parse_tool_call_output(cleaned)
        if tool_call_result is not None:
            return {**fallback, **tool_call_result}

        key_value_result = self._parse_key_value_output(cleaned)
        if key_value_result is not None:
            return {**fallback, **key_value_result}

        raise ValueError(f"Failed to parse structured output: {raw_output}")

    @staticmethod
    def _extract_json_block(text: str) -> str | None:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return match.group(0)
        fenced_match = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
        if fenced_match:
            return fenced_match.group(1)
        return None

    @classmethod
    def _parse_tool_call_output(cls, text: str) -> dict[str, Any] | None:
        invoke_match = re.search(r'<invoke name="([^"]+)">(.+?)</invoke>', text, re.DOTALL)
        if not invoke_match:
            return None

        tool_name = invoke_match.group(1)
        body = invoke_match.group(2)
        parameters = {
            name: value.strip()
            for name, value in re.findall(
                r'<parameter name="([^"]+)">(.*?)</parameter>', body, re.DOTALL
            )
        }

        if tool_name == "search_rfc_knowledge":
            return {
                "query": parameters.get("query"),
                "rfc_id": cls._normalize_rfc_id(parameters.get("rfc_id")),
                "needs_rfc_content": bool(parameters.get("rfc_id")),
                "should_check_local": bool(parameters.get("rfc_id")),
                "answer_strategy": "Answer from RFC search results.",
            }

        if tool_name == "check_rfc_status":
            rfc_id = cls._normalize_rfc_id(parameters.get("rfc_id"))
            return {
                "rfc_id": rfc_id,
                "needs_rfc_content": bool(rfc_id),
                "should_check_local": bool(rfc_id),
            }

        if tool_name == "add_rfc":
            rfc_id = cls._normalize_rfc_id(parameters.get("rfc_id"))
            return {
                "rfc_id": rfc_id,
                "needs_rfc_content": True,
                "should_check_local": bool(rfc_id),
            }

        return None

    @staticmethod
    def _parse_key_value_output(text: str) -> dict[str, Any] | None:
        pairs = re.findall(r"^\s*([a-zA-Z_]+)\s*:\s*(.+?)\s*$", text, re.MULTILINE)
        if not pairs:
            return None

        parsed: dict[str, Any] = {}
        for key, value in pairs:
            normalized = value.strip().strip('"')
            lowered = normalized.lower()
            if lowered in {"true", "false"}:
                parsed[key] = lowered == "true"
            elif re.fullmatch(r"\d+(\.\d+)?", normalized):
                parsed[key] = float(normalized) if "." in normalized else int(normalized)
            elif lowered == "null":
                parsed[key] = None
            else:
                parsed[key] = normalized
        return parsed


rfc_agent = RFCExpertAgentRuntime()
