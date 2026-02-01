"""
Test script for sandbox permission control (Test 6.4)
验证 can_use_tool 沙箱权限控制
"""
import requests
import json
import time

def test_sandbox_permission():
    url = 'http://localhost:8000/api/chat'

    # 测试请求：尝试在沙箱外创建文件
    payload = {
        'message': 'Please create a file named test_sandbox_block.txt at C:\\Users\\Administrator\\Desktop\\ with content "Sandbox test"',
        'session_id': f'test-sandbox-{int(time.time())}'
    }

    print("=" * 60)
    print("Test 6.4: Sandbox Permission Control")
    print("=" * 60)
    print(f"Request: {payload['message'][:80]}...")
    print(f"Session: {payload['session_id']}")
    print("-" * 60)

    try:
        response = requests.post(url, json=payload, stream=True, timeout=120)
        print(f"Status Code: {response.status_code}")
        print("-" * 60)

        # 读取 SSE 流
        event_count = 0
        for line in response.iter_lines(decode_unicode=True):
            if line:
                event_count += 1
                # 只打印关键事件
                if 'SANDBOX' in line or 'error' in line.lower() or 'block' in line.lower():
                    print(f"[KEY] {line[:200]}")
                elif event_count <= 10:
                    print(f"[{event_count}] {line[:150]}...")

        print("-" * 60)
        print(f"Total events: {event_count}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    test_sandbox_permission()
