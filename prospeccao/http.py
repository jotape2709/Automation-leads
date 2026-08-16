from __future__ import annotations

import json
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


PADROES_SEGREDO = (
    re.compile(r"AIza[0-9A-Za-z_-]{30,}"),
    re.compile(r"sk-(?:proj-)?[0-9A-Za-z_-]{20,}"),
    re.compile(r"(?i)(api[_-]?key|token|secret|password)([=: ]+)[^\s,;]+"),
)


def _redigir(texto: str) -> str:
    seguro = texto
    for padrao in PADROES_SEGREDO:
        seguro = padrao.sub(
            lambda resultado: (
                f"{resultado.group(1)}{resultado.group(2)}<redigido>"
                if resultado.lastindex == 2
                else "<segredo-redigido>"
            ),
            seguro,
        )
    return seguro[:500]


def post_json(url: str, payload: dict, headers: dict[str, str], timeout: int = 60) -> dict:
    request = Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            limite = 2 * 1024 * 1024
            conteudo = response.read(limite + 1)
            if len(conteudo) > limite:
                raise RuntimeError("A resposta da API excedeu o limite permitido.")
            return json.loads(conteudo.decode("utf-8"))
    except HTTPError as exc:
        detalhe = _redigir(exc.read(4096).decode("utf-8", errors="replace"))
        raise RuntimeError(f"API respondeu HTTP {exc.code}: {detalhe}") from exc
    except URLError as exc:
        raise RuntimeError(
            f"Não foi possível conectar à API: {_redigir(str(exc.reason))}"
        ) from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError("A API retornou uma resposta JSON inválida.") from exc
