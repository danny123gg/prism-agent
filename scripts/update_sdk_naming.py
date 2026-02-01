#!/usr/bin/env python3
"""
批量更新文档中的 SDK 命名
从 Claude Code SDK 更新为 Claude Agent SDK
"""

import os
import re
from pathlib import Path

# 定义替换规则
REPLACEMENTS = [
    ("Claude Code SDK", "Claude Agent SDK"),
    ("claude-code-sdk", "claude-agent-sdk"),
    ("ClaudeCodeSDKClient", "ClaudeSDKClient"),
    ("ClaudeCodeOptions", "ClaudeAgentOptions"),
    ("from claude_code_sdk import", "from claude_agent_sdk import"),
]

def update_file(file_path: Path) -> bool:
    """更新单个文件"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        original_content = content

        # 应用所有替换规则
        for old_text, new_text in REPLACEMENTS:
            content = content.replace(old_text, new_text)

        # 如果内容有变化，写回文件
        if content != original_content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return True

        return False
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return False

def main():
    # 要更新的目录和文件模式
    target_configs = [
        (Path("C:/Users/Administrator/Desktop/mvp-claude/docs"), "*.md"),
        (Path("C:/Users/Administrator/Desktop/mvp-claude/src"), "*.py"),
        (Path("C:/Users/Administrator/Desktop/mvp-claude/web/backend"), "*.py"),
        (Path("C:/Users/Administrator/Desktop/mvp-claude/web/backend"), "*.md"),
        (Path("C:/Users/Administrator/Desktop/mvp-claude/web/backend/sandbox"), "*.md"),
        (Path("C:/Users/Administrator/Desktop/mvp-claude/examples"), "*.py"),
        (Path("C:/Users/Administrator/Desktop/mvp-claude/tests"), "*.md"),
        (Path("C:/Users/Administrator/Desktop/mvp-claude/tests"), "*.py"),
        (Path("C:/Users/Administrator/Desktop/mvp-claude"), "*.md"),  # 根目录的 .md 文件
    ]

    updated_files = []

    for target_dir, pattern in target_configs:
        if not target_dir.exists():
            print(f"Directory not found: {target_dir}")
            continue

        # 处理匹配的文件
        for file_path in target_dir.glob(pattern):
            if update_file(file_path):
                updated_files.append(file_path)
                print(f"[OK] Updated: {file_path.relative_to(target_dir.parent)}")

    print(f"\n{'='*60}")
    print(f"Total files updated: {len(updated_files)}")
    print(f"{'='*60}")

    if updated_files:
        print("\nUpdated files:")
        for file_path in updated_files:
            print(f"  - {file_path}")

if __name__ == "__main__":
    main()
