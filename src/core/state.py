from typing import TypedDict, Annotated, List
from langchain_core.messages import BaseMessage
import operator

class AgentState(TypedDict, total=False):
    """The state of the agent."""
    messages: Annotated[List[BaseMessage], operator.add]
    query: str
    context: str
    target_rfc_ids: List[str]
    availability_status: str
    availability_message: str
    next_step: str
