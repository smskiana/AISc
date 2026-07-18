"""
本地 BGE Embedding 服务 — 用于计算记忆节点间的语义相似度。
替代 LLM 做 similar_to 判断，毫秒级零 API 调用。
"""
import os
import logging
import numpy as np
from threading import Lock
from typing import Optional

logger = logging.getLogger("sakurabashi.embedding")

# 国内 HuggingFace 镜像（无代理环境自动使用）
if "HF_ENDPOINT" not in os.environ and "HF_MIRROR" not in os.environ:
    os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

# 全局模型缓存
_model: Optional[object] = None
_model_lock = Lock()


def _get_model():
    """延迟加载 BGE 模型（首次调用时加载，之后复用）"""
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                try:
                    from sentence_transformers import SentenceTransformer
                    _model = SentenceTransformer("BAAI/bge-small-zh-v1.5", device="cpu",
                                                 local_files_only=True)
                    logger.info("BGE 模型加载完成 (bge-small-zh-v1.5)")
                except ImportError:
                    logger.warning("sentence-transformers 未安装，similar_to 将降级为基于关键词的简单匹配")
                    _model = False  # 标记为不可用
    return _model if _model is not False else None


def encode_batch(texts: list[str]) -> Optional[np.ndarray]:
    """批量编码文本为向量。返回 (N, 512) 矩阵，失败返回 None。"""
    if not texts:
        return np.empty((0, 512), dtype=np.float32)
    model = _get_model()
    if model is None:
        return None
    try:
        embeddings = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        return np.array(embeddings)
    except Exception as e:
        logger.warning(f"BGE 编码失败: {e}")
        return None


def cosine_similarity(vec_a: np.ndarray, vec_b: np.ndarray) -> float:
    """两个已归一化向量的余弦相似度（点积即余弦值）。"""
    return float(np.dot(vec_a, vec_b))


def pairwise_similarities(texts: list[str]) -> Optional[list[tuple[int, int, float]]]:
    """计算文本列表中所有 pair 的语义相似度。

    Args:
        texts: 文本值列表

    Returns:
        [(i, j, similarity), ...] 按相似度降序排列，>0.7 的才返回。
        失败返回 None。
    """
    if len(texts) < 2:
        return []

    vectors = encode_batch(texts)
    if vectors is None:
        return None

    results = []
    for i in range(len(texts)):
        for j in range(i + 1, len(texts)):
            sim = cosine_similarity(vectors[i], vectors[j])
            if sim > 0.7:
                results.append((i, j, round(float(sim), 3)))

    results.sort(key=lambda x: x[2], reverse=True)
    return results
