"""Pytest 共享夹具。

测试原则：所有测试均不依赖 Neo4j / LLM 等外部服务，
仅测试纯函数与安全关键逻辑。
"""
import os
import sys
from pathlib import Path

# 将项目根目录加入 sys.path，使 `import app...` / `import api...` 可用
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# 测试环境默认使用 development，避免触发生产环境 JWT 校验
os.environ.setdefault("APP_ENV", "development")
