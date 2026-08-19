"""Config 单元测试：生产环境 JWT_SECRET_KEY 安全校验。"""
import importlib
import os
import pytest
from pydantic import ValidationError


def _reload_config(env_overrides: dict):
    """用指定环境变量重载 config 模块，返回新的 settings 实例。"""
    # 备份当前环境变量
    old_values = {k: os.environ.get(k) for k in env_overrides}
    try:
        for k, v in env_overrides.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        # 重载模块以应用新的环境变量
        import app.core.config as config_module
        importlib.reload(config_module)
        return config_module.settings
    finally:
        # 恢复环境变量
        for k, old_val in old_values.items():
            if old_val is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = old_val


class TestJwtSecretValidation:
    def test_development_allows_default_secret(self):
        """开发环境允许使用默认密钥（向后兼容）。"""
        settings = _reload_config({
            "APP_ENV": "development",
            "JWT_SECRET_KEY": "dev_secret_key_change_in_production",
        })
        assert settings.APP_ENV == "development"
        assert settings.JWT_SECRET_KEY == "dev_secret_key_change_in_production"

    def test_production_rejects_default_secret(self):
        """生产环境拒绝默认密钥。"""
        with pytest.raises(ValidationError) as exc_info:
            _reload_config({
                "APP_ENV": "production",
                "JWT_SECRET_KEY": "dev_secret_key_change_in_production",
            })
        assert "JWT_SECRET_KEY" in str(exc_info.value) or "默认" in str(exc_info.value)

    def test_production_rejects_short_secret(self):
        """生产环境拒绝过短密钥（< 16 字符）。"""
        with pytest.raises(ValidationError) as exc_info:
            _reload_config({
                "APP_ENV": "production",
                "JWT_SECRET_KEY": "short",
            })
        assert "过短" in str(exc_info.value) or "length" in str(exc_info.value).lower()

    def test_production_accepts_strong_secret(self):
        """生产环境接受高强度密钥。"""
        strong_key = "a-very-secure-random-key-32-chars-long!!"
        settings = _reload_config({
            "APP_ENV": "production",
            "JWT_SECRET_KEY": strong_key,
        })
        assert settings.APP_ENV == "production"
        assert settings.JWT_SECRET_KEY == strong_key

    def test_production_accepts_min_length_secret(self):
        """生产环境接受刚好 16 字符的密钥（边界值）。"""
        boundary_key = "exactly16chars!!"  # 16 字符
        assert len(boundary_key) == 16
        settings = _reload_config({
            "APP_ENV": "production",
            "JWT_SECRET_KEY": boundary_key,
        })
        assert settings.JWT_SECRET_KEY == boundary_key
