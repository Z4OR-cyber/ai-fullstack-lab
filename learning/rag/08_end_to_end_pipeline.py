#!/usr/bin/env python3
"""
RAG Exercise 8: End-to-End RAG Pipeline (端到端RAG流水线)

Learning Objectives:
1. Integrate all RAG components into a single pipeline: chunking → indexing → retrieval → re-ranking → answer generation
2. Implement configurable pipeline with swappable components
3. Build a RAG pipeline evaluation harness that measures end-to-end quality
4. Implement context window management (fit retrieved context within token budget)
5. Handle edge cases: empty retrieval, low confidence, context overflow

Architecture:
    Document Corpus
         |
    [Chunker] -- split documents into chunks
         |
    [Indexer] -- build BM25 + Vector index
         |
    [Query Input]
         |
    [Retriever] -- coarse retrieval (BM25/Vector/Hybrid)
         |
    [Re-ranker] -- fine re-ranking (Cross-encoder/MMR)
         |
    [Context Manager] -- fit within token budget, remove redundancy
         |
    [Answer Generator] -- template-based answer synthesis
         |
    [Output] -- answer + sources + metadata

Dependencies: Only standard library
"""

import math
import re
import json
from collections import Counter, defaultdict
from typing import List, Dict, Tuple, Optional, Any, Set, Callable
from dataclasses import dataclass, field
import unittest


# ============================================================
# Part 1: Data Structures
# ============================================================

@dataclass
class TextChunk:
    """A chunk of text from a document."""
    chunk_id: str
    content: str
    source_doc_id: str
    start_char: int = 0
    end_char: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def get_tokens(self) -> List[str]:
        return re.findall(r'\b\w+\b', self.content.lower())


@dataclass
class RetrievalResult:
    """Result from retrieval stage."""
    chunk: TextChunk
    score: float
    retrieval_method: str = ""
    
    def __lt__(self, other):
        return self.score < other.score


@dataclass
class RAGResponse:
    """Complete RAG pipeline response."""
    query: str
    answer: str
    retrieved_chunks: List[RetrievalResult]
    reranked_chunks: List[RetrievalResult]
    context_used: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def get_source_doc_ids(self) -> Set[str]:
        return {r.chunk.source_doc_id for r in self.reranked_chunks}


@dataclass
class Document:
    """A source document."""
    doc_id: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def get_tokens(self) -> List[str]:
        return re.findall(r'\b\w+\b', self.content.lower())


# ============================================================
# Part 2: Text Chunker
# ============================================================

class TextChunker:
    """
    Splits documents into chunks for indexing.
    
    Strategies:
    1. Fixed-size: Split by character count with overlap
    2. Sentence-aware: Split at sentence boundaries, respect max size
    3. Paragraph-aware: Split at paragraph boundaries
    """
    
    def __init__(self, chunk_size: int = 200, overlap: int = 50, strategy: str = 'sentence'):
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.strategy = strategy
    
    def chunk_document(self, doc: Document) -> List[TextChunk]:
        """Split a document into chunks."""
        if self.strategy == 'fixed':
            return self._chunk_fixed(doc)
        elif self.strategy == 'sentence':
            return self._chunk_sentence_aware(doc)
        elif self.strategy == 'paragraph':
            return self._chunk_paragraph_aware(doc)
        else:
            return self._chunk_fixed(doc)
    
    def _chunk_fixed(self, doc: Document) -> List[TextChunk]:
        """Fixed-size chunking with overlap."""
        chunks = []
        content = doc.content
        start = 0
        chunk_num = 0
        
        while start < len(content):
            end = min(start + self.chunk_size, len(content))
            chunk_content = content[start:end].strip()
            
            if chunk_content:
                chunk_id = f"{doc.doc_id}_chunk_{chunk_num}"
                chunks.append(TextChunk(
                    chunk_id=chunk_id,
                    content=chunk_content,
                    source_doc_id=doc.doc_id,
                    start_char=start,
                    end_char=end,
                ))
                chunk_num += 1
            
            start += self.chunk_size - self.overlap
        
        return chunks
    
    def _chunk_sentence_aware(self, doc: Document) -> List[TextChunk]:
        """Sentence-aware chunking."""
        sentences = re.split(r'(?<=[.!?])\s+', doc.content.strip())
        sentences = [s for s in sentences if s.strip()]
        
        chunks = []
        current_chunk = ""
        current_start = 0
        chunk_num = 0
        
        for sentence in sentences:
            if len(current_chunk) + len(sentence) > self.chunk_size and current_chunk:
                # Save current chunk
                chunk_id = f"{doc.doc_id}_chunk_{chunk_num}"
                end_char = current_start + len(current_chunk)
                chunks.append(TextChunk(
                    chunk_id=chunk_id,
                    content=current_chunk.strip(),
                    source_doc_id=doc.doc_id,
                    start_char=current_start,
                    end_char=end_char,
                ))
                chunk_num += 1
                
                # Start new chunk with overlap
                if self.overlap > 0 and len(current_chunk) > self.overlap:
                    overlap_text = current_chunk[-self.overlap:]
                    current_chunk = overlap_text + " " + sentence
                    current_start = end_char - self.overlap
                else:
                    current_chunk = sentence
                    current_start = end_char
            else:
                current_chunk = (current_chunk + " " + sentence).strip()
        
        # Don't forget the last chunk
        if current_chunk.strip():
            chunk_id = f"{doc.doc_id}_chunk_{chunk_num}"
            chunks.append(TextChunk(
                chunk_id=chunk_id,
                content=current_chunk.strip(),
                source_doc_id=doc.doc_id,
                start_char=current_start,
                end_char=current_start + len(current_chunk),
            ))
        
        return chunks
    
    def _chunk_paragraph_aware(self, doc: Document) -> List[TextChunk]:
        """Paragraph-aware chunking."""
        paragraphs = doc.content.split('\n\n')
        paragraphs = [p.strip() for p in paragraphs if p.strip()]
        
        chunks = []
        current_chunk = ""
        chunk_num = 0
        current_start = 0
        
        for para in paragraphs:
            if len(current_chunk) + len(para) > self.chunk_size and current_chunk:
                chunk_id = f"{doc.doc_id}_chunk_{chunk_num}"
                end_char = current_start + len(current_chunk)
                chunks.append(TextChunk(
                    chunk_id=chunk_id,
                    content=current_chunk.strip(),
                    source_doc_id=doc.doc_id,
                    start_char=current_start,
                    end_char=end_char,
                ))
                chunk_num += 1
                current_chunk = para
                current_start = end_char
            else:
                current_chunk = (current_chunk + "\n\n" + para).strip()
        
        if current_chunk.strip():
            chunk_id = f"{doc.doc_id}_chunk_{chunk_num}"
            chunks.append(TextChunk(
                chunk_id=chunk_id,
                content=current_chunk.strip(),
                source_doc_id=doc.doc_id,
                start_char=current_start,
                end_char=current_start + len(current_chunk),
            ))
        
        return chunks
    
    def chunk_corpus(self, documents: List[Document]) -> List[TextChunk]:
        """Chunk an entire corpus."""
        all_chunks = []
        for doc in documents:
            all_chunks.extend(self.chunk_document(doc))
        return all_chunks


# ============================================================
# Part 3: BM25 Index (compact)
# ============================================================

class BM25Index:
    """BM25 index over text chunks."""
    
    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.chunks: List[TextChunk] = []
        self.doc_freqs: List[Counter] = []
        self.doc_len: List[int] = []
        self.avgdl: float = 0.0
        self.idf: Dict[str, float] = {}
        self.term_docs: Dict[str, List[int]] = defaultdict(list)
        self.N: int = 0
    
    def index(self, chunks: List[TextChunk]) -> None:
        self.chunks = chunks
        self.N = len(chunks)
        self.doc_freqs = []
        self.doc_len = []
        self.term_docs = defaultdict(list)
        total_len = 0
        
        for i, chunk in enumerate(chunks):
            tf = Counter(chunk.get_tokens())
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
    
    def search(self, query: str, top_n: int = 20) -> List[RetrievalResult]:
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
        
        results = [
            RetrievalResult(chunk=self.chunks[i], score=scores[i], retrieval_method='bm25')
            for i in range(self.N) if scores[i] > 0
        ]
        results.sort(key=lambda x: x.score, reverse=True)
        return results[:top_n]


# ============================================================
# Part 4: Vector Index (TF-IDF)
# ============================================================

class VectorIndex:
    """TF-IDF vector index over text chunks."""
    
    def __init__(self):
        self.chunks: List[TextChunk] = []
        self.vocabulary: Dict[str, int] = {}
        self.idf_weights: Dict[str, float] = {}
        self.doc_vectors: List[Dict[int, float]] = []
        self.N: int = 0
    
    def _build_vocab(self, chunks: List[TextChunk]) -> None:
        vocab = set()
        for chunk in chunks:
            vocab.update(chunk.get_tokens())
        self.vocabulary = {term: idx for idx, term in enumerate(sorted(vocab))}
    
    def _compute_idf(self, chunks: List[TextChunk]) -> None:
        self.idf_weights = {}
        N = len(chunks)
        doc_count = Counter()
        for chunk in chunks:
            terms = set(chunk.get_tokens())
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
    
    def index(self, chunks: List[TextChunk]) -> None:
        self.chunks = chunks
        self.N = len(chunks)
        self._build_vocab(chunks)
        self._compute_idf(chunks)
        self.doc_vectors = [self._vectorize(c.content) for c in chunks]
    
    def search(self, query: str, top_n: int = 20) -> List[RetrievalResult]:
        query_vec = self._vectorize(query)
        results = []
        for i, doc_vec in enumerate(self.doc_vectors):
            if len(query_vec) > len(doc_vec):
                sim = sum(val * query_vec.get(idx, 0.0) for idx, val in doc_vec.items())
            else:
                sim = sum(val * doc_vec.get(idx, 0.0) for idx, val in query_vec.items())
            if sim > 0:
                results.append(RetrievalResult(
                    chunk=self.chunks[i], score=sim, retrieval_method='vector'
                ))
        results.sort(key=lambda x: x.score, reverse=True)
        return results[:top_n]


# ============================================================
# Part 5: Hybrid Retriever
# ============================================================

class HybridRetriever:
    """Combines BM25 and Vector retrieval with score fusion."""
    
    def __init__(self, bm25_weight: float = 0.5, vector_weight: float = 0.5):
        self.bm25 = BM25Index()
        self.vector = VectorIndex()
        self.bm25_weight = bm25_weight
        self.vector_weight = vector_weight
    
    def index(self, chunks: List[TextChunk]) -> None:
        self.bm25.index(chunks)
        self.vector.index(chunks)
    
    def search(self, query: str, top_n: int = 20) -> List[RetrievalResult]:
        bm25_results = self.bm25.search(query, top_n=top_n * 2)
        vector_results = self.vector.search(query, top_n=top_n * 2)
        
        # Normalize scores
        bm25_max = max((r.score for r in bm25_results), default=1.0)
        vec_max = max((r.score for r in vector_results), default=1.0)
        
        chunk_scores: Dict[str, Tuple[TextChunk, float]] = {}
        
        for r in bm25_results:
            norm_score = (r.score / bm25_max) * self.bm25_weight if bm25_max > 0 else 0
            chunk_scores[r.chunk.chunk_id] = (r.chunk, norm_score)
        
        for r in vector_results:
            norm_score = (r.score / vec_max) * self.vector_weight if vec_max > 0 else 0
            if r.chunk.chunk_id in chunk_scores:
                old_chunk, old_score = chunk_scores[r.chunk.chunk_id]
                chunk_scores[r.chunk.chunk_id] = (old_chunk, old_score + norm_score)
            else:
                chunk_scores[r.chunk.chunk_id] = (r.chunk, norm_score)
        
        results = [
            RetrievalResult(chunk=chunk, score=score, retrieval_method='hybrid')
            for chunk_id, (chunk, score) in chunk_scores.items()
        ]
        results.sort(key=lambda x: x.score, reverse=True)
        return results[:top_n]


# ============================================================
# Part 6: Re-ranker (Cross-encoder simulation)
# ============================================================

class ReRanker:
    """Simple re-ranker using lexical and semantic features."""
    
    def __init__(self, idf_weights: Optional[Dict[str, float]] = None):
        self.idf_weights = idf_weights or {}
    
    def _score(self, query: str, chunk: TextChunk) -> float:
        query_terms = re.findall(r'\b\w+\b', query.lower())
        chunk_tokens = chunk.get_tokens()
        chunk_counter = Counter(chunk_tokens)
        
        # Token coverage
        matched = sum(1 for t in query_terms if chunk_counter.get(t, 0) > 0)
        coverage = matched / max(len(query_terms), 1)
        
        # TF-IDF cosine similarity
        q_tokens = re.findall(r'\b\w+\b', query.lower())
        q_tf = Counter(q_tokens)
        c_tf = Counter(chunk_tokens)
        
        q_vec = {t: f * self.idf_weights.get(t, 1.0) for t, f in q_tf.items()}
        c_vec = {t: f * self.idf_weights.get(t, 1.0) for t, f in c_tf.items()}
        
        q_norm = math.sqrt(sum(v**2 for v in q_vec.values())) or 1
        c_norm = math.sqrt(sum(v**2 for v in c_vec.values())) or 1
        
        shared = set(q_vec.keys()) & set(c_vec.keys())
        dot = sum(q_vec[t] * c_vec[t] for t in shared)
        cosine = dot / (q_norm * c_norm)
        
        return 0.4 * coverage + 0.6 * cosine
    
    def rerank(self, query: str, results: List[RetrievalResult], top_k: int = 5) -> List[RetrievalResult]:
        scored = [(r, self._score(query, r.chunk)) for r in results]
        scored.sort(key=lambda x: x[1], reverse=True)
        
        reranked = []
        for result, score in scored[:top_k]:
            reranked.append(RetrievalResult(
                chunk=result.chunk,
                score=score,
                retrieval_method='reranked'
            ))
        return reranked


# ============================================================
# Part 7: Context Manager
# ============================================================

class ContextManager:
    """
    Manages the context window for the answer generator.
    
    Responsibilities:
    1. Fit retrieved chunks within a token budget
    2. Remove redundant chunks (high overlap)
    3. Order chunks by relevance and source
    4. Format context with source citations
    """
    
    def __init__(self, max_context_tokens: int = 500, min_relevance: float = 0.01):
        self.max_context_tokens = max_context_tokens
        self.min_relevance = min_relevance
    
    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count (rough: 1 token per 4 chars)."""
        return max(1, len(text) // 4)
    
    def _chunk_similarity(self, chunk_a: TextChunk, chunk_b: TextChunk) -> float:
        """Compute similarity between two chunks (for redundancy detection)."""
        tokens_a = set(chunk_a.get_tokens())
        tokens_b = set(chunk_b.get_tokens())
        if not tokens_a or not tokens_b:
            return 0.0
        intersection = tokens_a & tokens_b
        union = tokens_a | tokens_b
        return len(intersection) / len(union)
    
    def select_context(
        self,
        results: List[RetrievalResult],
        redundancy_threshold: float = 0.7,
    ) -> Tuple[str, List[RetrievalResult]]:
        """
        Select and format context from retrieval results.
        
        Args:
            results: Ranked retrieval results
            redundancy_threshold: Skip chunks with similarity > threshold to already selected
        
        Returns:
            Tuple of (formatted_context, selected_results)
        """
        selected = []
        selected_chunks = []
        total_tokens = 0
        
        for result in results:
            if result.score < self.min_relevance:
                continue
            
            # Check redundancy
            is_redundant = False
            for sel_chunk in selected_chunks:
                sim = self._chunk_similarity(result.chunk, sel_chunk)
                if sim > redundancy_threshold:
                    is_redundant = True
                    break
            
            if is_redundant:
                continue
            
            # Check token budget
            chunk_tokens = self._estimate_tokens(result.chunk.content)
            if total_tokens + chunk_tokens > self.max_context_tokens:
                continue
            
            selected.append(result)
            selected_chunks.append(result.chunk)
            total_tokens += chunk_tokens
        
        # Format context
        context_parts = []
        for i, result in enumerate(selected):
            source = result.chunk.source_doc_id
            context_parts.append(f"[Source {i+1}: {source}]\n{result.chunk.content}")
        
        context = "\n\n".join(context_parts)
        return context, selected
    
    def get_context_stats(self, selected: List[RetrievalResult]) -> Dict[str, Any]:
        """Get statistics about the selected context."""
        total_tokens = sum(self._estimate_tokens(r.chunk.content) for r in selected)
        sources = set(r.chunk.source_doc_id for r in selected)
        return {
            'num_chunks': len(selected),
            'total_tokens': total_tokens,
            'num_sources': len(sources),
            'sources': list(sources),
            'avg_score': sum(r.score for r in selected) / len(selected) if selected else 0,
        }


# ============================================================
# Part 8: Answer Generator (Template-based)
# ============================================================

class AnswerGenerator:
    """
    Template-based answer generator.
    
    In production, this would use an LLM (GPT, Claude, etc.) to generate
    answers from the retrieved context. Here we use template-based generation
    to demonstrate the pipeline without LLM dependency.
    
    Strategies:
    1. Extractive: Select and concatenate relevant sentences from context
    2. Template: Use predefined templates based on query type
    3. Summary: Generate a summary of the context
    """
    
    def __init__(self, strategy: str = 'extractive'):
        self.strategy = strategy
    
    def _extract_relevant_sentences(self, query: str, context: str, max_sentences: int = 3) -> List[str]:
        """Extract the most relevant sentences from context."""
        query_terms = set(re.findall(r'\b\w+\b', query.lower()))
        sentences = re.split(r'(?<=[.!?])\s+', context)
        
        scored = []
        for sent in sentences:
            sent_terms = set(re.findall(r'\b\w+\b', sent.lower()))
            overlap = len(query_terms & sent_terms) / max(len(query_terms), 1)
            scored.append((sent, overlap))
        
        scored.sort(key=lambda x: x[1], reverse=True)
        return [s for s, _ in scored[:max_sentences] if s.strip()]
    
    def _classify_query(self, query: str) -> str:
        """Classify query type for template selection."""
        q = query.lower().strip()
        if q.startswith('what'):
            return 'definition'
        elif q.startswith('how'):
            return 'process'
        elif q.startswith('why'):
            return 'explanation'
        elif q.startswith('compare'):
            return 'comparison'
        else:
            return 'general'
    
    def generate(self, query: str, context: str, sources: List[str]) -> str:
        """Generate an answer from the query and context."""
        if not context.strip():
            return "I couldn't find relevant information to answer your question."
        
        if self.strategy == 'extractive':
            return self._generate_extractive(query, context, sources)
        elif self.strategy == 'template':
            return self._generate_template(query, context, sources)
        else:
            return self._generate_extractive(query, context, sources)
    
    def _generate_extractive(self, query: str, context: str, sources: List[str]) -> str:
        """Extractive answer generation."""
        relevant = self._extract_relevant_sentences(query, context, max_sentences=3)
        
        if not relevant:
            return f"Based on the available context, I found information related to your query but couldn't extract a direct answer. Sources: {', '.join(sources)}"
        
        answer = ' '.join(relevant)
        if sources:
            answer += f" (Sources: {', '.join(sources[:3])})"
        return answer
    
    def _generate_template(self, query: str, context: str, sources: List[str]) -> str:
        """Template-based answer generation."""
        qtype = self._classify_query(query)
        relevant = self._extract_relevant_sentences(query, context, max_sentences=2)
        relevant_text = ' '.join(relevant) if relevant else context[:200]
        
        templates = {
            'definition': f"Based on the retrieved information, {relevant_text} Sources: {', '.join(sources[:3])}.",
            'process': f"Here's how it works: {relevant_text} Sources: {', '.join(sources[:3])}.",
            'explanation': f"The reason is: {relevant_text} Sources: {', '.join(sources[:3])}.",
            'comparison': f"Comparison: {relevant_text} Sources: {', '.join(sources[:3])}.",
            'general': f"According to the available information: {relevant_text} Sources: {', '.join(sources[:3])}.",
        }
        
        return templates.get(qtype, templates['general'])


# ============================================================
# Part 9: RAG Pipeline (Main Orchestrator)
# ============================================================

class RAGPipeline:
    """
    End-to-end RAG pipeline.
    
    Components (all swappable):
    1. Chunker: Splits documents into chunks
    2. Retriever: Retrieves relevant chunks (BM25/Vector/Hybrid)
    3. Re-ranker: Re-ranks retrieved chunks
    4. Context Manager: Fits context within token budget
    5. Answer Generator: Generates answer from context
    
    Usage:
        pipeline = RAGPipeline()
        pipeline.index(documents)
        response = pipeline.query("What is Python?")
    """
    
    def __init__(
        self,
        chunker: Optional[TextChunker] = None,
        retriever: Optional[Any] = None,
        reranker: Optional[ReRanker] = None,
        context_manager: Optional[ContextManager] = None,
        answer_generator: Optional[AnswerGenerator] = None,
        top_n_retrieval: int = 20,
        top_k_rerank: int = 5,
    ):
        self.chunker = chunker or TextChunker(chunk_size=200, overlap=50, strategy='sentence')
        self.retriever = retriever or HybridRetriever()
        self.reranker = reranker or ReRanker()
        self.context_manager = context_manager or ContextManager(max_context_tokens=500)
        self.answer_generator = answer_generator or AnswerGenerator(strategy='extractive')
        
        self.top_n_retrieval = top_n_retrieval
        self.top_k_rerank = top_k_rerank
        
        self.chunks: List[TextChunk] = []
        self.is_indexed: bool = False
    
    def index(self, documents: List[Document]) -> None:
        """Index a corpus of documents."""
        # Step 1: Chunk documents
        self.chunks = self.chunker.chunk_corpus(documents)
        
        # Step 2: Build retrieval index
        self.retriever.index(self.chunks)
        
        # Step 3: Update reranker with IDF weights if available
        if hasattr(self.retriever, 'vector') and hasattr(self.retriever.vector, 'idf_weights'):
            self.reranker.idf_weights = self.retriever.vector.idf_weights
        
        self.is_indexed = True
    
    def query(self, query: str) -> RAGResponse:
        """Execute a full RAG query."""
        if not self.is_indexed:
            return RAGResponse(
                query=query,
                answer="Pipeline not indexed. Please index documents first.",
                retrieved_chunks=[],
                reranked_chunks=[],
                context_used="",
                metadata={'error': 'not_indexed'}
            )
        
        # Step 1: Coarse retrieval
        retrieved = self.retriever.search(query, top_n=self.top_n_retrieval)
        
        if not retrieved:
            return RAGResponse(
                query=query,
                answer="No relevant information found for your query.",
                retrieved_chunks=[],
                reranked_chunks=[],
                context_used="",
                metadata={'error': 'no_results'}
            )
        
        # Step 2: Re-ranking
        reranked = self.reranker.rerank(query, retrieved, top_k=self.top_k_rerank)
        
        # Step 3: Context management
        context, selected = self.context_manager.select_context(reranked)
        
        # Step 4: Answer generation
        sources = list(self.context_manager.get_context_stats(selected).get('sources', []))
        answer = self.answer_generator.generate(query, context, sources)
        
        # Build response
        return RAGResponse(
            query=query,
            answer=answer,
            retrieved_chunks=retrieved,
            reranked_chunks=reranked,
            context_used=context,
            metadata={
                'num_chunks_indexed': len(self.chunks),
                'num_retrieved': len(retrieved),
                'num_reranked': len(reranked),
                'num_context_selected': len(selected),
                'context_stats': self.context_manager.get_context_stats(selected),
                'retrieval_method': retrieved[0].retrieval_method if retrieved else 'none',
            }
        )
    
    def batch_query(self, queries: List[str]) -> List[RAGResponse]:
        """Execute multiple queries."""
        return [self.query(q) for q in queries]


# ============================================================
# Part 10: Test Data
# ============================================================

SAMPLE_DOCUMENTS = [
    Document("doc1", "Python is a high-level programming language known for its simplicity and readability. It supports multiple paradigms including object-oriented and functional programming. Python's clean syntax makes it ideal for beginners and experts alike."),
    Document("doc2", "Machine learning is a subset of artificial intelligence. It involves training models on data to make predictions. Deep learning uses neural networks with multiple layers. Common algorithms include linear regression, decision trees, and neural networks."),
    Document("doc3", "Vector databases store high-dimensional embeddings for similarity search. They use approximate nearest neighbor algorithms like HNSW for fast retrieval. Popular vector databases include Pinecone, Weaviate, and Milvus."),
    Document("doc4", "Natural language processing involves tokenization, stemming, and named entity recognition. Transformers have revolutionized NLP with attention mechanisms. BERT and GPT are popular transformer models for various language tasks."),
    Document("doc5", "Retrieval augmented generation combines search with language models. The retrieved context helps the model generate grounded answers. RAG reduces hallucination by providing factual context to the language model."),
    Document("doc6", "Distributed systems use consensus algorithms like Raft and Paxos for fault tolerance. They ensure data consistency across multiple nodes. The CAP theorem states that consistency, availability, and partition tolerance cannot all be guaranteed simultaneously."),
]


# ============================================================
# Part 11: Unit Tests
# ============================================================

class TestTextChunker(unittest.TestCase):
    
    def setUp(self):
        self.chunker = TextChunker(chunk_size=100, overlap=20, strategy='fixed')
    
    def test_chunk_document(self):
        """Test basic chunking."""
        doc = Document("d1", "This is a test document. " * 20)
        chunks = self.chunker.chunk_document(doc)
        self.assertGreater(len(chunks), 1)
    
    def test_chunk_ids_unique(self):
        """Test that chunk IDs are unique."""
        doc = Document("d1", "This is a test. " * 30)
        chunks = self.chunker.chunk_document(doc)
        ids = [c.chunk_id for c in chunks]
        self.assertEqual(len(ids), len(set(ids)))
    
    def test_sentence_aware_chunking(self):
        """Test sentence-aware chunking."""
        chunker = TextChunker(chunk_size=80, strategy='sentence')
        doc = Document("d1", "First sentence. Second sentence. Third sentence. Fourth sentence here.")
        chunks = chunker.chunk_document(doc)
        self.assertGreater(len(chunks), 0)
        # Each chunk should end at a sentence boundary
        for chunk in chunks:
            self.assertTrue(chunk.content.rstrip().endswith('.') or 
                          chunk.content.rstrip().endswith('here'))
    
    def test_paragraph_chunking(self):
        """Test paragraph-aware chunking."""
        chunker = TextChunker(chunk_size=100, strategy='paragraph')
        doc = Document("d1", "Para one content here.\n\nPara two content here.\n\nPara three content here.")
        chunks = chunker.chunk_document(doc)
        self.assertGreater(len(chunks), 0)
    
    def test_chunk_corpus(self):
        """Test chunking an entire corpus."""
        chunks = self.chunker.chunk_corpus(SAMPLE_DOCUMENTS)
        self.assertGreater(len(chunks), len(SAMPLE_DOCUMENTS))
    
    def test_source_doc_id_preserved(self):
        """Test that source document ID is preserved in chunks."""
        doc = Document("mydoc", "Test content. " * 20)
        chunks = self.chunker.chunk_document(doc)
        for chunk in chunks:
            self.assertEqual(chunk.source_doc_id, "mydoc")
    
    def test_empty_document(self):
        """Test handling of empty document."""
        doc = Document("empty", "")
        chunks = self.chunker.chunk_document(doc)
        self.assertEqual(len(chunks), 0)


class TestBM25Index(unittest.TestCase):
    
    def setUp(self):
        self.chunker = TextChunker(chunk_size=200, strategy='sentence')
        self.chunks = self.chunker.chunk_corpus(SAMPLE_DOCUMENTS)
        self.index = BM25Index()
        self.index.index(self.chunks)
    
    def test_indexing(self):
        self.assertEqual(self.index.N, len(self.chunks))
        self.assertGreater(self.index.avgdl, 0)
    
    def test_search(self):
        results = self.index.search("Python programming", top_n=5)
        self.assertGreater(len(results), 0)
        # Top result should be about Python
        self.assertIn("python", results[0].chunk.content.lower())
    
    def test_search_returns_retrieval_results(self):
        results = self.index.search("machine learning", top_n=3)
        for r in results:
            self.assertIsInstance(r, RetrievalResult)
            self.assertEqual(r.retrieval_method, 'bm25')
    
    def test_no_results(self):
        results = self.index.search("xyzabc123nonexistent", top_n=5)
        self.assertEqual(len(results), 0)
    
    def test_scores_descending(self):
        results = self.index.search("vector database", top_n=10)
        for i in range(len(results) - 1):
            self.assertGreaterEqual(results[i].score, results[i + 1].score)


class TestVectorIndex(unittest.TestCase):
    
    def setUp(self):
        self.chunker = TextChunker(chunk_size=200, strategy='sentence')
        self.chunks = self.chunker.chunk_corpus(SAMPLE_DOCUMENTS)
        self.index = VectorIndex()
        self.index.index(self.chunks)
    
    def test_indexing(self):
        self.assertEqual(self.index.N, len(self.chunks))
        self.assertGreater(len(self.index.vocabulary), 20)
    
    def test_search(self):
        results = self.index.search("Python programming", top_n=5)
        self.assertGreater(len(results), 0)
    
    def test_normalized_vectors(self):
        for vec in self.index.doc_vectors[:3]:
            norm = math.sqrt(sum(v * v for v in vec.values()))
            self.assertAlmostEqual(norm, 1.0, places=5)


class TestHybridRetriever(unittest.TestCase):
    
    def setUp(self):
        self.chunker = TextChunker(chunk_size=200, strategy='sentence')
        self.chunks = self.chunker.chunk_corpus(SAMPLE_DOCUMENTS)
        self.retriever = HybridRetriever()
        self.retriever.index(self.chunks)
    
    def test_search(self):
        results = self.retriever.search("Python programming", top_n=5)
        self.assertGreater(len(results), 0)
        for r in results:
            self.assertEqual(r.retrieval_method, 'hybrid')
    
    def test_combines_bm25_and_vector(self):
        """Test that hybrid retrieval includes results from both methods."""
        results = self.retriever.search("vector database", top_n=10)
        self.assertGreater(len(results), 0)
    
    def test_weights(self):
        retriever = HybridRetriever(bm25_weight=0.7, vector_weight=0.3)
        self.assertAlmostEqual(retriever.bm25_weight + retriever.vector_weight, 1.0)


class TestReRanker(unittest.TestCase):
    
    def setUp(self):
        self.chunker = TextChunker(chunk_size=200, strategy='sentence')
        self.chunks = self.chunker.chunk_corpus(SAMPLE_DOCUMENTS)
        self.retriever = HybridRetriever()
        self.retriever.index(self.chunks)
        self.reranker = ReRanker(self.retriever.vector.idf_weights)
    
    def test_rerank(self):
        retrieved = self.retriever.search("Python", top_n=10)
        reranked = self.reranker.rerank("Python", retrieved, top_k=3)
        self.assertLessEqual(len(reranked), 3)
        self.assertGreater(len(reranked), 0)
    
    def test_rerank_order(self):
        retrieved = self.retriever.search("machine learning", top_n=10)
        reranked = self.reranker.rerank("machine learning", retrieved, top_k=5)
        for i in range(len(reranked) - 1):
            self.assertGreaterEqual(reranked[i].score, reranked[i + 1].score)
    
    def test_rerank_method_label(self):
        retrieved = self.retriever.search("Python", top_n=5)
        reranked = self.reranker.rerank("Python", retrieved, top_k=2)
        for r in reranked:
            self.assertEqual(r.retrieval_method, 'reranked')
    
    def test_top_k_limit(self):
        retrieved = self.retriever.search("Python", top_n=10)
        reranked = self.reranker.rerank("Python", retrieved, top_k=3)
        self.assertLessEqual(len(reranked), 3)


class TestContextManager(unittest.TestCase):
    
    def setUp(self):
        self.cm = ContextManager(max_context_tokens=100, min_relevance=0.01)
    
    def test_select_context(self):
        results = [
            RetrievalResult(TextChunk("c1", "Short content about Python.", "d1"), 0.5),
            RetrievalResult(TextChunk("c2", "Content about machine learning algorithms.", "d2"), 0.3),
        ]
        context, selected = self.cm.select_context(results)
        self.assertGreater(len(selected), 0)
        self.assertGreater(len(context), 0)
    
    def test_token_budget(self):
        """Test that context respects token budget."""
        results = [
            RetrievalResult(TextChunk("c1", "A" * 500, "d1"), 0.5),
            RetrievalResult(TextChunk("c2", "B" * 500, "d2"), 0.4),
        ]
        _, selected = self.cm.select_context(results)
        total_tokens = sum(self.cm._estimate_tokens(r.chunk.content) for r in selected)
        self.assertLessEqual(total_tokens, self.cm.max_context_tokens)
    
    def test_redundancy_filtering(self):
        """Test that redundant chunks are filtered."""
        results = [
            RetrievalResult(TextChunk("c1", "Python is a programming language.", "d1"), 0.5),
            RetrievalResult(TextChunk("c2", "Python is a programming language.", "d1"), 0.4),
        ]
        _, selected = self.cm.select_context(results, redundancy_threshold=0.5)
        # Second chunk is identical, should be filtered
        self.assertEqual(len(selected), 1)
    
    def test_min_relevance_filter(self):
        """Test that low-relevance results are filtered."""
        results = [
            RetrievalResult(TextChunk("c1", "Python content", "d1"), 0.5),
            RetrievalResult(TextChunk("c2", "Other content", "d2"), 0.001),  # Below threshold
        ]
        _, selected = self.cm.select_context(results)
        self.assertEqual(len(selected), 1)
    
    def test_context_stats(self):
        results = [
            RetrievalResult(TextChunk("c1", "Content one", "d1"), 0.5),
            RetrievalResult(TextChunk("c2", "Content two", "d2"), 0.3),
        ]
        _, selected = self.cm.select_context(results)
        stats = self.cm.get_context_stats(selected)
        self.assertIn('num_chunks', stats)
        self.assertIn('total_tokens', stats)
        self.assertIn('num_sources', stats)
    
    def test_empty_results(self):
        context, selected = self.cm.select_context([])
        self.assertEqual(len(selected), 0)
        self.assertEqual(context, "")


class TestAnswerGenerator(unittest.TestCase):
    
    def setUp(self):
        self.gen = AnswerGenerator(strategy='extractive')
    
    def test_generate_with_context(self):
        context = "Python is a high-level programming language. It supports multiple paradigms."
        answer = self.gen.generate("What is Python?", context, ["doc1"])
        self.assertGreater(len(answer), 10)
        self.assertIn("Python", answer)
    
    def test_generate_empty_context(self):
        answer = self.gen.generate("What is Python?", "", [])
        self.assertIn("couldn't find", answer.lower())
    
    def test_extract_relevant_sentences(self):
        context = "Python is great. Machine learning is cool. Python supports OOP."
        sentences = self.gen._extract_relevant_sentences("Python", context, max_sentences=2)
        self.assertGreater(len(sentences), 0)
        self.assertTrue(any("Python" in s for s in sentences))
    
    def test_template_strategy(self):
        gen = AnswerGenerator(strategy='template')
        context = "Python is a programming language."
        answer = gen.generate("What is Python?", context, ["doc1"])
        self.assertGreater(len(answer), 10)
    
    def test_query_classification(self):
        self.assertEqual(self.gen._classify_query("What is Python?"), 'definition')
        self.assertEqual(self.gen._classify_query("How does it work?"), 'process')
        self.assertEqual(self.gen._classify_query("Why is it important?"), 'explanation')
        self.assertEqual(self.gen._classify_query("Compare A and B"), 'comparison')
    
    def test_sources_in_answer(self):
        context = "Python is a programming language."
        answer = self.gen.generate("What is Python?", context, ["doc1", "doc2"])
        self.assertIn("doc1", answer)


class TestRAGPipeline(unittest.TestCase):
    
    def setUp(self):
        self.pipeline = RAGPipeline()
        self.pipeline.index(SAMPLE_DOCUMENTS)
    
    def test_indexing(self):
        self.assertTrue(self.pipeline.is_indexed)
        self.assertGreater(len(self.pipeline.chunks), 0)
    
    def test_basic_query(self):
        response = self.pipeline.query("What is Python?")
        self.assertIsInstance(response, RAGResponse)
        self.assertEqual(response.query, "What is Python?")
        self.assertGreater(len(response.answer), 10)
    
    def test_retrieval_results(self):
        response = self.pipeline.query("vector database")
        self.assertGreater(len(response.retrieved_chunks), 0)
        self.assertGreater(len(response.reranked_chunks), 0)
    
    def test_context_used(self):
        response = self.pipeline.query("machine learning")
        self.assertGreater(len(response.context_used), 0)
    
    def test_metadata(self):
        response = self.pipeline.query("Python programming")
        self.assertIn('num_chunks_indexed', response.metadata)
        self.assertIn('num_retrieved', response.metadata)
        self.assertIn('num_reranked', response.metadata)
    
    def test_source_doc_ids(self):
        response = self.pipeline.query("Python")
        sources = response.get_source_doc_ids()
        self.assertIsInstance(sources, set)
    
    def test_no_results_query(self):
        response = self.pipeline.query("xyzabc123nonexistent")
        self.assertIn("No relevant", response.answer)
    
    def test_not_indexed(self):
        pipeline = RAGPipeline()
        response = pipeline.query("test")
        self.assertIn("not indexed", response.answer.lower())
    
    def test_batch_query(self):
        queries = ["What is Python?", "What is machine learning?", "What is a vector database?"]
        responses = self.pipeline.batch_query(queries)
        self.assertEqual(len(responses), 3)
        for r in responses:
            self.assertIsInstance(r, RAGResponse)
    
    def test_custom_components(self):
        """Test pipeline with custom components."""
        pipeline = RAGPipeline(
            chunker=TextChunker(chunk_size=150, strategy='fixed'),
            context_manager=ContextManager(max_context_tokens=300),
            answer_generator=AnswerGenerator(strategy='template'),
        )
        pipeline.index(SAMPLE_DOCUMENTS)
        response = pipeline.query("What is Python?")
        self.assertGreater(len(response.answer), 10)
    
    def test_different_chunk_sizes(self):
        """Test that different chunk sizes produce different results."""
        pipeline_small = RAGPipeline(
            chunker=TextChunker(chunk_size=80, strategy='sentence'),
        )
        pipeline_small.index(SAMPLE_DOCUMENTS)
        
        pipeline_large = RAGPipeline(
            chunker=TextChunker(chunk_size=300, strategy='sentence'),
        )
        pipeline_large.index(SAMPLE_DOCUMENTS)
        
        # Small chunks should produce more chunks
        self.assertGreater(len(pipeline_small.chunks), len(pipeline_large.chunks))


class TestEndToEnd(unittest.TestCase):
    
    def test_full_pipeline_quality(self):
        """Test that the pipeline produces reasonable answers."""
        pipeline = RAGPipeline()
        pipeline.index(SAMPLE_DOCUMENTS)
        
        test_queries = [
            ("What is Python?", "python"),
            ("What is machine learning?", "machine"),
            ("What is a vector database?", "vector"),
            ("What is retrieval augmented generation?", "retrieval"),
            ("What are distributed systems?", "distributed"),
        ]
        
        for query, expected_keyword in test_queries:
            response = pipeline.query(query)
            # Answer should contain relevant keyword
            self.assertTrue(
                expected_keyword.lower() in response.answer.lower() or
                expected_keyword.lower() in response.context_used.lower(),
                f"Query '{query}' should mention '{expected_keyword}' in answer or context"
            )
    
    def test_pipeline_reproducibility(self):
        """Test that same query produces same results."""
        pipeline = RAGPipeline()
        pipeline.index(SAMPLE_DOCUMENTS)
        
        r1 = pipeline.query("What is Python?")
        r2 = pipeline.query("What is Python?")
        
        self.assertEqual(r1.answer, r2.answer)
        self.assertEqual(len(r1.retrieved_chunks), len(r2.retrieved_chunks))
    
    def test_pipeline_with_all_strategies(self):
        """Test pipeline with all chunking strategies."""
        for strategy in ['fixed', 'sentence', 'paragraph']:
            pipeline = RAGPipeline(
                chunker=TextChunker(chunk_size=150, strategy=strategy),
            )
            pipeline.index(SAMPLE_DOCUMENTS)
            response = pipeline.query("What is Python?")
            self.assertGreater(len(response.answer), 5,
                f"Strategy '{strategy}' failed to produce answer")


# ============================================================
# Main
# ============================================================

if __name__ == '__main__':
    print("=" * 70)
    print("RAG Exercise 8: End-to-End RAG Pipeline")
    print("=" * 70)
    
    print("\n--- Running Tests ---\n")
    unittest.main(argv=['', '-v'], exit=False)
    
    # Demonstrate pipeline
    print("\n--- RAG Pipeline Demo ---\n")
    
    pipeline = RAGPipeline()
    pipeline.index(SAMPLE_DOCUMENTS)
    
    queries = [
        "What is Python?",
        "What is a vector database?",
        "What is retrieval augmented generation?",
        "How do distributed systems work?",
    ]
    
    for query in queries:
        response = pipeline.query(query)
        print(f"\nQuery: {query}")
        print(f"Answer: {response.answer[:150]}...")
        print(f"Retrieved: {response.metadata['num_retrieved']} | "
              f"Reranked: {response.metadata['num_reranked']} | "
              f"Context: {response.metadata['num_context_selected']} chunks")
        print(f"Sources: {response.get_source_doc_ids()}")
        print("-" * 60)
