"""Backend puro do DocManager: zero imports de UI, 100% testável.

Regra de ouro (KB §22.5): nenhum módulo daqui conhece tkinter, messagebox
ou filedialog. Progresso e log saem por callbacks.
"""
