#!/usr/bin/env python3
"""
Verify Claude Agent SDK Setup

Run: python scripts/verify_setup.py

Checks:
1. Python version
2. SDK package installation
3. API Key configuration
4. SDK core module import
"""

import sys
import os

def print_status(name: str, success: bool, message: str = ""):
    """Print check status"""
    status = "[OK]" if success else "[FAIL]"
    print(f"{status} {name}")
    if message:
        print(f"     {message}")

def check_python_version():
    """Check Python version"""
    version = sys.version_info
    success = version.major >= 3 and version.minor >= 10
    version_str = f"{version.major}.{version.minor}.{version.micro}"

    if success:
        print_status("Python Version", True, f"Current: {version_str} (requires 3.10+)")
    else:
        print_status("Python Version", False, f"Current: {version_str} (requires 3.10+)")

    return success

def check_sdk_installed():
    """Check if SDK is installed"""
    try:
        import claude_agent_sdk
        version = getattr(claude_agent_sdk, '__version__', 'unknown')
        print_status("SDK Installation", True, f"claude-agent-sdk version: {version}")
        return True
    except ImportError as e:
        print_status("SDK Installation", False, f"Not installed: {e}")
        print("     Run: pip install claude-agent-sdk")
        return False

def check_api_key():
    """Check API Key configuration"""
    # Try to load from .env file
    env_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
    if os.path.exists(env_file):
        with open(env_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line.startswith('ANTHROPIC_API_KEY='):
                    key = line.split('=', 1)[1].strip()
                    if key and key != 'your-api-key-here':
                        os.environ['ANTHROPIC_API_KEY'] = key
                elif line.startswith('ANTHROPIC_BASE_URL='):
                    url = line.split('=', 1)[1].strip()
                    if url:
                        os.environ['ANTHROPIC_BASE_URL'] = url

    api_key = os.environ.get('ANTHROPIC_API_KEY', '')
    base_url = os.environ.get('ANTHROPIC_BASE_URL', '')

    if api_key and api_key != 'your-api-key-here':
        # Only show first and last few chars
        masked = f"{api_key[:8]}...{api_key[-4:]}" if len(api_key) > 12 else "***"
        msg = f"Configured: {masked}"
        if base_url:
            msg += f" | Base URL: {base_url}"
        print_status("API Key", True, msg)
        return True
    else:
        print_status("API Key", False, "Not configured or default value")
        print("     1. Copy .env.example to .env")
        print("     2. Fill in your ANTHROPIC_API_KEY")
        return False

def check_sdk_import():
    """Check SDK core module import"""
    try:
        from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions
        print_status("SDK Core Modules", True, "ClaudeSDKClient, ClaudeAgentOptions available")
        return True
    except ImportError as e:
        print_status("SDK Core Modules", False, f"Import failed: {e}")
        return False

def main():
    print("=" * 50)
    print("Claude Agent SDK Setup Verification")
    print("=" * 50)
    print()

    results = []

    # 1. Python version
    results.append(("Python Version", check_python_version()))
    print()

    # 2. SDK installation
    results.append(("SDK Installation", check_sdk_installed()))
    print()

    # 3. API Key
    results.append(("API Key", check_api_key()))
    print()

    # 4. SDK module import
    if results[1][1]:  # Only check if SDK is installed
        results.append(("SDK Modules", check_sdk_import()))
        print()

    # Summary
    print("=" * 50)
    passed = sum(1 for _, success in results if success)
    total = len(results)

    if passed == total:
        print(f"All checks passed ({passed}/{total})")
        print()
        print("Next step: Run python src/v0_hello.py to start learning")
        return 0
    else:
        print(f"Some checks failed ({passed}/{total})")
        print()
        print("Please fix the issues above and run this script again")
        return 1

if __name__ == "__main__":
    sys.exit(main())
