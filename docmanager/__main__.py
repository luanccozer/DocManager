"""Ponto de entrada: python -m docmanager"""
from dotenv import load_dotenv

from .services.config import resource_path


def main():
    load_dotenv(resource_path(".env"))
    from .ui.main_app import main as run
    run()


if __name__ == "__main__":
    main()
