"""
统一的环境变量配置管理模块

这个模块负责：
1. 从 .env 文件读取配置
2. 验证必需的配置项
3. 提供统一的配置访问接口
4. 自动设置到 os.environ（让子进程能继承）

使用方式：
    from config import load_config, get_config

    # 在程序入口处加载配置
    load_config()

    # 访问配置
    config = get_config()
    api_key = config.anthropic_api_key
    model = config.anthropic_model
"""

import os
from pathlib import Path
from typing import Optional


class Config:
    """配置类"""

    def __init__(self):
        self.anthropic_api_key: str = ""
        self.anthropic_base_url: str = ""
        self.anthropic_model: str = "claude-sonnet-4-5-20250929"  # 默认模型（Normal 模式）
        self.anthropic_model_thinking: str = "claude-sonnet-4-5-20250929"  # Thinking 模式默认模型

    @property
    def is_valid(self) -> bool:
        """检查配置是否有效"""
        return bool(self.anthropic_api_key and
                   self.anthropic_api_key != "your-api-key-here")

    def __repr__(self) -> str:
        """格式化输出配置信息（隐藏敏感信息）"""
        masked_key = "未配置"
        if self.anthropic_api_key and self.anthropic_api_key != "your-api-key-here":
            if len(self.anthropic_api_key) > 12:
                masked_key = f"{self.anthropic_api_key[:8]}...{self.anthropic_api_key[-4:]}"
            else:
                masked_key = "***"

        return f"""Configuration:
  API Key: {masked_key}
  Base URL: {self.anthropic_base_url or '默认'}
  Model (Normal): {self.anthropic_model}
  Model (Thinking): {self.anthropic_model_thinking}"""


# 全局配置实例
_config: Optional[Config] = None


def load_config(env_file: Optional[str] = None) -> Config:
    """
    从 .env 文件加载配置

    Args:
        env_file: .env 文件路径，默认为项目根目录的 .env

    Returns:
        Config 实例

    注意：
        - 这个函数会自动将配置设置到 os.environ，让子进程能继承
        - 建议在程序入口处调用一次
    """
    global _config

    # 确定 .env 文件路径
    if env_file is None:
        # 默认使用项目根目录的 .env
        project_root = Path(__file__).parent
        env_file = project_root / ".env"
    else:
        env_file = Path(env_file)

    # 创建配置实例
    config = Config()

    # 如果 .env 文件存在，读取配置
    if env_file.exists():
        with open(env_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()

                # 跳过注释和空行
                if not line or line.startswith('#'):
                    continue

                # 解析 KEY=VALUE 格式
                if '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()

                    # 读取配置项
                    if key == 'ANTHROPIC_API_KEY':
                        config.anthropic_api_key = value
                    elif key == 'ANTHROPIC_BASE_URL':
                        config.anthropic_base_url = value
                    elif key == 'ANTHROPIC_MODEL':
                        config.anthropic_model = value
                    elif key == 'ANTHROPIC_MODEL_THINKING':
                        config.anthropic_model_thinking = value
                    # MCP 工具配置 - 直接设置到环境变量
                    elif key in ('TAVILY_API_KEY', 'SERPAPI_API_KEY'):
                        os.environ[key] = value

    # 如果环境变量中已经设置了配置，优先使用环境变量
    # 这样可以支持在容器或 CI 环境中通过环境变量覆盖配置
    if os.environ.get('ANTHROPIC_API_KEY'):
        config.anthropic_api_key = os.environ['ANTHROPIC_API_KEY']
    if os.environ.get('ANTHROPIC_BASE_URL'):
        config.anthropic_base_url = os.environ['ANTHROPIC_BASE_URL']
    if os.environ.get('ANTHROPIC_MODEL'):
        config.anthropic_model = os.environ['ANTHROPIC_MODEL']
    if os.environ.get('ANTHROPIC_MODEL_THINKING'):
        config.anthropic_model_thinking = os.environ['ANTHROPIC_MODEL_THINKING']

    # 将配置设置到 os.environ（让子进程能继承）
    if config.anthropic_api_key:
        os.environ['ANTHROPIC_API_KEY'] = config.anthropic_api_key
    if config.anthropic_base_url:
        os.environ['ANTHROPIC_BASE_URL'] = config.anthropic_base_url
    if config.anthropic_model:
        os.environ['ANTHROPIC_MODEL'] = config.anthropic_model
    if config.anthropic_model_thinking:
        os.environ['ANTHROPIC_MODEL_THINKING'] = config.anthropic_model_thinking

    # 保存全局实例
    _config = config

    return config


def get_config() -> Config:
    """
    获取配置实例

    Returns:
        Config 实例

    Raises:
        RuntimeError: 如果还没有调用 load_config()

    使用示例：
        config = get_config()
        api_key = config.anthropic_api_key
    """
    global _config

    if _config is None:
        raise RuntimeError(
            "配置还未加载，请先调用 load_config()\n"
            "建议在程序入口处添加：\n"
            "  from config import load_config\n"
            "  load_config()"
        )

    return _config


def validate_config() -> tuple[bool, str]:
    """
    验证配置是否完整

    Returns:
        (是否有效, 错误信息)

    使用示例：
        valid, error = validate_config()
        if not valid:
            print(f"配置错误: {error}")
    """
    try:
        config = get_config()
    except RuntimeError as e:
        return False, str(e)

    if not config.anthropic_api_key:
        return False, "ANTHROPIC_API_KEY 未配置"

    if config.anthropic_api_key == "your-api-key-here":
        return False, "ANTHROPIC_API_KEY 是示例值，请填写真实的 API Key"

    return True, ""


if __name__ == "__main__":
    # 测试配置加载
    print("=== 配置加载测试 ===\n")

    config = load_config()
    print(config)
    print()

    valid, error = validate_config()
    if valid:
        print("[OK] 配置有效")
    else:
        print(f"[FAIL] 配置无效: {error}")
