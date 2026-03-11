import asyncio
import os
import sys
import json
import time

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from os import getenv
import config.settings as cfg
try:
    from langsmith.run_trees import traceable
except Exception:
    traceable = None

from rfc_optimizer import RFCOptimizer

# Load environment variables from .env file
load_dotenv()

async def call_mcp_tool_traced(session, function_name, function_args):
    result = await session.call_tool(function_name, function_args)
    return result
if traceable:
    call_mcp_tool_traced = traceable(name="mcp_tool_call")(call_mcp_tool_traced)

async def run_agent():
    # check api key
    api_key = getenv("OPENROUTER_API_KEY")
    if not api_key:
        print("Please set OPENROUTER_API_KEY environment variable.", file=sys.stderr)
        return
    ls_enabled = os.getenv("LANGCHAIN_TRACING_V2", "").lower() in ("1", "true", "yes")
    if ls_enabled:
        print("LangSmith tracing is enabled.", file=sys.stderr)

    # Initialize the model with OpenRouter's base URL
    model = init_chat_model(
        model=cfg.DEFAULT_MODEL,
        model_provider=cfg.MODEL_PROVIDER,
        base_url=cfg.OPENROUTER_BASE_URL,
        api_key=api_key,

    )
    
    # Initialize Optimizer
    optimizer = RFCOptimizer(model)

    # Define the server parameters
    command = sys.executable
    server_params = StdioServerParameters(
        command=command,
        args=[cfg.SERVER_SCRIPT],
        env=os.environ.copy() # Pass current env
    )

    print("Connecting to MCP Server...", file=sys.stderr)
    
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            # Initialize connection
            await session.initialize()
            
            # List available tools
            tools_response = await session.list_tools()
            tools = tools_response.tools
            print(f"Connected. Available tools: {[t.name for t in tools]}", file=sys.stderr)

            # Convert MCP tools to OpenAI format and bind to model
            formatted_tools = []
            for tool in tools:
                formatted_tools.append({
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.inputSchema
                    }
                })
            
            model_with_tools = model.bind_tools(formatted_tools)
            print(f"Bound {len(formatted_tools)} tools to model.", file=sys.stderr)

            # Chat Loop
            messages = [
                {"role": "system", 
                 "content": "You are an RFC Expert Agent. You help users understand network protocols. You have access to a knowledge base of RFCs. Use the available tools to download new RFCs if needed, or search existing ones to answer questions. Always answer based on the retrieved context."
                }
            ]
            
            print(f"\nRFC Expert Agent is ready! (Using OpenRouter model: {cfg.DEFAULT_MODEL})", file=sys.stderr)
            print("Type 'quit' to exit.", file=sys.stderr)
            
            while True:
                user_input = input("\nUser: ")
                if user_input.lower() in ["quit", "exit"]:
                    break
                
                messages.append({"role": "user", "content": user_input})
                
                # Pre-RAG Optimization: Analyze and download missing RFCs
                print("\n[Optimizer] Analyzing user query...", file=sys.stderr)
                try:
                    processed_rfcs = await optimizer.process_query_pre_rag(user_input, session)
                    if processed_rfcs:
                        print(f"[Optimizer] Added relevant RFCs: {processed_rfcs}", file=sys.stderr)
                except Exception as e:
                    print(f"[Optimizer] Error in pre-processing: {e}", file=sys.stderr)
                
                start_time = time.perf_counter()
                # Loop for Agent execution (Think-Act-Observe loop)
                while True:
                    try:
                        runnable = model_with_tools.with_config({"run_name": "AgentStep", "tags": ["RFCexpert", "agent", "mcp", f"model:{cfg.DEFAULT_MODEL}"]})
                        response = runnable.invoke(messages)
                        
                        # Handle tool calls
                        if response.tool_calls:
                            messages.append(response)
                            if response.content:
                                print(f"Agent thought: {response.content}", file=sys.stderr)
                            
                            print(f"(Agent is calling tools: {[tc['name'] for tc in response.tool_calls]}...)", file=sys.stderr)
                            
                            for tool_call in response.tool_calls:
                                function_name = tool_call['name']
                                function_args = tool_call['args']
                                
                                result = await call_mcp_tool_traced(session, function_name, function_args)
                                
                                # MCP result content is a list of Content objects (TextContent usually)
                                tool_output = ""
                                if result.content:
                                    for content in result.content:
                                        if content.type == "text":
                                            tool_output += content.text
                                
                                # Context pollution detection
                                if function_name == "search_rfc_knowledge":
                                    try:
                                        is_polluted = await optimizer.detect_context_pollution(user_input, tool_output)
                                        if is_polluted:
                                            print("[Optimizer] Context pollution detected! RAG results seem irrelevant.", file=sys.stderr)
                                            tool_output += "\n\n[System Warning: The retrieved context seems irrelevant. Please verify the protocol name and try downloading the RFC if missing.]"
                                            
                                            # Trigger RFC completion flow (re-attempt download if missed)
                                            processed_rfcs_retry = await optimizer.process_query_pre_rag(user_input, session)
                                            if processed_rfcs_retry:
                                                print(f"[Optimizer] Retry: Added relevant RFCs: {processed_rfcs_retry}", file=sys.stderr)
                                    except Exception as e:
                                        print(f"[Optimizer] Error in context pollution detection: {e}", file=sys.stderr)
                                
                                messages.append({
                                    "role": "tool",
                                    "tool_call_id": tool_call['id'],
                                    "content": tool_output
                                })
                            # Continue to next iteration to let LLM process tool outputs
                            continue
                        
                        else:
                            # Final answer
                            print(f"\nAgent: {response.content}", file=sys.stderr)
                            messages.append(response)
                            break
                            
                    except Exception as e:
                        print(f"\nError calling LLM: {e}", file=sys.stderr)
                        break

                end_time = time.perf_counter()
                print(f"Agent response time: {end_time - start_time:.4f} seconds", file=sys.stderr)


if __name__ == "__main__":
    try:
        asyncio.run(run_agent())
    except KeyboardInterrupt:
        print("\nGoodbye!", file=sys.stderr)
    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
