"""
重启后端服务并配置 API Key
"""
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# 从统一配置模块加载配置
from config import load_config, get_config
load_config()
config = get_config()

print("[1/3] API 配置已加载")
# 隐藏 API Key 的敏感信息
masked_key = f"{config.anthropic_api_key[:8]}...{config.anthropic_api_key[-4:]}" if len(config.anthropic_api_key) > 12 else "***"
print(f"  ANTHROPIC_API_KEY: {masked_key}")
print(f"  ANTHROPIC_BASE_URL: {config.anthropic_base_url or '默认'}")
print(f"  ANTHROPIC_MODEL (Normal): {config.anthropic_model}")
print(f"  ANTHROPIC_MODEL (Thinking): {config.anthropic_model_thinking}")

# 查找并停止占用 8000 端口的进程
print("\n[2/3] 停止旧的后端进程...")
try:
    result = subprocess.run(
        'netstat -ano | findstr ":8000.*LISTENING"',
        shell=True,
        capture_output=True,
        text=True
    )

    if result.stdout:
        # 提取 PID
        for line in result.stdout.strip().split('\n'):
            parts = line.split()
            if len(parts) >= 5:
                pid = int(parts[-1])
                print(f"  找到进程 PID: {pid}")
                try:
                    os.kill(pid, signal.SIGTERM)
                    print(f"  已停止进程 {pid}")
                    time.sleep(2)
                except Exception as e:
                    print(f"  停止进程失败: {e}")
except Exception as e:
    print(f"  查找进程失败: {e}")

# 启动新的后端服务
print("\n[3/3] 启动新的后端服务...")
print("  后端服务已在后台启动")
print("  访问: http://localhost:8000")
print("\n按 Ctrl+C 停止服务")

# 启动服务
try:
    subprocess.run([sys.executable, "main.py"], cwd=os.path.dirname(__file__))
except KeyboardInterrupt:
    print("\n\n后端服务已停止")
