from langchain_openai import ChatOpenAI
from langchain_core.messages import AIMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langgraph.graph import StateGraph, END

from src.core.state import AgentState
import src.config.settings as cfg
from src.core.rfc_catalog import get_not_ingested_message, resolve_question_scope
from src.tools.rfc_tools import get_missing_rfc_ids, search_rfc_knowledge

# Initialize LLM
llm = ChatOpenAI(
    base_url=cfg.OPENROUTER_BASE_URL,
    api_key=cfg.OPENROUTER_API_KEY,
    model=cfg.DEFAULT_MODEL,
    temperature=0
)

def _build_search_query(question: str, target_rfc_ids: list[str]) -> str:
    system = """You generate concise English search queries for retrieving RFC content.

Focus on the protocol field, timer, packet behavior, state machine, or mechanism the user asked about.
Return only the English search query, with no explanation.
"""

    prompt = ChatPromptTemplate.from_messages([
        ("system", system),
        (
            "human",
            "Question: {question}\nTarget RFC IDs: {target_rfc_ids}\nEnglish search query:",
        ),
    ])

    chain = prompt | llm | StrOutputParser()
    try:
        return chain.invoke(
            {
                "question": question,
                "target_rfc_ids": ", ".join(target_rfc_ids),
            }
        ).strip()
    except Exception:
        return question


def analyze(state: AgentState):
    """Analyze the user's request and decide the next step."""
    messages = state["messages"]
    last_message = messages[-1].content

    resolved_scope = resolve_question_scope(last_message)
    if resolved_scope["availability_status"] != "supported":
        return {
            "target_rfc_ids": [],
            "availability_status": "not_ingested",
            "availability_message": resolved_scope["availability_message"],
            "next_step": "answer_not_ingested",
        }

    target_rfc_ids = resolved_scope["target_rfc_ids"]
    query = _build_search_query(last_message, target_rfc_ids) or last_message
    return {
        "target_rfc_ids": target_rfc_ids,
        "query": query,
        "availability_status": "supported",
        "availability_message": "",
        "next_step": "check_availability",
    }


async def check_availability(state: AgentState):
    """Check whether the required RFCs are already preloaded."""
    target_rfc_ids = state.get("target_rfc_ids", [])
    if not target_rfc_ids:
        return {
            "availability_status": "not_ingested",
            "availability_message": get_not_ingested_message(),
            "next_step": "answer_not_ingested",
        }

    missing_rfc_ids = await get_missing_rfc_ids(target_rfc_ids)
    if missing_rfc_ids:
        return {
            "availability_status": "not_ingested",
            "availability_message": get_not_ingested_message(),
            "next_step": "answer_not_ingested",
        }

    return {"availability_status": "ready", "next_step": "search"}


async def search(state: AgentState):
    """Search the knowledge base."""
    query = state.get("query")
    if not query:
        return {"next_step": "answer"}

    try:
        result = await search_rfc_knowledge(query, state.get("target_rfc_ids", []))
        return {"context": result, "next_step": "answer"}
    except Exception as e:
        return {"context": f"Search failed: {e}", "next_step": "answer"}


def answer_not_ingested(state: AgentState):
    """Return a fixed response for unsupported or not-preloaded protocols."""
    message = state.get("availability_message") or get_not_ingested_message()
    return {"messages": [AIMessage(content=message)]}


def answer(state: AgentState):
    """Generate the final answer."""
    messages = state["messages"]
    question = messages[-1].content
    context = state.get("context", "")

    system = """You are an expert network engineer. Answer the user's question based on the provided context.
    Prefer facts that are explicitly supported by the provided context.
    If the context is insufficient, say that the current preloaded RFC context does not contain enough information.
    """

    prompt = ChatPromptTemplate.from_messages([
        ("system", system),
        ("human", "Context:\n{context}\n\nQuestion: {question}")
    ])

    chain = prompt | llm | StrOutputParser()

    response = chain.invoke({"context": context, "question": question})
    return {"messages": [AIMessage(content=response)]}

# Graph Construction
workflow = StateGraph(AgentState)

workflow.add_node("analyze", analyze)
workflow.add_node("check_availability", check_availability)
workflow.add_node("search", search)
workflow.add_node("answer_not_ingested", answer_not_ingested)
workflow.add_node("answer", answer)

workflow.set_entry_point("analyze")

def route_after_analyze(state: AgentState):
    return state["next_step"]

def route_after_check_availability(state: AgentState):
    return state["next_step"]

def route_after_search(state: AgentState):
    return state["next_step"]

workflow.add_conditional_edges(
    "analyze",
    route_after_analyze,
    {
        "check_availability": "check_availability",
        "answer_not_ingested": "answer_not_ingested",
    }
)

workflow.add_conditional_edges(
    "check_availability",
    route_after_check_availability,
    {
        "search": "search",
        "answer_not_ingested": "answer_not_ingested",
    }
)

workflow.add_conditional_edges(
    "search",
    route_after_search,
    {
        "answer": "answer"
    }
)

workflow.add_edge("answer", END)
workflow.add_edge("answer_not_ingested", END)

rfc_agent = workflow.compile()
