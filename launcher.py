import customtkinter as ctk
import threading
import sys
import os
from PIL import Image
import time
from dotenv import load_dotenv
def resource_path(relative_path):
    """ Obtém o caminho absoluto para recursos (imagens/ícones) """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)
env_path = resource_path('.env')
load_dotenv(env_path)
class LoadingScreen(ctk.CTk):
    def __init__(self):
        super().__init__()

        # 1. Configuração de Janela Transparente (Estilo Flutuante)
        self.overrideredirect(True) # Remove bordas do Windows
        self.attributes("-topmost", True) # Mantém no topo

        # Define tamanho
        largura, altura = 450, 420  # Mais altura para a barra respirar longe do texto
        x = (self.winfo_screenwidth() // 2) - (largura // 2)
        y = (self.winfo_screenheight() // 2) - (altura // 2)
        self.geometry(f"{largura}x{altura}+{x}+{y}")
        # O TRUQUE DA TRANSPARÊNCIA:
        # Definimos uma cor de fundo específica (
#000001) e dizemos ao Windows 
        # para tornar essa cor invisível.
        cor_transparente = "
#000001" 
        self.config(bg=cor_transparente)
        self.attributes("-transparentcolor", cor_transparente)

        # Criamos o "Corpo" real da janela (Arredondado)
        # Este será o fundo visível
        self.main_frame = ctk.CTkFrame(self, fg_color="
#2C3E50", corner_radius=20)
        self.main_frame.pack(fill="both", expand=True)
        # Fecha o Splash do PyInstaller se existir
        try:
            import pyi_splash # type: ignore
            if pyi_splash.is_alive(): pyi_splash.close()
        except: pass
        self.setup_ui()

        # Inicia carregamento
        threading.Thread(target=self.carregar_sistema, daemon=True).start()
    def setup_ui(self):
        # --- AQUI ESTAVA O ERRO ---
        # Precisamos criar o self.container DENTRO do self.main_frame
        self.container = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        # Subimos levemente o bloco central (rely=0.42) para liberar a base inteira
        self.container.place(relx=0.5, rely=0.42, anchor="center")
        # 1. LOGO GIGANTE (Opção 3)
        try:
            img_path = resource_path("assets/logo_final.png")
            pil_img = Image.open(img_path)
            # Aumentando para 150px
            tk_img = ctk.CTkImage(pil_img, size=(150, 150)) 

            lbl_img = ctk.CTkLabel(self.container, text="", image=tk_img)
            lbl_img.pack(pady=(0, 15))
        except Exception:
            pass
        # 2. TIPOGRAFIA MODERNA
        self.lbl_titulo = ctk.CTkLabel(self.container, text="DOC MANAGER", font=("Segoe UI", 24, "bold"), text_color="white")
        self.lbl_titulo.pack(pady=(0, 5))
        versao_app = os.getenv("VERSAO", "2.0.0") 
        self.lbl_subtitulo = ctk.CTkLabel(self.container, text=f"Versão {versao_app}", font=("Segoe UI", 12), text_color="
#BDC3C7")
        self.lbl_subtitulo.pack(pady=(0, 25))
        # 3. BARRA DE PROGRESSO "SLIM"
        self.progress = ctk.CTkProgressBar(self.container, width=280, height=8, corner_radius=4, progress_color="
#2ECC71", fg_color="
#1A252F", border_width=0)
        self.progress.set(0)
        self.progress.pack(pady=(0, 10))

        # Status pequeno
        self.lbl_status = ctk.CTkLabel(self.container, text="Iniciando...", font=("Consolas", 10), text_color="
#7f8c8d")
        self.lbl_status.pack()
        # 4. CHANGELOG (Notas da Versão no canto inferior esquerdo)
        self.frame_changelog = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        # 'sw' (South-West) ancora o frame no canto inferior esquerdo
        self.frame_changelog.place(relx=0.05, rely=0.95, anchor="sw") 
        # Título bem discreto
        self.lbl_change_title = ctk.CTkLabel(self.frame_changelog, text="Atualizações da versão:", font=("Segoe UI", 10, "bold"), text_color="
#BDC3C7")
        self.lbl_change_title.pack(anchor="w")
        # Texto das mudanças
        texto_mudancas = (
            "• 2.2.1. Módulo Kaizen: Excel atualizado com injeção de Protocolos\n"
            #"• 2.2.1. Dashboard (BI): Filtra documentos aprovados no backlog\n"
            "• 2.2.1. Relatório de Avanço: Correção de 30 dias para Revisões 0A\n"
            "• 2.2.2. Mapeamento dos planos: Adição de colunas de gerenciamento\n"
            "• 2.2.2. Relatórios: Adicionado o relatório de integração"
        )
        # Fonte tamanho 9, cor cinza escuro para não chamar muita atenção
        self.lbl_mudancas = ctk.CTkLabel(self.frame_changelog, text=texto_mudancas, font=("Segoe UI", 9), text_color="
#7f8c8d", justify="left")
        self.lbl_mudancas.pack(anchor="w")
    def atualizar_status(self, texto, valor):
        self.lbl_status.configure(text=texto)
        self.progress.set(valor)
    def carregar_sistema(self):
        """ Simula e executa os imports pesados """

        self.after(0, self.atualizar_status, "Carregando Pandas...", 0.2)
        import pandas as pd
        time.sleep(0.3) 
        self.after(0, self.atualizar_status, "Carregando Motor Gráfico...", 0.5)
        import dash
        import plotly.graph_objects as go
        time.sleep(0.3)
        self.after(0, self.atualizar_status, "Carregando Interface...", 0.8)

        # Importa a classe principal
        from aconex_reviewer import MainApp 
        self.MainAppClass = MainApp 
        time.sleep(0.5)
        self.after(0, self.atualizar_status, "Pronto!", 1.0)
        time.sleep(0.5)
        self.after(0, self.iniciar_main)
    def iniciar_main(self):
        self.destroy()
        app = self.MainAppClass()
        app.mainloop()
if __name__ == "__main__":
    app = LoadingScreen()
    app.mainloop()