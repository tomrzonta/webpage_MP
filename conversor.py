import tkinter as tk
from tkinter import filedialog, messagebox
import pandas as pd
import os

def selecionar_arquivos():
    arquivos = filedialog.askopenfilenames(
        title="Selecione os arquivos CSV",
        filetypes=[("Arquivos CSV", "*.csv")]
    )
    lista_arquivos.delete(0, tk.END)
    for arquivo in arquivos:
        lista_arquivos.insert(tk.END, arquivo)

def selecionar_diretorio():
    pasta = filedialog.askdirectory(title="Selecione o diretório de salvamento")
    if pasta:
        entrada_diretorio.delete(0, tk.END)
        entrada_diretorio.insert(0, pasta)

def converter_arquivos():
    arquivos = lista_arquivos.get(0, tk.END)
    diretorio = entrada_diretorio.get()

    if not arquivos:
        messagebox.showwarning("Aviso", "Nenhum arquivo CSV selecionado.")
        return

    if not diretorio:
        messagebox.showwarning("Aviso", "Nenhum diretório de salvamento selecionado.")
        return

    for arquivo in arquivos:
        try:
            df = pd.read_csv(arquivo)
            nome_base = os.path.splitext(os.path.basename(arquivo))[0]
            novo_caminho = os.path.join(diretorio, f"{nome_base}.xlsx")
            df.to_excel(novo_caminho, index=False)
        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao converter {arquivo}:\n{str(e)}")
            return

    messagebox.showinfo("Sucesso", "Todos os arquivos foram convertidos com sucesso!")

# Interface
janela = tk.Tk()
janela.title("Conversor CSV para XLSX")
janela.geometry("600x400")
janela.resizable(False, False)

# Botões e lista
frame_topo = tk.Frame(janela)
frame_topo.pack(pady=10)

btn_selecionar = tk.Button(frame_topo, text="Selecionar Arquivos CSV", command=selecionar_arquivos)
btn_selecionar.pack()

lista_arquivos = tk.Listbox(janela, width=80, height=10)
lista_arquivos.pack(pady=10)

frame_diretorio = tk.Frame(janela)
frame_diretorio.pack(pady=5)

lbl_diretorio = tk.Label(frame_diretorio, text="Diretório de salvamento:")
lbl_diretorio.pack(side=tk.LEFT, padx=5)

entrada_diretorio = tk.Entry(frame_diretorio, width=40)
entrada_diretorio.pack(side=tk.LEFT)

btn_diretorio = tk.Button(frame_diretorio, text="Selecionar", command=selecionar_diretorio)
btn_diretorio.pack(side=tk.LEFT, padx=5)

btn_converter = tk.Button(janela, text="Converter para XLSX", command=converter_arquivos, bg="green", fg="white", width=30)
btn_converter.pack(pady=20)

janela.mainloop()


