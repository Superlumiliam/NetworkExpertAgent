from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
import src.config.settings as cfg
from src.core.answer_format import coerce_structured_answer

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

Return ONLY a JSON object with exactly these keys:
- "结论"
- "出处定位"
- "协议原文节选"

For general questions not based on RFC evidence:
- Put the direct answer in "结论".
- Set "出处定位" to "N/A".
- Set "协议原文节选" to "N/A".
    """
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", system),
        ("human", "{question}")
    ])
    
    chain = prompt | llm | StrOutputParser()

    response = chain.invoke({"question": question})
    return coerce_structured_answer(
        response,
        default_source="N/A",
        default_quote="N/A",
    )
