"""Cofre criptográfico local (AEAD) e controles de segurança de software da JPX Lab.

Implementa criptografia autenticada (Encrypt-then-MAC) usando primitivas
auditáveis da biblioteca padrão do Python:
- Derivação de chave: PBKDF2-HMAC-SHA256 com 600.000 iterações (recomendação OWASP)
- Separação de subchaves: HMAC-SHA256 (K_enc de 256 bits + K_mac de 256 bits)
- Cifra de fluxo em modo contador (CTR) com blocos HMAC-SHA256 e nonce CSPRNG de 128 bits
- Autenticação de integridade: HMAC-SHA256 em tempo constante (hmac.compare_digest)
- Proteção contra força bruta: Rate Limiter em memória por janela deslizante
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import struct
import time
from collections import deque
from pathlib import Path

MAGIC_HEADER = b"JPXVAULT1"
PBKDF2_ITERATIONS = 600_000
SALT_BYTES = 16
NONCE_BYTES = 16
MAC_BYTES = 32

CHAVES_SENSIVEIS = {
    "GOOGLE_PLACES_API_KEY",
    "OPENAI_API_KEY",
    "GEMINI_API_KEY",
}

CHAVES_CONFIGURAVEIS = {
    "GOOGLE_PLACES_API_KEY",
    "GOOGLE_PLACES_ENABLED",
    "MAX_PLACES_REQUESTS",
    "OPENAI_API_KEY",
    "OPENAI_MODEL",
    "GEMINI_API_KEY",
    "GEMINI_MODEL",
    "DEFAULT_AI_PROVIDER",
    "DEFAULT_TONE",
    "DEFAULT_SERVICE",
    "PROSPECTOR_NAME",
    "BUSINESS_NAME",
    "DAILY_CONTACT_LIMIT",
}

VALORES_PADRAO = {
    "GOOGLE_PLACES_API_KEY": "",
    "GOOGLE_PLACES_ENABLED": "0",
    "MAX_PLACES_REQUESTS": "60",
    "OPENAI_API_KEY": "",
    "OPENAI_MODEL": "gpt-5.6-luna",
    "GEMINI_API_KEY": "",
    "GEMINI_MODEL": "gemini-3.6-flash",
    "DEFAULT_AI_PROVIDER": "Modelo local",
    "DEFAULT_TONE": "Consultivo",
    "DEFAULT_SERVICE": "Landing Page Express — R$ 149",
    "PROSPECTOR_NAME": "João Pedro",
    "BUSINESS_NAME": "JPX Lab",
    "DAILY_CONTACT_LIMIT": "10",
}


def mascarar_segredo(valor: str) -> str:
    """Retorna uma representação mascarada segura de uma chave de API."""
    limpo = (valor or "").strip()
    if not limpo:
        return ""
    if len(limpo) <= 8:
        return "•" * len(limpo)
    return f"{limpo[:4]}{'•' * 8}{limpo[-4:]}"


def validar_formato_credencial(chave: str, valor: str) -> None:
    """Valida formato básico de chaves de API para evitar injeção ou erro de colagem."""
    v = (valor or "").strip()
    if not v:
        return
    if any(ord(c) < 32 or ord(c) == 127 for c in v):
        raise ValueError(f"A credencial {chave} contém caracteres de controle inválidos.")
    if len(v) > 256:
        raise ValueError(f"A credencial {chave} excede o tamanho máximo permitido.")
    if chave == "GOOGLE_PLACES_API_KEY":
        if not v.startswith("AIza") or not re.fullmatch(r"[0-9A-Za-z_-]{30,60}", v):
            raise ValueError(
                "GOOGLE_PLACES_API_KEY inválida (deve iniciar com 'AIza' e ter entre 30 e 60 caracteres)."
            )
    elif chave == "GEMINI_API_KEY":
        if not re.fullmatch(r"[0-9A-Za-z_-]{25,80}", v):
            raise ValueError("GEMINI_API_KEY possui formato inválido.")
    elif chave == "OPENAI_API_KEY":
        if not v.startswith("sk-") or len(v) < 20:
            raise ValueError("OPENAI_API_KEY inválida (deve iniciar com 'sk-').")


def _derivar_subchaves(segredo_mestre: bytes, salt: bytes) -> tuple[bytes, bytes]:
    material = hashlib.pbkdf2_hmac(
        "sha256", segredo_mestre, salt, PBKDF2_ITERATIONS, dklen=64
    )
    k_enc = hmac.new(material[:32], b"jpx-vault-enc-v1", hashlib.sha256).digest()
    k_mac = hmac.new(material[32:], b"jpx-vault-mac-v1", hashlib.sha256).digest()
    return k_enc, k_mac


def _keystream_xor(dados: bytes, k_enc: bytes, nonce: bytes) -> bytes:
    saida = bytearray(len(dados))
    blocos = (len(dados) + 31) // 32
    for contador in range(blocos):
        bloco_ctr = nonce + struct.pack(">Q", contador)
        keystream = hmac.new(k_enc, bloco_ctr, hashlib.sha256).digest()
        inicio = contador * 32
        fim = min(inicio + 32, len(dados))
        for i in range(inicio, fim):
            saida[i] = dados[i] ^ keystream[i - inicio]
    return bytes(saida)


def criptografar_bytes(plaintext: bytes, senha: str | bytes) -> bytes:
    """Criptografa bytes usando AEAD (PBKDF2-HMAC-SHA256 + CTR-HMAC-SHA256 + Encrypt-then-MAC)."""
    segredo = senha.encode("utf-8") if isinstance(senha, str) else bytes(senha)
    salt = secrets.token_bytes(SALT_BYTES)
    nonce = secrets.token_bytes(NONCE_BYTES)
    k_enc, k_mac = _derivar_subchaves(segredo, salt)
    ciphertext = _keystream_xor(plaintext, k_enc, nonce)
    payload_sem_mac = MAGIC_HEADER + salt + nonce + ciphertext
    tag = hmac.new(k_mac, payload_sem_mac, hashlib.sha256).digest()
    return base64.b64encode(payload_sem_mac + tag)


def descriptografar_bytes(pacote_b64: bytes, senha: str | bytes) -> bytes:
    """Verifica o MAC em tempo constante e descriptografa o pacote AEAD."""
    segredo = senha.encode("utf-8") if isinstance(senha, str) else bytes(senha)
    try:
        bruto = base64.b64decode(pacote_b64, validate=True)
    except Exception as exc:
        raise ValueError("Arquivo do cofre criptográfico corrompido (Base64 inválido).") from exc

    tamanho_minimo = len(MAGIC_HEADER) + SALT_BYTES + NONCE_BYTES + MAC_BYTES
    if len(bruto) < tamanho_minimo or not bruto.startswith(MAGIC_HEADER):
        raise ValueError("Formato de cofre criptográfico inválido ou versão não suportada.")

    pos_salt = len(MAGIC_HEADER)
    pos_nonce = pos_salt + SALT_BYTES
    pos_cipher = pos_nonce + NONCE_BYTES
    pos_mac = len(bruto) - MAC_BYTES

    salt = bruto[pos_salt:pos_nonce]
    nonce = bruto[pos_nonce:pos_cipher]
    ciphertext = bruto[pos_cipher:pos_mac]
    tag_recebida = bruto[pos_mac:]

    k_enc, k_mac = _derivar_subchaves(segredo, salt)
    tag_esperada = hmac.new(k_mac, bruto[:pos_mac], hashlib.sha256).digest()
    if not hmac.compare_digest(tag_recebida, tag_esperada):
        raise ValueError("Senha mestra incorreta ou integridade do cofre comprometida.")

    return _keystream_xor(ciphertext, k_enc, nonce)


class LimitadorTaxa:
    """Rate limiter por janela deslizante em memória contra força bruta."""

    def __init__(self, max_tentativas: int = 10, janela_segundos: int = 60) -> None:
        self.max_tentativas = max_tentativas
        self.janela = janela_segundos
        self._eventos: dict[str, deque[float]] = {}

    def verificar(self, chave: str) -> None:
        agora = time.monotonic()
        fila = self._eventos.setdefault(chave, deque())
        while fila and agora - fila[0] > self.janela:
            fila.popleft()
        if len(fila) >= self.max_tentativas:
            raise ValueError(
                "Limite de tentativas de segurança excedido. Aguarde 1 minuto antes de tentar novamente."
            )
        fila.append(agora)


class CofreCredenciais:
    """Gerencia configurações e credenciais criptografadas em disco e em memória."""

    def __init__(self, caminho_cofre: str | Path = "data/vault.enc") -> None:
        self.caminho = Path(caminho_cofre)
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        self.caminho_chave_local = self.caminho.parent / ".vault.key"
        self.caminho_meta = self.caminho.parent / "vault_meta.json"
        self.token_sessao = secrets.token_urlsafe(32)
        self.limitador = LimitadorTaxa(max_tentativas=10, janela_segundos=60)
        self._senha_customizada: str | None = None
        self._bloqueado: bool = False
        self._cache: dict[str, str] = {}
        self._inicializar()

    def _chave_maquina(self) -> bytes:
        if not self.caminho_chave_local.exists():
            entropia = secrets.token_bytes(32)
            self.caminho_chave_local.write_bytes(entropia)
            try:
                os.chmod(self.caminho_chave_local, 0o600)
            except OSError:
                pass
        return self.caminho_chave_local.read_bytes()

    def _segredo_efetivo(self, senha_mestra: str | None = None) -> bytes:
        base = self._chave_maquina()
        s = (senha_mestra if senha_mestra is not None else (self._senha_customizada or "")).strip()
        if s:
            return hmac.new(base, s.encode("utf-8"), hashlib.sha256).digest()
        return base

    def possui_senha_mestra(self) -> bool:
        if not self.caminho_meta.exists():
            return False
        try:
            meta = json.loads(self.caminho_meta.read_text(encoding="utf-8"))
            return bool(meta.get("custom_password", False))
        except Exception:
            return False

    def _salvar_meta(self, custom_password: bool) -> None:
        self.caminho_meta.write_text(
            json.dumps(
                {
                    "version": "JPXVAULT1",
                    "kdf": "PBKDF2-HMAC-SHA256",
                    "iterations": PBKDF2_ITERATIONS,
                    "cipher": "CTR-HMAC-SHA256-AEAD",
                    "custom_password": custom_password,
                    "updated_at": int(time.time()),
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    def _inicializar(self) -> None:
        if not self.caminho.exists():
            self._cache = {}
            self._bloqueado = False
            return
        if self.possui_senha_mestra():
            self._bloqueado = True
            self._cache = {}
            return
        try:
            bruto = descriptografar_bytes(self.caminho.read_bytes(), self._segredo_efetivo(""))
            self._cache = json.loads(bruto.decode("utf-8"))
            self._bloqueado = False
            self._aplicar_ambiente()
        except Exception:
            self._bloqueado = True
            self._cache = {}

    def _aplicar_ambiente(self) -> None:
        for chave, valor in self._cache.items():
            if chave in CHAVES_CONFIGURAVEIS and valor is not None:
                os.environ[chave] = str(valor)

    def esta_bloqueado(self) -> bool:
        return self._bloqueado

    def bloquear(self) -> None:
        """Remove chaves sensíveis descriptografadas da memória até novo desbloqueio."""
        for chave in CHAVES_SENSIVEIS:
            if chave in self._cache:
                os.environ.pop(chave, None)
        self._cache.clear()
        self._bloqueado = True

    def desbloquear(self, senha_mestra: str = "") -> bool:
        self.limitador.verificar("vault_unlock")
        if not self.caminho.exists():
            self._bloqueado = False
            return True
        bruto = descriptografar_bytes(
            self.caminho.read_bytes(), self._segredo_efetivo(senha_mestra)
        )
        dados = json.loads(bruto.decode("utf-8"))
        self._senha_customizada = senha_mestra.strip() or None
        self._cache = dados
        self._bloqueado = False
        self._aplicar_ambiente()
        return True

    def obter(self, chave: str, padrao: str = "") -> str:
        if not self._bloqueado and chave in self._cache and self._cache[chave] != "":
            return str(self._cache[chave])
        return os.getenv(chave, VALORES_PADRAO.get(chave, padrao))

    def salvar_configuracoes(
        self,
        novos_dados: dict[str, object],
        nova_senha_mestra: str | None = None,
        senha_atual: str | None = None,
    ) -> dict:
        self.limitador.verificar("vault_save")
        if self._bloqueado:
            if not senha_atual:
                raise ValueError("O cofre está bloqueado. Informe a Senha Mestra para salvar alterações.")
            self.desbloquear(senha_atual)

        atualizado = dict(self._cache)
        for chave in CHAVES_CONFIGURAVEIS:
            if chave not in novos_dados:
                continue
            valor_str = str(novos_dados[chave] or "").strip()
            if chave in CHAVES_SENSIVEIS:
                # Se veio vazio ou mascarado (contendo '•'), preserva o valor já salvo
                # a menos que o campo especial limpar_<chave> tenha sido enviado
                if not valor_str or "•" in valor_str:
                    if novos_dados.get(f"limpar_{chave}") is True:
                        atualizado.pop(chave, None)
                        os.environ.pop(chave, None)
                    continue
                validar_formato_credencial(chave, valor_str)
                atualizado[chave] = valor_str
            else:
                if chave == "MAX_PLACES_REQUESTS":
                    n = int(valor_str or "60")
                    if not 1 <= n <= 500:
                        raise ValueError("MAX_PLACES_REQUESTS deve estar entre 1 e 500.")
                    valor_str = str(n)
                elif chave == "DAILY_CONTACT_LIMIT":
                    n = int(valor_str or "10")
                    if not 1 <= n <= 200:
                        raise ValueError("DAILY_CONTACT_LIMIT deve estar entre 1 e 200.")
                    valor_str = str(n)
                elif chave == "GOOGLE_PLACES_ENABLED":
                    valor_str = "1" if valor_str in {"1", "true", "True"} else "0"
                atualizado[chave] = valor_str[:200]

        if nova_senha_mestra is not None:
            limpa = nova_senha_mestra.strip()
            if limpa and len(limpa) < 6:
                raise ValueError("A Senha Mestra deve ter pelo menos 6 caracteres.")
            self._senha_customizada = limpa if limpa else None

        payload_json = json.dumps(atualizado, ensure_ascii=False).encode("utf-8")
        pacote = criptografar_bytes(payload_json, self._segredo_efetivo(self._senha_customizada))
        self.caminho.write_bytes(pacote)
        try:
            os.chmod(self.caminho, 0o600)
        except OSError:
            pass

        self._salvar_meta(custom_password=bool(self._senha_customizada))
        self._cache = atualizado
        self._bloqueado = False
        self._aplicar_ambiente()
        return self.estado_publico()

    def rotacionar_chaves(self, senha_mestra: str = "") -> dict:
        """Gera novo salt, novo nonce e nova chave de máquina, re-criptografando o cofre."""
        if self._bloqueado:
            self.desbloquear(senha_mestra)
        entropia = secrets.token_bytes(32)
        self.caminho_chave_local.write_bytes(entropia)
        return self.salvar_configuracoes({}, nova_senha_mestra=self._senha_customizada)

    def estado_publico(self) -> dict:
        """Retorna estado seguro (com segredos mascarados) para exibição na interface."""
        credenciais = {}
        for chave in CHAVES_SENSIVEIS:
            valor_cofre = self._cache.get(chave, "") if not self._bloqueado else ""
            valor_env = os.getenv(chave, "")
            valor_ativo = valor_cofre or valor_env
            origem = (
                "Cofre Criptografado (AEAD)"
                if valor_cofre
                else ("Arquivo .env" if valor_env else "Não configurada")
            )
            credenciais[chave] = {
                "configurada": bool(valor_ativo),
                "mascara": mascarar_segredo(valor_ativo),
                "origem": origem,
            }

        config = {}
        for chave in CHAVES_CONFIGURAVEIS - CHAVES_SENSIVEIS:
            config[chave] = self.obter(chave, VALORES_PADRAO.get(chave, ""))

        return {
            "cofre_existe": self.caminho.exists(),
            "bloqueado": self._bloqueado,
            "possui_senha_mestra": self.possui_senha_mestra(),
            "criptografia": {
                "protocolo": "JPXVAULT1 (Encrypt-then-MAC AEAD)",
                "kdf": f"PBKDF2-HMAC-SHA256 ({PBKDF2_ITERATIONS:,} iterações)",
                "cifra": "CTR-HMAC-SHA256 (256 bits) + Nonce CSPRNG 128 bits",
                "integridade": "HMAC-SHA256 em tempo constante (compare_digest)",
            },
            "credenciais": credenciais,
            "config": config,
        }
