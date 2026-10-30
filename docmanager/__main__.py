"""Ponto de entrada: python -m docmanager"""


def main(argv=None):
    import sys

    argv = sys.argv[1:] if argv is None else argv
    try:
        from dotenv import load_dotenv

        from .services.config import resource_path
        load_dotenv(resource_path(".env"))
        if argv[:1] == ["--extrair-aconex"]:
            # sem janela, para a CMI Suite (extracao_headless.py); antes de importar a interface
            from .extracao_headless import main as extrair
            raise SystemExit(extrair(argv[1:]))
        from .ui.main_app import main as run
    except ModuleNotFoundError as e:
        # Rodou com o Python do sistema (sem as dependências) em vez do venv.
        raise SystemExit(
            f"Dependência ausente: '{e.name}'.\n"
            f"Abra pelo run.bat (cria o .venv e instala tudo na 1ª vez) - ou ative "
            f"o ambiente virtual antes:\n"
            f"    .venv\\Scripts\\activate   (ou o seu venv)\n"
            f"    python -m docmanager"
        ) from e
    run()


if __name__ == "__main__":
    main()
