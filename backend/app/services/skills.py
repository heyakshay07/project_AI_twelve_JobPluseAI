import re

# canonical skill -> aliases (all matched case-insensitively with token boundaries)
SKILL_ALIASES: dict[str, list[str]] = {
    "python": [],
    "java": [],
    "javascript": ["js"],
    "typescript": ["ts"],
    "react": ["react.js", "reactjs"],
    "angular": [],
    "vue": ["vue.js", "vuejs"],
    "node.js": ["nodejs", "node js"],
    "django": [],
    "flask": [],
    "fastapi": [],
    "spring boot": ["springboot"],
    "sql": [],
    "postgresql": ["postgres"],
    "mysql": [],
    "mongodb": [],
    "redis": [],
    "docker": [],
    "kubernetes": ["k8s"],
    "aws": ["amazon web services"],
    "azure": [],
    "gcp": ["google cloud"],
    "terraform": [],
    "pytorch": [],
    "tensorflow": [],
    "scikit-learn": ["sklearn"],
    "pandas": [],
    "numpy": [],
    "langchain": [],
    "langgraph": [],
    "llm": ["llms", "large language model", "large language models"],
    "rag": ["retrieval-augmented generation", "retrieval augmented generation"],
    "openai": [],
    "anthropic": [],
    "hugging face": ["huggingface"],
    "nlp": ["natural language processing"],
    "computer vision": [],
    "mlops": [],
    "generative ai": ["genai", "gen ai"],
    "vector database": ["vector databases", "pgvector", "pinecone", "weaviate", "qdrant", "chroma"],
    "c++": [],
    "c#": [],
    "golang": [],
    "rust": [],
    "graphql": [],
    "kafka": [],
    "spark": ["pyspark"],
}


def _compile(term: str) -> re.Pattern:
    return re.compile(rf"(?<![\w+#]){re.escape(term)}(?![\w+#])", re.I)


_PATTERNS: dict[str, list[re.Pattern]] = {
    skill: [_compile(t) for t in [skill, *aliases]] for skill, aliases in SKILL_ALIASES.items()
}


def extract_skills(text: str | None) -> list[str]:
    if not text:
        return []
    found = [s for s, pats in _PATTERNS.items() if any(p.search(text) for p in pats)]
    return sorted(found)


def skills_to_text(skills: list[str]) -> str:
    return "|" + "|".join(s.lower() for s in skills) + "|" if skills else ""
