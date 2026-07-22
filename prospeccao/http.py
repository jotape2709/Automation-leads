from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def post_json(url: str, payload: dict, headers: dict[str, str], timeout: int = 60) -> dict:
    request = Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detalhe = exc.read().decode("utf-8", errors="replace")[:800]
        raise RuntimeError(f"API respondeu HTTP {exc.code}: {detalhe}") from exc
    except URLError as exc:
        raise RuntimeError(f"Não foi possível conectar à API: {exc.reason}") from exc
