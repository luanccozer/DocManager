"""Cofre das credenciais do Aconex - o que substitui o `.env`.

Por que mudou
-------------
Até a v3.0.0 o app era distribuído como um ZIP e o `.env` (com o Client Secret)
viajava junto, copiado à mão para a máquina de cada pessoa. Com o instalador do
GitHub isso deixou de existir: ninguém mais recebe um `.env` pronto. Então o
cadastro passou a ser feito DENTRO do app - a tela de Extração pede os três
dados que o Aconex exige na primeira vez que a pessoa tenta extrair.

Onde fica e como é protegido
----------------------------
`Documentos\\DocManager_Itaipu\\credenciais.json` - fora da pasta do programa,
de propósito: assim a atualização (que reescreve Program Files) não encosta nas
credenciais de ninguém.

O Client Secret é cifrado com a **DPAPI do Windows** (`CryptProtectData`), a
mesma API que o Chrome e o Edge usam para guardar senhas. A chave é derivada da
conta do Windows: o arquivo copiado para outra máquina, ou aberto por outro
usuário, não decifra. Não é cofre de banco - quem já estiver logado como a
pessoa consegue ler , mas é muito melhor que o `.env` em texto puro, que
qualquer um lia com o Bloco de Notas.

Fora do Windows (desenvolvimento em Linux/macOS) a DPAPI não existe e o segredo
fica em base64, que **não é criptografia** - só evita leitura acidental. O campo
`cifrado` do arquivo registra qual dos dois foi usado.
"""
from __future__ import annotations

import base64
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

SCHEMA = 1


# ────────────────────────────── DPAPI (Windows) ─────────────────────────────

def dpapi_disponivel() -> bool:
    return os.name == "nt"


def _dpapi(funcao: str, dados: bytes) -> bytes:
    """Chama CryptProtectData/CryptUnprotectData via ctypes (sem dependência nova)."""
    import ctypes
    from ctypes import wintypes

    class BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD),
                    ("pbData", ctypes.POINTER(ctypes.c_char))]

    entrada = BLOB(len(dados), ctypes.cast(ctypes.create_string_buffer(dados),
                                           ctypes.POINTER(ctypes.c_char)))
    saida = BLOB()
    crypt32 = ctypes.windll.crypt32
    chamada = getattr(crypt32, funcao)
    # CRYPTPROTECT_UI_FORBIDDEN (0x1): nunca abrir caixa de diálogo - o app pode
    # estar cifrando dentro de uma thread de trabalho, sem janela para exibir.
    ok = chamada(ctypes.byref(entrada), None, None, None, None, 0x01, ctypes.byref(saida))
    if not ok:
        raise OSError(f"{funcao} falhou (erro {ctypes.GetLastError()})")
    try:
        return ctypes.string_at(saida.pbData, saida.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(saida.pbData)


def cifrar(segredo: str) -> tuple[str, bool]:
    """(texto guardável, cifrado_de_verdade). Cai para base64 fora do Windows."""
    bruto = segredo.encode("utf-8")
    if dpapi_disponivel():
        try:
            return base64.b64encode(_dpapi("CryptProtectData", bruto)).decode("ascii"), True
        except Exception:  # noqa: BLE001 - DPAPI indisponível: não perder o cadastro
            pass
    return base64.b64encode(bruto).decode("ascii"), False


def decifrar(texto: str, cifrado: bool) -> str:
    bruto = base64.b64decode(texto.encode("ascii"))
    if cifrado:
        return _dpapi("CryptUnprotectData", bruto).decode("utf-8")
    return bruto.decode("utf-8")


# ────────────────────────────────── modelo ──────────────────────────────────

@dataclass(frozen=True)
class Credencial:
    """Os três dados que o OAuth do Aconex exige, já em claro."""
    nome: str
    client_id: str
    user_id: str
    secret: str

    def completa(self) -> bool:
        return bool(self.client_id and self.user_id and self.secret)


def sufixo_env(nome: str) -> str:
    """'Luan Cozer' → 'LUAN_COZER' (o formato das variáveis SECRET_* do .env)."""
    return re.sub(r"[^A-Z0-9]+", "_", nome.upper()).strip("_")


def pasta_dados() -> Path:
    """Pasta de dados do usuário (credenciais, config, token de atualização).

    `DOCMANAGER_DADOS_DIR` redireciona tudo - é o que deixa os testes rodarem
    isolados, e serve a quem precisa dos dados fora de `Documentos`.
    """
    if (custom := os.getenv("DOCMANAGER_DADOS_DIR", "").strip()):
        p = Path(custom)
    else:
        p = Path.home() / "Documents" / "DocManager_Itaipu"
    p.mkdir(parents=True, exist_ok=True)
    return p


class Cofre:
    """Leitura/escrita do `credenciais.json`. O caminho é injetável (testes)."""

    def __init__(self, caminho: Path | str | None = None):
        self.caminho = Path(caminho) if caminho else pasta_dados() / "credenciais.json"
        self._dados = self._carregar()

    def _carregar(self) -> dict:
        try:
            if self.caminho.exists():
                d = json.loads(self.caminho.read_text(encoding="utf-8"))
                if isinstance(d, dict) and isinstance(d.get("usuarios"), dict):
                    return d
        except Exception:  # noqa: BLE001 - arquivo corrompido não pode travar o app
            pass
        return {"schema": SCHEMA, "usuarios": {}}

    def _salvar(self) -> None:
        self._dados["schema"] = SCHEMA
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        self.caminho.write_text(json.dumps(self._dados, indent=2, ensure_ascii=False),
                                encoding="utf-8")
        if os.name != "nt":
            # Sem DPAPI o segredo está só em base64 - ao menos feche o arquivo
            # para os outros usuários da máquina.
            try:
                self.caminho.chmod(0o600)
            except Exception:  # noqa: BLE001
                pass

    # --- consulta ---
    def listar(self) -> list[str]:
        """Nomes cadastrados, em ordem alfabética."""
        return sorted(self._dados.get("usuarios", {}))

    def vazio(self) -> bool:
        return not self._dados.get("usuarios")

    def obter(self, nome: str) -> Credencial | None:
        reg = self._dados.get("usuarios", {}).get(nome)
        if not reg:
            return None
        try:
            secret = decifrar(reg.get("secret", ""), bool(reg.get("cifrado", False)))
        except Exception:  # noqa: BLE001
            # Cadastro feito em OUTRA máquina/conta do Windows: a DPAPI recusa.
            # Devolver sem o secret faz a UI pedir o recadastro, que é o certo.
            secret = ""
        return Credencial(nome=nome, client_id=reg.get("client_id", ""),
                          user_id=reg.get("user_id", ""), secret=secret)

    # --- escrita ---
    def salvar(self, nome: str, client_id: str, user_id: str, secret: str) -> Credencial:
        nome = nome.strip()
        client_id, user_id, secret = client_id.strip(), user_id.strip(), secret.strip()
        if not nome:
            raise ValueError("Informe um nome para identificar o usuário.")
        if not (client_id and user_id and secret):
            raise ValueError("Client ID, User ID e Client Secret são obrigatórios - "
                             "o Aconex exige os três para autenticar.")
        if not user_id.isdigit():
            raise ValueError(f"O User ID do Aconex é numérico (ex.: 1208560183). "
                             f"Recebido: '{user_id}'.")
        guardado, cifrado = cifrar(secret)
        self._dados.setdefault("usuarios", {})[nome] = {
            "client_id": client_id, "user_id": user_id,
            "secret": guardado, "cifrado": cifrado,
        }
        self._salvar()
        return Credencial(nome, client_id, user_id, secret)

    def remover(self, nome: str) -> bool:
        if self._dados.get("usuarios", {}).pop(nome, None) is None:
            return False
        self._salvar()
        return True

    # --- migração do .env ---
    def importar_do_env(self, conhecidos: dict[str, dict] | None = None,
                        ambiente: dict | None = None) -> list[str]:
        """Traz para o cofre os usuários que ainda estão no `.env`. Devolve os nomes.

        Roda sozinho na primeira execução depois da atualização: quem já tinha um
        `.env` funcionando não precisa recadastrar nada. Quem já está no cofre
        NÃO é sobrescrito - o cadastro feito no app sempre vence o `.env` velho.

        `conhecidos` é o mapa de usuários com Client/User ID já sabidos
        (`aconex_backend.USUARIOS`); passado por parâmetro para este módulo não
        depender do backend (evita import circular).
        """
        env = os.environ if ambiente is None else ambiente
        conhecidos = conhecidos or {}
        # Um usuário conhecido é achado por DOIS sufixos: o derivado do nome
        # ('Luan Cozer' → LUAN_COZER) e o declarado no próprio mapa
        # ('env': 'SECRET_LUAN' → LUAN). O .env em uso hoje usa o segundo.
        por_sufixo: dict[str, tuple[str, dict]] = {}
        for nome, dados in conhecidos.items():
            por_sufixo[sufixo_env(nome)] = (nome, dados)
            declarado = str(dados.get("env", "")).strip()
            if declarado.startswith("SECRET_"):
                por_sufixo[declarado[len("SECRET_"):]] = (nome, dados)
        importados: list[str] = []

        for chave, valor in list(env.items()):
            if not chave.startswith("SECRET_") or not str(valor).strip():
                continue
            sufixo = chave[len("SECRET_"):]
            nome, dados = por_sufixo.get(sufixo, (sufixo.replace("_", " ").title(), {}))
            if nome in self._dados.get("usuarios", {}):
                continue
            client_id = str(env.get(f"CLIENTID_{sufixo}", "") or dados.get("client_id", "")).strip()
            user_id = str(env.get(f"USERID_{sufixo}", "") or dados.get("user_id", "")).strip()
            if not (client_id and user_id):
                continue   # sem os IDs o secret sozinho não autentica
            try:
                self.salvar(nome, client_id, user_id, str(valor).strip())
                importados.append(nome)
            except ValueError:
                continue
        return importados


_cofre: Cofre | None = None


def cofre() -> Cofre:
    """Instância única do cofre (o app inteiro fala com a mesma)."""
    global _cofre
    if _cofre is None:
        _cofre = Cofre()
    return _cofre


def recarregar() -> Cofre:
    """Descarta a instância em memória - usado depois de um cadastro externo."""
    global _cofre
    _cofre = None
    return cofre()
