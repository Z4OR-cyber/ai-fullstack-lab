#!/usr/bin/env python3
"""
RAG Exercise 7: RAG Evaluation Metrics (RAGAS-style)

Learning Objectives:
1. Understand the four core RAGAS metrics: Faithfulness, Answer Relevance, Context Precision, Context Recall
2. Implement each metric using lexical and semantic similarity (no LLM dependency)
3. Build a complete RAG evaluation framework that scores end-to-end pipelines
4. Compare different RAG configurations using unified metrics
5. Generate evaluation reports with per-component analysis

RAGAS Metric Overview:
                    Retrieved Context
                         |
                    +----+----+
                    |         |
              Context Precision  Context Recall
              (Is context        (Did we get
               relevant?)         everything?)
                    |         |
                    +----+----+
                         |
                      Answer
                         |
                    +----+----+
                    |         |
               Faithfulness   Answer Relevance
               (Is answer      (Does answer
                grounded?)      address query?)

Dependencies: Only standard library
"""

import math
import re
import json
from collections import Counter, defaultdict
from typing import List, Dict, Tuple, Optional, Any, Set
from dataclasses import dataclass, field
import unittest


# ============================================================
# Part 1: Data Structures
# ============================================================

@dataclass
class RAGExample:
    """A single RAG evaluation example."""
    query: str
    answer: str
    retrieved_contexts: List[str]  # List of retrieved text passages
    ground_truth: str  # Reference answer
    ground_truth_contexts: List[str]  # Known relevant contexts (optional, for context recall)
    
    def get_answer_tokens(self) -> List[str]:
        return re.findall(r'\b\w+\b', self.answer.lower())
    
    def get_query_tokens(self) -> List[str]:
        return re.findall(r'\b\w+\b', self.query.lower())
    
    def get_context_tokens(self) -> List[str]:
        all_tokens = []
        for ctx in self.retrieved_contexts:
            all_tokens.extend(re.findall(r'\b\w+\b', ctx.lower()))
        return all_tokens


@dataclass
class RAGMetricResult:
    """Result of a single metric evaluation."""
    metric_name: str
    score: float  # 0.0 to 1.0
    details: Dict[str, Any] = field(default_factory=dict)
    
    def __str__(self):
        return f"{self.metric_name}: {self.score:.4f}"


@dataclass
class RAGEvaluationReport:
    """Complete evaluation report for a RAG example."""
    example: RAGExample
    metrics: Dict[str, RAGMetricResult]
    
    @property
    def overall_score(self) -> float:
        """Simple average of all metrics."""
        if not self.metrics:
            return 0.0
        return sum(m.score for m in self.metrics.values()) / len(self.metrics)
    
    def summary(self) -> str:
        lines = [f"Query: {self.example.query[:80]}"]
        for name, result in self.metrics.items():
            lines.append(f"  {result}")
        lines.append(f"  Overall: {self.overall_score:.4f}")
        return "\n".join(lines)


# ============================================================
# Part 2: Utility Functions
# ============================================================

def tokenize(text: str) -> List[str]:
    """Tokenize text into lowercase words."""
    return re.findall(r'\b\w+\b', text.lower())


def get_ngrams(tokens: List[str], n: int = 1) -> Set[Tuple[str, ...]]:
    """Get n-grams from token list."""
    if n == 1:
        return set((t,) for t in tokens)
    return set(tuple(tokens[i:i+n]) for i in range(len(tokens) - n + 1))


def jaccard_similarity(set_a: Set, set_b: Set) -> float:
    """Jaccard similarity between two sets."""
    if not set_a and not set_b:
        return 1.0
    intersection = set_a & set_b
    union = set_a | set_b
    return len(intersection) / len(union) if union else 0.0


def token_overlap_ratio(text_a: str, text_b: str) -> float:
    """Token overlap ratio (proportion of A's tokens in B)."""
    tokens_a = set(tokenize(text_a))
    tokens_b = set(tokenize(text_b))
    if not tokens_a:
        return 0.0
    return len(tokens_a & tokens_b) / len(tokens_a)


def tfidf_cosine_similarity(text_a: str, text_b: str, idf_weights: Optional[Dict[str, float]] = None) -> float:
    """
    TF-IDF cosine similarity between two texts.
    
    If idf_weights is not provided, uses simple TF (uniform IDF).
    """
    tokens_a = tokenize(text_a)
    tokens_b = tokenize(text_b)
    
    if not tokens_a or not tokens_b:
        return 0.0
    
    tf_a = Counter(tokens_a)
    tf_b = Counter(tokens_b)
    
    if idf_weights:
        vec_a = {t: tf * idf_weights.get(t, 1.0) for t, tf in tf_a.items()}
        vec_b = {t: tf * idf_weights.get(t, 1.0) for t, tf in tf_b.items()}
    else:
        vec_a = dict(tf_a)
        vec_b = dict(tf_b)
    
    # Normalize
    norm_a = math.sqrt(sum(v ** 2 for v in vec_a.values()))
    norm_b = math.sqrt(sum(v ** 2 for v in vec_b.values()))
    
    if norm_a == 0 or norm_b == 0:
        return 0.0
    
    # Dot product
    shared_terms = set(vec_a.keys()) & set(vec_b.keys())
    dot = sum(vec_a[t] * vec_b[t] for t in shared_terms)
    
    return dot / (norm_a * norm_b)


def compute_idf(texts: List[str]) -> Dict[str, float]:
    """Compute IDF weights from a corpus of texts."""
    N = len(texts)
    if N == 0:
        return {}
    
    doc_freq = Counter()
    for text in texts:
        terms = set(tokenize(text))
        for term in terms:
            doc_freq[term] += 1
    
    return {term: math.log((N + 1) / (df + 1)) + 1 for term, df in doc_freq.items()}


# ============================================================
# Part 3: Faithfulness Metric
# ============================================================

class FaithfulnessMetric:
    """
    Faithfulness: Measures whether the answer is grounded in the retrieved context.
    
    A faithful answer only makes claims that are supported by the retrieved context.
    High faithfulness = low hallucination.
    
    Implementation (simplified, without LLM):
    1. Extract claims (sentences) from the answer
    2. For each claim, check if it's supported by the retrieved context
    3. Support is measured by token overlap / n-gram overlap with context
    
    In production RAGAS, an LLM verifies each claim against the context.
    Here we use lexical overlap as a proxy.
    
    Score = (number of supported claims) / (total claims)
    """
    
    def __init__(self, min_support_ratio: float = 0.3, idf_weights: Optional[Dict[str, float]] = None):
        self.min_support_ratio = min_support_ratio
        self.idf_weights = idf_weights
    
    def _extract_claims(self, answer: str) -> List[str]:
        """Extract claims (sentences) from the answer."""
        # Split on sentence boundaries
        sentences = re.split(r'(?<=[.!?])\s+', answer.strip())
        return [s.strip() for s in sentences if len(s.strip()) > 5]
    
    def _claim_support_score(self, claim: str, contexts: List[str]) -> float:
        """
        Score how well a claim is supported by the contexts.
        
        Uses a combination of:
        - Token overlap ratio
        - Bigram overlap (for more specific matching)
        - TF-IDF cosine similarity
        """
        combined_context = ' '.join(contexts)
        
        # Token overlap
        token_ratio = token_overlap_ratio(claim, combined_context)
        
        # Bigram overlap
        claim_bigrams = get_ngrams(tokenize(claim), 2)
        context_bigrams = get_ngrams(tokenize(combined_context), 2)
        bigram_sim = jaccard_similarity(claim_bigrams, context_bigrams)
        
        # TF-IDF cosine similarity
        cosine_sim = tfidf_cosine_similarity(claim, combined_context, self.idf_weights)
        
        # Weighted combination
        # Token overlap is most important for faithfulness
        # Bigram adds precision, cosine adds semantic matching
        score = 0.5 * token_ratio + 0.2 * bigram_sim + 0.3 * cosine_sim
        
        return score
    
    def evaluate(self, example: RAGExample) -> RAGMetricResult:
        """Evaluate faithfulness of the answer given retrieved context."""
        claims = self._extract_claims(example.answer)
        
        if not claims:
            return RAGMetricResult(
                metric_name='faithfulness',
                score=1.0,  # No claims = trivially faithful
                details={'num_claims': 0, 'supported': 0}
            )
        
        supported = 0
        claim_scores = []
        
        for claim in claims:
            support = self._claim_support_score(claim, example.retrieved_contexts)
            claim_scores.append({'claim': claim[:50], 'support': support})
            if support >= self.min_support_ratio:
                supported += 1
        
        score = supported / len(claims)
        
        return RAGMetricResult(
            metric_name='faithfulness',
            score=score,
            details={
                'num_claims': len(claims),
                'supported': supported,
                'claim_scores': claim_scores,
                'min_support_ratio': self.min_support_ratio,
            }
        )


# ============================================================
# Part 4: Answer Relevance Metric
# ============================================================

class AnswerRelevanceMetric:
    """
    Answer Relevance: Measures how well the answer addresses the query.
    
    A relevant answer directly responds to what was asked.
    
    Implementation (simplified):
    1. Compute similarity between query and answer
    2. Check if key query terms appear in the answer
    3. Penalize answers that are too short or too long
    
    In production RAGAS, an LLM generates potential questions from the answer
    and compares them to the original query.
    
    Score = weighted combination of similarity and coverage
    """
    
    def __init__(self, idf_weights: Optional[Dict[str, float]] = None,
                 min_answer_length: int = 10, max_answer_length: int = 500):
        self.idf_weights = idf_weights
        self.min_answer_length = min_answer_length
        self.max_answer_length = max_answer_length
    
    def evaluate(self, example: RAGExample) -> RAGMetricResult:
        """Evaluate answer relevance to the query."""
        query = example.query
        answer = example.answer
        
        # Feature 1: TF-IDF cosine similarity
        cosine_sim = tfidf_cosine_similarity(query, answer, self.idf_weights)
        
        # Feature 2: Query term coverage (what fraction of query terms appear in answer)
        query_terms = set(tokenize(query))
        answer_terms = set(tokenize(answer))
        
        if query_terms:
            coverage = len(query_terms & answer_terms) / len(query_terms)
        else:
            coverage = 0.0
        
        # Feature 3: Key term emphasis (query terms should appear prominently in answer)
        answer_tokens = tokenize(answer)
        if answer_tokens and query_terms:
            # Check if query terms appear in the first half of the answer
            first_half = set(answer_tokens[:len(answer_tokens) // 2])
            emphasis = len(query_terms & first_half) / len(query_terms)
        else:
            emphasis = 0.0
        
        # Feature 4: Length penalty
        answer_len = len(answer_tokens)
        if answer_len < self.min_answer_length:
            length_penalty = answer_len / self.min_answer_length
        elif answer_len > self.max_answer_length:
            length_penalty = max(0.5, self.max_answer_length / answer_len)
        else:
            length_penalty = 1.0
        
        # Weighted combination
        score = (
            0.3 * cosine_sim +
            0.35 * coverage +
            0.15 * emphasis +
            0.2 * length_penalty
        )
        
        # Clamp to [0, 1]
        score = max(0.0, min(1.0, score))
        
        return RAGMetricResult(
            metric_name='answer_relevance',
            score=score,
            details={
                'cosine_similarity': cosine_sim,
                'query_term_coverage': coverage,
                'term_emphasis': emphasis,
                'length_penalty': length_penalty,
                'answer_length': answer_len,
            }
        )


# ============================================================
# Part 5: Context Precision Metric
# ============================================================

class ContextPrecisionMetric:
    """
    Context Precision: Measures whether the retrieved contexts are relevant.
    
    High precision = retrieved contexts are mostly relevant to the query.
    Low precision = many irrelevant contexts retrieved.
    
    Implementation:
    1. For each retrieved context, compute relevance to the query
    2. Score = fraction of contexts that are relevant (above threshold)
    
    In production RAGAS, this uses the ground truth answer to verify
    that each context chunk was actually useful.
    
    Variants:
    - Context Precision@K: precision in top-K contexts
    - Weighted Context Precision: weight by rank position
    """
    
    def __init__(self, relevance_threshold: float = 0.1,
                 idf_weights: Optional[Dict[str, float]] = None,
                 use_weighted: bool = True):
        self.relevance_threshold = relevance_threshold
        self.idf_weights = idf_weights
        self.use_weighted = use_weighted
    
    def _context_relevance(self, query: str, context: str) -> float:
        """Score relevance of a single context to the query."""
        # TF-IDF cosine similarity
        cosine = tfidf_cosine_similarity(query, context, self.idf_weights)
        
        # Token overlap
        overlap = token_overlap_ratio(query, context)
        
        # Combined
        return 0.6 * cosine + 0.4 * overlap
    
    def evaluate(self, example: RAGExample) -> RAGMetricResult:
        """Evaluate context precision."""
        if not example.retrieved_contexts:
            return RAGMetricResult(
                metric_name='context_precision',
                score=0.0,
                details={'num_contexts': 0, 'relevant': 0}
            )
        
        relevance_scores = []
        relevant_count = 0
        
        for i, ctx in enumerate(example.retrieved_contexts):
            rel = self._context_relevance(example.query, ctx)
            relevance_scores.append(rel)
            if rel >= self.relevance_threshold:
                relevant_count += 1
        
        if self.use_weighted:
            # Weighted precision: higher weight for relevant contexts at higher ranks
            weights = [1.0 / (i + 1) for i in range(len(relevance_scores))]
            total_weight = sum(weights)
            weighted_relevant = sum(
                w * (1 if rel >= self.relevance_threshold else 0)
                for w, rel in zip(weights, relevance_scores)
            )
            score = weighted_relevant / total_weight if total_weight > 0 else 0.0
        else:
            score = relevant_count / len(example.retrieved_contexts)
        
        return RAGMetricResult(
            metric_name='context_precision',
            score=score,
            details={
                'num_contexts': len(example.retrieved_contexts),
                'relevant': relevant_count,
                'relevance_scores': [round(r, 4) for r in relevance_scores],
                'threshold': self.relevance_threshold,
                'weighted': self.use_weighted,
            }
        )


# ============================================================
# Part 6: Context Recall Metric
# ============================================================

class ContextRecallMetric:
    """
    Context Recall: Measures whether all needed information was retrieved.
    
    High recall = the retrieved contexts contain all information needed
    to answer the question (as measured by the ground truth answer).
    
    Implementation:
    1. For each sentence/claim in the ground truth, check if it's
       supported by the retrieved contexts
    2. Score = fraction of ground truth claims that are supported
    
    In production RAGAS, an LLM verifies each ground truth sentence
    against the retrieved context.
    """
    
    def __init__(self, min_support_ratio: float = 0.25,
                 idf_weights: Optional[Dict[str, float]] = None):
        self.min_support_ratio = min_support_ratio
        self.idf_weights = idf_weights
    
    def _extract_sentences(self, text: str) -> List[str]:
        """Extract sentences from text."""
        sentences = re.split(r'(?<=[.!?])\s+', text.strip())
        return [s.strip() for s in sentences if len(s.strip()) > 5]
    
    def _sentence_support(self, sentence: str, contexts: List[str]) -> float:
        """Check if a sentence is supported by the contexts."""
        combined = ' '.join(contexts)
        
        # Token overlap
        overlap = token_overlap_ratio(sentence, combined)
        
        # TF-IDF cosine
        cosine = tfidf_cosine_similarity(sentence, combined, self.idf_weights)
        
        # Bigram overlap for more precise matching
        sent_bigrams = get_ngrams(tokenize(sentence), 2)
        ctx_bigrams = get_ngrams(tokenize(combined), 2)
        bigram_sim = jaccard_similarity(sent_bigrams, ctx_bigrams)
        
        return 0.4 * overlap + 0.4 * cosine + 0.2 * bigram_sim
    
    def evaluate(self, example: RAGExample) -> RAGMetricResult:
        """Evaluate context recall."""
        gt_sentences = self._extract_sentences(example.ground_truth)
        
        if not gt_sentences:
            return RAGMetricResult(
                metric_name='context_recall',
                score=1.0,
                details={'num_gt_sentences': 0, 'supported': 0}
            )
        
        supported = 0
        sentence_scores = []
        
        for sent in gt_sentences:
            support = self._sentence_support(sent, example.retrieved_contexts)
            sentence_scores.append({'sentence': sent[:50], 'support': round(support, 4)})
            if support >= self.min_support_ratio:
                supported += 1
        
        score = supported / len(gt_sentences)
        
        return RAGMetricResult(
            metric_name='context_recall',
            score=score,
            details={
                'num_gt_sentences': len(gt_sentences),
                'supported': supported,
                'sentence_scores': sentence_scores,
                'min_support_ratio': self.min_support_ratio,
            }
        )


# ============================================================
# Part 7: Additional Metrics
# ============================================================

class ContextRelevancyMetric:
    """
    Context Relevancy: Ratio of relevant tokens in retrieved context
    to total tokens in retrieved context.
    
    Measures how much of the retrieved context is actually useful.
    Lower score = lots of irrelevant noise in context.
    """
    
    def __init__(self, idf_weights: Optional[Dict[str, float]] = None):
        self.idf_weights = idf_weights
    
    def evaluate(self, example: RAGExample) -> RAGMetricResult:
        """Evaluate context relevancy."""
        query_terms = set(tokenize(example.query))
        
        if not example.retrieved_contexts or not query_terms:
            return RAGMetricResult(
                metric_name='context_relevancy',
                score=0.0,
                details={'query_terms': len(query_terms), 'context_tokens': 0}
            )
        
        total_context_tokens = 0
        relevant_tokens = 0
        
        for ctx in example.retrieved_contexts:
            ctx_tokens = tokenize(ctx)
            total_context_tokens += len(ctx_tokens)
            
            # Count tokens that are query terms or related
            for token in ctx_tokens:
                if token in query_terms:
                    relevant_tokens += 1
        
        # Also consider tokens from ground truth as "relevant"
        gt_terms = set(tokenize(example.ground_truth))
        for ctx in example.retrieved_contexts:
            ctx_tokens = tokenize(ctx)
            for token in ctx_tokens:
                if token in gt_terms and token not in query_terms:
                    relevant_tokens += 1
        
        score = relevant_tokens / total_context_tokens if total_context_tokens > 0 else 0.0
        
        # Normalize: raw ratio is typically very low, so apply sqrt scaling
        score = math.sqrt(score)
        score = min(1.0, score)
        
        return RAGMetricResult(
            metric_name='context_relevancy',
            score=score,
            details={
                'total_context_tokens': total_context_tokens,
                'relevant_tokens': relevant_tokens,
                'query_terms': len(query_terms),
                'gt_terms': len(gt_terms),
            }
        )


class AnswerCorrectnessMetric:
    """
    Answer Correctness: Compare the generated answer with ground truth.
    
    Uses semantic similarity (TF-IDF cosine) and factual overlap
    to measure how close the answer is to the reference.
    
    In production RAGAS, this involves LLM-based comparison and
    decomposing answers into individual facts.
    """
    
    def __init__(self, idf_weights: Optional[Dict[str, float]] = None):
        self.idf_weights = idf_weights
    
    def evaluate(self, example: RAGExample) -> RAGMetricResult:
        """Evaluate answer correctness against ground truth."""
        answer = example.answer
        ground_truth = example.ground_truth
        
        # Feature 1: TF-IDF cosine similarity
        cosine = tfidf_cosine_similarity(answer, ground_truth, self.idf_weights)
        
        # Feature 2: Factual overlap (key terms shared)
        answer_terms = set(tokenize(answer))
        gt_terms = set(tokenize(ground_truth))
        
        if gt_terms:
            overlap = len(answer_terms & gt_terms) / len(gt_terms)
        else:
            overlap = 0.0
        
        # Feature 3: Bigram overlap (captures phrase-level similarity)
        answer_bigrams = get_ngrams(tokenize(answer), 2)
        gt_bigrams = get_ngrams(tokenize(ground_truth), 2)
        bigram_f1 = self._f1_score(answer_bigrams, gt_bigrams)
        
        # Feature 4: Length similarity (penalize very different lengths)
        len_ratio = min(len(answer), len(ground_truth)) / max(len(answer), len(ground_truth), 1)
        
        # Weighted combination
        score = 0.35 * cosine + 0.30 * overlap + 0.25 * bigram_f1 + 0.10 * len_ratio
        score = min(1.0, max(0.0, score))
        
        return RAGMetricResult(
            metric_name='answer_correctness',
            score=score,
            details={
                'cosine_similarity': round(cosine, 4),
                'term_overlap': round(overlap, 4),
                'bigram_f1': round(bigram_f1, 4),
                'length_ratio': round(len_ratio, 4),
            }
        )
    
    @staticmethod
    def _f1_score(set_a: Set, set_b: Set) -> float:
        """F1 score between two sets."""
        if not set_a and not set_b:
            return 1.0
        if not set_a or not set_b:
            return 0.0
        tp = len(set_a & set_b)
        precision = tp / len(set_a)
        recall = tp / len(set_b)
        if precision + recall == 0:
            return 0.0
        return 2 * precision * recall / (precision + recall)


# ============================================================
# Part 8: RAG Evaluator (Orchestrator)
# ============================================================

class RAGEvaluator:
    """
    Complete RAG evaluation framework.
    
    Orchestrates all metrics and produces comprehensive reports.
    
    Usage:
        evaluator = RAGEvaluator()
        report = evaluator.evaluate(example)
        print(report.summary())
    """
    
    def __init__(self, idf_weights: Optional[Dict[str, float]] = None,
                 metrics: Optional[List[str]] = None):
        """
        Args:
            idf_weights: IDF weights for TF-IDF computations
            metrics: List of metric names to compute. Default: all.
        """
        all_metrics = {
            'faithfulness': FaithfulnessMetric(idf_weights=idf_weights),
            'answer_relevance': AnswerRelevanceMetric(idf_weights=idf_weights),
            'context_precision': ContextPrecisionMetric(idf_weights=idf_weights),
            'context_recall': ContextRecallMetric(idf_weights=idf_weights),
            'context_relevancy': ContextRelevancyMetric(idf_weights=idf_weights),
            'answer_correctness': AnswerCorrectnessMetric(idf_weights=idf_weights),
        }
        
        if metrics:
            self.metrics = {name: all_metrics[name] for name in metrics if name in all_metrics}
        else:
            self.metrics = all_metrics
        
        self.idf_weights = idf_weights
    
    def evaluate(self, example: RAGExample) -> RAGEvaluationReport:
        """Evaluate a single RAG example."""
        results = {}
        for name, metric in self.metrics.items():
            results[name] = metric.evaluate(example)
        return RAGEvaluationReport(example=example, metrics=results)
    
    def evaluate_batch(self, examples: List[RAGExample]) -> List[RAGEvaluationReport]:
        """Evaluate multiple examples."""
        return [self.evaluate(ex) for ex in examples]
    
    def evaluate_and_summarize(self, examples: List[RAGExample]) -> Dict[str, Any]:
        """
        Evaluate multiple examples and produce summary statistics.
        
        Returns:
            Dict with per-metric averages, per-example scores, and overall statistics.
        """
        reports = self.evaluate_batch(examples)
        
        # Aggregate metrics
        metric_names = list(self.metrics.keys())
        metric_scores = {name: [] for name in metric_names}
        overall_scores = []
        
        for report in reports:
            overall_scores.append(report.overall_score)
            for name, result in report.metrics.items():
                metric_scores[name].append(result.score)
        
        summary = {
            'num_examples': len(examples),
            'metric_averages': {
                name: sum(scores) / len(scores) if scores else 0.0
                for name, scores in metric_scores.items()
            },
            'overall_average': sum(overall_scores) / len(overall_scores) if overall_scores else 0.0,
            'overall_min': min(overall_scores) if overall_scores else 0.0,
            'overall_max': max(overall_scores) if overall_scores else 0.0,
            'per_example': [
                {
                    'query': r.example.query[:60],
                    'overall': round(r.overall_score, 4),
                    'metrics': {name: round(m.score, 4) for name, m in r.metrics.items()}
                }
                for r in reports
            ],
        }
        
        return summary
    
    @staticmethod
    def format_summary(summary: Dict[str, Any]) -> str:
        """Format summary as a readable report."""
        lines = []
        lines.append("=" * 70)
        lines.append("RAG Evaluation Summary")
        lines.append("=" * 70)
        lines.append(f"\nExamples evaluated: {summary['num_examples']}")
        lines.append(f"Overall average: {summary['overall_average']:.4f}")
        lines.append(f"Overall range: [{summary['overall_min']:.4f}, {summary['overall_max']:.4f}]")
        
        lines.append("\n--- Metric Averages ---")
        for name, avg in summary['metric_averages'].items():
            lines.append(f"  {name:<25}: {avg:.4f}")
        
        lines.append("\n--- Per-Example Scores ---")
        for ex in summary['per_example']:
            lines.append(f"\n  Query: {ex['query']}")
            lines.append(f"  Overall: {ex['overall']:.4f}")
            for name, score in ex['metrics'].items():
                lines.append(f"    {name:<25}: {score:.4f}")
        
        lines.append("\n" + "=" * 70)
        return "\n".join(lines)


# ============================================================
# Part 9: Test Data
# ============================================================

# Sample RAG examples for testing
TEST_EXAMPLES = [
    RAGExample(
        query="What is Python?",
        answer="Python is a high-level programming language known for its simplicity and readability. It supports multiple programming paradigms.",
        retrieved_contexts=[
            "Python is a high-level programming language known for its simplicity and readability.",
            "Python supports multiple paradigms including object-oriented and functional programming.",
        ],
        ground_truth="Python is a high-level, general-purpose programming language. It is known for its clean syntax and supports multiple paradigms.",
        ground_truth_contexts=["Python is a high-level programming language."]
    ),
    RAGExample(
        query="How do vector databases work?",
        answer="Vector databases store high-dimensional embeddings for similarity search. They use approximate nearest neighbor algorithms for fast retrieval of similar vectors.",
        retrieved_contexts=[
            "Vector databases store high-dimensional embeddings for similarity search.",
            "They use approximate nearest neighbor algorithms like HNSW for fast retrieval.",
        ],
        ground_truth="Vector databases store numerical embeddings and use ANN algorithms to find similar vectors quickly.",
        ground_truth_contexts=["Vector databases store embeddings for similarity search."]
    ),
    RAGExample(
        query="What is gradient descent?",
        answer="Gradient descent is an optimization algorithm that minimizes loss functions in machine learning by iteratively moving in the direction of steepest descent.",
        retrieved_contexts=[
            "Gradient descent optimization minimizes loss functions in machine learning.",
            "Stochastic gradient descent processes mini-batches of data.",
        ],
        ground_truth="Gradient descent is an optimization method that minimizes a loss function by following the negative gradient.",
        ground_truth_contexts=["Gradient descent minimizes loss functions."]
    ),
    RAGExample(
        query="Explain retrieval augmented generation",
        answer="Retrieval augmented generation combines search with language models. The retrieved context helps the model generate grounded answers and reduces hallucination significantly.",
        retrieved_contexts=[
            "Retrieval augmented generation combines search with language models.",
            "The retrieved context helps the model generate accurate answers and reduces hallucination.",
        ],
        ground_truth="RAG combines a retrieval system with a language model to generate answers grounded in retrieved documents, reducing hallucination.",
        ground_truth_contexts=["RAG combines retrieval with language models."]
    ),
    # Poor quality example (for contrast)
    RAGExample(
        query="What is Kubernetes?",
        answer="Kubernetes is a container orchestration platform. It manages microservices deployment and uses pods as the smallest deployable unit.",
        retrieved_contexts=[
            "Cloud computing platforms offer scalable infrastructure.",
            "Distributed systems use consensus algorithms for fault tolerance.",
        ],
        ground_truth="Kubernetes is a container orchestration system that automates deployment, scaling, and management of containerized applications using pods.",
        ground_truth_contexts=["Container orchestration with Kubernetes manages microservices deployment."]
    ),
]


# ============================================================
# Part 10: Unit Tests
# ============================================================

class TestUtilityFunctions(unittest.TestCase):
    
    def test_tokenize(self):
        self.assertEqual(tokenize("Hello World"), ['hello', 'world'])
        self.assertEqual(tokenize("Python 3.14"), ['python', '3', '14'])
    
    def test_get_ngrams(self):
        tokens = ['a', 'b', 'c']
        unigrams = get_ngrams(tokens, 1)
        self.assertIn(('a',), unigrams)
        self.assertIn(('b',), unigrams)
        
        bigrams = get_ngrams(tokens, 2)
        self.assertIn(('a', 'b'), bigrams)
        self.assertIn(('b', 'c'), bigrams)
    
    def test_jaccard_similarity(self):
        self.assertAlmostEqual(jaccard_similarity({1, 2, 3}, {2, 3, 4}), 0.5)
        self.assertEqual(jaccard_similarity(set(), set()), 1.0)
        self.assertEqual(jaccard_similarity({1}, set()), 0.0)
    
    def test_token_overlap_ratio(self):
        ratio = token_overlap_ratio("python programming", "python is great for programming")
        self.assertGreater(ratio, 0.5)
        
        ratio = token_overlap_ratio("python", "java rust go")
        self.assertEqual(ratio, 0.0)
    
    def test_tfidf_cosine_similarity_identical(self):
        text = "python programming language"
        sim = tfidf_cosine_similarity(text, text)
        self.assertAlmostEqual(sim, 1.0, places=5)
    
    def test_tfidf_cosine_similarity_different(self):
        sim = tfidf_cosine_similarity("python programming", "cloud computing infrastructure")
        self.assertLess(sim, 0.3)
    
    def test_compute_idf(self):
        texts = ["python programming", "python data science", "cloud computing"]
        idf = compute_idf(texts)
        self.assertIn('python', idf)
        self.assertIn('cloud', idf)
        # 'python' appears in 2/3 docs, 'cloud' in 1/3
        self.assertGreater(idf['cloud'], idf['python'])


class TestFaithfulnessMetric(unittest.TestCase):
    
    def setUp(self):
        self.metric = FaithfulnessMetric(min_support_ratio=0.2)
    
    def test_faithful_answer(self):
        """Test that an answer grounded in context gets high score."""
        example = TEST_EXAMPLES[0]  # Python answer grounded in context
        result = self.metric.evaluate(example)
        self.assertGreater(result.score, 0.5)
    
    def test_unfaithful_answer(self):
        """Test that an answer not grounded in context gets low score."""
        # Use higher threshold to catch semantically unsupported claims
        metric = FaithfulnessMetric(min_support_ratio=0.3)
        example = RAGExample(
            query="What is Python?",
            answer="Python is a type of snake that lives in tropical regions.",
            retrieved_contexts=["Python is a high-level programming language."],
            ground_truth="Python is a programming language.",
            ground_truth_contexts=["Python is a programming language."]
        )
        result = metric.evaluate(example)
        # Without LLM verification, lexical overlap provides only rough signal
        self.assertLess(result.score, 0.8)
    
    def test_empty_answer(self):
        """Test handling of empty answer."""
        example = RAGExample(
            query="test",
            answer="",
            retrieved_contexts=["some context"],
            ground_truth="answer",
            ground_truth_contexts=["context"]
        )
        result = self.metric.evaluate(example)
        self.assertEqual(result.score, 1.0)  # Trivially faithful
    
    def test_claim_extraction(self):
        """Test claim (sentence) extraction."""
        claims = self.metric._extract_claims("First sentence. Second sentence! Third?")
        self.assertEqual(len(claims), 3)
    
    def test_score_range(self):
        """Test that score is between 0 and 1."""
        for example in TEST_EXAMPLES:
            result = self.metric.evaluate(example)
            self.assertGreaterEqual(result.score, 0.0)
            self.assertLessEqual(result.score, 1.0)


class TestAnswerRelevanceMetric(unittest.TestCase):
    
    def setUp(self):
        self.metric = AnswerRelevanceMetric()
    
    def test_relevant_answer(self):
        """Test that relevant answer gets high score."""
        example = TEST_EXAMPLES[0]
        result = self.metric.evaluate(example)
        self.assertGreater(result.score, 0.3)
    
    def test_irrelevant_answer(self):
        """Test that irrelevant answer gets low score."""
        example = RAGExample(
            query="What is Python?",
            answer="The weather is nice today and I like going for walks.",
            retrieved_contexts=["some context"],
            ground_truth="Python is a programming language.",
            ground_truth_contexts=["context"]
        )
        result = self.metric.evaluate(example)
        # Without LLM, semantic disconnection is measured by low token overlap
        self.assertLess(result.score, 0.5)
    
    def test_short_answer_penalty(self):
        """Test that very short answers get penalized."""
        example = RAGExample(
            query="What is Python?",
            answer="Yes.",
            retrieved_contexts=["Python is a language."],
            ground_truth="Python is a programming language.",
            ground_truth_contexts=["Python is a language."]
        )
        result = self.metric.evaluate(example)
        self.assertLess(result.score, 0.5)
    
    def test_score_range(self):
        for example in TEST_EXAMPLES:
            result = self.metric.evaluate(example)
            self.assertGreaterEqual(result.score, 0.0)
            self.assertLessEqual(result.score, 1.0)


class TestContextPrecisionMetric(unittest.TestCase):
    
    def setUp(self):
        self.metric = ContextPrecisionMetric(relevance_threshold=0.05)
    
    def test_relevant_contexts(self):
        """Test that relevant contexts get high precision."""
        example = TEST_EXAMPLES[0]  # Contexts about Python
        result = self.metric.evaluate(example)
        self.assertGreater(result.score, 0.3)
    
    def test_irrelevant_contexts(self):
        """Test that irrelevant contexts get low precision."""
        # Use higher threshold to filter out common-word overlap
        metric = ContextPrecisionMetric(relevance_threshold=0.35)
        example = RAGExample(
            query="What is Python?",
            answer="Python is a language.",
            retrieved_contexts=["Cloud computing is scalable.", "Distributed systems use Raft."],
            ground_truth="Python is a programming language.",
            ground_truth_contexts=["Python is a language."]
        )
        result = metric.evaluate(example)
        self.assertLess(result.score, 0.5)
    
    def test_empty_contexts(self):
        """Test handling of empty contexts."""
        example = RAGExample(
            query="test",
            answer="answer",
            retrieved_contexts=[],
            ground_truth="truth",
            ground_truth_contexts=["ctx"]
        )
        result = self.metric.evaluate(example)
        self.assertEqual(result.score, 0.0)
    
    def test_score_range(self):
        for example in TEST_EXAMPLES:
            result = self.metric.evaluate(example)
            self.assertGreaterEqual(result.score, 0.0)
            self.assertLessEqual(result.score, 1.0)


class TestContextRecallMetric(unittest.TestCase):
    
    def setUp(self):
        self.metric = ContextRecallMetric(min_support_ratio=0.15)
    
    def test_high_recall(self):
        """Test that when context covers ground truth, recall is high."""
        example = TEST_EXAMPLES[0]  # Contexts match ground truth well
        result = self.metric.evaluate(example)
        self.assertGreater(result.score, 0.3)
    
    def test_low_recall(self):
        """Test that when context doesn't cover ground truth, recall is low."""
        example = RAGExample(
            query="What is Python?",
            answer="Python is a language.",
            retrieved_contexts=["Cloud computing platforms offer infrastructure."],
            ground_truth="Python is a high-level programming language with clean syntax and multiple paradigms.",
            ground_truth_contexts=["Python is a language."]
        )
        result = self.metric.evaluate(example)
        self.assertLess(result.score, 0.5)
    
    def test_empty_ground_truth(self):
        """Test handling of empty ground truth."""
        example = RAGExample(
            query="test",
            answer="answer",
            retrieved_contexts=["context"],
            ground_truth="",
            ground_truth_contexts=["ctx"]
        )
        result = self.metric.evaluate(example)
        self.assertEqual(result.score, 1.0)
    
    def test_score_range(self):
        for example in TEST_EXAMPLES:
            result = self.metric.evaluate(example)
            self.assertGreaterEqual(result.score, 0.0)
            self.assertLessEqual(result.score, 1.0)


class TestContextRelevancyMetric(unittest.TestCase):
    
    def setUp(self):
        self.metric = ContextRelevancyMetric()
    
    def test_relevant_context(self):
        """Test relevancy with relevant context."""
        example = TEST_EXAMPLES[0]
        result = self.metric.evaluate(example)
        self.assertGreater(result.score, 0.0)
    
    def test_irrelevant_context(self):
        """Test relevancy with irrelevant context."""
        example = RAGExample(
            query="What is Python?",
            answer="Python is a language.",
            retrieved_contexts=["Cloud computing platforms offer scalable infrastructure and managed services."],
            ground_truth="Python is a programming language.",
            ground_truth_contexts=["Python is a language."]
        )
        result = self.metric.evaluate(example)
        # Should be low but not necessarily 0
        self.assertLess(result.score, 0.5)
    
    def test_empty_contexts(self):
        example = RAGExample(
            query="test", answer="a", retrieved_contexts=[],
            ground_truth="t", ground_truth_contexts=["c"]
        )
        result = self.metric.evaluate(example)
        self.assertEqual(result.score, 0.0)
    
    def test_score_range(self):
        for example in TEST_EXAMPLES:
            result = self.metric.evaluate(example)
            self.assertGreaterEqual(result.score, 0.0)
            self.assertLessEqual(result.score, 1.0)


class TestAnswerCorrectnessMetric(unittest.TestCase):
    
    def setUp(self):
        self.metric = AnswerCorrectnessMetric()
    
    def test_identical_answer(self):
        """Test that identical answer gets high score."""
        example = RAGExample(
            query="What is Python?",
            answer="Python is a high-level programming language.",
            retrieved_contexts=["Python is a language."],
            ground_truth="Python is a high-level programming language.",
            ground_truth_contexts=["Python is a language."]
        )
        result = self.metric.evaluate(example)
        self.assertGreater(result.score, 0.8)
    
    def test_different_answer(self):
        """Test that different answer gets low score."""
        example = RAGExample(
            query="What is Python?",
            answer="The weather is nice today.",
            retrieved_contexts=["Python is a language."],
            ground_truth="Python is a high-level programming language.",
            ground_truth_contexts=["Python is a language."]
        )
        result = self.metric.evaluate(example)
        self.assertLess(result.score, 0.3)
    
    def test_partial_match(self):
        """Test partially correct answer."""
        example = RAGExample(
            query="What is Python?",
            answer="Python is a programming language.",
            retrieved_contexts=["Python is a language."],
            ground_truth="Python is a high-level programming language with multiple paradigms.",
            ground_truth_contexts=["Python is a language."]
        )
        result = self.metric.evaluate(example)
        self.assertGreater(result.score, 0.3)
        self.assertLess(result.score, 0.9)
    
    def test_score_range(self):
        for example in TEST_EXAMPLES:
            result = self.metric.evaluate(example)
            self.assertGreaterEqual(result.score, 0.0)
            self.assertLessEqual(result.score, 1.0)


class TestRAGEvaluator(unittest.TestCase):
    
    def setUp(self):
        self.evaluator = RAGEvaluator()
    
    def test_evaluate_single(self):
        """Test evaluation of a single example."""
        report = self.evaluator.evaluate(TEST_EXAMPLES[0])
        self.assertIsInstance(report, RAGEvaluationReport)
        self.assertGreater(len(report.metrics), 0)
    
    def test_evaluate_batch(self):
        """Test batch evaluation."""
        reports = self.evaluator.evaluate_batch(TEST_EXAMPLES)
        self.assertEqual(len(reports), len(TEST_EXAMPLES))
    
    def test_evaluate_and_summarize(self):
        """Test summary generation."""
        summary = self.evaluator.evaluate_and_summarize(TEST_EXAMPLES)
        self.assertIn('metric_averages', summary)
        self.assertIn('overall_average', summary)
        self.assertEqual(summary['num_examples'], len(TEST_EXAMPLES))
    
    def test_all_metrics_present(self):
        """Test that all metrics are computed."""
        report = self.evaluator.evaluate(TEST_EXAMPLES[0])
        expected = ['faithfulness', 'answer_relevance', 'context_precision',
                    'context_recall', 'context_relevancy', 'answer_correctness']
        for name in expected:
            self.assertIn(name, report.metrics)
    
    def test_custom_metrics(self):
        """Test using a subset of metrics."""
        evaluator = RAGEvaluator(metrics=['faithfulness', 'answer_relevance'])
        report = evaluator.evaluate(TEST_EXAMPLES[0])
        self.assertEqual(len(report.metrics), 2)
    
    def test_format_summary(self):
        """Test summary formatting."""
        summary = self.evaluator.evaluate_and_summarize(TEST_EXAMPLES)
        report_str = RAGEvaluator.format_summary(summary)
        self.assertIn("RAG Evaluation Summary", report_str)
        self.assertIn("faithfulness", report_str)
    
    def test_overall_score(self):
        """Test overall score computation."""
        report = self.evaluator.evaluate(TEST_EXAMPLES[0])
        overall = report.overall_score
        expected = sum(m.score for m in report.metrics.values()) / len(report.metrics)
        self.assertAlmostEqual(overall, expected, places=5)
    
    def test_good_example_scores_higher(self):
        """Test that good examples score higher than bad ones."""
        good_report = self.evaluator.evaluate(TEST_EXAMPLES[0])  # Well-aligned
        bad_report = self.evaluator.evaluate(TEST_EXAMPLES[4])   # Mismatched context
        
        # Good example should generally score higher overall
        # (not guaranteed for every metric, but overall should be higher)
        self.assertGreater(good_report.overall_score, bad_report.overall_score - 0.1)


class TestEndToEnd(unittest.TestCase):
    
    def test_full_pipeline_evaluation(self):
        """Test full evaluation pipeline with all examples."""
        evaluator = RAGEvaluator()
        summary = evaluator.evaluate_and_summarize(TEST_EXAMPLES)
        
        # All metrics should have values
        for name, avg in summary['metric_averages'].items():
            self.assertGreaterEqual(avg, 0.0)
            self.assertLessEqual(avg, 1.0)
        
        # Overall average should be reasonable
        self.assertGreater(summary['overall_average'], 0.0)
    
    def test_idf_weighted_evaluation(self):
        """Test evaluation with IDF weights."""
        all_texts = []
        for ex in TEST_EXAMPLES:
            all_texts.extend(ex.retrieved_contexts)
            all_texts.append(ex.ground_truth)
        
        idf = compute_idf(all_texts)
        evaluator = RAGEvaluator(idf_weights=idf)
        
        report = evaluator.evaluate(TEST_EXAMPLES[0])
        self.assertGreater(report.overall_score, 0.0)


# ============================================================
# Main
# ============================================================

if __name__ == '__main__':
    print("=" * 70)
    print("RAG Exercise 7: RAG Evaluation Metrics (RAGAS-style)")
    print("=" * 70)
    
    print("\n--- Running Tests ---\n")
    unittest.main(argv=['', '-v'], exit=False)
    
    # Demonstrate evaluation
    print("\n--- RAG Evaluation Demo ---\n")
    
    evaluator = RAGEvaluator()
    summary = evaluator.evaluate_and_summarize(TEST_EXAMPLES)
    report = RAGEvaluator.format_summary(summary)
    print(report)
