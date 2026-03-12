from typing import TypedDict, Annotated, List, Optional
from langchain_core.messages import BaseMessage
import operator

class AgentState(TypedDict):
    """The state of the agent."""
    messages: Annotated[List[BaseMessage], operator.add]
    rfc_id: Optional[str]
    query: Optional[str]
    context: Optional[str]
    next_step: Optional[str]
