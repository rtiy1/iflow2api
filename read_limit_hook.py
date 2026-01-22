#!/usr/bin/env python3
"""
PreToolUse hook for Read tool - Enforce offset/limit and block large file reads.
"""
import json
import sys
import os
from datetime import datetime

# --- 配置区域 ---
MAX_FILE_LINES = 1000           # 超过这个行数必须切片读
MAX_FILE_BYTES = 50 * 1024      # 超过 50KB 必须切片读
MAX_SINGLE_READ_LINES = 500     # 一次最多读 500 行
MAX_SINGLE_READ_BYTES = 20 * 1024 

# 跳过不需要检查的二进制文件
SKIP_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.pdf', '.exe', '.dll', '.so', '.dylib', '.zip', '.tar', '.gz'}

# 日志文件（可选，帮你分析它浪费了多少次尝试）
LOG_FILE = os.path.expandvars ("$USERPROFILE/.claude/hooks/read-stats.log")

def get_file_stats (file_path):
    try:
        if not os.path.exists (file_path): return None, None
        size = os.path.getsize (file_path)
        with open (file_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = sum (1 for _ in f)
        return lines, size
    except:
        return None, None

def format_bytes (size):
    if size >= 1024 * 1024: return f"{size / (1024 * 1024):.1f} MB"
    if size >= 1024: return f"{size / 1024:.1f} KB"
    return f"{size} B"

def main ():
    try:
        input_data = json.load (sys.stdin)
    except:
        sys.exit (0) # 甚至不是 JSON，不管了

    tool_name = input_data.get ("tool_name", "")
    tool_input = input_data.get ("tool_input", {})

    # 只管 Read 工具
    if tool_name != "Read":
        sys.exit (0)

    file_path = tool_input.get ("file_path", "")
    offset = tool_input.get ("offset")
    limit = tool_input.get ("limit")

    # 1. 扩展名检查
    ext = os.path.splitext (file_path)[1].lower ()
    if ext in SKIP_EXTENSIONS: sys.exit (0)

    lines, size = get_file_stats (file_path)
    if lines is None: sys.exit (0) # 读不到文件，让 Claude 自己处理错误

    # 2. 检查是否是大文件
    is_large_file = lines > MAX_FILE_LINES or size > MAX_FILE_BYTES

    if is_large_file:
        # 如果是大文件，且没有指定 offset 或 limit -> 拦截！
        if offset is None or limit is None:
            reason = f"{lines} lines / {format_bytes (size)}"
            error_msg = (
                f"BLOCKED: File is too large ({reason}) for a full read.\n"
                f"You MUST use 'offset' and 'limit' to read specific sections.\n\n"
                f"Strategy:\n"
                f"1. Use`Grep`to find the line number of your function/variable.\n"
                f"2. Then`Read`with offset=LINE_NUM, limit=50.\n"
                f"DO NOT try to read the whole file again."
            )
            print (error_msg, file=sys.stderr)
            sys.exit (2) # 2 通常表示操作被拒绝

    # 3. 检查单次读取是否贪得无厌
    if limit is not None and limit > MAX_SINGLE_READ_LINES:
        print (f"BLOCKED: Limit {limit} is too high. Max allowed is {MAX_SINGLE_READ_LINES}.", file=sys.stderr)
        sys.exit (2)

    # 4. 贴心的小功能：如果有 offset 没 limit，自动帮它补上 limit，防止它犯傻
    if offset is not None and limit is None:
        output = {
            "hookSpecificOutput": {
                "permissionDecision": "allow",
                "updatedInput": { "limit": MAX_SINGLE_READ_LINES }
            }
        }
        print (json.dumps (output))
        sys.exit (0)

    sys.exit (0)

if __name__ == "__main__":
    main ()