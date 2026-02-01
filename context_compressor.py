"""
上下文自动压缩模块

当对话上下文接近 200k tokens 时，自动压缩以避免超出模型限制。
策略：滑动窗口 - 保留系统提示词 + 最近 N 轮对话
"""

import logging
from typing import Optional, Tuple, List, Dict

logger = logging.getLogger(__name__)

DEFAULT_MAX_TOKENS = 200000


def estimate_tokens(text) -> int:
    """
    估算文本的 token 数

    中文约 0.6 token/字符，英文/其他约 0.25 token/字符
    """
    if not text:
        return 0

    # 处理非字符串类型（Anthropic system 字段可能是数组或字典）
    if isinstance(text, dict):
        text = text.get("text", "") or str(text)
    elif isinstance(text, list):
        text = " ".join(item.get("text", "") if isinstance(item, dict) else str(item) for item in text)
    elif not isinstance(text, str):
        text = str(text)

    chinese_count = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    other_count = len(text) - chinese_count
    return int(chinese_count * 0.6 + other_count * 0.25) + 1


def estimate_message_tokens(msg: dict) -> int:
    """
    估算单条消息的 token 数

    支持 OpenAI 和 Anthropic 格式
    """
    tokens = 0

    # role 字段
    if "role" in msg:
        tokens += estimate_tokens(msg["role"])

    # content 字段 - 支持字符串或列表格式
    content = msg.get("content")
    if isinstance(content, str):
        tokens += estimate_tokens(content)
    elif isinstance(content, list):
        for item in content:
            if isinstance(item, dict):
                if "text" in item:
                    tokens += estimate_tokens(item["text"])
                elif "content" in item:
                    tokens += estimate_tokens(str(item["content"]))
            elif isinstance(item, str):
                tokens += estimate_tokens(item)

    # 消息结构开销
    tokens += 4

    return tokens


def compress_context(
    messages: list,
    system: Optional[str] = None,
    max_tokens: int = DEFAULT_MAX_TOKENS
) -> Tuple[List, Dict]:
    """
    压缩上下文，保留系统提示词和最近的消息

    Args:
        messages: 消息列表
        system: 系统提示词（始终保留）
        max_tokens: 最大 token 数阈值

    Returns:
        tuple: (压缩后的消息列表, 压缩统计信息)
    """
    if not messages:
        return messages, {"original_tokens": 0, "compressed_tokens": 0, "removed_count": 0}

    # 计算系统提示词 token 数
    system_tokens = estimate_tokens(system) if system else 0

    # 计算所有消息的 token 数
    message_tokens = [estimate_message_tokens(msg) for msg in messages]
    total_tokens = system_tokens + sum(message_tokens)

    # 如果未超过阈值，不需要压缩
    if total_tokens <= max_tokens:
        return messages, {
            "original_tokens": total_tokens,
            "compressed_tokens": total_tokens,
            "removed_count": 0
        }

    # 从最新消息向前累加，直到接近阈值
    available_tokens = max_tokens - system_tokens
    accumulated_tokens = 0
    keep_from_index = len(messages)

    for i in range(len(messages) - 1, -1, -1):
        if accumulated_tokens + message_tokens[i] > available_tokens:
            break
        accumulated_tokens += message_tokens[i]
        keep_from_index = i

    # 压缩后的消息
    compressed_messages = messages[keep_from_index:]
    removed_count = keep_from_index
    compressed_tokens = system_tokens + accumulated_tokens

    stats = {
        "original_tokens": total_tokens,
        "compressed_tokens": compressed_tokens,
        "removed_count": removed_count
    }

    if removed_count > 0:
        logger.info(
            f"上下文压缩: {total_tokens} -> {compressed_tokens} tokens, "
            f"删除 {removed_count} 条消息"
        )

    return compressed_messages, stats
