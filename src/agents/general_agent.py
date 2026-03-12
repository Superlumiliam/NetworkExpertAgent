from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
import src.config.settings as cfg

llm = ChatOpenAI(
    base_url=cfg.OPENROUTER_BASE_URL,
    api_key=cfg.OPENROUTER_API_KEY,
    model=cfg.DEFAULT_MODEL,
    temperature=0.7
)

def general_chat(question: str) -> str:
    """
    Handle general questions using the LLM directly.
    """
    system = """You are a helpful AI assistant. You can help with general questions, greetings, and casual conversation.
    If the user asks about technical networking details or RFCs, suggest they ask specifically about those topics so the expert agent can help.
    """
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", system),
        ("human", "{question}")
    ])
    
    chain = prompt | llm | StrOutputParser()
    
    return chain.invoke({"question": question})
