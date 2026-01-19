# -*- coding: utf-8 -*-

import tkinter as tk

class VentanaProductoNoEncontrado:
    """
    Diálogo modal que aparece cuando un código de barras no se encuentra en la BD,
    ofreciendo al usuario acciones para continuar.
    """
    def __init__(self, master, codigo):
        self.top = tk.Toplevel(master)
        self.top.title("Producto No Encontrado")
        self.top.geometry("450x280")
        self.top.resizable(False, False)
        self.top.grab_set() # Hacer modal
        self.top.transient(master)

        self.result = None # Almacenará la elección del usuario

        main_frame = tk.Frame(self.top, padx=20, pady=20)
        main_frame.pack(fill="both", expand=True)

        msg = f"El producto con código '{codigo}' no existe en la base de datos."
        tk.Label(main_frame, text=msg, wraplength=400, justify="center", font=("Segoe UI", 11)).pack(pady=(0, 10))
        tk.Label(main_frame, text="¿Qué deseas hacer?", font=("Segoe UI", 11, "bold")).pack()

        btn_style = {"font": ("Segoe UI", 10), "pady": 5, "padx": 10, "cursor": "hand2"}

        tk.Button(main_frame, text="➕ Añadir Nuevo Producto", command=self.on_add, bg="#28a745", fg="white", **btn_style).pack(pady=5, fill="x")
        tk.Button(main_frame, text="🔍 Buscar por Nombre", command=self.on_search, bg="#007bff", fg="white", **btn_style).pack(pady=5, fill="x")
        tk.Button(main_frame, text="✖️ Cancelar", command=self.on_cancel, **btn_style).pack(pady=5, fill="x")

    def on_add(self):
        self.result = 'add'
        self.top.destroy()

    def on_search(self):
        self.result = 'search'
        self.top.destroy()

    def on_cancel(self):
        self.result = 'cancel'
        self.top.destroy()
