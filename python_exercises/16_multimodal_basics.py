"""
第四阶段 4.3 多模态基础练习
用纯 NumPy 实现 CLIP、SAM、Whisper、多模态融合等核心概念
共 10 题，每题独立测试
"""

import numpy as np
import json, math
from collections import defaultdict

# ============================================================
# Test 01: CLIP 对比学习 (Contrastive Learning)
# 模拟 CLIP 的图文对齐机制
# ============================================================

def contrastive_loss(image_features, text_features, temperature=0.07):
    """
    CLIP 对比损失
    image_features: (N, D) 图像嵌入
    text_features: (N, D) 文本嵌入
    同一对的 (image_i, text_i) 应相似，不同对应应远离
    """
    # L2 归一化
    image_features = image_features / (np.linalg.norm(image_features, axis=1, keepdims=True) + 1e-8)
    text_features = text_features / (np.linalg.norm(text_features, axis=1, keepdims=True) + 1e-8)
    # 计算相似度矩阵
    logits = image_features @ text_features.T / temperature  # (N, N)
    # 对称损失: image -> text 和 text -> image
    labels = np.arange(len(image_features))
    # softmax cross-entropy
    def ce_loss(logits, labels):
        max_logits = np.max(logits, axis=1, keepdims=True)
        exp_logits = np.exp(logits - max_logits)
        log_sum_exp = np.log(np.sum(exp_logits, axis=1)) + max_logits.squeeze()
        loss = log_sum_exp - logits[np.arange(len(labels)), labels]
        return np.mean(loss)
    loss_i2t = ce_loss(logits, labels)
    loss_t2i = ce_loss(logits.T, labels)
    return (loss_i2t + loss_t2i) / 2, logits

def test_01_clip_contrastive():
    np.random.seed(42)
    N, D = 8, 64
    # 模拟：匹配的图文对相似度高
    image_features = np.random.randn(N, D)
    # 文本特征 = 图像特征 + 小噪声（模拟对齐）
    text_features = image_features + np.random.randn(N, D) * 0.3
    loss_aligned, logits_aligned = contrastive_loss(image_features, text_features)
    # 不匹配的图文对
    text_features_misaligned = np.random.randn(N, D)
    loss_misaligned, _ = contrastive_loss(image_features, text_features_misaligned)
    # 对齐的损失应更低
    assert loss_aligned < loss_misaligned, \
        f"Aligned loss ({loss_aligned:.4f}) should be < misaligned ({loss_misaligned:.4f})"
    # 对角线相似度应最高（匹配对）
    diag = np.diag(logits_aligned)
    assert np.all(diag >= np.sort(logits_aligned, axis=1)[:, -2]), \
        "Diagonal (matched pairs) should have highest or second-highest logits"
    print(f"   Aligned loss: {loss_aligned:.4f}, Misaligned loss: {loss_misaligned:.4f}")
    print("✅ Test 01 passed: CLIP Contrastive Learning")

# ============================================================
# Test 02: CLIP 零样本分类 (Zero-Shot Classification)
# ============================================================

def clip_zero_shot_classification(image_features, class_text_features, class_names):
    """
    零样本分类：计算图像与各类别文本的相似度，取最高
    image_features: (N, D)
    class_text_features: (C, D)
    """
    # L2 归一化
    image_features = image_features / (np.linalg.norm(image_features, axis=1, keepdims=True) + 1e-8)
    class_text_features = class_text_features / (np.linalg.norm(class_text_features, axis=1, keepdims=True) + 1e-8)
    # 相似度矩阵 (N, C)
    similarities = image_features @ class_text_features.T
    # 取每个图像最相似的类别
    predictions = np.argmax(similarities, axis=1)
    predicted_labels = [class_names[p] for p in predictions]
    return predicted_labels, similarities

def test_02_zero_shot():
    np.random.seed(42)
    D = 32
    class_names = ["猫", "狗", "鸟", "鱼"]
    # 每个类别的文本嵌入（用不同的随机种子模拟不同类别的嵌入）
    class_text_features = np.array([
        np.random.RandomState(i).randn(D) for i in range(4)
    ])
    # 测试图像：与各类别嵌入相近
    test_images = np.array([
        class_text_features[0] + np.random.randn(D) * 0.2,  # 猫
        class_text_features[1] + np.random.randn(D) * 0.2,  # 狗
        class_text_features[2] + np.random.randn(D) * 0.2,  # 鸟
        class_text_features[3] + np.random.randn(D) * 0.2,  # 鱼
        class_text_features[0] + np.random.randn(D) * 0.2,  # 猫
    ])
    true_labels = ["猫", "狗", "鸟", "鱼", "猫"]
    predicted, sims = clip_zero_shot_classification(test_images, class_text_features, class_names)
    assert len(predicted) == 5
    correct = sum(1 for p, t in zip(predicted, true_labels) if p == t)
    accuracy = correct / len(true_labels)
    assert accuracy >= 0.8, f"Zero-shot accuracy should be >= 80%, got {accuracy*100:.0f}%"
    # 相似度矩阵形状
    assert sims.shape == (5, 4), f"Similarity matrix shape mismatch: {sims.shape}"
    print(f"   Predicted: {predicted}")
    print(f"   True:      {true_labels}")
    print(f"   Accuracy: {accuracy*100:.0f}%")
    print("✅ Test 02 passed: CLIP Zero-Shot Classification")

# ============================================================
# Test 03: SAM (Segment Anything) 分割概念
# 模拟点引导分割 + 掩码生成
# ============================================================

def point_guided_segmentation(image, point, threshold=0.5):
    """
    模拟 SAM 的点引导分割
    image: (H, W) 灰度图（模拟特征图）
    point: (x, y) 提示点
    返回: (H, W) 二值掩码
    """
    H, W = image.shape
    px, py = point
    # 计算每个像素到提示点的距离
    yy, xx = np.meshgrid(np.arange(W), np.arange(H))
    distances = np.sqrt((xx - px) ** 2 + (yy - py) ** 2)
    # 基于距离和像素值相似度的组合
    point_value = image[py, px]
    value_diff = np.abs(image - point_value)
    # 分数 = 距离越近越好 + 值越相似越好
    distance_score = 1.0 / (1.0 + distances / max(H, W))
    value_score = 1.0 / (1.0 + value_diff)
    combined_score = 0.5 * distance_score + 0.5 * value_score
    mask = combined_score > threshold
    return mask.astype(np.uint8), combined_score

def test_03_sam_segmentation():
    np.random.seed(42)
    H, W = 64, 64
    # 创建一个有两个区域的图像：左上角亮区，右下角暗区
    image = np.zeros((H, W))
    image[:32, :32] = 0.8  # 左上角亮区
    image[32:, 32:] = 0.3  # 右下角暗区
    image[32:, :32] = 0.1  # 左下角
    image[:32, 32:] = 0.1  # 右上角
    # 在亮区中心点一个提示点
    mask, score = point_guided_segmentation(image, (16, 16), threshold=0.65)
    assert mask.shape == (H, W), f"Mask shape mismatch: {mask.shape}"
    assert mask.dtype == np.uint8
    # 掩码应该主要覆盖左上角区域
    coverage_top_left = np.mean(mask[:32, :32])
    coverage_bottom = np.mean(mask[32:, :32])
    coverage_right = np.mean(mask[:32, 32:])
    coverage_others = (coverage_bottom + coverage_right) / 2
    assert coverage_top_left > coverage_others, \
        f"Mask should cover top-left region more: {coverage_top_left:.2f} vs {coverage_others:.2f}"
    # 在暗区中心点提示
    mask2, _ = point_guided_segmentation(image, (48, 48), threshold=0.65)
    coverage_bottom_right = np.mean(mask2[32:, 32:])
    assert coverage_bottom_right > 0.3, "Second mask should cover bottom-right"
    # 两个掩码不应完全重叠
    overlap = np.mean(mask & mask2)
    assert overlap < 0.3, "Two masks should not heavily overlap"
    print(f"   Mask 1 coverage (top-left): {coverage_top_left:.2f}")
    print(f"   Mask 2 coverage (bottom-right): {coverage_bottom_right:.2f}")
    print("✅ Test 03 passed: SAM Point-Guided Segmentation")

# ============================================================
# Test 04: Whisper 语音识别概念 (CTC 解码)
# 模拟 CTC (Connectionist Temporal Classification) 解码
# ============================================================

def ctc_greedy_decode(log_probs, blank_id=0):
    """
    CTC 贪心解码
    log_probs: (T, V) 时间步 x 词表大小 的对数概率
    blank_id: 空白标签 ID
    返回: 解码后的序列
    """
    # 每个时间步取概率最高的 token
    best_path = np.argmax(log_probs, axis=1)
    # 合并重复的 token
    decoded = []
    prev = None
    for token in best_path:
        if token != prev and token != blank_id:
            decoded.append(int(token))
        prev = token
    return decoded

def ctc_beam_search_decode(log_probs, beam_width=3, blank_id=0):
    """
    CTC Beam Search 解码（简化版）
    每步保留 top-k 原始路径，最后对最佳路径做 CTC 解码
    """
    T, V = log_probs.shape
    beams = [((), 0.0)]  # (raw_path_tuple, log_prob)
    for t in range(T):
        candidates = []
        for path, log_prob in beams:
            top_tokens = np.argsort(log_probs[t])[-beam_width:][::-1]
            for v in top_tokens:
                new_path = path + (v,)
                new_log_prob = log_prob + log_probs[t, v]
                candidates.append((new_path, new_log_prob))
        candidates.sort(key=lambda x: x[1], reverse=True)
        beams = candidates[:beam_width]
    # 对最佳路径做 CTC 解码
    best_path = beams[0][0] if beams else ()
    decoded = []
    prev = None
    for token in best_path:
        if token != prev and token != blank_id:
            decoded.append(int(token))
        prev = token
    return decoded

def test_04_whisper_ctc():
    np.random.seed(42)
    T, V = 20, 6  # 20个时间步, 6个token (0=blank, 1-5=字符)
    # 构造有意义的概率分布：交替出现 token 1, 2, 3
    log_probs = np.full((T, V), -2.0)  # 默认低概率
    # 模拟语音信号：token 1 在时间 0-5，token 2 在时间 7-12，token 3 在时间 14-19
    for t in range(6):
        log_probs[t, 1] = 0.0  # token 1
    for t in range(6, 7):
        log_probs[t, 0] = 0.0  # blank (间隔)
    for t in range(7, 13):
        log_probs[t, 2] = 0.0  # token 2
    for t in range(13, 14):
        log_probs[t, 0] = 0.0  # blank
    for t in range(14, 20):
        log_probs[t, 3] = 0.0  # token 3
    # 贪心解码
    decoded = ctc_greedy_decode(log_probs, blank_id=0)
    assert decoded == [1, 2, 3], f"Expected [1,2,3], got {decoded}"
    # Beam search 解码
    beam_result = ctc_beam_search_decode(log_probs, beam_width=3, blank_id=0)
    assert beam_result == [1, 2, 3], f"Expected [1,2,3], got {beam_result}"
    # 测试连续相同 token
    log_probs2 = np.full((T, V), -2.0)
    for t in range(10):
        log_probs2[t, 1] = 0.0  # 连续 token 1
    for t in range(10, 11):
        log_probs2[t, 0] = 0.0  # blank
    for t in range(11, 20):
        log_probs2[t, 1] = 0.0  # 再次 token 1
    decoded2 = ctc_greedy_decode(log_probs2, blank_id=0)
    # 有 blank 分隔时应输出 [1, 1]
    assert decoded2 == [1, 1], f"Expected [1,1] with blank separation, got {decoded2}"
    # 无 blank 分隔时应合并
    log_probs3 = np.full((T, V), -2.0)
    for t in range(20):
        log_probs3[t, 1] = 0.0  # 全是 token 1
    decoded3 = ctc_greedy_decode(log_probs3, blank_id=0)
    assert decoded3 == [1], f"Expected [1] (merged), got {decoded3}"
    print(f"   Greedy decode: {decoded}")
    print(f"   Beam search decode: {beam_result}")
    print(f"   With blank separation: {decoded2}")
    print("✅ Test 04 passed: Whisper CTC Decoding")

# ============================================================
# Test 05: 多模态融合 (Early / Late / Cross-Attention Fusion)
# ============================================================

def early_fusion(text_features, image_features, projection_dim=32):
    """早期融合：将不同模态特征拼接后投影"""
    # 拼接
    concat = np.concatenate([text_features, image_features], axis=-1)
    # 随机投影到统一空间
    np.random.seed(42)
    W = np.random.randn(concat.shape[-1], projection_dim) * 0.1
    fused = concat @ W
    return fused

def late_fusion(text_logits, image_logits, alpha=0.5):
    """晚期融合：各模态独立预测后加权融合"""
    return alpha * text_logits + (1 - alpha) * image_logits

def cross_attention_fusion(query, key_value, d_k=32):
    """交叉注意力融合：用一种模态做 Query，另一种做 Key/Value"""
    np.random.seed(42)
    W_q = np.random.randn(query.shape[-1], d_k) * 0.1
    W_k = np.random.randn(key_value.shape[-1], d_k) * 0.1
    W_v = np.random.randn(key_value.shape[-1], d_k) * 0.1
    Q = query @ W_q
    K = key_value @ W_k
    V = key_value @ W_v
    d_k_actual = Q.shape[-1]
    scores = Q @ K.T / math.sqrt(d_k_actual)
    # softmax
    scores_max = np.max(scores, axis=-1, keepdims=True)
    attn = np.exp(scores - scores_max) / np.sum(np.exp(scores - scores_max), axis=-1, keepdims=True)
    output = attn @ V
    return output, attn

def test_05_multimodal_fusion():
    np.random.seed(42)
    D_text, D_image = 64, 128
    text_feat = np.random.randn(4, D_text)
    image_feat = np.random.randn(4, D_image)
    # 早期融合
    early = early_fusion(text_feat, image_feat, projection_dim=32)
    assert early.shape == (4, 32), f"Early fusion shape mismatch: {early.shape}"
    # 晚期融合
    text_logits = np.array([[0.8, 0.2], [0.3, 0.7], [0.6, 0.4], [0.1, 0.9]])
    image_logits = np.array([[0.6, 0.4], [0.5, 0.5], [0.7, 0.3], [0.2, 0.8]])
    late = late_fusion(text_logits, image_logits, alpha=0.6)
    assert late.shape == (4, 2)
    # 验证加权
    assert np.allclose(late[0], 0.6 * text_logits[0] + 0.4 * image_logits[0])
    # 交叉注意力融合
    cross_out, attn = cross_attention_fusion(text_feat, image_feat, d_k=32)
    assert cross_out.shape == (4, 32), f"Cross-attention output shape mismatch: {cross_out.shape}"
    assert attn.shape == (4, 4), f"Attention shape mismatch: {attn.shape}"
    # 注意力权重每行和为1
    assert np.allclose(np.sum(attn, axis=-1), 1.0), "Attention weights should sum to 1"
    print(f"   Early fusion: {text_feat.shape} + {image_feat.shape} -> {early.shape}")
    print(f"   Late fusion logits[0]: text={text_logits[0]}, image={image_logits[0]}, fused={late[0]}")
    print(f"   Cross-attention output: {cross_out.shape}")
    print("✅ Test 05 passed: Multimodal Fusion (Early/Late/Cross-Attention)")

# ============================================================
# Test 06: 图像描述生成 (Image Captioning) 模拟
# ============================================================

class MockImageCaptioner:
    """模拟图像描述生成流水线"""
    def __init__(self):
        # 模拟的视觉词汇表
        self.vocab = ["<START>", "<END>", "a", "cat", "dog", "sitting", "on", "table", "running", "grass", "red", "ball"]
        self.vocab_size = len(self.vocab)
        # 模拟的视觉概念到文本的映射
        self.concept_to_words = {
            "animal_cat": ["a", "cat", "sitting"],
            "animal_dog": ["a", "dog", "running"],
            "object_table": ["on", "table"],
            "object_ball": ["red", "ball"],
            "scene_grass": ["on", "grass"],
        }

    def extract_concepts(self, image_features):
        """模拟视觉特征 -> 概念提取"""
        # 用特征的统计特性决定概念
        concepts = []
        if image_features[0] > 0.5:
            concepts.append("animal_cat")
        elif image_features[0] > 0.2:
            concepts.append("animal_dog")
        if image_features[1] > 0.5:
            concepts.append("object_table")
        if image_features[2] > 0.5:
            concepts.append("object_ball")
        if image_features[3] > 0.5:
            concepts.append("scene_grass")
        return concepts

    def generate_caption(self, image_features):
        """生成图像描述"""
        concepts = self.extract_concepts(image_features)
        if not concepts:
            return "<START> <END>"
        # 拼接概念对应的词语
        words = ["<START>"]
        for concept in concepts:
            words.extend(self.concept_to_words[concept])
        words.append("<END>")
        return " ".join(words)

    def encode_caption(self, caption):
        """将文本编码为 token 序列"""
        words = caption.split()
        token_ids = [self.vocab.index(w) if w in self.vocab else 0 for w in words]
        return token_ids

def test_06_image_captioning():
    captioner = MockImageCaptioner()
    # 测试1：猫坐在桌子上
    features1 = np.array([0.8, 0.7, 0.1, 0.1])  # cat + table
    caption1 = captioner.generate_caption(features1)
    assert "cat" in caption1 and "table" in caption1, f"Caption should mention cat and table: {caption1}"
    assert caption1.startswith("<START>") and caption1.endswith("<END>")
    # 编码验证
    token_ids = captioner.encode_caption(caption1)
    assert isinstance(token_ids, list)
    assert token_ids[0] == 0  # <START> = index 0
    assert token_ids[-1] == 1  # <END> = index 1
    # 测试2：狗在草地上跑
    features2 = np.array([0.3, 0.1, 0.1, 0.8])  # dog + grass
    caption2 = captioner.generate_caption(features2)
    assert "dog" in caption2, f"Caption should mention dog: {caption2}"
    assert "grass" in caption2, f"Caption should mention grass: {caption2}"
    # 测试3：空场景
    features3 = np.array([0.0, 0.0, 0.0, 0.0])
    caption3 = captioner.generate_caption(features3)
    assert caption3 == "<START> <END>"
    print(f"   Caption 1 (cat+table): {caption1}")
    print(f"   Caption 2 (dog+grass): {caption2}")
    print(f"   Caption 3 (empty): {caption3}")
    print("✅ Test 06 passed: Image Captioning Pipeline")

# ============================================================
# Test 07: 文本生成图像 (Text-to-Image) 概念模拟
# 模拟扩散模型的核心概念
# ============================================================

def forward_diffusion(x_0, t, noise_schedule):
    """
    前向扩散：逐步添加噪声
    x_0: 原始数据
    t: 时间步
    noise_schedule: 每步的噪声系数 (beta_t)
    """
    x_t = x_0.copy()
    for step in range(t):
        noise = np.random.randn(*x_t.shape)
        x_t = np.sqrt(1 - noise_schedule[step]) * x_t + np.sqrt(noise_schedule[step]) * noise
    return x_t

def reverse_diffusion_step(x_t, t, noise_schedule, predicted_noise):
    """
    反向去噪一步
    """
    beta_t = noise_schedule[t]
    alpha_t = 1 - beta_t
    # 简化的去噪公式
    x_t_minus_1 = (1 / np.sqrt(alpha_t)) * (x_t - (beta_t / np.sqrt(1 - alpha_t)) * predicted_noise)
    return x_t_minus_1

def text_conditioned_denoise(x_t, t, noise_schedule, text_embedding, text_weight=0.1):
    """
    文本条件引导的去噪
    用文本嵌入引导去噪方向
    """
    np.random.seed(t)
    # 模拟模型预测的噪声（受文本嵌入影响）
    base_noise = np.random.randn(*x_t.shape) * 0.5
    # 文本引导：将文本嵌入投影到图像空间
    np.random.seed(t + 100)
    text_proj = np.random.randn(*x_t.shape) * text_weight
    predicted_noise = base_noise + text_proj * np.mean(text_embedding)
    # 去噪
    x_prev = reverse_diffusion_step(x_t, t, noise_schedule, predicted_noise)
    return x_prev, predicted_noise

def test_07_diffusion():
    np.random.seed(42)
    # 线性噪声调度表
    T = 50
    betas = np.linspace(0.001, 0.02, T)
    # 原始数据（模拟一张图片的嵌入）
    x_0 = np.random.randn(4, 32) * 0.5  # "干净的"数据
    # 前向扩散：T步后接近纯噪声
    x_T = forward_diffusion(x_0, T, betas)
    assert x_T.shape == x_0.shape
    # T步后数据应该比原始数据噪声更大
    noise_increase = np.std(x_T) - np.std(x_0)
    assert noise_increase > 0, "Forward diffusion should increase noise/std"
    # 反向去噪：逐步恢复
    text_emb = np.random.randn(64)
    x_current = x_T.copy()
    for t in range(T - 1, 0, -1):
        x_current, _ = text_conditioned_denoise(x_current, t, betas, text_emb, text_weight=0.05)
    assert x_current.shape == x_0.shape
    # 不同文本引导应产生不同结果
    text_emb2 = np.random.randn(64) * 2
    x_current2 = x_T.copy()
    for t in range(T - 1, 0, -1):
        x_current2, _ = text_conditioned_denoise(x_current2, t, betas, text_emb2, text_weight=0.05)
    assert not np.allclose(x_current, x_current2), "Different text embeddings should produce different outputs"
    print(f"   Original std: {np.std(x_0):.4f}, After diffusion: {np.std(x_T):.4f}")
    print(f"   Denoised std: {np.std(x_current):.4f}")
    print("✅ Test 07 passed: Text-to-Image Diffusion Concept")

# ============================================================
# Test 08: 多模态注意力 (Cross-Modal Attention)
# ============================================================

def cross_modal_attention(text_features, image_features, num_heads=4):
    """
    多模态交叉注意力：文本作为 Query 查询图像
    text_features: (T, D) 文本序列
    image_features: (I, D) 图像序列（如 patch 序列）
    """
    D = text_features.shape[-1]
    assert D == image_features.shape[-1]
    assert D % num_heads == 0
    d_k = D // num_heads
    np.random.seed(42)
    # 投影矩阵
    W_q = np.random.randn(D, D) * 0.1
    W_k = np.random.randn(D, D) * 0.1
    W_v = np.random.randn(D, D) * 0.1
    Q = text_features @ W_q  # (T, D)
    K = image_features @ W_k  # (I, D)
    V = image_features @ W_v  # (I, D)
    # 分头
    T = text_features.shape[0]
    I = image_features.shape[0]
    Q_h = Q.reshape(T, num_heads, d_k).transpose(1, 0, 2)  # (H, T, d_k)
    K_h = K.reshape(I, num_heads, d_k).transpose(1, 0, 2)  # (H, I, d_k)
    V_h = V.reshape(I, num_heads, d_k).transpose(1, 0, 2)  # (H, I, d_k)
    # 每个头独立计算
    head_outputs = []
    head_weights = []
    for h in range(num_heads):
        scores = Q_h[h] @ K_h[h].T / math.sqrt(d_k)  # (T, I)
        scores_max = np.max(scores, axis=-1, keepdims=True)
        attn = np.exp(scores - scores_max) / np.sum(np.exp(scores - scores_max), axis=-1, keepdims=True)
        out = attn @ V_h[h]  # (T, d_k)
        head_outputs.append(out)
        head_weights.append(attn)
    # 合并所有头
    concat = np.stack(head_outputs, axis=1).reshape(T, D)  # (T, D)
    W_o = np.random.randn(D, D) * 0.1
    output = concat @ W_o
    return output, head_weights

def test_08_cross_modal_attention():
    np.random.seed(42)
    T, I, D = 10, 16, 32  # 10个文本token, 16个图像patch, 32维
    text_feat = np.random.randn(T, D)
    image_feat = np.random.randn(I, D)
    output, weights = cross_modal_attention(text_feat, image_feat, num_heads=4)
    # 输出形状应与文本序列一致（因为文本是 Query）
    assert output.shape == (T, D), f"Output shape mismatch: {output.shape}"
    # 每个头的注意力权重形状为 (T, I)
    assert len(weights) == 4, f"Should have 4 heads, got {len(weights)}"
    assert weights[0].shape == (T, I), f"Head weight shape mismatch: {weights[0].shape}"
    # 注意力权重每行和为1
    for h in range(4):
        row_sums = np.sum(weights[h], axis=-1)
        assert np.allclose(row_sums, 1.0), f"Head {h} weights should sum to 1"
    # 输出不应全为0
    assert not np.allclose(output, 0), "Output should not be all zeros"
    # 对称方向：图像作为 Query 查询文本
    output_rev, _ = cross_modal_attention(image_feat, text_feat, num_heads=4)
    assert output_rev.shape == (I, D), "Reverse direction output shape mismatch"
    assert not np.allclose(output, output_rev[:T]), "Forward and reverse should differ"
    print(f"   Text->Image attention: text({T},{D}) queries image({I},{D}) -> ({output.shape})")
    print(f"   Image->Text attention: image({I},{D}) queries text({T},{D}) -> ({output_rev.shape})")
    print("✅ Test 08 passed: Cross-Modal Attention")

# ============================================================
# Test 09: 多模态检索 (Multimodal Retrieval)
# ============================================================

class MultimodalRetriever:
    """多模态检索系统"""
    def __init__(self):
        self.image_db = []   # (id, embedding, metadata)
        self.text_db = []    # (id, embedding, metadata)

    def add_images(self, embeddings, metadatas):
        for emb, meta in zip(embeddings, metadatas):
            self.image_db.append((len(self.image_db), emb, meta))

    def add_texts(self, embeddings, metadatas):
        for emb, meta in zip(embeddings, metadatas):
            self.text_db.append((len(self.text_db), emb, meta))

    def _cosine_sim(self, a, b):
        return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-8)

    def text_to_image(self, text_emb, top_k=3):
        """以文搜图"""
        sims = [(img_id, self._cosine_sim(text_emb, emb), meta) for img_id, emb, meta in self.image_db]
        sims.sort(key=lambda x: x[1], reverse=True)
        return sims[:top_k]

    def image_to_text(self, image_emb, top_k=3):
        """以图搜文"""
        sims = [(txt_id, self._cosine_sim(image_emb, emb), meta) for txt_id, emb, meta in self.text_db]
        sims.sort(key=lambda x: x[1], reverse=True)
        return sims[:top_k]

    def image_to_image(self, image_emb, top_k=3):
        """以图搜图"""
        sims = [(img_id, self._cosine_sim(image_emb, emb), meta) for img_id, emb, meta in self.image_db]
        sims.sort(key=lambda x: x[1], reverse=True)
        return sims[:top_k]

def test_09_multimodal_retrieval():
    np.random.seed(42)
    D = 32
    retriever = MultimodalRetriever()
    # 图像数据库
    img_embs = np.random.randn(10, D)
    img_metas = [{"caption": f"image_{i}", "category": f"cat_{i%3}"} for i in range(10)]
    retriever.add_images(img_embs, img_metas)
    # 文本数据库
    txt_embs = np.random.randn(8, D)
    txt_metas = [{"text": f"描述_{i}"} for i in range(8)]
    retriever.add_texts(txt_embs, txt_metas)
    # 以文搜图
    query_text = np.random.randn(D)
    t2i_results = retriever.text_to_image(query_text, top_k=3)
    assert len(t2i_results) == 3
    # 相似度降序
    sims = [r[1] for r in t2i_results]
    assert sims[0] >= sims[1] >= sims[2], "Results should be sorted by similarity"
    # 以图搜文
    query_image = np.random.randn(D)
    i2t_results = retriever.image_to_text(query_image, top_k=2)
    assert len(i2t_results) == 2
    # 以图搜图
    i2i_results = retriever.image_to_image(img_embs[0], top_k=5)
    assert len(i2i_results) == 5
    # 第一个结果应该是自己（相似度=1.0）
    assert i2i_results[0][0] == 0, "Top result for self-query should be the query image itself"
    assert abs(i2i_results[0][1] - 1.0) < 1e-5, "Self-similarity should be 1.0"
    print(f"   Text-to-Image: top1 sim={t2i_results[0][1]:.4f}")
    print(f"   Image-to-Text: top1 sim={i2t_results[0][1]:.4f}")
    print(f"   Image-to-Image: self sim={i2i_results[0][1]:.4f}")
    print("✅ Test 09 passed: Multimodal Retrieval")

# ============================================================
# Test 10: 多模态情感分析 (Multimodal Sentiment Analysis)
# 融合文本 + 图像 + 音频三种模态
# ============================================================

class MultimodalSentimentAnalyzer:
    """多模态情感分析"""
    def __init__(self, num_classes=3):
        self.num_classes = num_classes  # 0=negative, 1=neutral, 2=positive
        np.random.seed(42)
        # 各模态的分类器权重
        self.text_weight = np.random.randn(64, num_classes) * 0.1
        self.image_weight = np.random.randn(128, num_classes) * 0.1
        self.audio_weight = np.random.randn(32, num_classes) * 0.1
        # 模态权重（可学习）
        self.modality_weights = np.array([0.5, 0.3, 0.2])  # text, image, audio

    def predict_text(self, text_features):
        """文本模态预测"""
        logits = text_features @ self.text_weight
        # softmax
        exp_logits = np.exp(logits - np.max(logits))
        return exp_logits / np.sum(exp_logits)

    def predict_image(self, image_features):
        """图像模态预测"""
        logits = image_features @ self.image_weight
        exp_logits = np.exp(logits - np.max(logits))
        return exp_logits / np.sum(exp_logits)

    def predict_audio(self, audio_features):
        """音频模态预测"""
        logits = audio_features @ self.audio_weight
        exp_logits = np.exp(logits - np.max(logits))
        return exp_logits / np.sum(exp_logits)

    def predict(self, text_features, image_features, audio_features):
        """多模态融合预测"""
        text_prob = self.predict_text(text_features)
        image_prob = self.predict_image(image_features)
        audio_prob = self.predict_audio(audio_features)
        # 加权融合
        fused_prob = (self.modality_weights[0] * text_prob +
                      self.modality_weights[1] * image_prob +
                      self.modality_weights[2] * audio_prob)
        # 归一化
        fused_prob = fused_prob / np.sum(fused_prob)
        predicted_class = np.argmax(fused_prob)
        return {
            "fused_prob": fused_prob,
            "predicted_class": int(predicted_class),
            "text_prob": text_prob,
            "image_prob": image_prob,
            "audio_prob": audio_prob,
        }

def test_10_multimodal_sentiment():
    np.random.seed(42)
    analyzer = MultimodalSentimentAnalyzer(num_classes=3)
    # 生成测试数据
    text_feat = np.random.randn(64)
    image_feat = np.random.randn(128)
    audio_feat = np.random.randn(32)
    # 单模态预测
    text_prob = analyzer.predict_text(text_feat)
    assert len(text_prob) == 3
    assert np.allclose(np.sum(text_prob), 1.0)
    # 多模态融合预测
    result = analyzer.predict(text_feat, image_feat, audio_feat)
    assert "fused_prob" in result
    assert "predicted_class" in result
    assert result["predicted_class"] in [0, 1, 2]
    assert np.allclose(np.sum(result["fused_prob"]), 1.0)
    # 验证加权融合
    expected = (0.5 * result["text_prob"] + 0.3 * result["image_prob"] + 0.2 * result["audio_prob"])
    expected = expected / np.sum(expected)
    assert np.allclose(result["fused_prob"], expected), "Fused prob should match weighted sum"
    # 文本权重最高，当文本强烈指向某类时，融合结果应倾向该类
    # 构造文本强信号
    strong_text = np.zeros(64)
    strong_text[:10] = 10  # 强信号
    result_strong = analyzer.predict(strong_text, image_feat, audio_feat)
    text_pred = np.argmax(result_strong["text_prob"])
    assert result_strong["predicted_class"] == text_pred, \
        "When text signal is strong, fused prediction should follow text"
    # 各模态预测可以不同
    text_pred2 = np.argmax(result["text_prob"])
    image_pred2 = np.argmax(result["image_prob"])
    audio_pred2 = np.argmax(result["audio_prob"])
    print(f"   Text class: {text_pred2} (prob: {result['text_prob']})")
    print(f"   Image class: {image_pred2} (prob: {result['image_prob']})")
    print(f"   Audio class: {audio_pred2} (prob: {result['audio_prob']})")
    print(f"   Fused class: {result['predicted_class']} (prob: {result['fused_prob']})")
    print("✅ Test 10 passed: Multimodal Sentiment Analysis")

# ============================================================
# 运行所有测试
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("第四阶段 4.3 多模态基础练习")
    print("=" * 60)
    print()
    tests = [
        test_01_clip_contrastive,
        test_02_zero_shot,
        test_03_sam_segmentation,
        test_04_whisper_ctc,
        test_05_multimodal_fusion,
        test_06_image_captioning,
        test_07_diffusion,
        test_08_cross_modal_attention,
        test_09_multimodal_retrieval,
        test_10_multimodal_sentiment,
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
