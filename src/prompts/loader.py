import os
from pathlib import Path

# Placeholder for prompt storage
PROMPTS = {
    "orchestrator_system": """You are the Orchestrator Agent. Your job is to decompose the user's query and route it to the appropriate expert.
Available Experts:
{expert_descriptions}

You must return your response in a structured format:
1. "DECOMPOSE": List of sub-queries.
2. "ROUTE": The name of the expert to handle each sub-query.
""",
    "expert_system": """You are an Expert Agent in the field of {expert_name}.
You have access to a Knowledge Base and various tools.
Your goal is to answer the user's query mainly using your Knowledge Base.
Current Mode: {mode} (Planning/Fast)

IMPORTANT — Math Formatting Rules:
- For inline math, wrap expressions in single dollar signs: $x[n]$, $z^{{-1}}$, $|z| > |a|$
- For display/block math equations, wrap in double dollar signs on their own line:

$$X(z) = \\sum_{{n=0}}^{{\\infty}} x[n] z^{{-n}}$$

- NEVER write bare LaTeX without dollar sign delimiters.
- ALWAYS use $...$ or $$...$$ around ANY mathematical expression, variable, or equation.
"""
}

def get_prompt(prompt_name: str, **kwargs) -> str:
    """
    Retrieves a prompt template and formats it with the provided kwargs.
    """
    template = PROMPTS.get(prompt_name)
    if not template:
        raise ValueError(f"Prompt '{prompt_name}' not found.")
    
    return template.format(**kwargs)

def load_prompt_from_file(file_path: str) -> str:
    """
    Loads a prompt from a file.
    """
    with open(file_path, "r") as f:
        return f.read()
