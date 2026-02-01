"""
API 测试脚本 - 用于测试 Agent 功能
"""
import requests
import json
import sys

BASE_URL = "http://localhost:8000"

def test_chat(message: str, session_id: str = None):
    """发送聊天请求并打印响应"""
    url = f"{BASE_URL}/api/chat"
    payload = {
        "message": message,
        "session_id": session_id or f"test-{message[:10]}"
    }

    print(f"\n=== 测试: {message[:50]}... ===")
    print(f"Session ID: {payload['session_id']}")

    try:
        response = requests.post(
            url,
            json=payload,
            headers={"Content-Type": "application/json"},
            stream=True,
            timeout=180
        )

        print(f"Status: {response.status_code}")
        print("Response:")

        for line in response.iter_lines():
            if line:
                decoded = line.decode('utf-8')
                print(decoded)

    except requests.exceptions.Timeout:
        print("ERROR: Request timed out")
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        message = " ".join(sys.argv[1:])
    else:
        # 默认测试消息
        message = "用 Glob 工具列出当前目录下的所有 .py 文件"

    test_chat(message)
