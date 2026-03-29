from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser, JsonOutputParser
from langgraph.graph import StateGraph, END

from src.core.state import AgentState
import src.config.settings as cfg
from src.tools.rfc_tools import add_rfc, search_rfc_knowledge, check_rfc_status

# Initialize LLM
llm = ChatOpenAI(
    base_url=cfg.OPENROUTER_BASE_URL,
    api_key=cfg.OPENROUTER_API_KEY,
    model=cfg.DEFAULT_MODEL,
    temperature=0
)

# Load skills
try:
    with open("src/skills/skill.md", "r") as f:
        skills_doc = f.read()
except FileNotFoundError:
    skills_doc = "No skills loaded."

# Nodes
def analyze(state: AgentState):
    """Analyze the user's request and decide the next step."""
    messages = state['messages']
    last_message = messages[-1].content
    
    system = f"""You are an expert network engineer. Analyze the user's question.
    
    Available Skills:
    {skills_doc}
    
    Your task:
    1. Identify if the user is asking about a specific RFC (e.g., "What is in RFC 7540?").
    2. Extract the RFC number if present.
    3. If the user is asking about a specific protocol or technical detail but hasn't mentioned an RFC number, try to identify the most relevant standard RFC number for that topic (e.g., PIM -> 7761, OSPFv3 -> 5340, IGMPv3 -> 3376).
    4. Formulate a search query for the knowledge base. The query MUST be in English to better match RFC content (e.g., "Join/Prune Interval default value").
    
    Return a JSON object with:
    - "rfc_id": The RFC number (e.g., "7540") or null if not specific and cannot be inferred.
    - "query": A search query for the knowledge base.
    - "needs_rfc_content": boolean, true if we need to consult an RFC document.
    """
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", system),
        ("human", "{question}")
    ])
    
    chain = prompt | llm | JsonOutputParser()
    
    try:
        result = chain.invoke({"question": last_message})
        if result.get("rfc_id"):
            print(f"DEBUG: Identified/Inferred RFC ID: {result.get('rfc_id')}")
        
        return {
            "rfc_id": result.get("rfc_id"),
            "query": result.get("query"),
            "next_step": "check_local" if result.get("rfc_id") else "search"
        }
    except Exception as e:
        print(f"Analysis error: {e}")
        return {"next_step": "answer", "context": "Error analyzing request."}

async def check_local(state: AgentState):
    """Check if the RFC is already in the knowledge base."""
    rfc_id = state.get("rfc_id")
    if not rfc_id:
        return {"next_step": "search"}
        
    exists = await check_rfc_status.ainvoke(rfc_id)
    
    if exists:
        return {"next_step": "search"}
    else:
        return {"next_step": "download"}

async def download(state: AgentState):
    """Download the RFC."""
    rfc_id = state.get("rfc_id")
    if not rfc_id:
        return {"next_step": "search"}
        
    try:
        result = await add_rfc.ainvoke(rfc_id)
        return {"context": result, "next_step": "search"}
    except Exception as e:
        return {"context": f"Failed to download RFC {rfc_id}: {e}", "next_step": "answer"}

async def search(state: AgentState):
    """Search the knowledge base."""
    query = state.get("query")
    if not query:
        return {"next_step": "answer"}
        
    try:
        result = await search_rfc_knowledge.ainvoke(query)
        return {"context": result, "next_step": "answer"}
    except Exception as e:
        return {"context": f"Search failed: {e}", "next_step": "answer"}

from langchain_core.messages import AIMessage

def answer(state: AgentState):
    """Generate the final answer."""
    messages = state['messages']
    question = messages[-1].content
    context = state.get("context", "")
    
    system = """You are an expert network engineer. Answer the user's question based on the provided context.
    If the context doesn't contain the answer, say so, but try to be helpful based on your general knowledge if appropriate, 
    while clearly distinguishing between context-based facts and general knowledge.
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
workflow.add_node("check_local", check_local)
workflow.add_node("download", download)
workflow.add_node("search", search)
workflow.add_node("answer", answer)

workflow.set_entry_point("analyze")

def route_after_analyze(state: AgentState):
    return state["next_step"]

def route_after_check_local(state: AgentState):
    return state["next_step"]

def route_after_download(state: AgentState):
    return state["next_step"]

def route_after_search(state: AgentState):
    return state["next_step"]

workflow.add_conditional_edges(
    "analyze",
    route_after_analyze,
    {
        "check_local": "check_local",
        "search": "search",
        "answer": "answer"
    }
)

workflow.add_conditional_edges(
    "check_local",
    route_after_check_local,
    {
        "search": "search",
        "download": "download"
    }
)

workflow.add_conditional_edges(
    "download",
    route_after_download,
    {
        "search": "search",
        "answer": "answer"
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

rfc_agent = workflow.compile()
