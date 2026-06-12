"""Proxy configuration settings."""
from portprotonqt.config.base import BaseConfig, configparser
from portprotonqt.config.validators import validate_url, validate_string


class ProxyConfig(BaseConfig):
    """Proxy configuration settings."""

    _section = "Proxy"

    def ensure_section(self):
        """Ensure Proxy section exists."""
        cp = self._read_config() or configparser.ConfigParser()
        if self._section not in cp:
            cp.add_section(self._section)
            cp[self._section]["proxy_url"] = ""
            cp[self._section]["proxy_user"] = ""
            cp[self._section]["proxy_password"] = ""
            self._save_config(cp)

    def get_proxy(self) -> dict[str, str]:
        """Get proxy settings as dict."""
        self.ensure_section()
        cp = self._read_config()
        if cp is None:
            return {}

        proxy_url = cp.get(self._section, "proxy_url", fallback="").strip()
        if not proxy_url:
            return {}

        proxy_user = cp.get(self._section, "proxy_user", fallback="").strip()
        proxy_password = cp.get(self._section, "proxy_password", fallback="").strip()

        if "://" in proxy_url and "@" not in proxy_url and proxy_user and proxy_password:
            protocol, rest = proxy_url.split("://", 1)
            proxy_url = f"{protocol}://{proxy_user}:{proxy_password}@{rest}"

        return {"http": proxy_url, "https": proxy_url}

    def set_proxy(self, proxy_url: str = "", proxy_user: str = "", proxy_password: str = ""):
        """Set proxy settings."""
        validate_url(proxy_url, "proxy_url", allow_empty=True)
        validate_string(proxy_user, "proxy_user", max_len=100)
        validate_string(proxy_password, "proxy_password", max_len=100)

        cp = self._read_config() or configparser.ConfigParser()
        if self._section not in cp:
            cp[self._section] = {}
        cp[self._section]["proxy_url"] = proxy_url
        cp[self._section]["proxy_user"] = proxy_user
        cp[self._section]["proxy_password"] = proxy_password
        self._save_config(cp)
