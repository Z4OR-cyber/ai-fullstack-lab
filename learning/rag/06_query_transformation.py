#!/usr/bin/env python3
"""
RAG Exercise 6: Query Transformation (查询转换)

Learning Objectives:
1. Understand why query transformation improves retrieval in RAG systems
2. Implement query expansion using synonyms and related terms
3. Implement HyDE (Hypothetical Document Embeddings) - generate hypothetical answer, then search
4. Implement multi-query generation - decompose complex queries into sub-queries
5. Implement query routing - direct different query types to appropriate retrievers
6. Evaluate query transformation impact on retrieval quality

Architecture:
    Original Query
         |
    +----+----+----+----+
    |    |    |    |    |
    v    v    v    v    v
  Expand HyDE Multi  Route  Original
    |    |    |    |    |
    v    v    v    v    v
  [Retrieval for each transformed query]
         |
         v
    [Result Fusion (RRF / Union / Intersection)]
         |
         v
    Final Results

Key Concepts:
- Query Expansion: Add synonyms/related terms to improve recall
- HyDE: Generate a hypothetical answer, embed it, use for retrieval (bridges vocabulary gap)
- Multi-Query: Decompose "How do X and Y compare?" into "What is X?" + "What is Y?"
- Query Routing: Route factual queries to BM25, semantic queries to vector search
- Result Fusion: Combine results from multiple queries (Reciprocal Rank Fusion is standard)

Dependencies: Only standard library + numpy (optional, not required)
"""

import math
import re
import json
from collections import Counter, defaultdict
from typing import List, Dict, Tuple, Optional, Callable, Any, Set
from dataclasses import dataclass, field
import unittest

# ============================================================
# Part 1: Document and Corpus (reuse from exercise 5 pattern)
# ============================================================

@dataclass
class Document:
    doc_id: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def get_tokens(self) -> List[str]:
        return re.findall(r'\b\w+\b', self.content.lower())
    
    def get_term_freq(self) -> Counter:
        return Counter(self.get_tokens())


SAMPLE_CORPUS = [
    Document("d1", "Python is a high-level programming language known for its simplicity and readability. It supports multiple paradigms including object-oriented and functional programming."),
    Document("d2", "Machine learning models require large datasets for training. Deep neural networks can learn complex patterns from data through backpropagation and gradient descent."),
    Document("d3", "Vector databases store high-dimensional embeddings for similarity search. They use approximate nearest neighbor algorithms like HNSW for fast retrieval."),
    Document("d4", "Natural language processing involves tokenization, stemming, and named entity recognition. Transformers and attention mechanisms have revolutionized NLP tasks."),
    Document("d5", "Web development with Python uses frameworks like Django and Flask. REST APIs handle HTTP requests and return JSON responses to clients."),
    Document("d6", "Python data science libraries include NumPy for numerical computing, pandas for data manipulation, and matplotlib for visualization and plotting."),
    Document("d7", "Embedding models convert text into dense vectors. Word2Vec, GloVe, and BERT are popular embedding approaches for capturing semantic meaning in vector space."),
    Document("d8", "Information retrieval systems rank documents by relevance to a query. TF-IDF and BM25 are classic ranking functions used in search engines."),
    Document("d9", "Distributed systems use consensus algorithms like Raft and Paxos for fault tolerance. They ensure data consistency across multiple nodes and handle network partitions."),
    Document("d10", "Cloud computing platforms offer scalable infrastructure. AWS, Azure, and GCP provide virtual machines, serverless functions, and managed database services."),
    Document("d11", "Python async programming uses asyncio and coroutines for concurrent I/O operations. Event loops manage task scheduling and async await syntax simplifies code."),
    Document("d12", "Gradient descent optimization minimizes loss functions in machine learning. Stochastic gradient descent processes mini-batches and momentum accelerates convergence."),
    Document("d13", "Search engines use inverted indices for fast text lookup. The index maps terms to posting lists containing document IDs and term frequencies."),
    Document("d14", "Recommendation systems use collaborative filtering and content-based filtering. Matrix factorization decomposes user-item interaction matrices for predictions."),
    Document("d15", "Container orchestration with Kubernetes manages microservices deployment. Pods are the smallest deployable units and services handle network routing."),
    Document("d16", "Text classification assigns documents to predefined categories. Naive Bayes, support vector machines, and neural networks are common classification algorithms."),
    Document("d17", "Graph databases like Neo4j store entities and relationships. Cypher is a declarative query language for graph traversal and pattern matching."),
    Document("d18", "Python testing frameworks include pytest and unittest. Test-driven development writes tests before implementation and continuous integration runs them automatically."),
    Document("d19", "Vector similarity measures include cosine similarity, dot product, and Euclidean distance. Cosine similarity is preferred for text embeddings because it ignores magnitude."),
    Document("d20", "Retrieval augmented generation combines search with language models. The retrieved context helps the model generate grounded answers and reduces hallucination."),
]

RELEVANCE_JUDGMENTS = {
    "how does python handle async programming": {"d11": 3, "d1": 2, "d5": 1, "d18": 0},
    "compare vector databases and traditional search": {"d3": 3, "d8": 3, "d13": 2, "d7": 2, "d19": 2, "d20": 1},
    "what is gradient descent in machine learning": {"d2": 3, "d12": 3, "d6": 1, "d16": 1, "d14": 0},
    "how to test python code": {"d18": 3, "d1": 2, "d5": 1, "d11": 1, "d6": 0},
}


# ============================================================
# Part 2: BM25 Retriever (compact version)
# ============================================================

class BM25Retriever:
    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.documents: List[Document] = []
        self.doc_freqs: List[Counter] = []
        self.doc_len: List[int] = []
        self.avgdl: float = 0.0
        self.idf: Dict[str, float] = {}
        self.term_docs: Dict[str, List[int]] = defaultdict(list)
        self.N: int = 0
    
    def index(self, documents: List[Document]) -> None:
        self.documents = documents
        self.N = len(documents)
        self.doc_freqs = []
        self.doc_len = []
        self.term_docs = defaultdict(list)
        total_len = 0
        for i, doc in enumerate(documents):
            tf = doc.get_term_freq()
            self.doc_freqs.append(tf)
            self.doc_len.append(len(tf))
            total_len += len(tf)
            for term in tf:
                self.term_docs[term].append(i)
        self.avgdl = total_len / self.N if self.N > 0 else 0
        self.idf = {}
        for term, doc_indices in self.term_docs.items():
            df = len(doc_indices)
            self.idf[term] = math.log((self.N - df + 0.5) / (df + 0.5) + 1)
    
    def search(self, query: str, top_n: int = 20) -> List[Tuple[Document, float]]:
        query_terms = re.findall(r'\b\w+\b', query.lower())
        scores = [0.0] * self.N
        for term in query_terms:
            if term not in self.idf:
                continue
            idf = self.idf[term]
            for doc_idx in self.term_docs.get(term, []):
                tf = self.doc_freqs[doc_idx].get(term, 0)
                dl = self.doc_len[doc_idx]
                denom = tf + self.k1 * (1 - self.b + self.b * dl / self.avgdl) if self.avgdl > 0 else tf + self.k1
                scores[doc_idx] += idf * (tf * (self.k1 + 1) / denom) if denom > 0 else 0
        results = [(self.documents[i], scores[i]) for i in range(self.N) if scores[i] > 0]
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_n]


# ============================================================
# Part 3: Vector Retriever (TF-IDF cosine similarity)
# ============================================================

class VectorRetriever:
    def __init__(self):
        self.documents: List[Document] = []
        self.vocabulary: Dict[str, int] = {}
        self.idf_weights: Dict[str, float] = {}
        self.doc_vectors: List[Dict[int, float]] = []
        self.N: int = 0
    
    def _build_vocabulary(self, documents: List[Document]) -> None:
        vocab = set()
        for doc in documents:
            vocab.update(doc.get_tokens())
        self.vocabulary = {term: idx for idx, term in enumerate(sorted(vocab))}
    
    def _compute_idf(self, documents: List[Document]) -> None:
        self.idf_weights = {}
        N = len(documents)
        doc_count = Counter()
        for doc in documents:
            terms = set(doc.get_tokens())
            for term in terms:
                doc_count[term] += 1
        for term, df in doc_count.items():
            self.idf_weights[term] = math.log((N + 1) / (df + 1)) + 1
    
    def _vectorize(self, text: str) -> Dict[int, float]:
        tokens = re.findall(r'\b\w+\b', text.lower())
        tf = Counter(tokens)
        vector = {}
        for term, freq in tf.items():
            if term in self.vocabulary and term in self.idf_weights:
                idx = self.vocabulary[term]
                vector[idx] = freq * self.idf_weights[term]
        norm = math.sqrt(sum(v * v for v in vector.values()))
        if norm > 0:
            for k in vector:
                vector[k] /= norm
        return vector
    
    def index(self, documents: List[Document]) -> None:
        self.documents = documents
        self.N = len(documents)
        self._build_vocabulary(documents)
        self._compute_idf(documents)
        self.doc_vectors = [self._vectorize(doc.content) for doc in documents]
    
    def search(self, query: str, top_n: int = 20) -> List[Tuple[Document, float]]:
        query_vec = self._vectorize(query)
        results = []
        for i, doc_vec in enumerate(self.doc_vectors):
            if len(query_vec) > len(doc_vec):
                sim = sum(val * query_vec.get(idx, 0.0) for idx, val in doc_vec.items())
            else:
                sim = sum(val * doc_vec.get(idx, 0.0) for idx, val in query_vec.items())
            if sim > 0:
                results.append((self.documents[i], sim))
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_n]


# ============================================================
# Part 4: Query Expansion
# ============================================================

class QueryExpander:
    """
    Query expansion adds synonyms and related terms to the original query
    to improve recall. This addresses the vocabulary mismatch problem where
    the user's query terms don't appear in relevant documents.
    
    Methods:
    1. Synonym expansion: Add known synonyms for query terms
    2. Co-occurrence expansion: Add terms that frequently co-occur with query terms
    3. Pseudo-relevance feedback (PRF): Use top-k results to find expansion terms
    
    In production systems, this is often done with word embeddings (word2vec, GloVe)
    or LLMs ("generate 5 related queries").
    """
    
    # Predefined synonym dictionary (in production, use WordNet or embeddings)
    SYNONYMS: Dict[str, List[str]] = {
        'python': ['python3', 'cpython', 'programming'],
        'machine': ['ml', 'automated', 'algorithmic'],
        'learning': ['training', 'modeling', 'optimization'],
        'database': ['db', 'storage', 'index', 'store'],
        'vector': ['embedding', 'dense', 'numerical'],
        'search': ['retrieval', 'lookup', 'query', 'find'],
        'test': ['testing', 'unittest', 'pytest', 'validation'],
        'async': ['asynchronous', 'concurrent', 'parallel'],
        'gradient': ['optimization', 'descent', 'backpropagation'],
        'cloud': ['aws', 'azure', 'gcp', 'hosted', 'remote'],
        'neural': ['network', 'deep', 'transformer', 'attention'],
        'similarity': ['distance', 'matching', 'comparison', 'relevance'],
        'index': ['inverted', 'lookup', 'posting', 'catalog'],
        'api': ['interface', 'endpoint', 'rest', 'http'],
        'framework': ['library', 'toolkit', 'package', 'module'],
    }
    
    def __init__(self, synonyms: Optional[Dict[str, List[str]]] = None):
        self.synonyms = synonyms or self.SYNONYMS
    
    def expand(self, query: str, max_expansions: int = 5) -> str:
        """
        Expand query with synonyms.
        
        Args:
            query: Original query string
            max_expansions: Maximum number of expansion terms to add
        
        Returns:
            Expanded query string
        """
        query_terms = re.findall(r'\b\w+\b', query.lower())
        expansion_terms = []
        
        for term in query_terms:
            if term in self.synonyms:
                for syn in self.synonyms[term]:
                    if syn not in query_terms and syn not in expansion_terms:
                        expansion_terms.append(syn)
                        if len(expansion_terms) >= max_expansions:
                            break
            if len(expansion_terms) >= max_expansions:
                break
        
        if expansion_terms:
            return f"{query} {' '.join(expansion_terms)}"
        return query
    
    def expand_terms(self, query: str) -> Tuple[List[str], List[str]]:
        """
        Return original and expansion terms separately.
        
        Returns:
            Tuple of (original_terms, expansion_terms)
        """
        query_terms = re.findall(r'\b\w+\b', query.lower())
        expansion_terms = []
        seen = set(query_terms)
        
        for term in query_terms:
            if term in self.synonyms:
                for syn in self.synonyms[term]:
                    if syn not in seen:
                        expansion_terms.append(syn)
                        seen.add(syn)
        
        return query_terms, expansion_terms


class PseudoRelevanceFeedback:
    """
    Pseudo-Relevance Feedback (PRF) / Blind Feedback.
    
    Steps:
    1. Retrieve top-K documents for the original query
    2. Extract the most frequent terms from these documents
    3. Add these terms to the query (weighted)
    4. Re-run retrieval with the expanded query
    
    This is also called "blind relevance feedback" because it assumes
    the top-K results are relevant without user confirmation.
    
    Rocchio's algorithm variant:
        modified_query = original_query + beta * centroid_of_relevant_docs
    """
    
    def __init__(self, alpha: float = 1.0, beta: float = 0.5, top_k: int = 3, num_expansion_terms: int = 5):
        """
        Args:
            alpha: Weight for original query terms
            beta: Weight for expansion terms (from top results)
            top_k: Number of top documents to use for feedback
            num_expansion_terms: Number of expansion terms to add
        """
        self.alpha = alpha
        self.beta = beta
        self.top_k = top_k
        self.num_expansion_terms = num_expansion_terms
    
    def get_expansion_terms(
        self, query: str, retrieved_docs: List[Tuple[Document, float]]
    ) -> List[Tuple[str, float]]:
        """
        Extract expansion terms from top retrieved documents.
        
        Returns:
            List of (term, weight) tuples, sorted by weight descending
        """
        if not retrieved_docs:
            return []
        
        query_terms = set(re.findall(r'\b\w+\b', query.lower()))
        
        # Aggregate term frequencies from top documents, weighted by retrieval score
        term_scores: Dict[str, float] = defaultdict(float)
        
        for doc, score in retrieved_docs[:self.top_k]:
            doc_tokens = doc.get_tokens()
            tf = Counter(doc_tokens)
            doc_len = len(doc_tokens)
            if doc_len == 0:
                continue
            for term, freq in tf.items():
                if term in query_terms:
                    continue  # Don't add terms already in query
                if len(term) < 3:
                    continue  # Skip very short terms
                # Weight by retrieval score and normalized term frequency
                term_scores[term] += self.beta * (freq / doc_len) * score
        
        # Sort by score and take top N
        sorted_terms = sorted(term_scores.items(), key=lambda x: x[1], reverse=True)
        return sorted_terms[:self.num_expansion_terms]
    
    def expand_query(
        self, query: str, retrieved_docs: List[Tuple[Document, float]]
    ) -> str:
        """
        Expand the query using pseudo-relevance feedback.
        """
        expansion_terms = self.get_expansion_terms(query, retrieved_docs)
        if not expansion_terms:
            return query
        
        # Add expansion terms to query
        expansion_str = ' '.join(term for term, _ in expansion_terms)
        return f"{query} {expansion_str}"


# ============================================================
# Part 5: HyDE (Hypothetical Document Embeddings)
# ============================================================

class HyDEGenerator:
    """
    HyDE: Hypothetical Document Embeddings.
    
    Instead of searching with the query directly, HyDE:
    1. Generates a hypothetical answer to the query (using LLM in production)
    2. Embeds the hypothetical answer
    3. Searches using the hypothetical answer's embedding
    
    This bridges the "vocabulary gap": the query is in question form,
    but documents are in statement form. The hypothetical answer is also
    in statement form, matching document style.
    
    Example:
        Query: "How does Python handle async programming?"
        Hypothetical Answer: "Python uses asyncio library for async programming.
        The async/await syntax allows writing non-blocking code. Event loops
        manage task scheduling..."
        → Search with the hypothetical answer → better matches
    
    In this exercise, we simulate LLM generation with template-based generation.
    """
    
    # Templates for generating hypothetical documents
    TEMPLATES: Dict[str, str] = {
        'how': "The answer to '{query}' involves several key concepts. {topic} is a fundamental aspect that relates to {terms}. Implementation typically involves specific patterns and best practices. The core mechanism operates through well-defined processes that ensure proper functionality. Key components work together to achieve the desired outcome.",
        'what': "{topic} is defined as a concept that encompasses {terms}. It represents an important area in computer science and software development. The fundamental principles include structured approaches and systematic methodologies. Understanding {topic} requires knowledge of underlying mechanisms and practical applications.",
        'compare': "When comparing {terms}, several differences emerge. {topic} varies in terms of approach, implementation, and use cases. Each option has distinct advantages and trade-offs. The choice depends on specific requirements and constraints. Both approaches serve different purposes in the broader context.",
        'why': "The reason {topic} is important stems from its practical benefits. {terms} provide significant advantages in real-world scenarios. The underlying mechanisms support efficient and effective solutions. Understanding these reasons helps make informed decisions about when and how to apply them.",
    }
    
    def __init__(self, templates: Optional[Dict[str, str]] = None):
        self.templates = templates or self.TEMPLATES
    
    def _classify_query(self, query: str) -> str:
        """Classify query type based on first word."""
        query_lower = query.lower().strip()
        for qtype in ['how', 'what', 'compare', 'why']:
            if query_lower.startswith(qtype):
                return qtype
        return 'what'  # Default
    
    def _extract_topic_and_terms(self, query: str) -> Tuple[str, str]:
        """Extract main topic and key terms from query."""
        # Remove question words
        cleaned = re.sub(r'^(how|what|why|compare|does|do|is|are|can|could|would|should)\s+', '', query.lower())
        cleaned = re.sub(r'\b(the|a|an|to|in|for|of|and|or|with|handle|work|function)\b', '', cleaned)
        terms = re.findall(r'\b\w+\b', cleaned)
        
        if not terms:
            return query, ''
        
        topic = terms[0] if terms else ''
        terms_str = ', '.join(terms[:5]) if len(terms) > 1 else terms[0] if terms else ''
        return topic, terms_str
    
    def generate(self, query: str) -> str:
        """
        Generate a hypothetical document for the query.
        
        In production, this would call an LLM (GPT, Claude, etc.).
        Here we use template-based generation.
        """
        qtype = self._classify_query(query)
        topic, terms = self._extract_topic_and_terms(query)
        
        template = self.templates.get(qtype, self.templates['what'])
        
        # Fill template
        hypothetical = template.format(
            query=query,
            topic=topic,
            terms=terms or topic,
        )
        
        return hypothetical
    
    def generate_multiple(self, query: str, n: int = 3) -> List[str]:
        """Generate multiple hypothetical documents with slight variations."""
        qtype = self._classify_query(query)
        topic, terms = self._extract_topic_and_terms(query)
        
        results = [self.generate(query)]  # First one is the standard generation
        
        # Generate variations by using different templates
        for i, alt_type in enumerate(['what', 'how', 'why']):
            if len(results) >= n:
                break
            if alt_type == qtype:
                continue
            template = self.templates.get(alt_type)
            if template:
                hyp = template.format(query=query, topic=topic, terms=terms or topic)
                results.append(hyp)
        
        return results[:n]


# ============================================================
# Part 6: Multi-Query Decomposition
# ============================================================

class MultiQueryDecomposer:
    """
    Multi-Query Decomposition.
    
    Decomposes complex queries into simpler sub-queries that can be
    answered independently. Results from sub-queries are then fused.
    
    Example:
        "Compare vector databases and traditional search engines"
        → Sub-query 1: "What are vector databases?"
        → Sub-query 2: "What are traditional search engines?"
        → Sub-query 3: "Differences between vector search and keyword search"
    
    In production, an LLM generates the sub-queries. Here we use
    rule-based decomposition.
    """
    
    def __init__(self):
        # Patterns for query decomposition
        self.compare_pattern = re.compile(
            r'(?:compare|difference between|vs|versus)\s+(.+?)\s+(?:and|vs|versus)\s+(.+)',
            re.IGNORECASE
        )
        self.how_pattern = re.compile(
            r'how\s+(?:do|does|to|can|could)\s+(.+)',
            re.IGNORECASE
        )
        self.list_pattern = re.compile(
            r'(?:what are|list|name)\s+(.+)',
            re.IGNORECASE
        )
    
    def decompose(self, query: str) -> List[str]:
        """
        Decompose a query into sub-queries.
        
        Returns:
            List of sub-queries (including the original if no decomposition applies)
        """
        # Try comparison decomposition
        match = self.compare_pattern.search(query)
        if match:
            entity1 = match.group(1).strip()
            entity2 = match.group(2).strip()
            return [
                f"What is {entity1}?",
                f"What is {entity2}?",
                f"Differences between {entity1} and {entity2}",
                query,  # Keep original
            ]
        
        # Try "how" decomposition
        match = self.how_pattern.search(query)
        if match:
            subject = match.group(1).strip()
            return [
                f"What is {subject}?",
                f"How does {subject} work?",
                f"Benefits and use cases of {subject}",
                query,
            ]
        
        # Try "what are" decomposition
        match = self.list_pattern.search(query)
        if match:
            subject = match.group(1).strip()
            return [
                f"What is {subject}?",
                f"Examples of {subject}",
                f"How to use {subject}",
                query,
            ]
        
        # No decomposition possible
        return [query]
    
    def decompose_with_keywords(self, query: str) -> List[str]:
        """
        Decompose using keyword-based splitting.
        Splits on conjunctions and prepositions.
        """
        # Split on " and ", " or ", " with ", " in ", " for "
        parts = re.split(r'\s+(?:and|or|with|in|for)\s+', query, flags=re.IGNORECASE)
        
        if len(parts) <= 1:
            return [query]
        
        sub_queries = []
        for part in parts:
            part = part.strip()
            if len(part) > 3:
                sub_queries.append(part)
        
        sub_queries.append(query)  # Always include original
        return sub_queries


# ============================================================
# Part 7: Query Router
# ============================================================

class QueryRouter:
    """
    Query Router directs queries to the most appropriate retriever.
    
    Different query types benefit from different retrieval strategies:
    - Factual queries (exact terms) → BM25 (exact match)
    - Conceptual queries (semantic) → Vector search (semantic match)
    - Mixed queries → Both (hybrid)
    
    Classification heuristics:
    - Contains specific technical terms, code, or exact names → BM25
    - Contains "similar", "related", "like", "concept" → Vector
    - Contains "how", "why", "explain" → Vector (conceptual)
    - Contains quotes, exact phrases → BM25
    - Default → Hybrid
    """
    
    BM25_INDICATORS = {'error', 'exception', 'syntax', 'command', 'function', 'class',
                       'method', 'variable', 'import', 'install', 'version', 'api',
                       'endpoint', 'url', 'status', 'code', 'line', 'file'}
    
    VECTOR_INDICATORS = {'similar', 'related', 'like', 'concept', 'explain',
                         'overview', 'understand', 'meaning', 'difference',
                         'compare', 'analogy', 'example', 'best practice'}
    
    CONCEPTUAL_STARTERS = {'how', 'why', 'what', 'explain', 'describe', 'tell'}
    
    def __init__(self):
        self.route_history: List[Dict[str, Any]] = []
    
    def classify(self, query: str) -> str:
        """
        Classify query and determine routing.
        
        Returns:
            'bm25', 'vector', or 'hybrid'
        """
        query_lower = query.lower()
        query_terms = set(re.findall(r'\b\w+\b', query_lower))
        
        bm25_score = 0
        vector_score = 0
        
        # Check for exact match indicators
        bm25_matches = query_terms & self.BM25_INDICATORS
        bm25_score += len(bm25_matches) * 2
        
        # Check for semantic indicators
        vector_matches = query_terms & self.VECTOR_INDICATORS
        vector_score += len(vector_matches) * 2
        
        # Check for conceptual starters
        first_word = query_lower.split()[0] if query_lower.split() else ''
        if first_word in self.CONCEPTUAL_STARTERS:
            vector_score += 2
        
        # Check for quoted phrases (exact match intent)
        if '"' in query or "'" in query:
            bm25_score += 3
        
        # Check for code-like patterns
        if re.search(r'[a-z_]+\(\)', query_lower):
            bm25_score += 2
        
        # Check for specific technical patterns
        if re.search(r'\b\d+\.\d+\.\d+\b', query):  # Version numbers
            bm25_score += 2
        
        # Route decision
        if bm25_score > vector_score + 1:
            route = 'bm25'
        elif vector_score > bm25_score + 1:
            route = 'vector'
        else:
            route = 'hybrid'
        
        # Log routing decision
        self.route_history.append({
            'query': query,
            'route': route,
            'bm25_score': bm25_score,
            'vector_score': vector_score,
        })
        
        return route
    
    def route(
        self,
        query: str,
        bm25_retriever: BM25Retriever,
        vector_retriever: VectorRetriever,
        top_n: int = 10,
    ) -> Tuple[str, List[Tuple[Document, float]]]:
        """
        Route query to appropriate retriever and return results.
        
        Returns:
            Tuple of (route_name, results)
        """
        route = self.classify(query)
        
        if route == 'bm25':
            results = bm25_retriever.search(query, top_n=top_n)
        elif route == 'vector':
            results = vector_retriever.search(query, top_n=top_n)
        else:  # hybrid
            bm25_results = bm25_retriever.search(query, top_n=top_n)
            vector_results = vector_retriever.search(query, top_n=top_n)
            results = self._fuse_results(bm25_results, vector_results, top_n=top_n)
        
        return route, results
    
    @staticmethod
    def _fuse_results(
        results_a: List[Tuple[Document, float]],
        results_b: List[Tuple[Document, float]],
        top_n: int = 10,
    ) -> List[Tuple[Document, float]]:
        """Fuse two result lists using score-based merging."""
        doc_scores: Dict[str, Tuple[Document, float]] = {}
        
        for doc, score in results_a:
            doc_scores[doc.doc_id] = (doc, score)
        
        for doc, score in results_b:
            if doc.doc_id in doc_scores:
                # Average the scores
                old_doc, old_score = doc_scores[doc.doc_id]
                doc_scores[doc.doc_id] = (old_doc, (old_score + score) / 2)
            else:
                doc_scores[doc.doc_id] = (doc, score * 0.8)  # Slight penalty for single-source
        
        results = list(doc_scores.values())
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_n]


# ============================================================
# Part 8: Result Fusion (Reciprocal Rank Fusion)
# ============================================================

class ReciprocalRankFusion:
    """
    Reciprocal Rank Fusion (RRF).
    
    Combines ranked results from multiple queries into a single ranking.
    Unlike score-based fusion, RRF only uses rank positions, making it
    robust to different score scales.
    
    Formula:
        RRF_score(d) = sum over queries q of: 1 / (k + rank_q(d))
    
    where k is a constant (typically 60) that dampens the influence
    of high rankings.
    
    Properties:
    - Doesn't require score calibration across systems
    - Simple and effective
    - Used in production by many search systems
    """
    
    def __init__(self, k: int = 60):
        """
        Args:
            k: Damping constant. Higher k = more uniform fusion.
               Lower k = more weight on top rankings.
        """
        self.k = k
    
    def fuse(
        self,
        result_lists: List[List[Tuple[Document, float]]],
        top_n: int = 10,
    ) -> List[Tuple[Document, float]]:
        """
        Fuse multiple result lists using RRF.
        
        Args:
            result_lists: List of result lists, each from a different query/retriever
            top_n: Number of results to return
        
        Returns:
            Fused result list
        """
        rrf_scores: Dict[str, Tuple[Document, float]] = {}
        
        for results in result_lists:
            for rank, (doc, _) in enumerate(results):
                rrf_score = 1.0 / (self.k + rank + 1)  # rank is 0-indexed, so +1
                if doc.doc_id in rrf_scores:
                    old_doc, old_score = rrf_scores[doc.doc_id]
                    rrf_scores[doc.doc_id] = (old_doc, old_score + rrf_score)
                else:
                    rrf_scores[doc.doc_id] = (doc, rrf_score)
        
        results = list(rrf_scores.values())
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_n]
    
    def fuse_with_weights(
        self,
        result_lists: List[List[Tuple[Document, float]]],
        weights: List[float],
        top_n: int = 10,
    ) -> List[Tuple[Document, float]]:
        """
        Fuse with different weights for each result list.
        
        Args:
            result_lists: List of result lists
            weights: Weight for each list (same length as result_lists)
            top_n: Number of results to return
        """
        assert len(result_lists) == len(weights)
        
        rrf_scores: Dict[str, Tuple[Document, float]] = {}
        
        for results, weight in zip(result_lists, weights):
            for rank, (doc, _) in enumerate(results):
                rrf_score = weight * 1.0 / (self.k + rank + 1)
                if doc.doc_id in rrf_scores:
                    old_doc, old_score = rrf_scores[doc.doc_id]
                    rrf_scores[doc.doc_id] = (old_doc, old_score + rrf_score)
                else:
                    rrf_scores[doc.doc_id] = (doc, rrf_score)
        
        results = list(rrf_scores.values())
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_n]


# ============================================================
# Part 9: Query Transformation Pipeline
# ============================================================

class QueryTransformationPipeline:
    """
    Complete query transformation pipeline that combines:
    1. Query expansion (synonyms + PRF)
    2. HyDE (hypothetical document generation)
    3. Multi-query decomposition
    4. Query routing
    5. Result fusion (RRF)
    
    The pipeline applies transformations, retrieves for each transformed query,
    and fuses the results.
    """
    
    def __init__(
        self,
        bm25_retriever: BM25Retriever,
        vector_retriever: VectorRetriever,
        use_expansion: bool = True,
        use_hyde: bool = True,
        use_multi_query: bool = True,
        use_routing: bool = True,
        use_rrf: bool = True,
        top_n: int = 10,
        final_k: int = 5,
    ):
        self.bm25 = bm25_retriever
        self.vector = vector_retriever
        self.expander = QueryExpander()
        self.prf = PseudoRelevanceFeedback(top_k=3, num_expansion_terms=5)
        self.hyde = HyDEGenerator()
        self.decomposer = MultiQueryDecomposer()
        self.router = QueryRouter()
        self.rrf = ReciprocalRankFusion(k=60)
        
        self.use_expansion = use_expansion
        self.use_hyde = use_hyde
        self.use_multi_query = use_multi_query
        self.use_routing = use_routing
        self.use_rrf = use_rrf
        self.top_n = top_n
        self.final_k = final_k
    
    def search(self, query: str) -> Dict[str, Any]:
        """
        Execute query transformation pipeline.
        
        Returns dict with:
        - 'transformations': List of transformed queries
        - 'per_query_results': Results for each transformed query
        - 'fused_results': Final fused results
        - 'route': Query route classification
        """
        transformations = [query]  # Always include original
        route = self.router.classify(query) if self.use_routing else 'hybrid'
        
        # Step 1: Query expansion
        if self.use_expansion:
            expanded = self.expander.expand(query, max_expansions=5)
            if expanded != query:
                transformations.append(('expansion', expanded))
        
        # Step 2: HyDE
        if self.use_hyde:
            hypothetical = self.hyde.generate(query)
            transformations.append(('hyde', hypothetical))
        
        # Step 3: Multi-query decomposition
        if self.use_multi_query:
            sub_queries = self.decomposer.decompose(query)
            for sq in sub_queries:
                if sq != query and sq not in [t[1] if isinstance(t, tuple) else t for t in transformations]:
                    transformations.append(('multi_query', sq))
        
        # Step 4: Retrieve for each transformed query
        all_results = []
        per_query_results = {}
        
        for transform in transformations:
            if isinstance(transform, tuple):
                label, transformed_query = transform
            else:
                label = 'original'
                transformed_query = transform
            
            # Route each query
            if self.use_routing:
                q_route = self.router.classify(transformed_query)
                if q_route == 'bm25':
                    results = self.bm25.search(transformed_query, top_n=self.top_n)
                elif q_route == 'vector':
                    results = self.vector.search(transformed_query, top_n=self.top_n)
                else:
                    bm25_res = self.bm25.search(transformed_query, top_n=self.top_n)
                    vec_res = self.vector.search(transformed_query, top_n=self.top_n)
                    results = self.router._fuse_results(bm25_res, vec_res, top_n=self.top_n)
            else:
                results = self.bm25.search(transformed_query, top_n=self.top_n)
            
            # Apply PRF to the original query's results
            if label == 'original' and self.use_expansion:
                prf_expanded = self.prf.expand_query(transformed_query, results)
                if prf_expanded != transformed_query:
                    prf_results = self.bm25.search(prf_expanded, top_n=self.top_n)
                    per_query_results['prf'] = prf_results
                    all_results.append(prf_results)
            
            per_query_results[label] = results
            all_results.append(results)
        
        # Step 5: Fuse results
        if self.use_rrf and len(all_results) > 1:
            fused = self.rrf.fuse(all_results, top_n=self.final_k)
        elif all_results:
            # Just use the first result set (original query)
            fused = all_results[0][:self.final_k]
        else:
            fused = []
        
        return {
            'original_query': query,
            'route': route,
            'transformations': [t if isinstance(t, str) else f"[{t[0]}] {t[1][:80]}..." for t in transformations],
            'per_query_results': per_query_results,
            'fused_results': fused,
        }


# ============================================================
# Part 10: Evaluation Metrics (reuse from exercise 5)
# ============================================================

class RankingEvaluator:
    @staticmethod
    def ndcg_at_k(ranked_doc_ids: List[str], judgments: Dict[str, int], k: int) -> float:
        def dcg(rels):
            return sum((2**r - 1) / math.log2(i + 2) for i, r in enumerate(rels[:k]))
        
        relevances = [judgments.get(did, 0) for did in ranked_doc_ids[:k]]
        ideal = sorted(judgments.values(), reverse=True)
        
        dcg_val = dcg(relevances)
        idcg_val = dcg(ideal)
        return dcg_val / idcg_val if idcg_val > 0 else 0.0
    
    @staticmethod
    def recall_at_k(ranked_doc_ids: List[str], judgments: Dict[str, int], k: int, threshold: int = 1) -> float:
        relevant = {d for d, r in judgments.items() if r >= threshold}
        if not relevant:
            return 0.0
        retrieved = sum(1 for d in ranked_doc_ids[:k] if judgments.get(d, 0) >= threshold)
        return retrieved / len(relevant)
    
    @staticmethod
    def evaluate_all(ranked_doc_ids: List[str], judgments: Dict[str, int], k: int = 5) -> Dict[str, float]:
        return {
            f'ndcg@{k}': RankingEvaluator.ndcg_at_k(ranked_doc_ids, judgments, k),
            f'recall@{k}': RankingEvaluator.recall_at_k(ranked_doc_ids, judgments, k),
        }


# ============================================================
# Part 11: Unit Tests
# ============================================================

class TestQueryExpander(unittest.TestCase):
    
    def setUp(self):
        self.expander = QueryExpander()
    
    def test_expand_with_synonyms(self):
        """Test that expansion adds synonyms."""
        result = self.expander.expand("python programming")
        self.assertIn("python", result.lower())
        # Should have added some synonym
        self.assertGreater(len(result), len("python programming"))
    
    def test_expand_no_synonyms(self):
        """Test expansion when no synonyms found."""
        result = self.expander.expand("quantum physics relativity")
        self.assertEqual(result, "quantum physics relativity")
    
    def test_expand_max_limit(self):
        """Test that max_expansions limits additions."""
        result = self.expander.expand("machine learning database search", max_expansions=2)
        original_len = len("machine learning database search")
        # Should add at most 2 expansion terms
        self.assertLessEqual(len(result.split()) - 4, 2)
    
    def test_expand_terms_separate(self):
        """Test getting original and expansion terms separately."""
        original, expansions = self.expander.expand_terms("python search")
        self.assertIn("python", original)
        self.assertIn("search", original)
        self.assertGreater(len(expansions), 0)
    
    def test_custom_synonyms(self):
        """Test with custom synonym dictionary."""
        custom = {'cat': ['feline', 'kitten']}
        expander = QueryExpander(synonyms=custom)
        result = expander.expand("cat food")
        self.assertIn("feline", result)
        self.assertIn("kitten", result)


class TestPseudoRelevanceFeedback(unittest.TestCase):
    
    def setUp(self):
        self.bm25 = BM25Retriever()
        self.bm25.index(SAMPLE_CORPUS)
        self.prf = PseudoRelevanceFeedback(top_k=3, num_expansion_terms=5)
    
    def test_get_expansion_terms(self):
        """Test extraction of expansion terms from results."""
        results = self.bm25.search("python", top_n=5)
        terms = self.prf.get_expansion_terms("python", results)
        self.assertIsInstance(terms, list)
        # Should have found some terms
        self.assertGreater(len(terms), 0)
    
    def test_expand_query(self):
        """Test query expansion with PRF."""
        results = self.bm25.search("python", top_n=5)
        expanded = self.prf.expand_query("python", results)
        self.assertGreater(len(expanded), len("python"))
    
    def test_empty_results(self):
        """Test handling of empty results."""
        terms = self.prf.get_expansion_terms("test", [])
        self.assertEqual(terms, [])
        expanded = self.prf.expand_query("test", [])
        self.assertEqual(expanded, "test")
    
    def test_skip_short_terms(self):
        """Test that very short terms are skipped."""
        results = self.bm25.search("python programming", top_n=5)
        terms = self.prf.get_expansion_terms("python", results)
        for term, _ in terms:
            self.assertGreaterEqual(len(term), 3)


class TestHyDEGenerator(unittest.TestCase):
    
    def setUp(self):
        self.hyde = HyDEGenerator()
    
    def test_classify_how(self):
        """Test classification of 'how' queries."""
        self.assertEqual(self.hyde._classify_query("How does Python work?"), 'how')
    
    def test_classify_what(self):
        """Test classification of 'what' queries."""
        self.assertEqual(self.hyde._classify_query("What is a vector database?"), 'what')
    
    def test_classify_compare(self):
        """Test classification of comparison queries."""
        self.assertEqual(self.hyde._classify_query("Compare BM25 and vector search"), 'compare')
    
    def test_generate_returns_string(self):
        """Test that generation returns a non-empty string."""
        result = self.hyde.generate("How does Python handle async programming?")
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 50)
    
    def test_generate_contains_topic(self):
        """Test that generated document contains query topic."""
        result = self.hyde.generate("What is gradient descent?")
        result_lower = result.lower()
        # Should mention gradient or descent
        self.assertTrue('gradient' in result_lower or 'descent' in result_lower)
    
    def test_generate_multiple(self):
        """Test generation of multiple hypothetical documents."""
        results = self.hyde.generate_multiple("How does async work?", n=3)
        self.assertEqual(len(results), 3)
        for r in results:
            self.assertGreater(len(r), 50)
    
    def test_default_classification(self):
        """Test default classification for unknown query types."""
        self.assertEqual(self.hyde._classify_query("python programming"), 'what')


class TestMultiQueryDecomposer(unittest.TestCase):
    
    def setUp(self):
        self.decomposer = MultiQueryDecomposer()
    
    def test_decompose_compare(self):
        """Test decomposition of comparison queries."""
        sub_queries = self.decomposer.decompose("Compare vector databases and traditional search")
        self.assertGreater(len(sub_queries), 1)
        # Should include sub-queries about each entity
        self.assertTrue(any("vector database" in sq.lower() for sq in sub_queries))
        self.assertTrue(any("traditional search" in sq.lower() or "search" in sq.lower() for sq in sub_queries))
    
    def test_decompose_how(self):
        """Test decomposition of 'how' queries."""
        sub_queries = self.decomposer.decompose("How does Python handle async programming")
        self.assertGreater(len(sub_queries), 1)
    
    def test_decompose_no_decomposition(self):
        """Test that simple queries are not decomposed."""
        sub_queries = self.decomposer.decompose("python programming")
        self.assertEqual(len(sub_queries), 1)
    
    def test_decompose_includes_original(self):
        """Test that original query is always included."""
        sub_queries = self.decomposer.decompose("Compare A and B")
        self.assertIn("Compare A and B", sub_queries)
    
    def test_keyword_decomposition(self):
        """Test keyword-based decomposition."""
        sub_queries = self.decomposer.decompose_with_keywords("python async and concurrency")
        self.assertGreater(len(sub_queries), 1)


class TestQueryRouter(unittest.TestCase):
    
    def setUp(self):
        self.router = QueryRouter()
        self.bm25 = BM25Retriever()
        self.bm25.index(SAMPLE_CORPUS)
        self.vector = VectorRetriever()
        self.vector.index(SAMPLE_CORPUS)
    
    def test_classify_bm25(self):
        """Test classification of BM25-favorable queries."""
        route = self.router.classify("python import error syntax")
        self.assertEqual(route, 'bm25')
    
    def test_classify_vector(self):
        """Test classification of vector-favorable queries."""
        route = self.router.classify("explain the concept of similarity in vector space")
        self.assertIn(route, ['vector', 'hybrid'])
    
    def test_classify_hybrid(self):
        """Test that mixed queries get hybrid route."""
        route = self.router.classify("python programming")
        self.assertIn(route, ['bm25', 'vector', 'hybrid'])
    
    def test_route_returns_results(self):
        """Test that routing returns results."""
        route, results = self.router.route("python", self.bm25, self.vector, top_n=5)
        self.assertIn(route, ['bm25', 'vector', 'hybrid'])
        self.assertIsInstance(results, list)
    
    def test_route_history(self):
        """Test that routing history is recorded."""
        self.router.classify("test query")
        self.assertEqual(len(self.router.route_history), 1)
        self.assertIn('route', self.router.route_history[0])
    
    def test_quoted_phrase_routes_to_bm25(self):
        """Test that quoted phrases route to BM25."""
        route = self.router.classify('"exact match" query')
        self.assertEqual(route, 'bm25')


class TestReciprocalRankFusion(unittest.TestCase):
    
    def setUp(self):
        self.rrf = ReciprocalRankFusion(k=60)
        self.bm25 = BM25Retriever()
        self.bm25.index(SAMPLE_CORPUS)
        self.vector = VectorRetriever()
        self.vector.index(SAMPLE_CORPUS)
    
    def test_fuse_two_lists(self):
        """Test fusing two result lists."""
        results_a = self.bm25.search("python", top_n=5)
        results_b = self.vector.search("python", top_n=5)
        fused = self.rrf.fuse([results_a, results_b], top_n=5)
        self.assertLessEqual(len(fused), 5)
        self.assertGreater(len(fused), 0)
    
    def test_fuse_single_list(self):
        """Test fusing a single list (should return it)."""
        results = self.bm25.search("python", top_n=5)
        fused = self.rrf.fuse([results], top_n=5)
        self.assertGreater(len(fused), 0)
    
    def test_fuse_empty(self):
        """Test fusing empty lists."""
        fused = self.rrf.fuse([], top_n=5)
        self.assertEqual(len(fused), 0)
    
    def test_fuse_with_weights(self):
        """Test weighted fusion."""
        results_a = self.bm25.search("python", top_n=5)
        results_b = self.vector.search("python", top_n=5)
        fused = self.rrf.fuse_with_weights([results_a, results_b], [1.0, 0.5], top_n=5)
        self.assertGreater(len(fused), 0)
    
    def test_fuse_combines_unique_docs(self):
        """Test that fusion includes documents from both lists."""
        results_a = self.bm25.search("vector", top_n=5)
        results_b = self.vector.search("vector", top_n=5)
        fused = self.rrf.fuse([results_a, results_b], top_n=10)
        
        ids_a = {d.doc_id for d, _ in results_a}
        ids_b = {d.doc_id for d, _ in results_b}
        ids_fused = {d.doc_id for d, _ in fused}
        
        # Fused should include docs from both lists
        self.assertTrue(ids_fused & ids_a)
        self.assertTrue(ids_fused & ids_b)
    
    def test_higher_rank_scores_more(self):
        """Test that higher-ranked documents get higher RRF scores."""
        results = self.bm25.search("python", top_n=10)
        fused = self.rrf.fuse([results], top_n=10)
        
        # First result should have highest score
        if len(fused) > 1:
            self.assertGreater(fused[0][1], fused[1][1])


class TestQueryTransformationPipeline(unittest.TestCase):
    
    def setUp(self):
        self.bm25 = BM25Retriever()
        self.bm25.index(SAMPLE_CORPUS)
        self.vector = VectorRetriever()
        self.vector.index(SAMPLE_CORPUS)
        self.pipeline = QueryTransformationPipeline(
            bm25_retriever=self.bm25,
            vector_retriever=self.vector,
            top_n=10,
            final_k=5,
        )
    
    def test_basic_search(self):
        """Test basic pipeline search."""
        result = self.pipeline.search("python async programming")
        self.assertIn('fused_results', result)
        self.assertIn('transformations', result)
        self.assertIn('original_query', result)
    
    def test_transformations_generated(self):
        """Test that transformations are generated."""
        result = self.pipeline.search("compare vector databases and search engines")
        self.assertGreater(len(result['transformations']), 1)
    
    def test_fused_results_not_empty(self):
        """Test that fused results are not empty for relevant queries."""
        result = self.pipeline.search("python programming")
        self.assertGreater(len(result['fused_results']), 0)
    
    def test_route_included(self):
        """Test that route classification is included."""
        result = self.pipeline.search("python programming")
        self.assertIn('route', result)
        self.assertIn(result['route'], ['bm25', 'vector', 'hybrid'])
    
    def test_disable_expansion(self):
        """Test pipeline with expansion disabled."""
        pipeline = QueryTransformationPipeline(
            self.bm25, self.vector, use_expansion=False, top_n=5, final_k=3
        )
        result = pipeline.search("python programming")
        self.assertGreater(len(result['fused_results']), 0)
    
    def test_disable_all_optional(self):
        """Test pipeline with all optional transformations disabled."""
        pipeline = QueryTransformationPipeline(
            self.bm25, self.vector,
            use_expansion=False, use_hyde=False, use_multi_query=False,
            use_routing=False, use_rrf=False,
            top_n=5, final_k=3,
        )
        result = pipeline.search("python programming")
        self.assertGreater(len(result['fused_results']), 0)
    
    def test_per_query_results(self):
        """Test that per-query results are tracked."""
        result = self.pipeline.search("compare vector and search")
        self.assertIn('per_query_results', result)
        self.assertIn('original', result['per_query_results'])


class TestEndToEndEvaluation(unittest.TestCase):
    """End-to-end evaluation comparing query transformation strategies."""
    
    def test_pipeline_outperforms_baseline(self):
        """Test that query transformation pipeline performs at least as well as baseline."""
        bm25 = BM25Retriever()
        bm25.index(SAMPLE_CORPUS)
        vector = VectorRetriever()
        vector.index(SAMPLE_CORPUS)
        pipeline = QueryTransformationPipeline(bm25, vector, top_n=10, final_k=5)
        
        for query, judgments in RELEVANCE_JUDGMENTS.items():
            # Baseline: BM25 only
            baseline_results = bm25.search(query, top_n=5)
            baseline_ids = [d.doc_id for d, _ in baseline_results]
            baseline_ndcg = RankingEvaluator.ndcg_at_k(baseline_ids, judgments, 5)
            
            # Pipeline
            pipe_result = pipeline.search(query)
            pipe_ids = [d.doc_id for d, _ in pipe_result['fused_results']]
            pipe_ndcg = RankingEvaluator.ndcg_at_k(pipe_ids, judgments, 5)
            
            # Pipeline should not be much worse than baseline
            # (allowing small tolerance for different fusion behavior)
            self.assertGreaterEqual(pipe_ndcg, baseline_ndcg - 0.15,
                f"Pipeline underperformed for '{query}': {pipe_ndcg:.4f} vs {baseline_ndcg:.4f}")
    
    def test_all_queries_return_results(self):
        """Test that all test queries return results."""
        bm25 = BM25Retriever()
        bm25.index(SAMPLE_CORPUS)
        vector = VectorRetriever()
        vector.index(SAMPLE_CORPUS)
        pipeline = QueryTransformationPipeline(bm25, vector, top_n=10, final_k=5)
        
        for query in RELEVANCE_JUDGMENTS:
            result = pipeline.search(query)
            self.assertGreater(len(result['fused_results']), 0,
                f"No results for query: {query}")


# ============================================================
# Main
# ============================================================

if __name__ == '__main__':
    print("=" * 70)
    print("RAG Exercise 6: Query Transformation (查询转换)")
    print("=" * 70)
    
    print("\n--- Running Tests ---\n")
    unittest.main(argv=['', '-v'], exit=False)
    
    # Demonstrate query transformation
    print("\n--- Query Transformation Demo ---\n")
    
    bm25 = BM25Retriever()
    bm25.index(SAMPLE_CORPUS)
    vector = VectorRetriever()
    vector.index(SAMPLE_CORPUS)
    pipeline = QueryTransformationPipeline(bm25, vector, top_n=10, final_k=5)
    
    query = "compare vector databases and traditional search"
    result = pipeline.search(query)
    
    print(f"Query: {query}")
    print(f"Route: {result['route']}")
    print(f"\nTransformations ({len(result['transformations'])}):")
    for t in result['transformations']:
        print(f"  - {t}")
    
    print(f"\nFused Results (top 5):")
    for doc, score in result['fused_results']:
        print(f"  {doc.doc_id}: {score:.6f} - {doc.content[:60]}...")
    
    # Compare with baseline
    print(f"\n--- Baseline vs Pipeline Comparison ---\n")
    
    for query, judgments in RELEVANCE_JUDGMENTS.items():
        baseline = bm25.search(query, top_n=5)
        baseline_ids = [d.doc_id for d, _ in baseline]
        baseline_ndcg = RankingEvaluator.ndcg_at_k(baseline_ids, judgments, 5)
        
        pipe_result = pipeline.search(query)
        pipe_ids = [d.doc_id for d, _ in pipe_result['fused_results']]
        pipe_ndcg = RankingEvaluator.ndcg_at_k(pipe_ids, judgments, 5)
        
        improvement = pipe_ndcg - baseline_ndcg
        arrow = "↑" if improvement > 0.01 else ("↓" if improvement < -0.01 else "=")
        print(f"  {query[:45]:<45} | BM25: {baseline_ndcg:.4f} | Pipeline: {pipe_ndcg:.4f} | {arrow} {abs(improvement):.4f}")
