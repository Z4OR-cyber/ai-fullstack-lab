"""
第四阶段 4.1 大语言模型（LLM）基础练习
用纯 NumPy 从零实现 Transformer 核心组件
共 10 题，每题独立测试
"""

import numpy as np
import json, math, re
from collections import defaultdict, Counter

# ============================================================
# Test 01: 位置编码 (Positional Encoding)
# 实现标准的 sin/cos 位置编码
# ============================================================

def positional_encoding(max_len, d_model):
    """
    实现 Transformer 论文中的位置编码
    PE(pos, 2i) = sin(pos / 10000^(2i/d_model))
    PE(pos, 2i+1) = cos(pos / 10000^(2i/d_model))
    返回 shape: (max_len, d_model)
    """
    pe = np.zeros((max_len, d_model))
    position = np.arange(max_len).reshape(-1, 1)
    div_term = np.exp(np.arange(0, d_model, 2) * (-math.log(10000.0) / d_model))
    pe[:, 0::2] = np.sin(position * div_term)
    pe[:, 1::2] = np.cos(position * div_term)
    return pe

def test_01_positional_encoding():
    pe = positional_encoding(max_len=10, d_model=16)
    assert pe.shape == (10, 16), f"Shape should be (10,16), got {pe.shape}"
    assert np.allclose(pe[0, 0], 0.0), "PE(0,0) = sin(0) = 0"
    assert np.allclose(pe[0, 1], 1.0), "PE(0,1) = cos(0) = 1"
    # 不同位置的编码应不同
    assert not np.allclose(pe[0], pe[1]), "Different positions should have different encodings"
    # 相邻位置编码相似度较高
    sim_01 = np.dot(pe[0], pe[1]) / (np.linalg.norm(pe[0]) * np.linalg.norm(pe[1]))
    sim_09 = np.dot(pe[0], pe[9]) / (np.linalg.norm(pe[0]) * np.linalg.norm(pe[9]))
    assert sim_01 > sim_09, "Closer positions should have higher similarity"
    print("✅ Test 01 passed: Positional Encoding")

# ============================================================
# Test 02: Scaled Dot-Product Attention
# 实现缩放点积注意力
# ============================================================

def scaled_dot_product_attention(Q, K, V, mask=None):
    """
    Q, K, V: shape (seq_len, d_k)
    Attention(Q,K,V) = softmax(QK^T / sqrt(d_k)) V
    """
    d_k = Q.shape[-1]
    scores = Q @ K.T / math.sqrt(d_k)
    if mask is not None:
        scores = scores + mask  # mask中 -inf 的位置会被屏蔽
    # softmax with numerical stability
    scores_max = np.max(scores, axis=-1, keepdims=True)
    exp_scores = np.exp(scores - scores_max)
    attention_weights = exp_scores / np.sum(exp_scores, axis=-1, keepdims=True)
    output = attention_weights @ V
    return output, attention_weights

def test_02_attention():
    np.random.seed(42)
    Q = np.random.randn(4, 8)
    K = np.random.randn(4, 8)
    V = np.random.randn(4, 8)
    output, weights = scaled_dot_product_attention(Q, K, V)
    assert output.shape == (4, 8), f"Output shape mismatch: {output.shape}"
    assert weights.shape == (4, 4), f"Weights shape mismatch: {weights.shape}"
    # 每行权重和为1
    row_sums = np.sum(weights, axis=-1)
    assert np.allclose(row_sums, 1.0), f"Attention weights should sum to 1, got {row_sums}"
    # 所有权重非负
    assert np.all(weights >= 0), "Attention weights should be non-negative"
    # 因果 mask: 下三角为0, 上三角为-inf
    mask = np.triu(np.ones((4, 4)) * -np.inf, k=1)
    output_masked, weights_masked = scaled_dot_product_attention(Q, K, V, mask=mask)
    # 上三角应为0
    assert np.allclose(weights_masked[np.triu_indices(4, k=1)], 0.0), "Upper triangle should be masked"
    # 第一个位置只关注自己
    assert np.allclose(weights_masked[0], [1.0, 0.0, 0.0, 0.0]), \
        f"First position should only attend to itself, got {weights_masked[0]}"
    print("✅ Test 02 passed: Scaled Dot-Product Attention")

# ============================================================
# Test 03: Multi-Head Attention
# 实现多头注意力机制
# ============================================================

class MultiHeadAttention:
    def __init__(self, d_model, num_heads):
        assert d_model % num_heads == 0
        self.d_model = d_model
        self.num_heads = num_heads
        self.d_k = d_model // num_heads
        # 初始化权重矩阵
        self.W_q = np.random.randn(d_model, d_model) * 0.1
        self.W_k = np.random.randn(d_model, d_model) * 0.1
        self.W_v = np.random.randn(d_model, d_model) * 0.1
        self.W_o = np.random.randn(d_model, d_model) * 0.1

    def forward(self, x, mask=None):
        seq_len = x.shape[0]
        Q = x @ self.W_q
        K = x @ self.W_k
        V = x @ self.W_v
        # 分头: (seq_len, d_model) -> (num_heads, seq_len, d_k)
        Q = Q.reshape(seq_len, self.num_heads, self.d_k).transpose(1, 0, 2)
        K = K.reshape(seq_len, self.num_heads, self.d_k).transpose(1, 0, 2)
        V = V.reshape(seq_len, self.num_heads, self.d_k).transpose(1, 0, 2)
        # 每个头独立计算 attention
        outputs = []
        for i in range(self.num_heads):
            out, _ = scaled_dot_product_attention(Q[i], K[i], V[i], mask)
            outputs.append(out)
        # 拼接所有头: (num_heads, seq_len, d_k) -> (seq_len, d_model)
        concat = np.stack(outputs, axis=1).reshape(seq_len, self.d_model)
        return concat @ self.W_o

def test_03_multi_head_attention():
    np.random.seed(42)
    d_model, num_heads = 32, 4
    mha = MultiHeadAttention(d_model, num_heads)
    x = np.random.randn(6, d_model)
    output = mha.forward(x)
    assert output.shape == (6, d_model), f"Output shape mismatch: {output.shape}"
    # 因果 mask 测试
    mask = np.triu(np.ones((6, 6)) * -np.inf, k=1)
    output_masked = mha.forward(x, mask)
    assert output_masked.shape == (6, d_model), "Masked output shape mismatch"
    # 带 mask 和不带 mask 的输出应该不同
    assert not np.allclose(output, output_masked), "Mask should change the output"
    print("✅ Test 03 passed: Multi-Head Attention")

# ============================================================
# Test 04: Feed-Forward Network + Layer Normalization
# ============================================================

def feed_forward(x, d_ff, w1=None, b1=None, w2=None, b2=None):
    """FFN(x) = max(0, xW1 + b1) W2 + b2"""
    d_model = x.shape[-1]
    if w1 is None:
        w1 = np.random.randn(d_model, d_ff) * 0.1
        b1 = np.zeros(d_ff)
        w2 = np.random.randn(d_ff, d_model) * 0.1
        b2 = np.zeros(d_model)
    hidden = np.maximum(0, x @ w1 + b1)  # ReLU
    return hidden @ w2 + b2

def layer_norm(x, eps=1e-6):
    """Layer Normalization: 对最后一个维度做归一化"""
    mean = np.mean(x, axis=-1, keepdims=True)
    var = np.var(x, axis=-1, keepdims=True)
    return (x - mean) / np.sqrt(var + eps)

def test_04_ffn_and_layernorm():
    np.random.seed(42)
    x = np.random.randn(4, 16) * 5 + 10  # 偏移数据
    # FFN
    ff_out = feed_forward(x, d_ff=64)
    assert ff_out.shape == (4, 16), f"FFN output shape mismatch: {ff_out.shape}"
    # LayerNorm
    ln_out = layer_norm(x)
    assert ln_out.shape == x.shape, "LayerNorm shape mismatch"
    # 归一化后每行均值为0，方差为1
    row_means = np.mean(ln_out, axis=-1)
    row_stds = np.std(ln_out, axis=-1)
    assert np.allclose(row_means, 0, atol=1e-5), f"Mean should be ~0, got {row_means}"
    assert np.allclose(row_stds, 1, atol=1e-2), f"Std should be ~1, got {row_stds}"
    # FFN + LayerNorm (残差连接)
    x_normed = layer_norm(x + ff_out)  # Post-LN
    assert x_normed.shape == x.shape
    print("✅ Test 04 passed: Feed-Forward Network + Layer Normalization")

# ============================================================
# Test 05: BPE 分词器 (Byte-Pair Encoding)
# ============================================================

class SimpleBPE:
    """简化版 BPE 分词器"""
    def __init__(self):
        self.merges = []
        self.vocab = {}

    def get_pairs(self, word):
        """获取词中所有相邻字符对"""
        return [(word[i], word[i+1]) for i in range(len(word)-1)]

    def train(self, corpus, num_merges=20):
        """从语料库训练 BPE 合并规则"""
        # 统计词频
        word_freqs = Counter()
        for text in corpus:
            for word in text.split():
                # 每个词表示为字符元组，末尾加 </w>
                word_tuple = tuple(word) + ('</w>',)
                word_freqs[word_tuple] += 1
        # 迭代合并
        for _ in range(num_merges):
            pairs = Counter()
            for word, freq in word_freqs.items():
                for p in self.get_pairs(list(word)):
                    pairs[p] += freq
            if not pairs:
                break
            best_pair = pairs.most_common(1)[0][0]
            self.merges.append(best_pair)
            # 合并所有词中的该字符对
            new_word_freqs = Counter()
            for word, freq in word_freqs.items():
                new_word = self._merge_word(list(word), best_pair)
                new_word_freqs[tuple(new_word)] += freq
            word_freqs = new_word_freqs
        # 构建词表
        self.vocab = set()
        for word in word_freqs:
            for token in word:
                self.vocab.add(token)
        return self.vocab

    def _merge_word(self, word, pair):
        """在词中合并指定的字符对"""
        result = []
        i = 0
        while i < len(word):
            if i < len(word) - 1 and word[i] == pair[0] and word[i+1] == pair[1]:
                result.append(word[i] + word[i+1])
                i += 2
            else:
                result.append(word[i])
                i += 1
        return result

    def encode(self, word):
        """对单个词进行 BPE 编码"""
        tokens = list(word) + ['</w>']
        for merge in self.merges:
            tokens = self._merge_word(tokens, merge)
        return tokens

def test_05_bpe():
    corpus = [
        "low low low low low",
        "lower lower newer newer newer",
        "newest newest lowest newest",
        "newer newest low lower",
    ]
    bpe = SimpleBPE()
    vocab = bpe.train(corpus, num_merges=15)
    assert len(vocab) > 0, "Vocab should not be empty"
    assert '</w>' in vocab or any('w>' in v for v in vocab), "End token should be in vocab"
    # 编码测试
    tokens = bpe.encode("lowest")
    assert isinstance(tokens, list), "Encode should return a list"
    assert len(tokens) >= 1, "Should have at least one token"
    # 训练后的合并应该减少 token 数量
    raw_tokens = list("lowest") + ['</w>']
    assert len(tokens) <= len(raw_tokens), "BPE should reduce token count"
    # 重复词应被合并成更少的 token
    tokens_newer = bpe.encode("newer")
    tokens_new = bpe.encode("new")
    # newer 应该比 new + er 更紧凑（如果 er 被合并了）
    print(f"   'lowest' -> {tokens}")
    print(f"   'newer' -> {tokens_newer}")
    print(f"   'new' -> {tokens_new}")
    print("✅ Test 05 passed: BPE Tokenizer")

# ============================================================
# Test 06: LoRA (Low-Rank Adaptation) 模拟
# ============================================================

def lora_linear(x, W, A, B):
    """
    LoRA: output = x @ W + x @ A @ B
    其中 A: (d_in, r), B: (r, d_out), r << min(d_in, d_out)
    """
    return x @ W + x @ A @ B

def test_06_lora():
    np.random.seed(42)
    d_in, d_out, r = 64, 64, 4  # r=4 远小于 64
    W = np.random.randn(d_in, d_out) * 0.1  # 原始权重（冻结）
    # LoRA 参数
    A = np.random.randn(d_in, r) * 0.01  # 低秩矩阵 A
    B = np.zeros((r, d_out))              # 初始 B=0, 训练时更新
    x = np.random.randn(8, d_in)
    # 初始时 B=0, LoRA 贡献为0
    y_base = x @ W
    y_lora_init = lora_linear(x, W, A, B)
    assert np.allclose(y_base, y_lora_init), "With B=0, LoRA should not change output"
    # 训练后 B 非零
    B_trained = np.random.randn(r, d_out) * 0.1
    y_lora_trained = lora_linear(x, W, A, B_trained)
    assert not np.allclose(y_base, y_lora_trained), "After training, LoRA should change output"
    # 参数量对比
    full_params = d_in * d_out
    lora_params = d_in * r + r * d_out
    assert lora_params < full_params, f"LoRA params ({lora_params}) should be less than full ({full_params})"
    compression_ratio = full_params / lora_params
    print(f"   Full params: {full_params}, LoRA params: {lora_params}, compression: {compression_ratio:.1f}x")
    print("✅ Test 06 passed: LoRA (Low-Rank Adaptation)")

# ============================================================
# Test 07: RAG (检索增强生成) 模拟
# ============================================================

def cosine_similarity(a, b):
    """计算余弦相似度"""
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-8)

def rag_retrieve(query_embedding, doc_embeddings, top_k=3):
    """检索最相关的文档"""
    similarities = [cosine_similarity(query_embedding, doc) for doc in doc_embeddings]
    ranked_indices = np.argsort(similarities)[::-1][:top_k]
    return ranked_indices.tolist(), similarities

def rag_generate(query, retrieved_docs):
    """模拟生成：拼接检索到的上下文"""
    context = " ".join(retrieved_docs)
    return f"基于以下上下文回答问题 '{query}': 上下文=[{context}]"

def test_07_rag():
    np.random.seed(42)
    # 模拟文档嵌入向量
    docs = [
        "Python 是一种解释型编程语言",
        "Transformer 使用自注意力机制处理序列",
        "LoRA 通过低秩矩阵减少微调参数",
        "RAG 结合检索和生成提升回答质量",
        "FastAPI 是一个高性能的 Python Web 框架",
    ]
    # 模拟嵌入：让相关文档向量接近
    doc_embeddings = np.random.randn(5, 64)
    # 让第1个和第3个文档与查询更相似（关于 Transformer 和 LoRA）
    query_embedding = 0.7 * doc_embeddings[1] + 0.5 * doc_embeddings[2] + 0.3 * np.random.randn(64)
    # 检索
    indices, sims = rag_retrieve(query_embedding, doc_embeddings, top_k=3)
    assert len(indices) == 3, f"Should retrieve 3 docs, got {len(indices)}"
    assert indices[0] in [1, 2], f"Top result should be doc 1 or 2, got doc {indices[0]}"
    # 相似度排序
    retrieved_sims = [sims[i] for i in indices]
    assert retrieved_sims[0] >= retrieved_sims[1] >= retrieved_sims[2], "Should be sorted by similarity"
    # 生成
    retrieved_docs = [docs[i] for i in indices]
    answer = rag_generate("什么是 LoRA?", retrieved_docs)
    assert "LoRA" in answer, "Answer should mention LoRA"
    assert "上下文" in answer, "Answer should include context"
    print(f"   Retrieved: {[docs[i][:20] for i in indices]}")
    print(f"   Answer: {answer[:80]}...")
    print("✅ Test 07 passed: RAG (Retrieval-Augmented Generation)")

# ============================================================
# Test 08: 模型量化模拟 (INT8 / INT4)
# ============================================================

def quantize_int8(weights):
    """
    INT8 量化：将浮点权重映射到 [-128, 127]
    scale = max(|w|) / 127
    quantized = round(w / scale)
    """
    max_val = np.max(np.abs(weights))
    scale = max_val / 127.0
    quantized = np.round(weights / scale).astype(np.int8)
    return quantized, scale

def dequantize(quantized, scale):
    """反量化：恢复为浮点数"""
    return quantized.astype(np.float32) * scale

def quantize_int4(weights):
    """
    INT4 量化：映射到 [-8, 7]
    """
    max_val = np.max(np.abs(weights))
    scale = max_val / 7.0
    quantized = np.round(weights / scale).astype(np.int8)
    quantized = np.clip(quantized, -8, 7)
    return quantized, scale

def test_08_quantization():
    np.random.seed(42)
    W = np.random.randn(128, 128).astype(np.float32) * 0.5
    # INT8 量化
    q8, scale8 = quantize_int8(W)
    deq8 = dequantize(q8, scale8)
    assert q8.dtype == np.int8, f"INT8 quantized should be int8, got {q8.dtype}"
    assert np.max(q8) <= 127 and np.min(q8) >= -128, "INT8 range should be [-128, 127]"
    # 量化误差
    mse_int8 = np.mean((W - deq8) ** 2)
    # INT4 量化
    q4, scale4 = quantize_int4(W)
    deq4 = dequantize(q4, scale4)
    assert np.max(q4) <= 7 and np.min(q4) >= -8, "INT4 range should be [-8, 7]"
    mse_int4 = np.mean((W - deq4) ** 2)
    # INT4 误差应大于 INT8
    assert mse_int4 > mse_int8, f"INT4 error ({mse_int4}) should be larger than INT8 ({mse_int8})"
    # 内存占用对比（理论值）
    mem_fp32 = W.nbytes
    mem_int8 = q8.nbytes
    mem_int4 = q4.nbytes // 2  # INT4 理论上半字节
    print(f"   FP32 memory: {mem_fp32} bytes, INT8: {mem_int8} bytes, INT4(est): {mem_int4} bytes")
    print(f"   MSE: INT8={mse_int8:.6f}, INT4={mse_int4:.6f}")
    print("✅ Test 08 passed: Model Quantization (INT8/INT4)")

# ============================================================
# Test 09: Beam Search 解码
# ============================================================

def beam_search(initial_state, get_next_tokens, beam_width=3, max_steps=5):
    """
    简化版 Beam Search
    initial_state: 初始状态
    get_next_tokens: 函数(state) -> [(log_prob, token, new_state), ...]
    返回: [(log_prob, token_sequence), ...]
    """
    beams = [(0.0, [], initial_state)]  # (cumulative_log_prob, tokens, state)
    for step in range(max_steps):
        candidates = []
        for log_prob, tokens, state in beams:
            next_tokens = get_next_tokens(state)
            for np_log, token, new_state in next_tokens:
                candidates.append((log_prob + np_log, tokens + [token], new_state))
        # 保留 top-beam_width
        candidates.sort(key=lambda x: x[0], reverse=True)
        beams = candidates[:beam_width]
    return [(lp, toks) for lp, toks, _ in beams]

def test_09_beam_search():
    np.random.seed(42)
    # 模拟一个简单的解码图
    # 每个状态返回3个候选 token 及其 log prob
    token_vocab = ["hello", "world", "foo", "bar", "end"]
    state_counter = [0]  # 用列表做可变计数器
    def get_next_tokens(state):
        state_counter[0] += 1
        np.random.seed(state * 42 + state_counter[0])
        results = []
        for i in range(3):
            log_prob = np.random.uniform(-2, 0)  # log prob in [-2, 0]
            token = token_vocab[(state + i) % len(token_vocab)]
            new_state = state + i + 1
            results.append((log_prob, token, new_state))
        return results
    results = beam_search(1, get_next_tokens, beam_width=3, max_steps=4)
    assert len(results) == 3, f"Should return 3 beams, got {len(results)}"
    # 结果按 log_prob 降序排列
    log_probs = [r[0] for r in results]
    assert log_probs[0] >= log_probs[1] >= log_probs[2], "Results should be sorted by log prob"
    # 每个 beam 有4个 token（4步）
    for lp, tokens in results:
        assert len(tokens) == 4, f"Each beam should have 4 tokens, got {len(tokens)}"
    print(f"   Top beam: log_prob={results[0][0]:.4f}, tokens={results[0][1]}")
    print(f"   All beam scores: {[f'{r[0]:.4f}' for r in results]}")
    print("✅ Test 09 passed: Beam Search")

# ============================================================
# Test 10: KV Cache 模拟 + 推理优化
# ============================================================

class KVCache:
    """模拟 Transformer 的 KV Cache"""
    def __init__(self, num_layers, num_heads, d_k, max_seq_len=256):
        self.num_layers = num_layers
        self.num_heads = num_heads
        self.d_k = d_k
        self.max_seq_len = max_seq_len
        self.k_cache = {}  # layer -> list of (seq_len, d_k) arrays per head
        self.v_cache = {}
        for layer in range(num_layers):
            self.k_cache[layer] = [np.zeros((0, d_k)) for _ in range(num_heads)]
            self.v_cache[layer] = [np.zeros((0, d_k)) for _ in range(num_heads)]
        self.seq_len = 0

    def append(self, layer, head, k_new, v_new):
        """追加新的 K, V"""
        self.k_cache[layer][head] = np.vstack([self.k_cache[layer][head], k_new.reshape(1, -1)])
        self.v_cache[layer][head] = np.vstack([self.v_cache[layer][head], v_new.reshape(1, -1)])

    def get(self, layer, head):
        """获取该层该头的所有 K, V"""
        return self.k_cache[layer][head], self.v_cache[layer][head]

def test_10_kv_cache():
    np.random.seed(42)
    num_layers, num_heads, d_k = 4, 4, 16
    cache = KVCache(num_layers, num_heads, d_k)
    # 模拟逐 token 生成
    num_tokens = 5
    for t in range(num_tokens):
        for layer in range(num_layers):
            for head in range(num_heads):
                k = np.random.randn(d_k)
                v = np.random.randn(d_k)
                cache.append(layer, head, k, v)
    cache.seq_len = num_tokens
    # 验证缓存大小
    for layer in range(num_layers):
        for head in range(num_heads):
            k, v = cache.get(layer, head)
            assert k.shape == (num_tokens, d_k), \
                f"Layer {layer} head {head}: K shape {k.shape}, expected ({num_tokens}, {d_k})"
            assert v.shape == (num_tokens, d_k), "V shape mismatch"
    # 模拟有/无 cache 的计算量对比
    # 无 cache: 每生成一个 token 需要对之前所有 token 重新计算 K, V
    # 有 cache: 只需计算新 token 的 K, V
    total_no_cache = 0
    total_with_cache = 0
    for t in range(1, num_tokens + 1):
        total_no_cache += t  # 重新计算 t 个 token 的 K,V
        total_with_cache += 1  # 只计算 1 个新 token
    speedup = total_no_cache / total_with_cache
    print(f"   Tokens: {num_tokens}, Total K,V computations without cache: {total_no_cache}, with cache: {total_with_cache}")
    print(f"   Theoretical speedup: {speedup:.1f}x")
    assert total_with_cache < total_no_cache, "Cache should reduce computation"
    assert speedup > 1, "Should have speedup > 1x"
    print("✅ Test 10 passed: KV Cache + Inference Optimization")

# ============================================================
# 运行所有测试
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("第四阶段 4.1 大语言模型（LLM）基础练习")
    print("=" * 60)
    print()
    tests = [
        test_01_positional_encoding,
        test_02_attention,
        test_03_multi_head_attention,
        test_04_ffn_and_layernorm,
        test_05_bpe,
        test_06_lora,
        test_07_rag,
        test_08_quantization,
        test_09_beam_search,
        test_10_kv_cache,
    ]
    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"❌ {test.__name__} FAILED: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
        print()
    print("=" * 60)
    print(f"结果: {passed}/{passed + failed} 通过")
    print("=" * 60)
