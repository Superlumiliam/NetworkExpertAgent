
import asyncio
import sys
from typing import List, Dict, Any
from langchain.chat_models import init_chat_model
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field
import config.settings as cfg
from mcp import ClientSession

try:
    from langsmith.run_trees import traceable
except ImportError:
    def traceable(*args, **kwargs):
        def decorator(func):
            return func
        return decorator

class RFCOptimizer:
    def __init__(self, model):
        self.model = model
        self.rfc_mapping = self._load_rfc_mapping()
        
    def _load_rfc_mapping(self) -> Dict[str, List[str]]:
        # This is a simplified decision tree/mapping for demonstration
        # In a real system, this would be a more comprehensive database or logic
        return {
            "http/2": ["7540"],
            "http/3": ["9114"],
            "quic": ["9000"],
            "tls 1.3": ["8446"],
            "oauth 2.0": ["6749"],
            "jwt": ["7519"],
            "websocket": ["6455"],
            "mqtt": ["5048"], # MQTT v5.0
            "coap": ["7252"],
            "dns": ["1035", "1034"],
            "smtp": ["5321"],
            "imap": ["3501"],
            "pop3": ["1939"],
            "dhcp": ["2131"],
            "tcp": ["793"], # Original TCP
            "udp": ["768"],
            "ip": ["791"],
            "ipv6": ["8200"],
        }

    @traceable(name="extract_keywords")
    async def extract_keywords(self, query: str) -> List[str]:
        """
        Extract protocol/standard related entities from the user query.
        """
        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are an expert in network protocols. Extract key protocol names, standards, or technical terms from the user's query that likely have associated RFCs. Return a JSON object with a key 'keywords' containing a list of strings."),
            ("user", "{query}")
        ])
        
        chain = prompt | self.model | JsonOutputParser()
        
        try:
            result = await chain.ainvoke({"query": query})
            return result.get("keywords", [])
        except Exception as e:
            print(f"Error extracting keywords: {e}", file=sys.stderr)
            return []

    @traceable(name="identify_relevant_rfcs")
    def identify_relevant_rfcs(self, keywords: List[str]) -> List[str]:
        """
        Match keywords to RFCs using the priority decision tree (mapping).
        """
        relevant_rfcs = set()
        for keyword in keywords:
            keyword_lower = keyword.lower()
            # Direct match
            if keyword_lower in self.rfc_mapping:
                relevant_rfcs.update(self.rfc_mapping[keyword_lower])
            
            # Partial match search (simple version of decision tree logic)
            else:
                for key, rfcs in self.rfc_mapping.items():
                    if key in keyword_lower or keyword_lower in key:
                        relevant_rfcs.update(rfcs)
        
        # Sort by some priority if needed, here just by ID for stability
        return sorted(list(relevant_rfcs))

    @traceable(name="detect_context_pollution")
    async def detect_context_pollution(self, query: str, context: str) -> bool:
        """
        Check if the RAG retrieved context is relevant to the user's query.
        Returns True if pollution is detected (irrelevant context), False otherwise.
        """
        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are a quality assurance assistant. Determine if the provided context contains information relevant to the user's query about network protocols. Return JSON with 'is_relevant' boolean."),
            ("user", "Query: {query}\n\nContext: {context}")
        ])
        
        chain = prompt | self.model | JsonOutputParser()
        
        try:
            result = await chain.ainvoke({"query": query, "context": context})
            return not result.get("is_relevant", False)
        except Exception as e:
            print(f"Error detecting pollution: {e}", file=sys.stderr)
            return False

    @traceable(name="process_query_pre_rag")
    async def process_query_pre_rag(self, query: str, session: ClientSession) -> List[str]:
        """
        Execute the pre-RAG optimization flow:
        1. Extract Keywords
        2. Identify RFCs
        3. Download missing RFCs
        Returns the list of RFCs processed.
        """
        keywords = await self.extract_keywords(query)
        if not keywords:
            return []
            
        target_rfcs = self.identify_relevant_rfcs(keywords)
        
        processed_rfcs = []
        for rfc_id in target_rfcs:
            print(f"[Optimizer] Identified relevant RFC: {rfc_id}", file=sys.stderr)
            try:
                # Call add_rfc tool
                # We don't check if it exists because add_rfc is idempotent or handles it
                # But to be safe and efficient, the server should handle checking.
                # Assuming add_rfc handles duplicates gracefully.
                await session.call_tool("add_rfc", {"rfc_id": rfc_id})
                processed_rfcs.append(rfc_id)
            except Exception as e:
                print(f"[Optimizer] Failed to download RFC {rfc_id}: {e}", file=sys.stderr)
                
        return processed_rfcs
