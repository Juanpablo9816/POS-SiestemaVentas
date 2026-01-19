# -*- coding: utf-8 -*-

import tkinter as tk
from tkinter import messagebox

class VentanaVentaGranel:
    """
    Pequeña ventana para ingresar el precio de una venta de producto a granel.
    """
    def __init__(self, master, producto, callback):
        """
        Inicializa la ventana de venta a granel. Esta pequeña ventana aparece cuando se escanea
        un producto configurado como 'Granel', para poder ingresar el precio de la venta actual.
        - `master`: La ventana principal.
        - `producto`: El diccionario del producto que se está vendiendo.
        - `callback`: La función que se llamará para agregar el producto al carrito.
        """
        self.top = tk.Toplevel(master)
        self.top.title("Venta a granel")
        self.top.geometry("300x200")
        self.top.grab_set() # Ventana modal.

        self.producto = producto
        self.callback = callback
        self.var_precio = tk.DoubleVar(value=0.0)

        # Muestra el nombre del producto para referencia.
        tk.Label(self.top, text=producto['nombre'], font=("Segoe UI", 11, "bold")).pack(pady=10)
        
        # Campo para ingresar el precio de esta venta específica.
        tk.Label(self.top, text="Precio de esta venta ($):").pack()
        entry = tk.Entry(self.top, textvariable=self.var_precio, font=("Segoe UI", 14), justify="center")
        entry.pack(pady=5)
        entry.bind("<Return>", lambda e: self.confirmar()) # Enter confirma.
        entry.focus_set() # Foco inicial en el campo de precio.

        # Botón para confirmar y agregar al carrito.
        tk.Button(self.top, text="Aceptar", bg="#28a745", fg="white", command=self.confirmar).pack(pady=10, fill="x", padx=30)

    def confirmar(self):
        """Valida el precio y llama al callback para agregar el producto al carrito."""
        try:
            precio = self.var_precio.get()
            if precio <= 0:
                messagebox.showwarning("Atención", "El precio debe ser mayor que 0.")
                return
        except ValueError:
            messagebox.showwarning("Atención", "Ingrese un precio válido.")
            return
        self.top.destroy()
        self.callback(self.producto, precio)
