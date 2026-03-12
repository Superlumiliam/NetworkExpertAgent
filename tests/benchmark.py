import asyncio
import time
import re
import sys
import os
from typing import List, Dict

# Add project root to path
sys.path.append(os.getcwd())

from src.main import process_question
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
import src.config.settings as cfg

async def evaluate_answer(question: str, expected: str, actual: str) -> int:
    """
    Evaluate the answer using an LLM judge.
    Returns a score from 0 to 10.
    """
    llm = ChatOpenAI(
        base_url=cfg.OPENROUTER_BASE_URL,
        api_key=cfg.OPENROUTER_API_KEY,
        model=cfg.DEFAULT_MODEL,
        temperature=0
    )
    
    system = """You are an impartial judge. Evaluate the actual answer against the expected answer for the given question.
    Assign a score from 0 to 10 based on semantic accuracy and completeness.
    - 10: Perfect match in meaning and key details.
    - 0: Completely wrong or irrelevant.
    
    Return ONLY the integer score.
    """
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", system),
        ("human", "Question: {question}\nExpected: {expected}\nActual: {actual}")
    ])
    
    chain = prompt | llm | StrOutputParser()
    
    try:
        score_str = await chain.ainvoke({
            "question": question,
            "expected": expected,
            "actual": actual
        })
        return int(re.search(r'\d+', score_str).group())
    except Exception as e:
        print(f"Evaluation error: {e}")
        return 0

def parse_quiz(file_path: str) -> List[Dict[str, str]]:
    """Parse the quiz markdown file."""
    with open(file_path, 'r') as f:
        content = f.read()
    
    questions = []
    # Split by "### Question"
    parts = re.split(r'### Question \d+', content)
    for part in parts:
        if not part.strip():
            continue
            
        if "### Expected Answer" in part:
            q_part, a_part = part.split("### Expected Answer")
            questions.append({
                "question": q_part.strip(),
                "expected": a_part.strip()
            })
            
    return questions

async def run_benchmark():
    """Run the benchmark."""
    print("Starting Benchmark...")
    quiz_path = "tests/quiz.md"
    questions = parse_quiz(quiz_path)
    
    total_score = 0
    total_time = 0
    results = []
    
    for i, item in enumerate(questions):
        q = item['question']
        expected = item['expected']
        
        print(f"\nProcessing Q{i+1}: {q}")
        
        start_time = time.time()
        try:
            actual = await process_question(q)
        except Exception as e:
            actual = f"Error: {e}"
        end_time = time.time()
        
        duration = end_time - start_time
        total_time += duration
        
        score = await evaluate_answer(q, expected, actual)
        total_score += score
        
        print(f"Time: {duration:.2f}s | Score: {score}/10")
        print(f"Actual Answer: {actual[:100]}...")
        
        results.append({
            "question": q,
            "score": score,
            "time": duration
        })
        
    avg_score = total_score / len(questions) if questions else 0
    avg_time = total_time / len(questions) if questions else 0
    
    print("\n" + "="*50)
    print(f"Benchmark Complete")
    print(f"Average Score: {avg_score:.2f}/10")
    print(f"Average Time: {avg_time:.2f}s")
    print("="*50)

if __name__ == "__main__":
    asyncio.run(run_benchmark())
