#!/usr/bin/env python3
"""
RAG Exercise 5: Re-ranking (重排序)

Learning Objectives:
1. Understand why re-ranking improves retrieval quality after initial retrieval
2. Implement cross-encoder style re-ranking using lexical + semantic signals
3. Build a two-stage retrieval pipeline: coarse retrieval -> fine re-ranking
4. Compare re-ranking strategies: lexical overlap, semantic similarity, hybrid scoring
5. Implement Maximal Marginal Relevance (MMR) for diversity-aware re-ranking
6. Evaluate re-ranking impact using ranking metrics (NDCG, MRR, Recall@K)

Architecture:
    Query
      |
      v
    [Stage 1: Coarse Retrieval]  -- BM25 or Vector search, retrieve top-N (e.g., 20)
      |
      v
    [Stage 2: Fine Re-ranking]   -- Cross-encoder / hybrid scoring, re-rank to top-K (e.g., 5)
      |
      v
    Final Results

Key Concepts:
- Two-stage retrieval: trade recall for precision
- Cross-encoder vs Bi-encoder: cross-encoder reads query+doc together (better but slower)
- MMR: balance relevance and diversity to avoid redundant results
- Ranking metrics: NDCG, MRR, Recall@K to measure ranking quality

Dependencies: Only standard library + numpy (for vector operations)
"""

import math
import re
import json
import hashlib
from collections import Counter, defaultdict
from typing import List, Dict, Tuple, Optional, Callable, Any
from dataclasses import dataclass, field
import unittest

# ============================================================
# Part 1: Document and Corpus Setup
# ============================================================

@dataclass
class Document:
    """A document with content and optional metadata."""
    doc_id: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def get_tokens(self) -> List[str]:
        """Tokenize content into lowercase words."""
        return re.findall(r'\b\w+\b', self.content.lower())
    
    def get_term_freq(self) -> Counter:
        """Get term frequency counter."""
        return Counter(self.get_tokens())


# Sample corpus: tech articles about different topics
SAMPLE_CORPUS = [
    Document("d1", "Python is a high-level programming language known for its simplicity and readability. It supports multiple paradigms including object-oriented and functional programming."),
    Document("d2", "Machine learning models require large datasets for training. Deep neural networks can learn complex patterns from data through backpropagation."),
    Document("d3", "Vector databases store high-dimensional embeddings for similarity search. They use approximate nearest neighbor algorithms for fast retrieval."),
    Document("d4", "Natural language processing involves tokenization, stemming, and named entity recognition. Transformers have revolutionized NLP tasks."),
    Document("d5", "Web development with Python uses frameworks like Django and Flask. REST APIs handle HTTP requests and return JSON responses."),
    Document("d6", "Python data science libraries include NumPy for numerical computing, pandas for data manipulation, and matplotlib for visualization."),
    Document("d7", "Embedding models convert text into dense vectors. Word2Vec and BERT are popular embedding approaches for capturing semantic meaning."),
    Document("d8", "Information retrieval systems rank documents by relevance to a query. TF-IDF and BM25 are classic ranking functions."),
    Document("d9", "Distributed systems use consensus algorithms like Raft and Paxos. They handle fault tolerance and data consistency across nodes."),
    Document("d10", "Cloud computing platforms offer scalable infrastructure. AWS, Azure, and GCP provide virtual machines and managed services."),
    Document("d11", "Python async programming uses asyncio and coroutines for concurrent I/O operations. Event loops manage task scheduling."),
    Document("d12", "Gradient descent optimization minimizes loss functions in machine learning. Stochastic gradient descent processes batches of data."),
    Document("d13", "Search engines use inverted indices for fast text lookup. The index maps terms to posting lists of document IDs."),
    Document("d14", "Recommendation systems use collaborative filtering and content-based filtering. Matrix factorization decomposes user-item interactions."),
    Document("d15", "Container orchestration with Kubernetes manages microservices deployment. Pods are the smallest deployable units."),
    Document("d16", "Text classification assigns documents to predefined categories. Naive Bayes and support vector machines are common classifiers."),
    Document("d17", "Graph databases like Neo4j store entities and relationships. Cypher is a declarative query language for graph traversal."),
    Document("d18", "Python testing frameworks include pytest and unittest. Test-driven development writes tests before implementation code."),
    Document("d19", "Vector similarity measures include cosine similarity, dot product, and Euclidean distance. Cosine similarity is preferred for text embeddings."),
    Document("d20", "Retrieval augmented generation combines search with language models. The retrieved context helps the model generate accurate answers."),
]

# Relevance judgments: query -> {doc_id: relevance_score (0-3)}
# 3=perfectly relevant, 2=relevant, 1=marginally relevant, 0=irrelevant
RELEVANCE_JUDGMENTS = {
    "python programming": {"d1": 3, "d5": 2, "d6": 2, "d11": 2, "d18": 1, "d12": 0},
    "vector database search": {"d3": 3, "d7": 2, "d8": 2, "d13": 2, "d19": 2, "d20": 1},
    "machine learning training": {"d2": 3, "d12": 3, "d4": 2, "d16": 1, "d6": 1, "d14": 1},
    "text retrieval ranking": {"d8": 3, "d13": 3, "d19": 2, "d3": 2, "d4": 2, "d20": 2, "d16": 1},
}


# ============================================================
# Part 2: BM25 Retriever (Coarse Retrieval Stage)
# ============================================================

class BM25Retriever:
    """
    BM25 (Best Matching 25) retriever for coarse retrieval.
    
    BM25 formula:
        score(q, d) = sum over terms t in q of:
            IDF(t) * (f(t,d) * (k1 + 1)) / (f(t,d) + k1 * (1 - b + b * |d| / avgdl))
    
    where:
        f(t,d) = term frequency of t in document d
        |d| = document length
        avgdl = average document length
        k1 = term frequency saturation (typically 1.2-2.0)
        b = length normalization (typically 0.75)
    """
    
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
        """Index the corpus."""
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
        
        # Compute IDF for each term
        self.idf = {}
        for term, doc_indices in self.term_docs.items():
            df = len(doc_indices)
            # BM25 IDF: log((N - df + 0.5) / (df + 0.5) + 1)
            self.idf[term] = math.log((self.N - df + 0.5) / (df + 0.5) + 1)
    
    def search(self, query: str, top_n: int = 20) -> List[Tuple[Document, float]]:
        """
        Search for documents matching the query.
        Returns list of (document, score) tuples, sorted by score descending.
        """
        query_terms = re.findall(r'\b\w+\b', query.lower())
        scores = [0.0] * self.N
        
        for term in query_terms:
            if term not in self.idf:
                continue
            idf = self.idf[term]
            for doc_idx in self.term_docs.get(term, []):
                tf = self.doc_freqs[doc_idx].get(term, 0)
                dl = self.doc_len[doc_idx]
                # BM25 score component
                numerator = tf * (self.k1 + 1)
                denominator = tf + self.k1 * (1 - self.b + self.b * dl / self.avgdl) if self.avgdl > 0 else tf + self.k1
                scores[doc_idx] += idf * (numerator / denominator) if denominator > 0 else 0
        
        # Sort by score descending
        results = [(self.documents[i], scores[i]) for i in range(self.N) if scores[i] > 0]
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_n]


# ============================================================
# Part 3: Vector Retriever (Coarse Retrieval Stage - alternative)
# ============================================================

class VectorRetriever:
    """
    TF-IDF based vector retriever for coarse retrieval.
    
    Uses TF-IDF vectors and cosine similarity for semantic matching.
    """
    
    def __init__(self):
        self.documents: List[Document] = []
        self.vocabulary: Dict[str, int] = {}
        self.idf_weights: Dict[str, float] = {}
        self.doc_vectors: List[Dict[int, float]] = []
        self.N: int = 0
    
    def _build_vocabulary(self, documents: List[Document]) -> None:
        """Build vocabulary from corpus."""
        vocab = set()
        for doc in documents:
            vocab.update(doc.get_tokens())
        self.vocabulary = {term: idx for idx, term in enumerate(sorted(vocab))}
    
    def _compute_idf(self, documents: List[Document]) -> None:
        """Compute IDF weights for all terms."""
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
        """Convert text to TF-IDF vector (sparse representation)."""
        tokens = re.findall(r'\b\w+\b', text.lower())
        tf = Counter(tokens)
        vector = {}
        for term, freq in tf.items():
            if term in self.vocabulary and term in self.idf_weights:
                idx = self.vocabulary[term]
                tfidf = freq * self.idf_weights[term]
                vector[idx] = tfidf
        # Normalize
        norm = math.sqrt(sum(v * v for v in vector.values()))
        if norm > 0:
            for k in vector:
                vector[k] /= norm
        return vector
    
    def index(self, documents: List[Document]) -> None:
        """Index the corpus."""
        self.documents = documents
        self.N = len(documents)
        self._build_vocabulary(documents)
        self._compute_idf(documents)
        self.doc_vectors = [self._vectorize(doc.content) for doc in documents]
    
    def search(self, query: str, top_n: int = 20) -> List[Tuple[Document, float]]:
        """Search using cosine similarity."""
        query_vec = self._vectorize(query)
        results = []
        
        for i, doc_vec in enumerate(self.doc_vectors):
            sim = self._cosine_similarity(query_vec, doc_vec)
            if sim > 0:
                results.append((self.documents[i], sim))
        
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_n]
    
    @staticmethod
    def _cosine_similarity(vec1: Dict[int, float], vec2: Dict[int, float]) -> float:
        """Compute cosine similarity between two sparse vectors."""
        # Iterate over the smaller vector
        if len(vec1) > len(vec2):
            vec1, vec2 = vec2, vec1
        dot = sum(val * vec2.get(idx, 0.0) for idx, val in vec1.items())
        return dot  # Already normalized


# ============================================================
# Part 4: Re-rankers (Fine Re-ranking Stage)
# ============================================================

class LexicalOverlapReranker:
    """
    Lexical overlap re-ranker.
    
    Scores documents based on exact term overlap with the query.
    This is a simple but effective re-ranking signal that captures
    lexical precision that BM25 might miss due to length normalization.
    
    Score = sum of query term frequencies in document / document length
    """
    
    def __init__(self, weight: float = 1.0):
        self.weight = weight
    
    def score(self, query: str, doc: Document) -> float:
        """Score a single document against the query."""
        query_terms = re.findall(r'\b\w+\b', query.lower())
        doc_tokens = doc.get_tokens()
        doc_len = len(doc_tokens)
        if doc_len == 0:
            return 0.0
        
        doc_counter = Counter(doc_tokens)
        overlap = sum(doc_counter.get(term, 0) for term in query_terms)
        # Normalize by document length to avoid bias toward long documents
        return self.weight * (overlap / doc_len)
    
    def rerank(self, query: str, documents: List[Document]) -> List[Tuple[Document, float]]:
        """Re-rank documents by lexical overlap score."""
        scored = [(doc, self.score(query, doc)) for doc in documents]
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored


class SemanticReranker:
    """
    Semantic similarity re-ranker using TF-IDF cosine similarity.
    
    Unlike the coarse vector retriever which uses the same TF-IDF,
    this re-ranker computes similarity against individual documents
    with higher precision (no truncation, exact matching).
    
    In a real system, this would use a cross-encoder model that reads
    query and document together, capturing deeper semantic relationships.
    """
    
    def __init__(self, idf_weights: Dict[str, float] = None):
        self.idf_weights = idf_weights or {}
    
    def _get_tfidf_vector(self, text: str) -> Dict[str, float]:
        """Get normalized TF-IDF vector for text."""
        tokens = re.findall(r'\b\w+\b', text.lower())
        tf = Counter(tokens)
        vector = {}
        for term, freq in tf.items():
            idf = self.idf_weights.get(term, math.log(20 / 1 + 1))  # Default IDF
            vector[term] = freq * idf
        norm = math.sqrt(sum(v * v for v in vector.values()))
        if norm > 0:
            for k in vector:
                vector[k] /= norm
        return vector
    
    def score(self, query: str, doc: Document) -> float:
        """Score using cosine similarity between query and document."""
        q_vec = self._get_tfidf_vector(query)
        d_vec = self._get_tfidf_vector(doc.content)
        # Cosine similarity (already normalized)
        dot = sum(q_vec.get(term, 0) * d_vec.get(term, 0) for term in q_vec)
        return dot
    
    def rerank(self, query: str, documents: List[Document]) -> List[Tuple[Document, float]]:
        """Re-rank by semantic similarity."""
        scored = [(doc, self.score(query, doc)) for doc in documents]
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored


class HybridReranker:
    """
    Hybrid re-ranker combining multiple signals.
    
    Combines lexical overlap, semantic similarity, and original retrieval score
    into a weighted sum. This simulates how production re-rankers use multiple
    features to produce final ranking.
    
    Score = alpha * lexical + beta * semantic + gamma * original_score
    """
    
    def __init__(
        self,
        idf_weights: Dict[str, float] = None,
        alpha: float = 0.3,   # lexical weight
        beta: float = 0.5,    # semantic weight (higher = more semantic)
        gamma: float = 0.2,   # original retrieval score weight
    ):
        self.lexical = LexicalOverlapReranker()
        self.semantic = SemanticReranker(idf_weights)
        self.alpha = alpha
        self.beta = beta
        self.gamma = gamma
    
    def score(self, query: str, doc: Document, original_score: float = 0.0) -> float:
        """Score using weighted combination of signals."""
        lex = self.lexical.score(query, doc)
        sem = self.semantic.score(query, doc)
        return self.alpha * lex + self.beta * sem + self.gamma * original_score
    
    def rerank(
        self, query: str, documents: List[Tuple[Document, float]]
    ) -> List[Tuple[Document, float]]:
        """
        Re-rank documents with their original scores.
        
        Args:
            query: The search query
            documents: List of (document, original_score) from coarse retrieval
        
        Returns:
            Re-ranked list of (document, new_score)
        """
        scored = [
            (doc, self.score(query, doc, orig_score))
            for doc, orig_score in documents
        ]
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored


class MMRReranker:
    """
    Maximal Marginal Relevance (MMR) re-ranker.
    
    MMR selects documents that are both relevant to the query AND diverse
    from already-selected documents. This prevents redundant results.
    
    MMR formula:
        MMR = argmax [ alpha * Sim(query, d_i) - (1 - alpha) * max(Sim(d_i, d_j)) for j in selected ]
    
    where alpha controls the relevance-diversity trade-off:
        alpha = 1.0: pure relevance (same as normal ranking)
        alpha = 0.0: pure diversity (maximally different from selected)
        alpha = 0.5-0.7: balanced (recommended)
    
    Reference: Carbonell & Goldstein (1998)
    """
    
    def __init__(self, idf_weights: Dict[str, float] = None, alpha: float = 0.7):
        self.semantic = SemanticReranker(idf_weights)
        self.alpha = alpha
        self._doc_vectors: Dict[str, Dict[str, float]] = {}
    
    def _get_doc_vector(self, doc: Document) -> Dict[str, float]:
        """Get or compute TF-IDF vector for a document."""
        if doc.doc_id not in self._doc_vectors:
            self._doc_vectors[doc.doc_id] = self.semantic._get_tfidf_vector(doc.content)
        return self._doc_vectors[doc.doc_id]
    
    def _doc_similarity(self, doc1: Document, doc2: Document) -> float:
        """Compute similarity between two documents."""
        vec1 = self._get_doc_vector(doc1)
        vec2 = self._get_doc_vector(doc2)
        # Cosine similarity (vectors are normalized)
        return sum(vec1.get(term, 0) * vec2.get(term, 0) for term in vec1)
    
    def rerank(
        self,
        query: str,
        documents: List[Tuple[Document, float]],
        top_k: int = 5,
    ) -> List[Tuple[Document, float]]:
        """
        Re-rank using MMR to balance relevance and diversity.
        
        Args:
            query: Search query
            documents: List of (document, original_score) from coarse retrieval
            top_k: Number of documents to select
        
        Returns:
            Selected documents with MMR scores
        """
        if not documents:
            return []
        
        # Compute relevance scores for all candidates
        candidates = []
        for doc, orig_score in documents:
            rel_score = self.semantic.score(query, doc)
            candidates.append({
                'doc': doc,
                'relevance': rel_score,
                'orig_score': orig_score,
                'mmr_score': 0.0,
                'selected': False,
            })
        
        selected = []
        remaining = list(candidates)
        
        # Step 1: Select the most relevant document first
        remaining.sort(key=lambda x: x['relevance'], reverse=True)
        best = remaining.pop(0)
        best['mmr_score'] = best['relevance']
        best['selected'] = True
        selected.append(best)
        
        # Step 2: Iteratively select documents using MMR
        while remaining and len(selected) < top_k:
            for cand in remaining:
                # Compute max similarity to already selected documents
                max_sim = max(
                    self._doc_similarity(cand['doc'], sel['doc'])
                    for sel in selected
                )
                # MMR score: alpha * relevance - (1 - alpha) * max_similarity
                cand['mmr_score'] = (
                    self.alpha * cand['relevance']
                    - (1 - self.alpha) * max_sim
                )
            
            # Select the candidate with highest MMR score
            remaining.sort(key=lambda x: x['mmr_score'], reverse=True)
            best = remaining.pop(0)
            best['selected'] = True
            selected.append(best)
        
        return [(item['doc'], item['mmr_score']) for item in selected]


class CrossEncoderSimulator:
    """
    Simulates a cross-encoder re-ranker.
    
    A real cross-encoder (like ms-marco-MiniLM-L-12-v2) reads [query, document]
    pairs together through a transformer, capturing fine-grained interactions.
    
    This simulation uses multiple lexical and semantic features to approximate
    cross-encoder behavior:
    1. Exact phrase matching (query bigrams in document)
    2. Term proximity (how close query terms appear in document)
    3. Coverage (what fraction of query terms appear in document)
    4. Semantic similarity (TF-IDF cosine)
    5. Length ratio penalty (penalize very short or very long docs)
    """
    
    def __init__(self, idf_weights: Dict[str, float] = None):
        self.idf_weights = idf_weights or {}
        self.semantic = SemanticReranker(idf_weights)
    
    def _get_bigrams(self, text: str) -> set:
        """Extract bigrams from text."""
        tokens = re.findall(r'\b\w+\b', text.lower())
        return set(zip(tokens, tokens[1:]))
    
    def _term_proximity(self, query_terms: List[str], doc_tokens: List[str]) -> float:
        """
        Compute average distance between query terms in the document.
        Lower distance = higher score.
        """
        if len(query_terms) < 2:
            return 1.0
        
        # Find positions of each query term
        positions = defaultdict(list)
        for i, token in enumerate(doc_tokens):
            if token in query_terms:
                positions[token].append(i)
        
        if len(positions) < 2:
            return 0.3  # At least one term missing
        
        # Compute minimum distance between consecutive query terms
        min_distances = []
        for i in range(len(query_terms) - 1):
            t1, t2 = query_terms[i], query_terms[i + 1]
            if t1 in positions and t2 in positions:
                min_dist = min(
                    abs(p1 - p2)
                    for p1 in positions[t1]
                    for p2 in positions[t2]
                )
                # Convert distance to score: closer = higher
                min_distances.append(1.0 / (1.0 + min_dist))
        
        return sum(min_distances) / len(min_distances) if min_distances else 0.3
    
    def score(self, query: str, doc: Document) -> float:
        """Score using simulated cross-encoder features."""
        query_terms = re.findall(r'\b\w+\b', query.lower())
        doc_tokens = doc.get_tokens()
        doc_counter = Counter(doc_tokens)
        
        # Feature 1: Bigram matching
        query_bigrams = self._get_bigrams(query)
        doc_bigrams = self._get_bigrams(doc.content)
        bigram_score = len(query_bigrams & doc_bigrams) / max(len(query_bigrams), 1)
        
        # Feature 2: Term proximity
        proximity_score = self._term_proximity(query_terms, doc_tokens)
        
        # Feature 3: Coverage
        matched = sum(1 for t in query_terms if doc_counter.get(t, 0) > 0)
        coverage_score = matched / max(len(query_terms), 1)
        
        # Feature 4: Semantic similarity
        sem_score = self.semantic.score(query, doc)
        
        # Feature 5: Length ratio penalty
        doc_len = len(doc_tokens)
        query_len = len(query_terms)
        length_ratio = min(doc_len, query_len * 20) / max(doc_len, 1)  # Cap at 20x query
        length_penalty = 1.0 if 0.3 < length_ratio < 1.0 else 0.7
        
        # Weighted combination (cross-encoder style)
        score = (
            0.15 * bigram_score +
            0.20 * proximity_score +
            0.25 * coverage_score +
            0.30 * sem_score +
            0.10 * length_penalty
        )
        
        return score
    
    def rerank(self, query: str, documents: List[Document]) -> List[Tuple[Document, float]]:
        """Re-rank using simulated cross-encoder scoring."""
        scored = [(doc, self.score(query, doc)) for doc in documents]
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored


# ============================================================
# Part 5: Two-Stage Retrieval Pipeline
# ============================================================

class TwoStageRetrievalPipeline:
    """
    Two-stage retrieval pipeline:
    
    Stage 1 (Coarse): Retrieve top-N candidates using fast retriever (BM25 or Vector)
    Stage 2 (Fine): Re-rank top-N candidates using a more expensive re-ranker
    
    This is the standard architecture used in production RAG systems:
    - Stage 1: ~20-100 candidates, cheap, high recall
    - Stage 2: Top-K (3-10), expensive, high precision
    """
    
    def __init__(
        self,
        retriever: Any,  # BM25Retriever or VectorRetriever
        reranker: Any,   # Any reranker class
        coarse_top_n: int = 20,
        final_top_k: int = 5,
    ):
        self.retriever = retriever
        self.reranker = reranker
        self.coarse_top_n = coarse_top_n
        self.final_top_k = final_top_k
    
    def search(self, query: str) -> Dict[str, Any]:
        """
        Execute two-stage retrieval.
        
        Returns:
            Dict with:
            - 'coarse_results': Stage 1 results
            - 'reranked_results': Stage 2 results
            - 'final_results': Final top-K results
        """
        # Stage 1: Coarse retrieval
        coarse_results = self.retriever.search(query, top_n=self.coarse_top_n)
        
        # Stage 2: Re-ranking
        # Different rerankers have different interfaces
        if isinstance(self.reranker, (HybridReranker, MMRReranker)):
            # These take (doc, score) pairs
            if isinstance(self.reranker, MMRReranker):
                reranked = self.reranker.rerank(query, coarse_results, top_k=self.final_top_k)
            else:
                reranked = self.reranker.rerank(query, coarse_results)
                reranked = reranked[:self.final_top_k]
        else:
            # These take just documents
            docs = [doc for doc, _ in coarse_results]
            reranked = self.reranker.rerank(query, docs)
            reranked = reranked[:self.final_top_k]
        
        return {
            'coarse_results': coarse_results,
            'reranked_results': reranked,
            'final_results': reranked[:self.final_top_k],
            'query': query,
        }


# ============================================================
# Part 6: Ranking Evaluation Metrics
# ============================================================

class RankingEvaluator:
    """
    Evaluate ranking quality using standard IR metrics.
    
    Metrics:
    - NDCG@K (Normalized Discounted Cumulative Gain):
        Measures ranking quality with graded relevance.
        DCG@K = sum(rel_i / log2(i + 1)) for i=1..K
        NDCG@K = DCG@K / IDCG@K  (normalized by ideal ranking)
    
    - MRR (Mean Reciprocal Rank):
        Average of 1/rank of first relevant document.
    
    - Recall@K:
        Fraction of relevant documents in top-K.
    
    - Precision@K:
        Fraction of top-K that are relevant.
    """
    
    @staticmethod
    def dcg_at_k(relevances: List[int], k: int) -> float:
        """Compute DCG@K."""
        dcg = 0.0
        for i, rel in enumerate(relevances[:k]):
            # Use 2^rel - 1 for graded relevance (NDCG variant)
            dcg += (2 ** rel - 1) / math.log2(i + 2)
        return dcg
    
    @staticmethod
    def ndcg_at_k(ranked_doc_ids: List[str], judgments: Dict[str, int], k: int) -> float:
        """
        Compute NDCG@K.
        
        Args:
            ranked_doc_ids: List of document IDs in ranked order
            judgments: Dict of {doc_id: relevance_score}
            k: Cutoff rank
        
        Returns:
            NDCG score between 0 and 1
        """
        # Get relevance scores for ranked documents
        relevances = [judgments.get(doc_id, 0) for doc_id in ranked_doc_ids[:k]]
        dcg = RankingEvaluator.dcg_at_k(relevances, k)
        
        # Compute ideal DCG (sort by relevance descending)
        ideal_relevances = sorted(judgments.values(), reverse=True)[:k]
        idcg = RankingEvaluator.dcg_at_k(ideal_relevances, k)
        
        return dcg / idcg if idcg > 0 else 0.0
    
    @staticmethod
    def mrr(ranked_doc_ids: List[str], judgments: Dict[str, int], threshold: int = 1) -> float:
        """
        Compute Reciprocal Rank (1/rank of first relevant doc).
        
        Args:
            threshold: Minimum relevance score to be considered relevant
        """
        for i, doc_id in enumerate(ranked_doc_ids):
            if judgments.get(doc_id, 0) >= threshold:
                return 1.0 / (i + 1)
        return 0.0
    
    @staticmethod
    def recall_at_k(ranked_doc_ids: List[str], judgments: Dict[str, int], k: int, threshold: int = 1) -> float:
        """
        Compute Recall@K.
        
        Recall = |relevant docs in top-K| / |total relevant docs|
        """
        relevant_docs = {doc_id for doc_id, rel in judgments.items() if rel >= threshold}
        if not relevant_docs:
            return 0.0
        
        retrieved_relevant = sum(
            1 for doc_id in ranked_doc_ids[:k]
            if judgments.get(doc_id, 0) >= threshold
        )
        return retrieved_relevant / len(relevant_docs)
    
    @staticmethod
    def precision_at_k(ranked_doc_ids: List[str], judgments: Dict[str, int], k: int, threshold: int = 1) -> float:
        """
        Compute Precision@K.
        
        Precision = |relevant docs in top-K| / K
        """
        retrieved_relevant = sum(
            1 for doc_id in ranked_doc_ids[:k]
            if judgments.get(doc_id, 0) >= threshold
        )
        return retrieved_relevant / k if k > 0 else 0.0
    
    @staticmethod
    def evaluate_all(
        ranked_doc_ids: List[str],
        judgments: Dict[str, int],
        k: int = 5,
    ) -> Dict[str, float]:
        """Compute all metrics at once."""
        return {
            f'ndcg@{k}': RankingEvaluator.ndcg_at_k(ranked_doc_ids, judgments, k),
            f'mrr': RankingEvaluator.mrr(ranked_doc_ids, judgments),
            f'recall@{k}': RankingEvaluator.recall_at_k(ranked_doc_ids, judgments, k),
            f'precision@{k}': RankingEvaluator.precision_at_k(ranked_doc_ids, judgments, k),
        }


# ============================================================
# Part 7: Comprehensive Evaluation Harness
# ============================================================

def evaluate_reranking_strategies(
    corpus: List[Document],
    queries: Dict[str, Dict[str, int]],
    k: int = 5,
) -> Dict[str, Any]:
    """
    Evaluate different re-ranking strategies across multiple queries.
    
    Compares:
    1. BM25 only (no re-ranking)
    2. BM25 + Lexical overlap re-ranking
    3. BM25 + Semantic re-ranking
    4. BM25 + Hybrid re-ranking
    5. BM25 + Cross-encoder simulation
    6. BM25 + MMR (diversity-aware)
    
    Returns comprehensive evaluation report.
    """
    # Build retrievers
    bm25 = BM25Retriever(k1=1.5, b=0.75)
    bm25.index(corpus)
    
    vector_ret = VectorRetriever()
    vector_ret.index(corpus)
    
    # Build re-rankers
    idf_weights = vector_ret.idf_weights
    rerankers = {
        'bm25_only': None,
        'bm25+lexical': LexicalOverlapReranker(),
        'bm25+semantic': SemanticReranker(idf_weights),
        'bm25+hybrid': HybridReranker(idf_weights, alpha=0.3, beta=0.5, gamma=0.2),
        'bm25+cross_encoder': CrossEncoderSimulator(idf_weights),
        'bm25+mmr': MMRReranker(idf_weights, alpha=0.7),
    }
    
    results = {}
    
    for strategy_name, reranker in rerankers.items():
        strategy_metrics = []
        
        for query, judgments in queries.items():
            # Stage 1: Coarse retrieval
            coarse_results = bm25.search(query, top_n=20)
            
            if reranker is None:
                # No re-ranking
                ranked = [(doc, score) for doc, score in coarse_results[:k]]
            elif isinstance(reranker, HybridReranker):
                ranked = reranker.rerank(query, coarse_results)[:k]
            elif isinstance(reranker, MMRReranker):
                ranked = reranker.rerank(query, coarse_results, top_k=k)
            else:
                docs = [doc for doc, _ in coarse_results]
                ranked = reranker.rerank(query, docs)[:k]
            
            # Get doc IDs in ranked order
            ranked_doc_ids = [doc.doc_id for doc, _ in ranked]
            
            # Evaluate
            metrics = RankingEvaluator.evaluate_all(ranked_doc_ids, judgments, k=k)
            strategy_metrics.append({
                'query': query,
                'metrics': metrics,
                'ranked_docs': ranked_doc_ids,
            })
        
        # Average metrics across queries
        avg_metrics = {}
        metric_keys = list(strategy_metrics[0]['metrics'].keys())
        for mk in metric_keys:
            values = [sm['metrics'][mk] for sm in strategy_metrics]
            avg_metrics[mk] = sum(values) / len(values)
        
        results[strategy_name] = {
            'avg_metrics': avg_metrics,
            'per_query': strategy_metrics,
        }
    
    return results


def print_evaluation_report(results: Dict[str, Any]) -> str:
    """Format evaluation results as a readable report."""
    lines = []
    lines.append("=" * 80)
    lines.append("RERANKING STRATEGY EVALUATION REPORT")
    lines.append("=" * 80)
    lines.append("")
    
    # Header
    strategies = list(results.keys())
    metric_keys = list(results[strategies[0]]['avg_metrics'].keys())
    
    # Table header
    header = f"{'Strategy':<25}"
    for mk in metric_keys:
        header += f" | {mk:>12}"
    lines.append(header)
    lines.append("-" * len(header))
    
    # Table rows
    for strategy in strategies:
        row = f"{strategy:<25}"
        for mk in metric_keys:
            val = results[strategy]['avg_metrics'][mk]
            row += f" | {val:>12.4f}"
        lines.append(row)
    
    lines.append("")
    lines.append("=" * 80)
    
    # Find best strategy per metric
    lines.append("\nBest strategy per metric:")
    for mk in metric_keys:
        best_strategy = max(strategies, key=lambda s: results[s]['avg_metrics'][mk])
        best_val = results[best_strategy]['avg_metrics'][mk]
        lines.append(f"  {mk:>15}: {best_strategy} ({best_val:.4f})")
    
    return "\n".join(lines)


# ============================================================
# Part 8: Unit Tests
# ============================================================

class TestBM25Retriever(unittest.TestCase):
    """Test BM25 retriever."""
    
    def setUp(self):
        self.bm25 = BM25Retriever(k1=1.5, b=0.75)
        self.bm25.index(SAMPLE_CORPUS)
    
    def test_indexing(self):
        """Test that indexing produces correct statistics."""
        self.assertEqual(self.bm25.N, 20)
        self.assertGreater(self.bm25.avgdl, 0)
        self.assertGreater(len(self.bm25.idf), 0)
    
    def test_basic_search(self):
        """Test basic search returns relevant results."""
        results = self.bm25.search("python programming", top_n=5)
        self.assertGreater(len(results), 0)
        # d1 is about Python programming, should be top
        self.assertEqual(results[0][0].doc_id, "d1")
    
    def test_no_results_for_unknown_terms(self):
        """Test that unknown terms return no results."""
        results = self.bm25.search("xyzabc123", top_n=5)
        self.assertEqual(len(results), 0)
    
    def test_top_n_limit(self):
        """Test that top_n limits results."""
        results = self.bm25.search("python", top_n=3)
        self.assertLessEqual(len(results), 3)
    
    def test_scores_descending(self):
        """Test that results are sorted by score descending."""
        results = self.bm25.search("vector database", top_n=10)
        for i in range(len(results) - 1):
            self.assertGreaterEqual(results[i][1], results[i + 1][1])
    
    def test_idf_positive(self):
        """Test that IDF values are positive for non-stopwords."""
        # 'python' appears in several docs, IDF should be positive
        self.assertIn('python', self.bm25.idf)
        self.assertGreater(self.bm25.idf['python'], 0)


class TestVectorRetriever(unittest.TestCase):
    """Test vector retriever."""
    
    def setUp(self):
        self.vr = VectorRetriever()
        self.vr.index(SAMPLE_CORPUS)
    
    def test_indexing(self):
        """Test that indexing builds vocabulary and vectors."""
        self.assertEqual(self.vr.N, 20)
        self.assertGreater(len(self.vr.vocabulary), 50)
        self.assertEqual(len(self.vr.doc_vectors), 20)
    
    def test_search(self):
        """Test search returns relevant results."""
        results = self.vr.search("machine learning", top_n=5)
        self.assertGreater(len(results), 0)
    
    def test_cosine_similarity_normalized(self):
        """Test that vectors are normalized."""
        for vec in self.vr.doc_vectors[:3]:
            norm = math.sqrt(sum(v * v for v in vec.values()))
            self.assertAlmostEqual(norm, 1.0, places=5)
    
    def test_no_zero_norm_vectors(self):
        """Test that no document has zero norm."""
        for vec in self.vr.doc_vectors:
            norm = math.sqrt(sum(v * v for v in vec.values()))
            self.assertGreater(norm, 0)


class TestLexicalOverlapReranker(unittest.TestCase):
    """Test lexical overlap re-ranker."""
    
    def setUp(self):
        self.reranker = LexicalOverlapReranker()
    
    def test_score(self):
        """Test scoring."""
        doc = Document("test", "python programming language tutorial")
        score = self.reranker.score("python programming", doc)
        self.assertGreater(score, 0)
    
    def test_no_overlap(self):
        """Test zero score for no overlap."""
        doc = Document("test", "cloud computing infrastructure")
        score = self.reranker.score("python programming", doc)
        self.assertEqual(score, 0.0)
    
    def test_rerank_order(self):
        """Test that re-ranking puts better matches first."""
        docs = [
            Document("d1", "python is great"),
            Document("d2", "cloud computing platform"),
            Document("d3", "python programming tutorial"),
        ]
        results = self.reranker.rerank("python programming", docs)
        self.assertEqual(results[0][0].doc_id, "d3")  # Better match
    
    def test_empty_doc(self):
        """Test handling of empty document."""
        doc = Document("empty", "")
        score = self.reranker.score("test", doc)
        self.assertEqual(score, 0.0)


class TestSemanticReranker(unittest.TestCase):
    """Test semantic re-ranker."""
    
    def setUp(self):
        self.vr = VectorRetriever()
        self.vr.index(SAMPLE_CORPUS)
        self.reranker = SemanticReranker(self.vr.idf_weights)
    
    def test_score_range(self):
        """Test that scores are between 0 and 1."""
        doc = SAMPLE_CORPUS[0]
        score = self.reranker.score("python programming", doc)
        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 1.0)
    
    def test_self_similarity(self):
        """Test that a document is most similar to itself."""
        doc = SAMPLE_CORPUS[0]
        score_self = self.reranker.score(doc.content, doc)
        doc_other = SAMPLE_CORPUS[5]
        score_other = self.reranker.score(doc_other.content, doc)
        self.assertGreater(score_self, score_other)
    
    def test_rerank(self):
        """Test re-ranking order."""
        docs = [d for d in SAMPLE_CORPUS[:10]]
        results = self.reranker.rerank("vector database", docs)
        # d3 is about vector databases
        self.assertEqual(results[0][0].doc_id, "d3")


class TestHybridReranker(unittest.TestCase):
    """Test hybrid re-ranker."""
    
    def setUp(self):
        self.vr = VectorRetriever()
        self.vr.index(SAMPLE_CORPUS)
        self.reranker = HybridReranker(self.vr.idf_weights)
    
    def test_score_combination(self):
        """Test that score combines multiple signals."""
        doc = SAMPLE_CORPUS[0]
        score = self.reranker.score("python programming", doc, original_score=2.0)
        self.assertGreater(score, 0)
    
    def test_weights_sum(self):
        """Test that weights sum to 1.0."""
        total = self.reranker.alpha + self.reranker.beta + self.reranker.gamma
        self.assertAlmostEqual(total, 1.0, places=5)
    
    def test_rerank_with_original_scores(self):
        """Test re-ranking using original retrieval scores."""
        bm25 = BM25Retriever()
        bm25.index(SAMPLE_CORPUS)
        coarse = bm25.search("python", top_n=10)
        reranked = self.reranker.rerank("python", coarse)
        self.assertEqual(len(reranked), len(coarse))
        # Check descending order
        for i in range(len(reranked) - 1):
            self.assertGreaterEqual(reranked[i][1], reranked[i + 1][1])


class TestMMRReranker(unittest.TestCase):
    """Test MMR re-ranker."""
    
    def setUp(self):
        self.vr = VectorRetriever()
        self.vr.index(SAMPLE_CORPUS)
        self.reranker = MMRReranker(self.vr.idf_weights, alpha=0.7)
        self.bm25 = BM25Retriever()
        self.bm25.index(SAMPLE_CORPUS)
    
    def test_selects_top_k(self):
        """Test that MMR selects exactly top_k documents."""
        coarse = self.bm25.search("python", top_n=10)
        results = self.reranker.rerank("python", coarse, top_k=5)
        self.assertEqual(len(results), 5)
    
    def test_diversity_vs_pure_relevance(self):
        """Test that MMR produces more diverse results than pure relevance."""
        query = "python programming"
        coarse = self.bm25.search(query, top_n=10)
        
        # MMR results
        mmr_results = self.reranker.rerank(query, coarse, top_k=5)
        
        # Pure relevance (alpha=1.0)
        pure_mmr = MMRReranker(self.vr.idf_weights, alpha=1.0)
        pure_results = pure_mmr.rerank(query, coarse, top_k=5)
        
        # Compute diversity (average pairwise similarity)
        def avg_similarity(docs):
            total = 0
            count = 0
            for i in range(len(docs)):
                for j in range(i + 1, len(docs)):
                    total += self.reranker._doc_similarity(docs[i], docs[j])
                    count += 1
            return total / count if count > 0 else 0
        
        mmr_docs = [doc for doc, _ in mmr_results]
        pure_docs = [doc for doc, _ in pure_results]
        
        mmr_div = avg_similarity(mmr_docs)
        pure_div = avg_similarity(pure_docs)
        
        # MMR should produce lower average similarity (more diverse)
        self.assertLessEqual(mmr_div, pure_div + 0.01)  # Small tolerance
    
    def test_alpha_extremes(self):
        """Test that alpha=1.0 behaves like pure relevance ranking."""
        coarse = self.bm25.search("python", top_n=10)
        
        # alpha=1.0: pure relevance
        high_alpha = MMRReranker(self.vr.idf_weights, alpha=1.0)
        results = high_alpha.rerank("python", coarse, top_k=3)
        
        # First result should be the most relevant
        semantic = SemanticReranker(self.vr.idf_weights)
        all_scores = [(doc, semantic.score("python", doc)) for doc, _ in coarse]
        all_scores.sort(key=lambda x: x[1], reverse=True)
        
        self.assertEqual(results[0][0].doc_id, all_scores[0][0].doc_id)
    
    def test_empty_input(self):
        """Test handling of empty input."""
        results = self.reranker.rerank("test", [], top_k=5)
        self.assertEqual(len(results), 0)


class TestCrossEncoderSimulator(unittest.TestCase):
    """Test cross-encoder simulator."""
    
    def setUp(self):
        self.vr = VectorRetriever()
        self.vr.index(SAMPLE_CORPUS)
        self.reranker = CrossEncoderSimulator(self.vr.idf_weights)
    
    def test_score_range(self):
        """Test that scores are non-negative."""
        doc = SAMPLE_CORPUS[0]
        score = self.reranker.score("python programming", doc)
        self.assertGreaterEqual(score, 0)
    
    def test_better_match_higher_score(self):
        """Test that better matches get higher scores."""
        query = "vector database search"
        d3 = SAMPLE_CORPUS[2]  # About vector databases
        d10 = SAMPLE_CORPUS[9]  # About cloud computing
        
        score_d3 = self.reranker.score(query, d3)
        score_d10 = self.reranker.score(query, d10)
        
        self.assertGreater(score_d3, score_d10)
    
    def test_bigram_extraction(self):
        """Test bigram extraction."""
        bigrams = self.reranker._get_bigrams("python programming language")
        self.assertIn(("python", "programming"), bigrams)
        self.assertIn(("programming", "language"), bigrams)
    
    def test_term_proximity(self):
        """Test term proximity scoring."""
        # Terms close together
        doc_close = Document("close", "the vector database is fast")
        score_close = self.reranker._term_proximity(
            ["vector", "database"], doc_close.get_tokens()
        )
        
        # Terms far apart
        doc_far = Document("far", "vector machines are useful. " * 20 + "database stores data")
        score_far = self.reranker._term_proximity(
            ["vector", "database"], doc_far.get_tokens()
        )
        
        self.assertGreater(score_close, score_far)
    
    def test_rerank_order(self):
        """Test re-ranking puts most relevant first."""
        docs = [d for d in SAMPLE_CORPUS[:10]]
        results = self.reranker.rerank("machine learning training", docs)
        # d2 is about machine learning
        self.assertIn(results[0][0].doc_id, ["d2", "d12"])


class TestTwoStagePipeline(unittest.TestCase):
    """Test two-stage retrieval pipeline."""
    
    def setUp(self):
        self.bm25 = BM25Retriever()
        self.bm25.index(SAMPLE_CORPUS)
        self.vr = VectorRetriever()
        self.vr.index(SAMPLE_CORPUS)
    
    def test_bm25_hybrid_pipeline(self):
        """Test BM25 + Hybrid re-ranker pipeline."""
        reranker = HybridReranker(self.vr.idf_weights)
        pipeline = TwoStageRetrievalPipeline(
            retriever=self.bm25,
            reranker=reranker,
            coarse_top_n=10,
            final_top_k=3,
        )
        result = pipeline.search("python programming")
        
        # Coarse results may be fewer than requested if corpus is small
        self.assertGreater(len(result['coarse_results']), 0)
        self.assertLessEqual(len(result['final_results']), 3)
        self.assertIn('query', result)
    
    def test_bm25_mmr_pipeline(self):
        """Test BM25 + MMR pipeline."""
        reranker = MMRReranker(self.vr.idf_weights, alpha=0.7)
        pipeline = TwoStageRetrievalPipeline(
            retriever=self.bm25,
            reranker=reranker,
            coarse_top_n=10,
            final_top_k=3,
        )
        result = pipeline.search("vector database")
        
        self.assertEqual(len(result['final_results']), 3)
    
    def test_bm25_cross_encoder_pipeline(self):
        """Test BM25 + Cross-encoder pipeline."""
        reranker = CrossEncoderSimulator(self.vr.idf_weights)
        pipeline = TwoStageRetrievalPipeline(
            retriever=self.bm25,
            reranker=reranker,
            coarse_top_n=10,
            final_top_k=5,
        )
        result = pipeline.search("machine learning")
        
        self.assertLessEqual(len(result['final_results']), 5)
        # Results should be relevant
        doc_ids = [doc.doc_id for doc, _ in result['final_results']]
        self.assertIn("d2", doc_ids)  # ML document
    
    def test_coarse_results_not_empty(self):
        """Test that coarse retrieval returns results."""
        reranker = HybridReranker(self.vr.idf_weights)
        pipeline = TwoStageRetrievalPipeline(
            retriever=self.bm25,
            reranker=reranker,
            coarse_top_n=10,
            final_top_k=3,
        )
        result = pipeline.search("python")
        self.assertGreater(len(result['coarse_results']), 0)
    
    def test_final_results_subset_of_coarse(self):
        """Test that final results are a subset of coarse results."""
        reranker = HybridReranker(self.vr.idf_weights)
        pipeline = TwoStageRetrievalPipeline(
            retriever=self.bm25,
            reranker=reranker,
            coarse_top_n=10,
            final_top_k=3,
        )
        result = pipeline.search("python programming")
        
        coarse_ids = {doc.doc_id for doc, _ in result['coarse_results']}
        final_ids = {doc.doc_id for doc, _ in result['final_results']}
        self.assertTrue(final_ids.issubset(coarse_ids))


class TestRankingEvaluator(unittest.TestCase):
    """Test ranking evaluation metrics."""
    
    def test_dcg_at_k(self):
        """Test DCG computation."""
        # Perfect ranking: [3, 2, 1, 0]
        relevances = [3, 2, 1, 0]
        dcg = RankingEvaluator.dcg_at_k(relevances, 4)
        # DCG = (2^3-1)/log2(2) + (2^2-1)/log2(3) + (2^1-1)/log2(4) + 0
        expected = 7/1 + 3/1.585 + 1/2 + 0
        self.assertAlmostEqual(dcg, expected, places=3)
    
    def test_ndcg_perfect_ranking(self):
        """Test that perfect ranking gives NDCG=1.0."""
        judgments = {"d1": 3, "d2": 2, "d3": 1}
        ranked = ["d1", "d2", "d3"]  # Perfect order
        ndcg = RankingEvaluator.ndcg_at_k(ranked, judgments, k=3)
        self.assertAlmostEqual(ndcg, 1.0, places=5)
    
    def test_ndcg_worst_ranking(self):
        """Test NDCG for worst possible ranking."""
        judgments = {"d1": 3, "d2": 2, "d3": 1}
        ranked = ["d3", "d2", "d1"]  # Reverse order
        ndcg = RankingEvaluator.ndcg_at_k(ranked, judgments, k=3)
        self.assertLess(ndcg, 1.0)
    
    def test_mrr_first_position(self):
        """Test MRR when relevant doc is first."""
        judgments = {"d1": 3, "d2": 0}
        ranked = ["d1", "d2"]
        mrr = RankingEvaluator.mrr(ranked, judgments)
        self.assertEqual(mrr, 1.0)
    
    def test_mrr_second_position(self):
        """Test MRR when relevant doc is second."""
        judgments = {"d1": 0, "d2": 3}
        ranked = ["d1", "d2"]
        mrr = RankingEvaluator.mrr(ranked, judgments)
        self.assertAlmostEqual(mrr, 0.5, places=5)
    
    def test_mrr_no_relevant(self):
        """Test MRR when no relevant doc."""
        judgments = {"d1": 0, "d2": 0}
        ranked = ["d1", "d2"]
        mrr = RankingEvaluator.mrr(ranked, judgments)
        self.assertEqual(mrr, 0.0)
    
    def test_recall_at_k(self):
        """Test Recall@K."""
        judgments = {"d1": 3, "d2": 2, "d3": 1, "d4": 0}
        ranked = ["d1", "d4", "d2"]
        # 2 relevant in top-3 out of 3 total relevant
        recall = RankingEvaluator.recall_at_k(ranked, judgments, k=3, threshold=1)
        self.assertAlmostEqual(recall, 2/3, places=5)
    
    def test_precision_at_k(self):
        """Test Precision@K."""
        judgments = {"d1": 3, "d2": 0, "d3": 2, "d4": 0}
        ranked = ["d1", "d2", "d3", "d4"]
        # 2 relevant out of 4
        precision = RankingEvaluator.precision_at_k(ranked, judgments, k=4, threshold=1)
        self.assertAlmostEqual(precision, 0.5, places=5)
    
    def test_evaluate_all(self):
        """Test evaluate_all returns all metrics."""
        judgments = {"d1": 3, "d2": 2, "d3": 1, "d4": 0}
        ranked = ["d1", "d2", "d3", "d4"]
        metrics = RankingEvaluator.evaluate_all(ranked, judgments, k=3)
        
        self.assertIn('ndcg@3', metrics)
        self.assertIn('mrr', metrics)
        self.assertIn('recall@3', metrics)
        self.assertIn('precision@3', metrics)
    
    def test_ndcg_empty_judgments(self):
        """Test NDCG with empty judgments."""
        ndcg = RankingEvaluator.ndcg_at_k(["d1"], {}, k=1)
        self.assertEqual(ndcg, 0.0)


class TestEndToEndEvaluation(unittest.TestCase):
    """Test end-to-end evaluation of re-ranking strategies."""
    
    def test_evaluate_reranking_strategies(self):
        """Test that evaluation runs without errors."""
        results = evaluate_reranking_strategies(
            corpus=SAMPLE_CORPUS,
            queries=RELEVANCE_JUDGMENTS,
            k=5,
        )
        
        # Check all strategies present
        expected_strategies = [
            'bm25_only', 'bm25+lexical', 'bm25+semantic',
            'bm25+hybrid', 'bm25+cross_encoder', 'bm25+mmr'
        ]
        for strategy in expected_strategies:
            self.assertIn(strategy, results)
        
        # Check metrics present
        for strategy in expected_strategies:
            self.assertIn('avg_metrics', results[strategy])
            self.assertIn('ndcg@5', results[strategy]['avg_metrics'])
    
    def test_reranking_improves_or_matches_bm25(self):
        """Test that at least one re-ranking strategy improves over BM25-only."""
        results = evaluate_reranking_strategies(
            corpus=SAMPLE_CORPUS,
            queries=RELEVANCE_JUDGMENTS,
            k=5,
        )
        
        bm25_ndcg = results['bm25_only']['avg_metrics']['ndcg@5']
        best_rerank_ndcg = max(
            results[s]['avg_metrics']['ndcg@5']
            for s in results if s != 'bm25_only'
        )
        
        # Re-ranking should not hurt (at least match)
        self.assertGreaterEqual(best_rerank_ndcg, bm25_ndcg - 0.01)
    
    def test_print_report(self):
        """Test that report printing works."""
        results = evaluate_reranking_strategies(
            corpus=SAMPLE_CORPUS,
            queries=RELEVANCE_JUDGMENTS,
            k=5,
        )
        report = print_evaluation_report(results)
        self.assertIn("RERANKING STRATEGY", report)
        self.assertIn("ndcg@5", report)
    
    def test_all_queries_evaluated(self):
        """Test that all queries are evaluated."""
        results = evaluate_reranking_strategies(
            corpus=SAMPLE_CORPUS,
            queries=RELEVANCE_JUDGMENTS,
            k=5,
        )
        for strategy in results:
            self.assertEqual(len(results[strategy]['per_query']), len(RELEVANCE_JUDGMENTS))


# ============================================================
# Main: Run tests and demonstrate
# ============================================================

if __name__ == '__main__':
    print("=" * 70)
    print("RAG Exercise 5: Re-ranking (重排序)")
    print("=" * 70)
    
    # Run tests
    print("\n--- Running Tests ---\n")
    unittest.main(argv=['', '-v'], exit=False)
    
    # Demonstrate evaluation
    print("\n--- Re-ranking Strategy Evaluation ---\n")
    results = evaluate_reranking_strategies(SAMPLE_CORPUS, RELEVANCE_JUDGMENTS, k=5)
    report = print_evaluation_report(results)
    print(report)
    
    # Show example query results
    print("\n--- Example: Query 'vector database search' ---\n")
    bm25 = BM25Retriever()
    bm25.index(SAMPLE_CORPUS)
    vr = VectorRetriever()
    vr.index(SAMPLE_CORPUS)
    
    pipeline = TwoStageRetrievalPipeline(
        retriever=bm25,
        reranker=CrossEncoderSimulator(vr.idf_weights),
        coarse_top_n=10,
        final_top_k=5,
    )
    result = pipeline.search("vector database search")
    
    print("Stage 1 (Coarse - BM25 Top 10):")
    for doc, score in result['coarse_results']:
        print(f"  {doc.doc_id}: {score:.4f} - {doc.content[:60]}...")
    
    print("\nStage 2 (Fine - Cross-Encoder Top 5):")
    for doc, score in result['final_results']:
        print(f"  {doc.doc_id}: {score:.4f} - {doc.content[:60]}...")
    
    # Show MMR diversity comparison
    print("\n--- MMR Diversity Comparison ---\n")
    mmr_reranker = MMRReranker(vr.idf_weights, alpha=0.7)
    coarse = bm25.search("python programming", top_n=10)
    
    print("Pure relevance (alpha=1.0):")
    pure = MMRReranker(vr.idf_weights, alpha=1.0).rerank("python programming", coarse, top_k=5)
    for doc, score in pure:
        print(f"  {doc.doc_id}: {score:.4f} - {doc.content[:50]}...")
    
    print("\nMMR balanced (alpha=0.7):")
    balanced = mmr_reranker.rerank("python programming", coarse, top_k=5)
    for doc, score in balanced:
        print(f"  {doc.doc_id}: {score:.4f} - {doc.content[:50]}...")
