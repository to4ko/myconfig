import re
from logging import LogRecord
from urllib.parse import urlencode

from homeassistant.const import __version__

RE_PATH = re.compile(r"/(custom_components|site-packages)/(.+)$")


def github_get_link(record: LogRecord) -> str | None:
    if record.pathname.startswith("/usr/src/homeassistant/"):
        base = f"https://github.com/home-assistant/core/blob"
        return f"{base}/{__version__}/{record.pathname[23:]}#L{record.lineno}"

    if m := RE_PATH.search(record.pathname):
        path = f"{m[1]}/{m[2]}" if m[1] == "custom_components" else m[2]
        query = urlencode({"q": f"path:{path} {record.funcName}", "type": "code"})
        return f"https://github.com/search?{query}#L{record.lineno}"

    return None
