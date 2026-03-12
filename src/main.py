import os
import sys
import asyncio
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Set LangSmith environment variables if enabled
import src.config.settings as cfg

if cfg.ENABLE_LANGSMITH_TRACING:
    # Environment variables are already set in settings.py
    print("LangSmith tracing enabled.", file=sys.stderr)
else:
    # Ensure it's disabled if not configured
    os.environ["LANGCHAIN_TRACING_V2"] = "false"
    print("LangSmith tracing disabled.", file=sys.stderr)

from src.core.router import route_question
from src.agents.rfc_agent import rfc_agent
from src.agents.general_agent import general_chat
from langchain_core.messages import HumanMessage

async def process_question(question: str):
    """
    Process the user's question through the appropriate agent.
    """
    # 1. Route the question
    print(f"Routing question: '{question}'", file=sys.stderr)
    agent_type = route_question(question)
    print(f"Routed to: {agent_type}", file=sys.stderr)
    
    if agent_type == "rfc_expert":
        # 2. Invoke RFC Expert Agent
        initial_state = {"messages": [HumanMessage(content=question)]}
        result = await rfc_agent.ainvoke(initial_state)
        messages = result.get("messages", [])
        if messages:
            return messages[-1].content
        return "Sorry, I couldn't generate an answer."
    else:
        # 3. Invoke General Agent
        return general_chat(question)

def main():
    """CLI Entry Point"""
    print("Network Expert Agent (Type 'exit' or 'quit' to stop)")
    print("-" * 50)
    
    while True:
        try:
            user_input = input("\nYou: ").strip()
            if user_input.lower() in ["exit", "quit"]:
                break
                
            if not user_input:
                continue
                
            response = asyncio.run(process_question(user_input))
            print(f"\nAgent: {response}")
            
        except KeyboardInterrupt:
            print("\nExiting...")
            break
        except EOFError:
            print("\nExiting (EOF)...")
            break
        except Exception as e:
            print(f"\nError: {e}", file=sys.stderr)

if __name__ == "__main__":
    main()
