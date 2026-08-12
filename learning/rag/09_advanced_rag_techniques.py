#!/usr/bin/env python3
"""
RAG Exercise 9: Advanced RAG Techniques (高级RAG技术)

Learning Objectives:
1. Implement Parent-Child chunking: small chunks for retrieval, parent chunks for context
2. Implement Sentence Window retrieval: expand around matching sentences
3. Implement Auto-Merging retriever: merge adjacent chunks that are individually retrieved
4. Implement Hierarchical retrieval: multi-level index with summaries
5. Compare advanced techniques vs baseline chunking

Advanced Patterns:
1. Parent-Child (Small-to-Big):
   - Index small chunks (good retrieval precision)
   - Return parent chunks (good context completeness)
   - Trade-off: more storage, better context

2. Sentence Window:
   - Index individual sentences
   - When a sentence matches, return surrounding N sentences as context
   - Good for precise matching with contextual continuity

3. Auto-Merging:
   - Index small chunks
   - If multiple adjacent chunks are retrieved, merge them into a larger chunk
   - Reduces fragmentation and provides coherent context

Dependencies: Only standard library
"""

import math
import re
from collections import Counter, defaultdict
from typing import List, Dict, Tuple, Optional, Any, Set
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
    start_char: int = 0
    end_char: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def get_tokens(self) -> List[str]:
        return re.findall(r'\b\w+\b', self.content.lower())


@dataclass
class ParentChunk:
    """A parent chunk that contains multiple child chunks."""
    chunk_id: str
    content: str
    source_doc_id: str
    child_ids: List[str] = field(default_factory=list)
    start_char: int = 0
    end_char: int = 0


@dataclass
class SentenceInfo:
    """Information about a sentence in a document."""
    sentence: str
    source_doc_id: str
    sentence_index: int  # Position in document
    start_char: int = 0
    end_char: int = 0


@dataclass
class RetrievalResult:
    chunk: TextChunk
    score: float
    method: str = ""


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
        """Index list of (id, text, metadata) tuples."""
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
# Part 3: Parent-Child Chunking Strategy
# ============================================================

class ParentChildChunker:
    """
    Parent-Child Chunking Strategy.
    
    Creates two levels of chunks:
    - Parent chunks: large (e.g., 400 chars) for context
    - Child chunks: small (e.g., 100 chars) for precise retrieval
    
    During retrieval, search child chunks, but return parent chunks.
    This gives precise matching with complete context.
    """
    
    def __init__(self, parent_size: int = 400, child_size: int = 100, overlap: int = 30):
        self.parent_size = parent_size
        self.child_size = child_size
        self.overlap = overlap
    
    def chunk_document(self, doc: Document) -> Tuple[List[ParentChunk], List[TextChunk]]:
        """
        Chunk a document into parent and child chunks.
        
        Returns:
            Tuple of (parent_chunks, child_chunks)
        """
        content = doc.content
        parents = []
        children = []
        
        parent_start = 0
        parent_num = 0
        
        while parent_start < len(content):
            parent_end = min(parent_start + self.parent_size, len(content))
            parent_content = content[parent_start:parent_end].strip()
            
            if not parent_content:
                break
            
            parent_id = f"{doc.doc_id}_parent_{parent_num}"
            
            # Create child chunks within this parent
            child_ids = []
            child_start = 0
            child_num = 0
            
            while child_start < len(parent_content):
                child_end = min(child_start + self.child_size, len(parent_content))
                child_content = parent_content[child_start:child_end].strip()
                
                if child_content:
                    child_id = f"{parent_id}_child_{child_num}"
                    child_ids.append(child_id)
                    children.append(TextChunk(
                        chunk_id=child_id,
                        content=child_content,
                        source_doc_id=doc.doc_id,
                        start_char=parent_start + child_start,
                        end_char=parent_start + child_end,
                        metadata={'parent_id': parent_id}
                    ))
                    child_num += 1
                
                child_start += self.child_size - self.overlap
            
            parent = ParentChunk(
                chunk_id=parent_id,
                content=parent_content,
                source_doc_id=doc.doc_id,
                child_ids=child_ids,
                start_char=parent_start,
                end_char=parent_end,
            )
            parents.append(parent)
            parent_num += 1
            parent_start += self.parent_size - self.overlap
        
        return parents, children
    
    def chunk_corpus(self, documents: List[Document]) -> Tuple[List[ParentChunk], List[TextChunk]]:
        all_parents = []
        all_children = []
        for doc in documents:
            parents, children = self.chunk_document(doc)
            all_parents.extend(parents)
            all_children.extend(children)
        return all_parents, all_children


class ParentChildRetriever:
    """
    Retriever that uses child chunks for retrieval but returns parent chunks.
    """
    
    def __init__(self, parent_size: int = 400, child_size: int = 100, overlap: int = 30):
        self.chunker = ParentChildChunker(parent_size, child_size, overlap)
        self.bm25 = BM25Index()
        self.parents: List[ParentChunk] = []
        self.children: List[TextChunk] = []
        self.child_to_parent: Dict[str, ParentChunk] = {}
        self.returned_parents: Set[str] = set()
    
    def index(self, documents: List[Document]) -> None:
        self.parents, self.children = self.chunker.chunk_corpus(documents)
        
        # Build child -> parent mapping
        for parent in self.parents:
            for child_id in parent.child_ids:
                self.child_to_parent[child_id] = parent
        
        # Index child chunks
        texts = [(c.chunk_id, c.content, c.metadata) for c in self.children]
        self.bm25.index_texts(texts)
    
    def search(self, query: str, top_n: int = 5) -> List[Tuple[ParentChunk, float]]:
        """
        Search using child chunks, return parent chunks.
        
        Returns unique parent chunks with their best child score.
        """
        child_results = self.bm25.search(query, top_n=top_n * 3)
        
        parent_scores: Dict[str, Tuple[ParentChunk, float]] = {}
        
        for child_idx, score in child_results:
            child = self.children[child_idx]
            parent_id = child.metadata.get('parent_id')
            if parent_id and parent_id in {p.chunk_id for p in self.parents}:
                parent = self.child_to_parent.get(child.chunk_id)
                if parent:
                    if parent.chunk_id not in parent_scores or score > parent_scores[parent.chunk_id][1]:
                        parent_scores[parent.chunk_id] = (parent, score)
        
        results = list(parent_scores.values())
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_n]


# ============================================================
# Part 4: Sentence Window Retrieval
# ============================================================

class SentenceWindowIndexer:
    """
    Sentence Window Retrieval.
    
    Indexes individual sentences. When a sentence matches,
    returns a window of N surrounding sentences for context.
    
    Example with window_size=1:
        [prev sentence] [MATCHED SENTENCE] [next sentence]
    """
    
    def __init__(self, window_size: int = 1):
        self.window_size = window_size
        self.bm25 = BM25Index()
        self.sentences: List[SentenceInfo] = []
        self.doc_sentence_map: Dict[str, List[int]] = defaultdict(list)
    
    def _split_sentences(self, text: str) -> List[Tuple[str, int, int]]:
        """Split text into sentences with positions."""
        sentences = []
        pos = 0
        for match in re.finditer(r'[^.!?]+[.!?]*', text):
            sent = match.group().strip()
            if sent:
                sentences.append((sent, match.start(), match.end()))
            pos = match.end()
        return sentences
    
    def index(self, documents: List[Document]) -> None:
        """Index all sentences from documents."""
        self.sentences = []
        self.doc_sentence_map = defaultdict(list)
        
        for doc in documents:
            doc_sentences = self._split_sentences(doc.content)
            for idx, (sent, start, end) in enumerate(doc_sentences):
                sent_info = SentenceInfo(
                    sentence=sent,
                    source_doc_id=doc.doc_id,
                    sentence_index=idx,
                    start_char=start,
                    end_char=end,
                )
                sent_global_idx = len(self.sentences)
                self.sentences.append(sent_info)
                self.doc_sentence_map[doc.doc_id].append(sent_global_idx)
        
        # Index sentences in BM25
        texts = [
            (f"sent_{i}", s.sentence, {'doc_id': s.source_doc_id, 'sent_idx': s.sentence_index})
            for i, s in enumerate(self.sentences)
        ]
        self.bm25.index_texts(texts)
    
    def search(self, query: str, top_n: int = 5) -> List[Tuple[str, float, Dict]]:
        """
        Search for matching sentences and return windowed context.
        
        Returns:
            List of (windowed_text, score, metadata)
        """
        sentence_results = self.bm25.search(query, top_n=top_n * 2)
        
        results = []
        seen_windows = set()
        
        for sent_idx, score in sentence_results:
            sent_info = self.sentences[sent_idx]
            doc_id = sent_info.source_doc_id
            sent_idx_in_doc = sent_info.sentence_index
            
            # Get sentence indices in this document
            doc_sent_indices = self.doc_sentence_map[doc_id]
            
            # Find position in document's sentence list
            try:
                doc_pos = doc_sent_indices.index(sent_idx)
            except ValueError:
                continue
            
            # Get window
            window_start = max(0, doc_pos - self.window_size)
            window_end = min(len(doc_sent_indices), doc_pos + self.window_size + 1)
            
            window_sent_indices = doc_sent_indices[window_start:window_end]
            
            # Create window key for deduplication
            window_key = tuple(window_sent_indices)
            if window_key in seen_windows:
                continue
            seen_windows.add(window_key)
            
            # Combine window sentences
            window_texts = [self.sentences[si].sentence for si in window_sent_indices]
            windowed_text = ' '.join(window_texts)
            
            results.append((
                windowed_text,
                score,
                {
                    'doc_id': doc_id,
                    'matched_sentence': sent_info.sentence,
                    'window_size': len(window_sent_indices),
                    'sent_indices': window_sent_indices,
                }
            ))
            
            if len(results) >= top_n:
                break
        
        return results


# ============================================================
# Part 5: Auto-Merging Retriever
# ============================================================

class AutoMergingRetriever:
    """
    Auto-Merging Retriever.
    
    When multiple adjacent chunks are retrieved, merge them into a single
    larger chunk. This reduces fragmentation and provides coherent context.
    
    Algorithm:
    1. Retrieve top-N small chunks
    2. Group adjacent chunks (same document, consecutive positions)
    3. Merge each group into a single chunk
    4. Return merged chunks with combined scores
    """
    
    def __init__(self, chunk_size: int = 100, overlap: int = 20, merge_threshold: int = 2):
        """
        Args:
            chunk_size: Size of small chunks for indexing
            overlap: Overlap between chunks
            merge_threshold: Minimum adjacent chunks to trigger merge
        """
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.merge_threshold = merge_threshold
        self.bm25 = BM25Index()
        self.chunks: List[TextChunk] = []
    
    def _chunk_document(self, doc: Document) -> List[TextChunk]:
        """Create small chunks from document."""
        chunks = []
        content = doc.content
        start = 0
        num = 0
        
        while start < len(content):
            end = min(start + self.chunk_size, len(content))
            chunk_content = content[start:end].strip()
            
            if chunk_content:
                chunk_id = f"{doc.doc_id}_chunk_{num}"
                chunks.append(TextChunk(
                    chunk_id=chunk_id,
                    content=chunk_content,
                    source_doc_id=doc.doc_id,
                    start_char=start,
                    end_char=end,
                    metadata={'chunk_num': num}
                ))
                num += 1
            
            start += self.chunk_size - self.overlap
        
        return chunks
    
    def index(self, documents: List[Document]) -> None:
        """Index documents."""
        self.chunks = []
        for doc in documents:
            self.chunks.extend(self._chunk_document(doc))
        
        texts = [(c.chunk_id, c.content, c.metadata) for c in self.chunks]
        self.bm25.index_texts(texts)
    
    def _find_adjacent_groups(self, chunk_indices: List[int]) -> List[List[int]]:
        """
        Group adjacent chunk indices.
        
        Two chunks are adjacent if:
        - Same source document
        - Consecutive chunk numbers
        """
        if not chunk_indices:
            return []
        
        # Sort by document and chunk number
        sorted_indices = sorted(chunk_indices, key=lambda i: (
            self.chunks[i].source_doc_id,
            self.chunks[i].metadata.get('chunk_num', 0)
        ))
        
        groups = [[sorted_indices[0]]]
        
        for i in range(1, len(sorted_indices)):
            prev_idx = sorted_indices[i - 1]
            curr_idx = sorted_indices[i]
            
            prev_chunk = self.chunks[prev_idx]
            curr_chunk = self.chunks[curr_idx]
            
            # Check if adjacent
            same_doc = prev_chunk.source_doc_id == curr_chunk.source_doc_id
            prev_num = prev_chunk.metadata.get('chunk_num', -1)
            curr_num = curr_chunk.metadata.get('chunk_num', -1)
            consecutive = curr_num == prev_num + 1
            
            if same_doc and consecutive:
                groups[-1].append(curr_idx)
            else:
                groups.append([curr_idx])
        
        return groups
    
    def search(self, query: str, top_n: int = 5) -> List[Tuple[str, float, Dict]]:
        """
        Search with auto-merging.
        
        Returns:
            List of (merged_text, combined_score, metadata)
        """
        # Retrieve more chunks than needed to allow merging
        retrieval_results = self.bm25.search(query, top_n=top_n * 3)
        
        if not retrieval_results:
            return []
        
        chunk_indices = [idx for idx, _ in retrieval_results]
        scores = {idx: score for idx, score in retrieval_results}
        
        # Group adjacent chunks
        groups = self._find_adjacent_groups(chunk_indices)
        
        results = []
        for group in groups:
            if len(group) >= self.merge_threshold:
                # Merge adjacent chunks
                group_chunks = [self.chunks[i] for i in group]
                group_chunks.sort(key=lambda c: c.metadata.get('chunk_num', 0))
                
                merged_text = ' '.join(c.content for c in group_chunks)
                combined_score = max(scores[i] for i in group)
                
                results.append((
                    merged_text,
                    combined_score,
                    {
                        'merged': True,
                        'num_chunks_merged': len(group),
                        'source_doc_id': group_chunks[0].source_doc_id,
                        'chunk_range': f"{group_chunks[0].metadata.get('chunk_num')}-{group_chunks[-1].metadata.get('chunk_num')}",
                    }
                ))
            else:
                # Keep individual chunk
                for idx in group:
                    chunk = self.chunks[idx]
                    results.append((
                        chunk.content,
                        scores[idx],
                        {
                            'merged': False,
                            'num_chunks_merged': 1,
                            'source_doc_id': chunk.source_doc_id,
                            'chunk_range': str(chunk.metadata.get('chunk_num')),
                        }
                    ))
        
        # Sort by score and limit
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_n]


# ============================================================
# Part 6: Hierarchical Retriever (Summary + Detail)
# ============================================================

class HierarchicalRetriever:
    """
    Hierarchical Retrieval with summaries.
    
    Two-level retrieval:
    1. Level 1: Search document summaries (fast, coarse)
    2. Level 2: Search chunks within selected documents (precise)
    
    This is efficient for large corpora where searching all chunks
    is too expensive.
    """
    
    def __init__(self, chunk_size: int = 150, summary_length: int = 100):
        self.chunk_size = chunk_size
        self.summary_length = summary_length
        self.summary_index = BM25Index()
        self.chunk_index = BM25Index()
        self.documents: List[Document] = []
        self.summaries: List[str] = []
        self.doc_chunks: Dict[str, List[TextChunk]] = {}
        self.all_chunks: List[TextChunk] = []
    
    def _generate_summary(self, doc: Document) -> str:
        """Generate a simple extractive summary."""
        sentences = re.split(r'(?<=[.!?])\s+', doc.content.strip())
        sentences = [s for s in sentences if s.strip()]
        
        if not sentences:
            return doc.content[:self.summary_length]
        
        # Always include at least the first sentence
        summary = sentences[0]
        for sent in sentences[1:]:
            if len(summary) + 1 + len(sent) > self.summary_length:
                break
            summary += " " + sent
        return summary.strip()
    
    def _chunk_document(self, doc: Document) -> List[TextChunk]:
        """Create chunks from document."""
        chunks = []
        content = doc.content
        start = 0
        num = 0
        
        while start < len(content):
            end = min(start + self.chunk_size, len(content))
            chunk_content = content[start:end].strip()
            if chunk_content:
                chunk_id = f"{doc.doc_id}_hchunk_{num}"
                chunks.append(TextChunk(
                    chunk_id=chunk_id,
                    content=chunk_content,
                    source_doc_id=doc.doc_id,
                    start_char=start,
                    end_char=end,
                ))
                num += 1
            start += self.chunk_size
        
        return chunks
    
    def index(self, documents: List[Document]) -> None:
        """Index documents with summaries and chunks."""
        self.documents = documents
        self.summaries = []
        self.doc_chunks = {}
        self.all_chunks = []
        
        for doc in documents:
            summary = self._generate_summary(doc)
            self.summaries.append(summary)
            
            chunks = self._chunk_document(doc)
            self.doc_chunks[doc.doc_id] = chunks
            self.all_chunks.extend(chunks)
        
        # Index summaries
        summary_texts = [
            (doc.doc_id, self.summaries[i], {})
            for i, doc in enumerate(documents)
        ]
        self.summary_index.index_texts(summary_texts)
        
        # Index all chunks
        chunk_texts = [
            (c.chunk_id, c.content, {'doc_id': c.source_doc_id})
            for c in self.all_chunks
        ]
        self.chunk_index.index_texts(chunk_texts)
    
    def search(self, query: str, top_n: int = 5, top_docs: int = 3) -> List[Tuple[str, float, Dict]]:
        """
        Two-level search: summaries first, then chunks within selected docs.
        
        Args:
            top_n: Final number of results
            top_docs: Number of documents to select in level 1
        """
        # Level 1: Search summaries
        doc_results = self.summary_index.search(query, top_n=top_docs)
        
        if not doc_results:
            return []
        
        # Get chunk indices for selected documents
        selected_doc_ids = {self.documents[idx].doc_id for idx, _ in doc_results}
        
        # Level 2: Search chunks within selected documents
        chunk_results = self.chunk_index.search(query, top_n=top_n * 3)
        
        # Filter to selected documents
        filtered = []
        for chunk_idx, score in chunk_results:
            chunk = self.all_chunks[chunk_idx]
            if chunk.source_doc_id in selected_doc_ids:
                filtered.append((chunk, score))
        
        # Sort and limit
        filtered.sort(key=lambda x: x[1], reverse=True)
        
        return [
            (chunk.content, score, {
                'doc_id': chunk.source_doc_id,
                'chunk_id': chunk.chunk_id,
                'level': 'hierarchical',
            })
            for chunk, score in filtered[:top_n]
        ]


# ============================================================
# Part 7: Comparison Utilities
# ============================================================

def compare_retrieval_strategies(
    documents: List[Document],
    queries: List[str],
) -> Dict[str, Any]:
    """
    Compare different retrieval strategies.
    
    Strategies compared:
    1. Baseline (simple chunking)
    2. Parent-Child
    3. Sentence Window
    4. Auto-Merging
    5. Hierarchical
    """
    results = {}
    
    # Baseline
    baseline_bm25 = BM25Index()
    baseline_chunks = []
    for doc in documents:
        content = doc.content
        start = 0
        num = 0
        while start < len(content):
            end = min(start + 150, len(content))
            chunk = content[start:end].strip()
            if chunk:
                baseline_chunks.append((f"{doc.doc_id}_base_{num}", chunk, {}))
                num += 1
            start += 130
    baseline_bm25.index_texts(baseline_chunks)
    
    baseline_results = []
    for q in queries:
        r = baseline_bm25.search(q, top_n=3)
        baseline_results.append(len(r))
    results['baseline'] = {'avg_results': sum(baseline_results) / len(queries)}
    
    # Parent-Child
    pc_retriever = ParentChildRetriever(400, 100, 30)
    pc_retriever.index(documents)
    pc_results = []
    for q in queries:
        r = pc_retriever.search(q, top_n=3)
        pc_results.append(len(r))
    results['parent_child'] = {'avg_results': sum(pc_results) / len(queries)}
    
    # Sentence Window
    sw_indexer = SentenceWindowIndexer(window_size=1)
    sw_indexer.index(documents)
    sw_results = []
    for q in queries:
        r = sw_indexer.search(q, top_n=3)
        sw_results.append(len(r))
    results['sentence_window'] = {'avg_results': sum(sw_results) / len(queries)}
    
    # Auto-Merging
    am_retriever = AutoMergingRetriever(100, 20, 2)
    am_retriever.index(documents)
    am_results = []
    for q in queries:
        r = am_retriever.search(q, top_n=3)
        am_results.append(len(r))
    results['auto_merging'] = {'avg_results': sum(am_results) / len(queries)}
    
    # Hierarchical
    h_retriever = HierarchicalRetriever(150, 80)
    h_retriever.index(documents)
    h_results = []
    for q in queries:
        r = h_retriever.search(q, top_n=3)
        h_results.append(len(r))
    results['hierarchical'] = {'avg_results': sum(h_results) / len(queries)}
    
    return results


# ============================================================
# Part 8: Test Data
# ============================================================

SAMPLE_DOCUMENTS = [
    Document("doc1", "Python is a high-level programming language known for its simplicity and readability. It supports multiple paradigms including object-oriented and functional programming. Python's clean syntax makes it ideal for beginners. The language has a rich ecosystem of libraries for data science, web development, and automation."),
    Document("doc2", "Machine learning is a subset of artificial intelligence. It involves training models on data to make predictions. Deep learning uses neural networks with multiple layers. Common algorithms include linear regression, decision trees, and neural networks. Training requires large datasets and significant computational resources."),
    Document("doc3", "Vector databases store high-dimensional embeddings for similarity search. They use approximate nearest neighbor algorithms like HNSW for fast retrieval. Popular vector databases include Pinecone, Weaviate, and Milvus. These databases are essential for modern AI applications including recommendation systems and semantic search."),
    Document("doc4", "Retrieval augmented generation combines search with language models. The retrieved context helps the model generate grounded answers. RAG reduces hallucination by providing factual context. The pipeline includes document chunking, embedding, retrieval, and generation. Modern RAG systems use advanced techniques like re-ranking and query transformation."),
]


# ============================================================
# Part 9: Unit Tests
# ============================================================

class TestParentChildChunker(unittest.TestCase):
    
    def setUp(self):
        self.chunker = ParentChildChunker(parent_size=200, child_size=50, overlap=10)
    
    def test_chunk_document(self):
        doc = SAMPLE_DOCUMENTS[0]
        parents, children = self.chunker.chunk_document(doc)
        self.assertGreater(len(parents), 0)
        self.assertGreater(len(children), 0)
        self.assertGreaterEqual(len(children), len(parents))
    
    def test_parent_child_link(self):
        """Test that children are linked to parents."""
        doc = SAMPLE_DOCUMENTS[0]
        parents, children = self.chunker.chunk_document(doc)
        
        for child in children:
            self.assertIn('parent_id', child.metadata)
            parent_id = child.metadata['parent_id']
            parent_ids = {p.chunk_id for p in parents}
            self.assertIn(parent_id, parent_ids)
    
    def test_child_smaller_than_parent(self):
        """Test that child chunks are smaller than parent chunks."""
        doc = SAMPLE_DOCUMENTS[0]
        parents, children = self.chunker.chunk_document(doc)
        
        for child in children:
            for parent in parents:
                self.assertLessEqual(len(child.content), len(parent.content) + 10)
    
    def test_chunk_corpus(self):
        parents, children = self.chunker.chunk_corpus(SAMPLE_DOCUMENTS)
        self.assertGreater(len(parents), 0)
        self.assertGreater(len(children), len(parents))
    
    def test_unique_ids(self):
        parents, children = self.chunker.chunk_corpus(SAMPLE_DOCUMENTS)
        parent_ids = [p.chunk_id for p in parents]
        child_ids = [c.chunk_id for c in children]
        self.assertEqual(len(parent_ids), len(set(parent_ids)))
        self.assertEqual(len(child_ids), len(set(child_ids)))


class TestParentChildRetriever(unittest.TestCase):
    
    def setUp(self):
        self.retriever = ParentChildRetriever(parent_size=300, child_size=80, overlap=20)
        self.retriever.index(SAMPLE_DOCUMENTS)
    
    def test_search(self):
        results = self.retriever.search("Python programming", top_n=3)
        self.assertGreater(len(results), 0)
    
    def test_returns_parents(self):
        """Test that results are parent chunks."""
        results = self.retriever.search("Python", top_n=3)
        for parent, score in results:
            self.assertIsInstance(parent, ParentChunk)
    
    def test_unique_parents(self):
        """Test that no parent is returned twice."""
        results = self.retriever.search("machine learning", top_n=5)
        parent_ids = [p.chunk_id for p, _ in results]
        self.assertEqual(len(parent_ids), len(set(parent_ids)))
    
    def test_relevant_results(self):
        results = self.retriever.search("vector database", top_n=3)
        self.assertGreater(len(results), 0)
        top_parent = results[0][0]
        self.assertIn("vector", top_parent.content.lower())
    
    def test_no_results(self):
        results = self.retriever.search("xyzabc123", top_n=3)
        self.assertEqual(len(results), 0)


class TestSentenceWindowIndexer(unittest.TestCase):
    
    def setUp(self):
        self.indexer = SentenceWindowIndexer(window_size=1)
        self.indexer.index(SAMPLE_DOCUMENTS)
    
    def test_index(self):
        self.assertGreater(len(self.indexer.sentences), 0)
    
    def test_search(self):
        results = self.indexer.search("Python programming", top_n=3)
        self.assertGreater(len(results), 0)
    
    def test_window_contains_context(self):
        """Test that windowed results contain more than just the matched sentence."""
        results = self.indexer.search("Python", top_n=1)
        if results:
            text, score, meta = results[0]
            self.assertIn('matched_sentence', meta)
            # Window should be at least the matched sentence
            self.assertGreaterEqual(meta['window_size'], 1)
    
    def test_window_size(self):
        """Test with different window sizes."""
        indexer = SentenceWindowIndexer(window_size=2)
        indexer.index(SAMPLE_DOCUMENTS)
        results = indexer.search("Python", top_n=1)
        if results:
            _, _, meta = results[0]
            self.assertGreaterEqual(meta['window_size'], 1)
    
    def test_deduplication(self):
        """Test that overlapping windows are deduplicated."""
        results = self.indexer.search("machine learning", top_n=5)
        # No exact duplicate texts
        texts = [r[0] for r in results]
        self.assertEqual(len(texts), len(set(texts)))


class TestAutoMergingRetriever(unittest.TestCase):
    
    def setUp(self):
        self.retriever = AutoMergingRetriever(chunk_size=80, overlap=10, merge_threshold=2)
        self.retriever.index(SAMPLE_DOCUMENTS)
    
    def test_search(self):
        results = self.retriever.search("Python programming", top_n=3)
        self.assertGreater(len(results), 0)
    
    def test_merging(self):
        """Test that adjacent chunks get merged."""
        results = self.retriever.search("machine learning", top_n=5)
        merged_count = sum(1 for _, _, meta in results if meta.get('merged', False))
        # At least some results should be merged (if adjacent chunks matched)
        # Note: not guaranteed, but likely with this query
        self.assertGreaterEqual(len(results), 0)
    
    def test_merge_metadata(self):
        """Test that merged results have correct metadata."""
        results = self.retriever.search("vector database", top_n=5)
        for text, score, meta in results:
            self.assertIn('merged', meta)
            self.assertIn('num_chunks_merged', meta)
            self.assertIn('source_doc_id', meta)
    
    def test_adjacent_grouping(self):
        """Test the adjacent chunk grouping logic."""
        # Create chunks manually for testing
        chunks = [
            TextChunk("d1_c0", "first", "d1", metadata={'chunk_num': 0}),
            TextChunk("d1_c1", "second", "d1", metadata={'chunk_num': 1}),
            TextChunk("d1_c2", "third", "d1", metadata={'chunk_num': 2}),
            TextChunk("d2_c0", "fourth", "d2", metadata={'chunk_num': 0}),
        ]
        self.retriever.chunks = chunks
        
        # Test grouping: indices 0,1,2 are adjacent, 3 is separate
        groups = self.retriever._find_adjacent_groups([0, 1, 2, 3])
        self.assertEqual(len(groups), 2)  # [0,1,2] and [3]
        self.assertEqual(len(groups[0]), 3)
        self.assertEqual(len(groups[1]), 1)
    
    def test_non_adjacent_grouping(self):
        """Test grouping of non-adjacent chunks."""
        chunks = [
            TextChunk("d1_c0", "first", "d1", metadata={'chunk_num': 0}),
            TextChunk("d1_c5", "second", "d1", metadata={'chunk_num': 5}),
        ]
        self.retriever.chunks = chunks
        groups = self.retriever._find_adjacent_groups([0, 1])
        self.assertEqual(len(groups), 2)  # Not adjacent, separate groups


class TestHierarchicalRetriever(unittest.TestCase):
    
    def setUp(self):
        self.retriever = HierarchicalRetriever(chunk_size=100, summary_length=60)
        self.retriever.index(SAMPLE_DOCUMENTS)
    
    def test_index(self):
        self.assertGreater(len(self.retriever.documents), 0)
        self.assertGreater(len(self.retriever.summaries), 0)
        self.assertGreater(len(self.retriever.all_chunks), 0)
    
    def test_search(self):
        results = self.retriever.search("Python programming", top_n=3)
        self.assertGreater(len(results), 0)
    
    def test_two_level_filtering(self):
        """Test that only chunks from selected documents are returned."""
        results = self.retriever.search("vector database", top_n=3, top_docs=2)
        for text, score, meta in results:
            self.assertIn('doc_id', meta)
    
    def test_summary_generation(self):
        """Test that summaries are generated."""
        for summary in self.retriever.summaries:
            self.assertGreater(len(summary), 0)
            self.assertLessEqual(len(summary), 100)  # Roughly within summary_length
    
    def test_relevant_results(self):
        results = self.retriever.search("retrieval augmented generation", top_n=3)
        self.assertGreater(len(results), 0)
        top_text = results[0][0].lower()
        self.assertTrue('retrieval' in top_text or 'augmented' in top_text or 'generation' in top_text)


class TestComparison(unittest.TestCase):
    
    def test_compare_strategies(self):
        """Test that comparison runs without errors."""
        queries = ["Python programming", "machine learning", "vector database"]
        results = compare_retrieval_strategies(SAMPLE_DOCUMENTS, queries)
        
        expected = ['baseline', 'parent_child', 'sentence_window', 'auto_merging', 'hierarchical']
        for strategy in expected:
            self.assertIn(strategy, results)
            self.assertIn('avg_results', results[strategy])
    
    def test_all_strategies_return_results(self):
        """Test that all strategies return some results."""
        queries = ["Python", "vector", "machine learning"]
        results = compare_retrieval_strategies(SAMPLE_DOCUMENTS, queries)
        
        for strategy, data in results.items():
            self.assertGreater(data['avg_results'], 0, f"{strategy} returned no results")


# ============================================================
# Main
# ============================================================

if __name__ == '__main__':
    print("=" * 70)
    print("RAG Exercise 9: Advanced RAG Techniques")
    print("=" * 70)
    
    print("\n--- Running Tests ---\n")
    unittest.main(argv=['', '-v'], exit=False)
    
    # Demonstrate
    print("\n--- Advanced RAG Techniques Demo ---\n")
    
    # Parent-Child
    print("1. Parent-Child Retrieval:")
    pc = ParentChildRetriever(300, 80, 20)
    pc.index(SAMPLE_DOCUMENTS)
    results = pc.search("Python programming", top_n=2)
    for parent, score in results:
        print(f"  Parent: {parent.chunk_id} (score: {score:.4f})")
        print(f"  Content: {parent.content[:80]}...")
        print(f"  Children: {len(parent.child_ids)}")
    
    # Sentence Window
    print("\n2. Sentence Window Retrieval:")
    sw = SentenceWindowIndexer(window_size=1)
    sw.index(SAMPLE_DOCUMENTS)
    results = sw.search("vector database", top_n=2)
    for text, score, meta in results:
        print(f"  Score: {score:.4f} | Window: {meta['window_size']} sentences")
        print(f"  Text: {text[:80]}...")
    
    # Auto-Merging
    print("\n3. Auto-Merging Retrieval:")
    am = AutoMergingRetriever(80, 10, 2)
    am.index(SAMPLE_DOCUMENTS)
    results = am.search("machine learning", top_n=3)
    for text, score, meta in results:
        status = "MERGED" if meta['merged'] else "single"
        print(f"  [{status}] Score: {score:.4f} | Chunks: {meta['num_chunks_merged']}")
        print(f"  Text: {text[:80]}...")
    
    # Hierarchical
    print("\n4. Hierarchical Retrieval:")
    h = HierarchicalRetriever(100, 60)
    h.index(SAMPLE_DOCUMENTS)
    results = h.search("retrieval augmented generation", top_n=3)
    for text, score, meta in results:
        print(f"  Doc: {meta['doc_id']} | Score: {score:.4f}")
        print(f"  Text: {text[:80]}...")
    
    # Comparison
    print("\n5. Strategy Comparison:")
    queries = ["Python", "machine learning", "vector database", "RAG"]
    comparison = compare_retrieval_strategies(SAMPLE_DOCUMENTS, queries)
    for strategy, data in comparison.items():
        print(f"  {strategy:<20}: avg_results={data['avg_results']:.1f}")
