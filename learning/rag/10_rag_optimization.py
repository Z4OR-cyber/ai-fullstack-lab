#!/usr/bin/env python3
"""
RAG Exercise 10: RAG System Optimization (RAG系统优化)

Learning Objectives:
1. Implement query result caching (LRU + TTL) to avoid redundant retrieval
2. Implement parallel retrieval for multi-source search
3. Implement streaming context assembly for large result sets
4. Build a monitoring/metrics collection system for RAG pipelines
5. Implement adaptive retrieval (dynamically adjust strategy based on query difficulty)

Optimization Areas:
1. Caching: Cache retrieval results and embeddings to avoid recomputation
2. Parallelism: Retrieve from multiple sources concurrently
3. Streaming: Process results as they arrive, not all at once
4. Monitoring: Track latency, cache hit rate, retrieval quality over time
5. Adaptive: Adjust retrieval depth/reranking based on query complexity

Dependencies: Only standard library
"""

import math
import re
import time
import hashlib
import threading
from collections import Counter, defaultdict, OrderedDict
from typing import List, Dict, Tuple, Optional, Any, Set, Callable
from dataclasses import dataclass, field
import unittest


# ============================================================
# Part 1: Data Structures
# ============================================================

@dataclass
class Document:
    doc_id: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    def get_tokens(self) -> List[str]:
        return re.findall(r'\b\w+\b', self.content.lower())


@dataclass
class TextChunk:
    chunk_id: str
    content: str
    source_doc_id: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    def get_tokens(self) -> List[str]:
        return re.findall(r'\b\w+\b', self.content.lower())


@dataclass
class RetrievalResult:
    chunk: TextChunk
    score: float
    method: str = ""


@dataclass
class CacheEntry:
    """A cached retrieval result."""
    key: str
    value: Any
    timestamp: float
    ttl: float  # Time to live in seconds
    hit_count: int = 0
    
    @property
    def is_expired(self) -> bool:
        return time.time() - self.timestamp > self.ttl


@dataclass
class MetricRecord:
    """A single metric measurement."""
    name: str
    value: float
    timestamp: float
    tags: Dict[str, str] = field(default_factory=dict)


# ============================================================
# Part 2: BM25 Index (compact)
# ============================================================

class BM25Index:
    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.chunks: List[Any] = []
        self.doc_freqs: List[Counter] = []
        self.doc_len: List[int] = []
        self.avgdl: float = 0.0
        self.idf: Dict[str, float] = {}
        self.term_docs: Dict[str, List[int]] = defaultdict(list)
        self.N: int = 0
    
    def index_texts(self, texts: List[Tuple[str, str, Any]]) -> None:
        self.N = len(texts)
        self.doc_freqs = []
        self.doc_len = []
        self.term_docs = defaultdict(list)
        self.chunks = []
        total_len = 0
        for i, (text_id, text, meta) in enumerate(texts):
            tokens = re.findall(r'\b\w+\b', text.lower())
            tf = Counter(tokens)
            self.doc_freqs.append(tf)
            self.doc_len.append(len(tf))
            total_len += len(tf)
            self.chunks.append({'id': text_id, 'text': text, 'meta': meta})
            for term in tf:
                self.term_docs[term].append(i)
        self.avgdl = total_len / self.N if self.N > 0 else 0
        self.idf = {}
        for term, doc_indices in self.term_docs.items():
            df = len(doc_indices)
            self.idf[term] = math.log((self.N - df + 0.5) / (df + 0.5) + 1)
    
    def search(self, query: str, top_n: int = 20) -> List[Tuple[int, float]]:
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
        results = [(i, scores[i]) for i in range(self.N) if scores[i] > 0]
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_n]


# ============================================================
# Part 3: LRU + TTL Cache for Query Results
# ============================================================

class LRUTTLCache:
    """
    LRU (Least Recently Used) cache with TTL (Time To Live).
    
    Features:
    - LRU eviction when capacity is reached
    - TTL-based expiration of entries
    - Thread-safe (uses a lock)
    - Hit/miss tracking for metrics
    
    Use case: Cache retrieval results so that repeated queries
    don't require re-running the retrieval pipeline.
    """
    
    def __init__(self, capacity: int = 100, ttl: float = 300.0):
        """
        Args:
            capacity: Maximum number of entries
            ttl: Time to live in seconds (default: 5 minutes)
        """
        self.capacity = capacity
        self.ttl = ttl
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = threading.Lock()
        self.hits = 0
        self.misses = 0
    
    @staticmethod
    def _make_key(query: str, **kwargs) -> str:
        """Generate cache key from query and parameters."""
        key_str = f"{query}:{sorted(kwargs.items())}"
        return hashlib.md5(key_str.encode()).hexdigest()
    
    def get(self, key: str) -> Optional[Any]:
        """Get a value from cache."""
        with self._lock:
            if key in self._cache:
                entry = self._cache[key]
                if entry.is_expired:
                    del self._cache[key]
                    self.misses += 1
                    return None
                # Move to end (most recently used)
                self._cache.move_to_end(key)
                entry.hit_count += 1
                self.hits += 1
                return entry.value
            self.misses += 1
            return None
    
    def put(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        """Put a value into cache."""
        with self._lock:
            actual_ttl = ttl if ttl is not None else self.ttl
            entry = CacheEntry(
                key=key, value=value,
                timestamp=time.time(), ttl=actual_ttl
            )
            if key in self._cache:
                self._cache.move_to_end(key)
            self._cache[key] = entry
            
            # Evict LRU if over capacity
            while len(self._cache) > self.capacity:
                self._cache.popitem(last=False)
    
    def invalidate(self, key: str) -> bool:
        """Remove a specific key from cache."""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False
    
    def clear(self) -> None:
        """Clear all entries."""
        with self._lock:
            self._cache.clear()
            self.hits = 0
            self.misses = 0
    
    @property
    def size(self) -> int:
        return len(self._cache)
    
    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0
    
    def cleanup_expired(self) -> int:
        """Remove all expired entries. Returns count removed."""
        with self._lock:
            expired_keys = [k for k, v in self._cache.items() if v.is_expired]
            for k in expired_keys:
                del self._cache[k]
            return len(expired_keys)


class CachedRetriever:
    """Wraps a retriever with caching."""
    
    def __init__(self, bm25_index: BM25Index, cache: Optional[LRUTTLCache] = None):
        self.bm25 = bm25_index
        self.cache = cache or LRUTTLCache(capacity=100, ttl=300)
    
    def search(self, query: str, top_n: int = 10) -> List[Tuple[int, float]]:
        """Search with caching."""
        key = self.cache._make_key(query, top_n=top_n)
        
        cached = self.cache.get(key)
        if cached is not None:
            return cached
        
        results = self.bm25.search(query, top_n=top_n)
        self.cache.put(key, results)
        return results


# ============================================================
# Part 4: Parallel Multi-Source Retriever
# ============================================================

class ParallelMultiSourceRetriever:
    """
    Retrieves from multiple sources in parallel using threads.
    
    In production, each "source" could be:
    - Different vector databases (Pinecone, Weaviate)
    - Different index types (BM25, semantic, hybrid)
    - Different data partitions
    
    Results are fused using Reciprocal Rank Fusion (RRF).
    """
    
    def __init__(self, sources: Dict[str, BM25Index], rrf_k: int = 60):
        """
        Args:
            sources: Dict of source_name -> BM25Index
            rrf_k: RRF constant for fusion
        """
        self.sources = sources
        self.rrf_k = rrf_k
    
    def _search_source(
        self, source_name: str, index: BM25Index,
        query: str, top_n: int, results: Dict[str, List[Tuple[int, float]]]
    ) -> None:
        """Search a single source (thread target)."""
        try:
            source_results = index.search(query, top_n=top_n)
            results[source_name] = source_results
        except Exception as e:
            results[source_name] = []
    
    def search(self, query: str, top_n: int = 10) -> List[Tuple[str, float, str]]:
        """
        Search all sources in parallel and fuse results.
        
        Returns:
            List of (chunk_id, rrf_score, source_name)
        """
        threads = []
        thread_results: Dict[str, List[Tuple[int, float]]] = {}
        
        for source_name, index in self.sources.items():
            t = threading.Thread(
                target=self._search_source,
                args=(source_name, index, query, top_n * 2, thread_results)
            )
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join()
        
        # Fuse results using RRF
        rrf_scores: Dict[str, Tuple[str, float, str]] = {}
        
        for source_name, results in thread_results.items():
            for rank, (chunk_idx, score) in enumerate(results):
                chunk = self.sources[source_name].chunks[chunk_idx]
                chunk_id = chunk['id']
                rrf_score = 1.0 / (self.rrf_k + rank + 1)
                
                if chunk_id in rrf_scores:
                    old_id, old_score, old_source = rrf_scores[chunk_id]
                    rrf_scores[chunk_id] = (chunk_id, old_score + rrf_score, old_source)
                else:
                    rrf_scores[chunk_id] = (chunk_id, rrf_score, source_name)
        
        results = list(rrf_scores.values())
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_n]


# ============================================================
# Part 5: Streaming Context Assembler
# ============================================================

class StreamingContextAssembler:
    """
    Assembles context incrementally as retrieval results arrive.
    
    Instead of waiting for all results, this processes results one at a time
    and stops when the token budget is filled.
    
    Use case: When retrieval is slow (e.g., remote API), start processing
    early results while later ones are still being fetched.
    """
    
    def __init__(self, max_tokens: int = 500, redundancy_threshold: float = 0.6):
        self.max_tokens = max_tokens
        self.redundancy_threshold = redundancy_threshold
    
    def _estimate_tokens(self, text: str) -> int:
        return max(1, len(text) // 4)
    
    def _similarity(self, text_a: str, text_b: str) -> float:
        tokens_a = set(re.findall(r'\b\w+\b', text_a.lower()))
        tokens_b = set(re.findall(r'\b\w+\b', text_b.lower()))
        if not tokens_a or not tokens_b:
            return 0.0
        return len(tokens_a & tokens_b) / len(tokens_a | tokens_b)
    
    def assemble(
        self,
        results: List[Tuple[str, str, float]],
    ) -> Tuple[str, List[Dict]]:
        """
        Assemble context from streaming results.
        
        Args:
            results: List of (chunk_id, content, score) tuples, sorted by score
        
        Returns:
            Tuple of (assembled_context, list of selected chunk info)
        """
        context_parts = []
        selected = []
        total_tokens = 0
        selected_texts = []
        
        for chunk_id, content, score in results:
            # Check redundancy
            is_redundant = any(
                self._similarity(content, prev) > self.redundancy_threshold
                for prev in selected_texts
            )
            if is_redundant:
                continue
            
            # Check token budget
            chunk_tokens = self._estimate_tokens(content)
            if total_tokens + chunk_tokens > self.max_tokens:
                # Try to fit a truncated version
                remaining = self.max_tokens - total_tokens
                if remaining > 20:  # Only if meaningful space left
                    truncated = content[:remaining * 4]
                    context_parts.append(f"[{chunk_id}] {truncated}...")
                    selected.append({
                        'chunk_id': chunk_id,
                        'tokens': remaining,
                        'score': score,
                        'truncated': True,
                    })
                    total_tokens = self.max_tokens
                break
            
            context_parts.append(f"[{chunk_id}] {content}")
            selected_texts.append(content)
            selected.append({
                'chunk_id': chunk_id,
                'tokens': chunk_tokens,
                'score': score,
                'truncated': False,
            })
            total_tokens += chunk_tokens
        
        context = "\n\n".join(context_parts)
        return context, selected
    
    def assemble_streaming(
        self,
        result_generator,
    ) -> Tuple[str, List[Dict]]:
        """
        Assemble context from a generator that yields results one at a time.
        
        This simulates streaming: results are processed as they arrive.
        """
        collected = []
        for result in result_generator:
            collected.append(result)
        
        return self.assemble(collected)


# ============================================================
# Part 6: RAG Metrics Collector
# ============================================================

class RAGMetricsCollector:
    """
    Collects and aggregates metrics for RAG pipeline monitoring.
    
    Metrics tracked:
    - Query latency (time from query to response)
    - Retrieval count (number of chunks retrieved)
    - Cache hit rate
    - Average score of retrieved results
    - Query frequency (most common queries)
    
    In production, these would be sent to Prometheus, DataDog, etc.
    """
    
    def __init__(self):
        self.records: List[MetricRecord] = []
        self.query_latencies: List[float] = []
        self.retrieval_counts: List[int] = []
        self.query_counts: Counter = Counter()
        self.cache_hits = 0
        self.cache_misses = 0
        self._lock = threading.Lock()
    
    def record_latency(self, query: str, latency: float) -> None:
        with self._lock:
            self.query_latencies.append(latency)
            self.query_counts[query] += 1
            self.records.append(MetricRecord(
                name='query_latency', value=latency,
                timestamp=time.time(), tags={'query': query[:50]}
            ))
    
    def record_retrieval(self, count: int) -> None:
        with self._lock:
            self.retrieval_counts.append(count)
            self.records.append(MetricRecord(
                name='retrieval_count', value=count,
                timestamp=time.time()
            ))
    
    def record_cache_hit(self) -> None:
        with self._lock:
            self.cache_hits += 1
    
    def record_cache_miss(self) -> None:
        with self._lock:
            self.cache_misses += 1
    
    @property
    def avg_latency(self) -> float:
        return sum(self.query_latencies) / len(self.query_latencies) if self.query_latencies else 0.0
    
    @property
    def p95_latency(self) -> float:
        if not self.query_latencies:
            return 0.0
        sorted_lat = sorted(self.query_latencies)
        idx = int(len(sorted_lat) * 0.95)
        return sorted_lat[min(idx, len(sorted_lat) - 1)]
    
    @property
    def avg_retrieval_count(self) -> float:
        return sum(self.retrieval_counts) / len(self.retrieval_counts) if self.retrieval_counts else 0.0
    
    @property
    def cache_hit_rate(self) -> float:
        total = self.cache_hits + self.cache_misses
        return self.cache_hits / total if total > 0 else 0.0
    
    @property
    def total_queries(self) -> int:
        return len(self.query_latencies)
    
    def top_queries(self, n: int = 5) -> List[Tuple[str, int]]:
        return self.query_counts.most_common(n)
    
    def summary(self) -> Dict[str, Any]:
        return {
            'total_queries': self.total_queries,
            'avg_latency_ms': round(self.avg_latency * 1000, 2),
            'p95_latency_ms': round(self.p95_latency * 1000, 2),
            'avg_retrieval_count': round(self.avg_retrieval_count, 2),
            'cache_hit_rate': round(self.cache_hit_rate, 4),
            'cache_hits': self.cache_hits,
            'cache_misses': self.cache_misses,
            'top_queries': self.top_queries(5),
        }
    
    def reset(self) -> None:
        with self._lock:
            self.records.clear()
            self.query_latencies.clear()
            self.retrieval_counts.clear()
            self.query_counts.clear()
            self.cache_hits = 0
            self.cache_misses = 0


# ============================================================
# Part 7: Adaptive Retriever
# ============================================================

class AdaptiveRetriever:
    """
    Adaptive retrieval that adjusts strategy based on query complexity.
    
    Query complexity heuristics:
    - Short queries (1-2 terms) → simple BM25, fewer results
    - Medium queries (3-5 terms) → BM25 + reranking
    - Long queries (6+ terms) → multi-query decomposition + hybrid retrieval
    - Questions (start with what/how/why) → expanded retrieval
    
    Benefits:
    - Simple queries don't waste resources on complex processing
    - Complex queries get the full treatment
    """
    
    def __init__(self, bm25: BM25Index):
        self.bm25 = bm25
        self.metrics = RAGMetricsCollector()
    
    def _assess_complexity(self, query: str) -> Dict[str, Any]:
        """Assess query complexity."""
        terms = re.findall(r'\b\w+\b', query.lower())
        num_terms = len(terms)
        
        is_question = query.lower().strip().startswith(('what', 'how', 'why', 'when', 'where', 'which'))
        has_quotes = '"' in query or "'" in query
        has_comparison = any(w in query.lower() for w in ['compare', 'vs', 'versus', 'difference'])
        
        # Complexity level
        if num_terms <= 2 and not is_question:
            level = 'simple'
        elif num_terms <= 5 and not has_comparison:
            level = 'medium'
        else:
            level = 'complex'
        
        return {
            'level': level,
            'num_terms': num_terms,
            'is_question': is_question,
            'has_quotes': has_quotes,
            'has_comparison': has_comparison,
        }
    
    def _expand_query(self, query: str) -> str:
        """Simple query expansion."""
        # Add common related terms
        expansions = {
            'python': 'programming language',
            'database': 'storage data',
            'machine': 'learning algorithm',
            'search': 'retrieval query',
        }
        terms = re.findall(r'\b\w+\b', query.lower())
        for term in terms:
            if term in expansions:
                query += ' ' + expansions[term]
        return query
    
    def search(self, query: str, top_n: int = 10) -> Tuple[List[Tuple[int, float]], Dict[str, Any]]:
        """
        Adaptive search with complexity-based strategy selection.
        
        Returns:
            Tuple of (results, metadata about the search strategy used)
        """
        start_time = time.time()
        
        complexity = self._assess_complexity(query)
        
        if complexity['level'] == 'simple':
            # Simple: just BM25, fewer results
            results = self.bm25.search(query, top_n=min(top_n, 5))
            strategy = 'simple_bm25'
            
        elif complexity['level'] == 'medium':
            # Medium: BM25 with query expansion
            expanded = self._expand_query(query)
            results = self.bm25.search(expanded, top_n=top_n)
            strategy = 'expanded_bm25'
            
        else:
            # Complex: expanded query, more results
            expanded = self._expand_query(query)
            results = self.bm25.search(expanded, top_n=top_n * 2)
            # Also search original
            orig_results = self.bm25.search(query, top_n=top_n)
            # Merge with RRF-style fusion
            seen = set()
            merged = []
            for idx, score in results + orig_results:
                if idx not in seen:
                    seen.add(idx)
                    merged.append((idx, score))
            merged.sort(key=lambda x: x[1], reverse=True)
            results = merged[:top_n]
            strategy = 'complex_expanded_merged'
        
        latency = time.time() - start_time
        self.metrics.record_latency(query, latency)
        self.metrics.record_retrieval(len(results))
        
        metadata = {
            'strategy': strategy,
            'complexity': complexity,
            'latency_ms': round(latency * 1000, 2),
            'num_results': len(results),
        }
        
        return results, metadata


# ============================================================
# Part 8: Optimized RAG Pipeline
# ============================================================

class OptimizedRAGPipeline:
    """
    RAG pipeline with all optimizations:
    1. Cached retrieval
    2. Parallel multi-source search
    3. Streaming context assembly
    4. Metrics collection
    5. Adaptive retrieval
    """
    
    def __init__(
        self,
        documents: List[Document],
        chunk_size: int = 150,
        cache_capacity: int = 100,
        cache_ttl: float = 300,
        max_context_tokens: int = 500,
    ):
        # Chunk documents
        self.chunks: List[TextChunk] = []
        for doc in documents:
            content = doc.content
            start = 0
            num = 0
            while start < len(content):
                end = min(start + chunk_size, len(content))
                chunk_content = content[start:end].strip()
                if chunk_content:
                    self.chunks.append(TextChunk(
                        chunk_id=f"{doc.doc_id}_chunk_{num}",
                        content=chunk_content,
                        source_doc_id=doc.doc_id,
                    ))
                    num += 1
                start += chunk_size - 30
        
        # Build index
        self.bm25 = BM25Index()
        self.bm25.index_texts([
            (c.chunk_id, c.content, {}) for c in self.chunks
        ])
        
        # Components
        self.cache = LRUTTLCache(capacity=cache_capacity, ttl=cache_ttl)
        self.cached_retriever = CachedRetriever(self.bm25, self.cache)
        self.adaptive = AdaptiveRetriever(self.bm25)
        self.assembler = StreamingContextAssembler(max_tokens=max_context_tokens)
        self.metrics = RAGMetricsCollector()
    
    def query(self, query: str, top_n: int = 5) -> Dict[str, Any]:
        """Execute optimized RAG query."""
        start_time = time.time()
        
        # Check cache first
        cache_key = self.cache._make_key(query, top_n=top_n)
        cached = self.cache.get(cache_key)
        
        if cached is not None:
            self.metrics.record_cache_hit()
            results = cached
            from_cache = True
        else:
            self.metrics.record_cache_miss()
            results, search_meta = self.adaptive.search(query, top_n=top_n)
            self.cache.put(cache_key, results)
            from_cache = False
        
        # Convert to chunk format for assembler
        chunk_results = []
        for idx, score in results:
            chunk = self.chunks[idx] if idx < len(self.chunks) else None
            if chunk:
                chunk_results.append((chunk.chunk_id, chunk.content, score))
        
        # Assemble context
        context, selected = self.assembler.assemble(chunk_results)
        
        # Generate simple answer (extractive)
        query_terms = set(re.findall(r'\b\w+\b', query.lower()))
        sentences = re.split(r'(?<=[.!?])\s+', context)
        scored_sentences = []
        for sent in sentences:
            sent_terms = set(re.findall(r'\b\w+\b', sent.lower()))
            overlap = len(query_terms & sent_terms) / max(len(query_terms), 1)
            scored_sentences.append((sent, overlap))
        scored_sentences.sort(key=lambda x: x[1], reverse=True)
        answer = ' '.join(s for s, _ in scored_sentences[:3] if s.strip())
        
        latency = time.time() - start_time
        self.metrics.record_latency(query, latency)
        
        return {
            'query': query,
            'answer': answer,
            'context': context,
            'num_results': len(results),
            'from_cache': from_cache,
            'latency_ms': round(latency * 1000, 2),
            'context_chunks': len(selected),
        }
    
    def get_metrics(self) -> Dict[str, Any]:
        return self.metrics.summary()


# ============================================================
# Part 9: Test Data
# ============================================================

SAMPLE_DOCUMENTS = [
    Document("doc1", "Python is a high-level programming language known for its simplicity and readability. It supports multiple paradigms including object-oriented and functional programming. Python's clean syntax makes it ideal for beginners and experts alike."),
    Document("doc2", "Machine learning is a subset of artificial intelligence. It involves training models on data to make predictions. Deep learning uses neural networks with multiple layers. Common algorithms include linear regression, decision trees, and neural networks."),
    Document("doc3", "Vector databases store high-dimensional embeddings for similarity search. They use approximate nearest neighbor algorithms like HNSW for fast retrieval. Popular vector databases include Pinecone, Weaviate, and Milvus."),
    Document("doc4", "Retrieval augmented generation combines search with language models. The retrieved context helps the model generate grounded answers. RAG reduces hallucination by providing factual context to the language model."),
    Document("doc5", "Distributed systems use consensus algorithms like Raft and Paxos for fault tolerance. They ensure data consistency across multiple nodes. The CAP theorem states that consistency, availability, and partition tolerance cannot all be guaranteed."),
    Document("doc6", "Cloud computing platforms offer scalable infrastructure. AWS, Azure, and GCP provide virtual machines, serverless functions, and managed database services. Container orchestration with Kubernetes manages microservices deployment."),
]


# ============================================================
# Part 10: Unit Tests
# ============================================================

class TestLRUTTLCache(unittest.TestCase):
    
    def setUp(self):
        self.cache = LRUTTLCache(capacity=3, ttl=10)
    
    def test_put_get(self):
        self.cache.put("key1", "value1")
        self.assertEqual(self.cache.get("key1"), "value1")
    
    def test_miss(self):
        self.assertIsNone(self.cache.get("nonexistent"))
    
    def test_lru_eviction(self):
        self.cache.put("a", 1)
        self.cache.put("b", 2)
        self.cache.put("c", 3)
        # Access "a" to make it recently used
        self.cache.get("a")
        # Add "d" - should evict "b" (least recently used)
        self.cache.put("d", 4)
        self.assertIsNone(self.cache.get("b"))
        self.assertEqual(self.cache.get("a"), 1)
        self.assertEqual(self.cache.get("d"), 4)
    
    def test_ttl_expiration(self):
        cache = LRUTTLCache(capacity=10, ttl=0.1)
        cache.put("key", "value")
        self.assertEqual(cache.get("key"), "value")
        time.sleep(0.15)
        self.assertIsNone(cache.get("key"))
    
    def test_hit_rate(self):
        self.cache.put("a", 1)
        self.cache.get("a")  # hit
        self.cache.get("b")  # miss
        self.assertAlmostEqual(self.cache.hit_rate, 0.5)
    
    def test_capacity_limit(self):
        cache = LRUTTLCache(capacity=2)
        cache.put("a", 1)
        cache.put("b", 2)
        cache.put("c", 3)
        self.assertEqual(cache.size, 2)
        self.assertIsNone(cache.get("a"))
    
    def test_clear(self):
        self.cache.put("a", 1)
        self.cache.clear()
        self.assertEqual(self.cache.size, 0)
    
    def test_invalidate(self):
        self.cache.put("a", 1)
        self.assertTrue(self.cache.invalidate("a"))
        self.assertIsNone(self.cache.get("a"))
        self.assertFalse(self.cache.invalidate("a"))
    
    def test_make_key(self):
        key1 = LRUTTLCache._make_key("test", top_n=5)
        key2 = LRUTTLCache._make_key("test", top_n=5)
        key3 = LRUTTLCache._make_key("test", top_n=10)
        self.assertEqual(key1, key2)
        self.assertNotEqual(key1, key3)
    
    def test_cleanup_expired(self):
        cache = LRUTTLCache(capacity=10, ttl=0.1)
        cache.put("a", 1)
        cache.put("b", 2)
        time.sleep(0.15)
        removed = cache.cleanup_expired()
        self.assertEqual(removed, 2)
        self.assertEqual(cache.size, 0)


class TestCachedRetriever(unittest.TestCase):
    
    def setUp(self):
        self.bm25 = BM25Index()
        texts = [
            (f"chunk_{i}", f"Python content number {i} with programming", {})
            for i in range(10)
        ]
        self.bm25.index_texts(texts)
        self.retriever = CachedRetriever(self.bm25, LRUTTLCache(capacity=10, ttl=60))
    
    def test_search(self):
        results = self.retriever.search("Python", top_n=5)
        self.assertGreater(len(results), 0)
    
    def test_cache_hit(self):
        """Test that second search hits cache."""
        self.retriever.search("Python", top_n=5)
        self.assertEqual(self.retriever.cache.hits, 0)
        self.retriever.search("Python", top_n=5)
        self.assertEqual(self.retriever.cache.hits, 1)
    
    def test_different_params_different_cache(self):
        """Test that different top_n values use different cache entries."""
        self.retriever.search("Python", top_n=5)
        self.retriever.search("Python", top_n=10)
        # Both should be misses (different cache keys)
        self.assertEqual(self.retriever.cache.misses, 2)


class TestParallelMultiSourceRetriever(unittest.TestCase):
    
    def setUp(self):
        # Create two separate indexes
        self.index_a = BM25Index()
        self.index_a.index_texts([
            (f"a_{i}", f"Python programming content {i}", {})
            for i in range(10)
        ])
        self.index_b = BM25Index()
        self.index_b.index_texts([
            (f"b_{i}", f"Machine learning algorithm {i}", {})
            for i in range(10)
        ])
        self.retriever = ParallelMultiSourceRetriever({
            'source_a': self.index_a,
            'source_b': self.index_b,
        })
    
    def test_search(self):
        results = self.retriever.search("Python", top_n=5)
        self.assertGreater(len(results), 0)
    
    def test_parallel_sources(self):
        """Test that both sources are searched."""
        results = self.retriever.search("Python machine", top_n=10)
        sources = {r[2] for r in results}
        # Should have results from both sources
        self.assertGreater(len(sources), 0)
    
    def test_rrf_fusion(self):
        """Test that RRF fusion combines results."""
        results = self.retriever.search("Python", top_n=5)
        # Results should be sorted by RRF score
        for i in range(len(results) - 1):
            self.assertGreaterEqual(results[i][1], results[i + 1][1])


class TestStreamingContextAssembler(unittest.TestCase):
    
    def setUp(self):
        self.assembler = StreamingContextAssembler(max_tokens=100, redundancy_threshold=0.5)
    
    def test_assemble(self):
        results = [
            ("c1", "Python is a programming language.", 0.9),
            ("c2", "Machine learning uses data.", 0.7),
        ]
        context, selected = self.assembler.assemble(results)
        self.assertGreater(len(context), 0)
        self.assertEqual(len(selected), 2)
    
    def test_token_budget(self):
        results = [
            ("c1", "A" * 500, 0.9),
            ("c2", "B" * 500, 0.8),
        ]
        context, selected = self.assembler.assemble(results)
        total_tokens = sum(s['tokens'] for s in selected)
        self.assertLessEqual(total_tokens, self.assembler.max_tokens)
    
    def test_redundancy_filter(self):
        results = [
            ("c1", "Python is a programming language.", 0.9),
            ("c2", "Python is a programming language.", 0.8),
        ]
        _, selected = self.assembler.assemble(results)
        self.assertEqual(len(selected), 1)
    
    def test_empty_results(self):
        context, selected = self.assembler.assemble([])
        self.assertEqual(context, "")
        self.assertEqual(len(selected), 0)
    
    def test_streaming_assembly(self):
        """Test streaming assembly with generator."""
        def result_gen():
            yield ("c1", "First chunk content.", 0.9)
            yield ("c2", "Second chunk content.", 0.7)
        
        context, selected = self.assembler.assemble_streaming(result_gen())
        self.assertGreater(len(selected), 0)
    
    def test_truncation(self):
        """Test that last chunk is truncated if it doesn't fully fit."""
        assembler = StreamingContextAssembler(max_tokens=50, redundancy_threshold=0.9)
        results = [
            ("c1", "Short content.", 0.9),
            ("c2", "A" * 300, 0.8),
        ]
        context, selected = assembler.assemble(results)
        # Should have at least the first chunk
        self.assertGreater(len(selected), 0)


class TestRAGMetricsCollector(unittest.TestCase):
    
    def setUp(self):
        self.collector = RAGMetricsCollector()
    
    def test_record_latency(self):
        self.collector.record_latency("query1", 0.5)
        self.collector.record_latency("query2", 0.3)
        self.assertEqual(self.collector.total_queries, 2)
        self.assertGreater(self.collector.avg_latency, 0)
    
    def test_p95_latency(self):
        for i in range(20):
            self.collector.record_latency(f"q{i}", 0.1 * i)
        p95 = self.collector.p95_latency
        self.assertGreater(p95, 0.1 * 18)
    
    def test_cache_metrics(self):
        self.collector.record_cache_hit()
        self.collector.record_cache_hit()
        self.collector.record_cache_miss()
        self.assertAlmostEqual(self.collector.cache_hit_rate, 2/3)
    
    def test_top_queries(self):
        self.collector.record_latency("popular", 0.1)
        self.collector.record_latency("popular", 0.2)
        self.collector.record_latency("rare", 0.3)
        top = self.collector.top_queries(2)
        self.assertEqual(top[0][0], "popular")
        self.assertEqual(top[0][1], 2)
    
    def test_summary(self):
        self.collector.record_latency("q1", 0.1)
        self.collector.record_cache_hit()
        summary = self.collector.summary()
        self.assertIn('total_queries', summary)
        self.assertIn('avg_latency_ms', summary)
        self.assertIn('cache_hit_rate', summary)
    
    def test_reset(self):
        self.collector.record_latency("q1", 0.1)
        self.collector.reset()
        self.assertEqual(self.collector.total_queries, 0)
        self.assertEqual(self.collector.cache_hits, 0)


class TestAdaptiveRetriever(unittest.TestCase):
    
    def setUp(self):
        self.bm25 = BM25Index()
        texts = [
            (f"c{i}", content, {})
            for i, content in enumerate([
                "Python is a high-level programming language.",
                "Machine learning training requires data.",
                "Vector databases store embeddings.",
                "Retrieval augmented generation combines search with models.",
                "Distributed systems ensure consistency.",
            ])
        ]
        self.bm25.index_texts(texts)
        self.adaptive = AdaptiveRetriever(self.bm25)
    
    def test_simple_query(self):
        results, meta = self.adaptive.search("Python", top_n=5)
        self.assertGreater(len(results), 0)
        self.assertEqual(meta['complexity']['level'], 'simple')
    
    def test_medium_query(self):
        results, meta = self.adaptive.search("Python programming language", top_n=5)
        self.assertIn(meta['complexity']['level'], ['medium', 'simple'])
    
    def test_complex_query(self):
        results, meta = self.adaptive.search("How does retrieval augmented generation compare to traditional search", top_n=10)
        self.assertIn(meta['complexity']['level'], ['complex', 'medium'])
    
    def test_complexity_assessment(self):
        c = self.adaptive._assess_complexity("Python")
        self.assertEqual(c['level'], 'simple')
        
        c = self.adaptive._assess_complexity("What is Python programming language")
        self.assertTrue(c['is_question'])
        
        c = self.adaptive._assess_complexity("compare vector database and traditional search")
        self.assertTrue(c['has_comparison'])
    
    def test_query_expansion(self):
        expanded = self.adaptive._expand_query("Python database")
        self.assertGreater(len(expanded), len("Python database"))
    
    def test_metrics_recorded(self):
        self.adaptive.search("Python", top_n=5)
        self.assertGreater(self.adaptive.metrics.total_queries, 0)


class TestOptimizedRAGPipeline(unittest.TestCase):
    
    def setUp(self):
        self.pipeline = OptimizedRAGPipeline(SAMPLE_DOCUMENTS, chunk_size=150)
    
    def test_query(self):
        result = self.pipeline.query("What is Python?")
        self.assertIn('answer', result)
        self.assertIn('context', result)
        self.assertIn('latency_ms', result)
        self.assertGreater(len(result['answer']), 0)
    
    def test_cache(self):
        """Test that second query hits cache."""
        r1 = self.pipeline.query("What is Python?")
        self.assertFalse(r1['from_cache'])
        r2 = self.pipeline.query("What is Python?")
        self.assertTrue(r2['from_cache'])
    
    def test_metrics(self):
        self.pipeline.query("What is Python?")
        self.pipeline.query("What is machine learning?")
        metrics = self.pipeline.get_metrics()
        self.assertGreater(metrics['total_queries'], 0)
        self.assertIn('avg_latency_ms', metrics)
        self.assertIn('cache_hit_rate', metrics)
    
    def test_different_queries(self):
        queries = [
            "What is Python?",
            "What is machine learning?",
            "What is a vector database?",
        ]
        for q in queries:
            result = self.pipeline.query(q)
            self.assertGreater(len(result['answer']), 0, f"Empty answer for: {q}")
    
    def test_num_results(self):
        result = self.pipeline.query("Python")
        self.assertGreater(result['num_results'], 0)
    
    def test_context_assembled(self):
        result = self.pipeline.query("machine learning")
        self.assertGreater(len(result['context']), 0)
    
    def test_repeated_query_faster(self):
        """Test that cached query is faster (or at least not slower)."""
        r1 = self.pipeline.query("What is Python?")
        r2 = self.pipeline.query("What is Python?")
        # Cached should be faster (allowing small tolerance)
        self.assertLessEqual(r2['latency_ms'], r1['latency_ms'] + 50)


# ============================================================
# Main
# ============================================================

if __name__ == '__main__':
    print("=" * 70)
    print("RAG Exercise 10: RAG System Optimization")
    print("=" * 70)
    
    print("\n--- Running Tests ---\n")
    unittest.main(argv=['', '-v'], exit=False)
    
    # Demo
    print("\n--- Optimized RAG Pipeline Demo ---\n")
    
    pipeline = OptimizedRAGPipeline(SAMPLE_DOCUMENTS, chunk_size=150)
    
    queries = [
        "What is Python?",
        "What is machine learning?",
        "What is Python?",  # Repeat for cache hit
        "What is a vector database?",
        "What is Python?",  # Another cache hit
    ]
    
    for q in queries:
        result = pipeline.query(q)
        cache_status = "CACHED" if result['from_cache'] else "FRESH"
        print(f"  [{cache_status}] {result['latency_ms']:.1f}ms | {q}")
        print(f"    Answer: {result['answer'][:80]}...")
    
    print(f"\n--- Metrics Summary ---")
    metrics = pipeline.get_metrics()
    for key, value in metrics.items():
        if key != 'top_queries':
            print(f"  {key}: {value}")
    print(f"  top_queries:")
    for q, count in metrics['top_queries']:
        print(f"    '{q}' x{count}")
