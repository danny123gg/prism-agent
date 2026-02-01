"""
Extended Thinking 示例 - 获取 Claude 的思考过程

注意：Claude Agent SDK 不支持获取 thinking 内容，
因此本示例直接使用 Anthropic API。

使用方法:
    python examples/extended_thinking.py
"""

import os
import sys

# Windows 控制台 UTF-8 编码支持
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

from anthropic import Anthropic

def main():
    # 创建 Anthropic 客户端
    client = Anthropic()

    # 需要复杂推理的问题
    question = """
    一个农夫需要将一只狼、一只羊和一棵白菜运过河。
    他只有一条小船，每次只能带一样东西过河。
    如果农夫不在场，狼会吃羊，羊会吃白菜。
    请问农夫应该如何安全地将所有东西运过河？
    """

    print("=" * 60)
    print("Extended Thinking 示例")
    print("=" * 60)
    print(f"\n问题: {question.strip()}\n")
    print("-" * 60)

    # 调用 API，启用 extended thinking
    response = client.messages.create(
        model="claude-sonnet-4-20250514",  # 支持 extended thinking 的模型
        max_tokens=16000,
        thinking={
            "type": "enabled",
            "budget_tokens": 10000  # 分配给思考过程的 token 预算
        },
        messages=[
            {
                "role": "user",
                "content": question
            }
        ]
    )

    # 解析响应，分离 thinking 和 text 内容
    thinking_content = None
    text_content = None

    for block in response.content:
        if block.type == "thinking":
            thinking_content = block.thinking
        elif block.type == "text":
            text_content = block.text

    # 显示思考过程
    if thinking_content:
        print("\n🧠 思考过程 (Thinking):")
        print("-" * 60)
        print(thinking_content)
        print("-" * 60)

    # 显示最终回答
    if text_content:
        print("\n💬 最终回答:")
        print("-" * 60)
        print(text_content)
        print("-" * 60)

    # 显示 token 使用情况
    print("\n📊 Token 使用统计:")
    print(f"  - 输入 tokens: {response.usage.input_tokens}")
    print(f"  - 输出 tokens: {response.usage.output_tokens}")
    if hasattr(response.usage, 'cache_creation_input_tokens'):
        print(f"  - 缓存创建 tokens: {response.usage.cache_creation_input_tokens}")
    if hasattr(response.usage, 'cache_read_input_tokens'):
        print(f"  - 缓存读取 tokens: {response.usage.cache_read_input_tokens}")


def streaming_example():
    """流式输出版本 - 实时显示思考和回答"""

    client = Anthropic()

    question = "证明根号2是无理数"

    print("\n" + "=" * 60)
    print("Extended Thinking 流式输出示例")
    print("=" * 60)
    print(f"\n问题: {question}\n")

    # 使用流式 API
    with client.messages.stream(
        model="claude-sonnet-4-20250514",
        max_tokens=16000,
        thinking={
            "type": "enabled",
            "budget_tokens": 8000
        },
        messages=[{"role": "user", "content": question}]
    ) as stream:

        current_block_type = None

        for event in stream:
            # 处理内容块开始事件
            if event.type == "content_block_start":
                block = event.content_block
                if block.type == "thinking":
                    current_block_type = "thinking"
                    print("\n🧠 思考中...")
                    print("-" * 40)
                elif block.type == "text":
                    current_block_type = "text"
                    print("\n\n💬 回答:")
                    print("-" * 40)

            # 处理内容增量事件
            elif event.type == "content_block_delta":
                delta = event.delta
                if hasattr(delta, 'thinking'):
                    print(delta.thinking, end="", flush=True)
                elif hasattr(delta, 'text'):
                    print(delta.text, end="", flush=True)

    print("\n" + "-" * 40)
    print("流式输出完成")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--stream":
        streaming_example()
    else:
        main()
        print("\n提示: 使用 --stream 参数可以看到流式输出效果")
