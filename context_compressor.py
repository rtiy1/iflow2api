"""
上下文自动压缩模块

当对话上下文接近 180k tokens 时，自动压缩以避免超出模型限制。
策略：LLM 摘要 - 使用 LLM 生成历史对话摘要 + 保留最近 6 轮对话
"""

import logging
import hashlib
import json
import os
from pathlib import Path
from typing import Optional, Tuple, List, Dict

logger = logging.getLogger(__name__)

DEFAULT_MAX_TOKENS = 180000
KEEP_MESSAGE_COUNT = 6
MAX_TOOL_LOOKBACK = 10
CHARS_PER_TOKEN = 2
MAX_BATCH_CHARS = 80000


def get_cache_dir() -> Path:
    """获取缓存目录"""
    cache_dir = Path.home() / ".iflow2api" / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def hash_batch(text: str) -> str:
    """计算文本哈希"""
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def get_cached_summary(hash_key: str) -> Optional[str]:
    """获取缓存的摘要"""
    cache_file = get_cache_dir() / hash_key
    if cache_file.exists():
        return cache_file.read_text(encoding="utf-8")
    return None


def cache_summary(hash_key: str, summary: str):
    """缓存摘要"""
    cache_file = get_cache_dir() / hash_key
    cache_file.write_text(summary, encoding="utf-8")


def estimate_tokens(messages: List[Dict]) -> int:
    """估算消息列表的 token 数（简化版：2 字符 ≈ 1 token）"""
    total_chars = 0
    for msg in messages:
        content = msg.get("content", "")
        if isinstance(content, str):
            total_chars += len(content)
        elif isinstance(content, list):
            for item in content:
                if isinstance(item, dict):
                    if "text" in item:
                        total_chars += len(item["text"])
                    if "input" in item:
                        total_chars += len(json.dumps(item["input"]))
    return total_chars // CHARS_PER_TOKEN


def extract_text(content) -> str:
    """从消息内容中提取文本"""
    if isinstance(content, str):
        return content
    elif isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                if "text" in item:
                    parts.append(item["text"])
                if item.get("type") == "tool_use":
                    parts.append(f"[调用工具: {item.get('name', 'unknown')}]")
                if item.get("type") == "tool_result":
                    parts.append(f"[工具结果: {extract_text(item.get('content', ''))}]")
        return " ".join(parts)
    return ""


def collect_tool_result_ids(messages: List[Dict]) -> set:
    """收集消息中的 tool_result ID"""
    ids = set()
    for msg in messages:
        if msg.get("role") != "user":
            continue
        content = msg.get("content", [])
        if isinstance(content, list):
            for item in content:
                if isinstance(item, dict) and item.get("type") == "tool_result":
                    tool_id = item.get("tool_use_id")
                    if tool_id:
                        ids.add(tool_id)
    return ids


def find_tool_use_index(messages: List[Dict], before_idx: int, tool_id: str) -> int:
    """在指定范围内查找 tool_use"""
    for i in range(before_idx - 1, max(-1, before_idx - MAX_TOOL_LOOKBACK - 1), -1):
        msg = messages[i]
        if msg.get("role") != "assistant":
            continue
        content = msg.get("content", [])
        if isinstance(content, list):
            for item in content:
                if isinstance(item, dict) and item.get("type") == "tool_use":
                    if item.get("id") == tool_id:
                        return i
    return -1


def find_keep_boundary(messages: List[Dict]) -> int:
    """找到保留消息的起始索引，处理工具调用成对问题"""
    n = len(messages)
    if n <= KEEP_MESSAGE_COUNT:
        return 0

    keep_start = n - KEEP_MESSAGE_COUNT
    tool_result_ids = collect_tool_result_ids(messages[keep_start:])

    if not tool_result_ids:
        return keep_start

    for tool_id in tool_result_ids:
        tool_use_idx = find_tool_use_index(messages, keep_start, tool_id)
        if tool_use_idx >= 0:
            distance = keep_start - tool_use_idx
            if distance <= MAX_TOOL_LOOKBACK:
                logger.debug(f"找到对应 tool_use (id={tool_id}, distance={distance})，扩展保留边界")
                if tool_use_idx < keep_start:
                    keep_start = tool_use_idx

    return keep_start


async def generate_summary(messages: List[Dict], proxy_instance) -> str:
    """使用 LLM 生成摘要"""
    batch_text = "\n\n".join([f"{msg.get('role', 'unknown')}: {extract_text(msg.get('content', ''))}" for msg in messages])

    # 检查缓存
    hash_key = hash_batch(batch_text)
    cached = get_cached_summary(hash_key)
    if cached:
        logger.info(f"使用缓存摘要 (hash={hash_key})")
        return cached

    # 生成摘要
    prompt = f"请将以下对话历史压缩为简洁摘要（200字以内），保留关键信息、决策和工具调用结果：\n\n{batch_text}"

    try:
        result = await proxy_instance.proxy_request(
            endpoint="/v1/messages",
            body={
                "model": "claude-sonnet-4-5-20250929",
                "max_tokens": 1024,
                "messages": [{"role": "user", "content": prompt}]
            },
            model="claude-sonnet-4-5-20250929",
            stream=False
        )

        # 提取摘要文本
        summary = ""
        if "content" in result:
            for item in result["content"]:
                if isinstance(item, dict) and item.get("type") == "text":
                    summary += item.get("text", "")

        if summary:
            cache_summary(hash_key, summary)
            logger.info(f"生成摘要完成 (hash={hash_key})")

        return summary
    except Exception as e:
        logger.error(f"生成摘要失败: {e}")
        return "[摘要生成失败]"


async def compress_context(
    messages: List[Dict],
    proxy_instance,
    max_tokens: int = DEFAULT_MAX_TOKENS
) -> Tuple[List[Dict], Dict]:
    """
    压缩上下文，使用 LLM 生成摘要 + 保留最近消息

    Args:
        messages: 消息列表
        proxy_instance: 代理实例（用于调用 LLM）
        max_tokens: 最大 token 数阈值

    Returns:
        tuple: (压缩后的消息列表, 压缩统计信息)
    """
    if not messages:
        return messages, {"original_tokens": 0, "compressed_tokens": 0, "removed_count": 0}

    total_tokens = estimate_tokens(messages)

    # 如果未超过阈值，不需要压缩
    if total_tokens <= max_tokens:
        logger.info(f"上下文 token 估算: {total_tokens}, 阈值: {max_tokens}, 无需压缩")
        return messages, {
            "original_tokens": total_tokens,
            "compressed_tokens": total_tokens,
            "removed_count": 0
        }

    # 如果消息数量少于保留数量，不需要压缩
    if len(messages) <= KEEP_MESSAGE_COUNT:
        return messages, {
            "original_tokens": total_tokens,
            "compressed_tokens": total_tokens,
            "removed_count": 0
        }

    # 找到保留边界（处理工具调用成对问题）
    keep_start = find_keep_boundary(messages)
    if keep_start <= 0:
        logger.info("无需压缩，保留边界为 0")
        return messages, {
            "original_tokens": total_tokens,
            "compressed_tokens": total_tokens,
            "removed_count": 0
        }

    to_compress = messages[:keep_start]
    to_keep = messages[keep_start:]

    logger.info(f"开始压缩上下文: 总消息数={len(messages)}, 待压缩={len(to_compress)}, 保留={len(to_keep)}")

    # 生成摘要
    summary = await generate_summary(to_compress, proxy_instance)

    # 构建压缩后的消息
    result = [
        {"role": "user", "content": f"[历史对话摘要]\n{summary}"},
        {"role": "assistant", "content": "好的，我已了解之前的对话上下文。"}
    ]
    result.extend(to_keep)

    compressed_tokens = estimate_tokens(result)

    logger.info(f"上下文压缩完成: {len(messages)} -> {len(result)} 条消息, {total_tokens} -> {compressed_tokens} tokens")

    return result, {
        "original_tokens": total_tokens,
        "compressed_tokens": compressed_tokens,
        "removed_count": len(to_compress)
    }
