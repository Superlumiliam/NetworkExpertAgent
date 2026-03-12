from typing import Literal
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import StrOutputParser
import src.config.settings as cfg

def route_question(question: str) -> Literal["rfc_expert", "general_agent"]:
    """
    Route the user's question to the appropriate agent.
    """
    llm = ChatOpenAI(
        base_url=cfg.OPENROUTER_BASE_URL,
        api_key=cfg.OPENROUTER_API_KEY,
        model=cfg.DEFAULT_MODEL,
        temperature=0
    )
    
    system = """You are an expert at routing user questions to the appropriate assistant.
    
    The available assistants are:
    1. "rfc_expert": Use this for questions about Network Protocols, RFCs (Request for Comments), IETF standards, packet structures, headers, or specific networking technical details.
    2. "general_agent": Use this for greetings, general questions, casual chat, or questions unrelated to computer networking protocols.
    
    Return only the name of the assistant: "rfc_expert" or "general_agent".
    """
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", system),
        ("human", "{question}")
    ])
    
    chain = prompt | llm | StrOutputParser()
    
    try:
        route = chain.invoke({"question": question}).strip().lower()
        if "rfc" in route or "expert" in route:
            return "rfc_expert"
        return "general_agent"
    except Exception as e:
        print(f"Routing error: {e}")
        # Default to general agent on error
        return "general_agent"
