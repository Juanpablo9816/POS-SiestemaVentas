# -*- coding: utf-8 -*-

import tkinter as tk
from tkinter import ttk, messagebox

class VentanaCobro:
    """
    Gestiona la ventana de cobro, permitiendo seleccionar método de pago,
    aplicar intereses y manejar pagos simples o mixtos.
    """
    def __init__(self, master, total_a_pagar, callback_guardar):
        """
        Inicializa la ventana de cobro.
        - `master`: La ventana principal.
        - `total_a_pagar`: El monto total del carrito que se debe cobrar.
        - `callback_guardar`: La función que se ejecutará al confirmar el pago.
        """
        self.top = tk.Toplevel(master)
        self.top.title("Cierre de Caja")
        self.top.geometry("460x700")
        self.top.grab_set() # Hace que esta ventana sea modal (bloquea la principal).
        
        # --- Estilos y Variables ---
        BG_COLOR = "#e3e3e3" 
        self.top.config(bg=BG_COLOR)
        
        self.total_original = total_a_pagar
        self.total_final = total_a_pagar 
        self.callback = callback_guardar # Función para guardar la venta en la BD.
        
        # Definición de fuentes para consistencia visual.
        self.FONT_BIG = ("Segoe UI", 28, "bold") 
        self.FONT_TITLE = ("Segoe UI", 11)
        self.FONT_OPTION = ("Segoe UI", 12)
        self.FONT_SELECTED = ("Segoe UI", 12, "bold")
        self.FONT_INPUT = ("Segoe UI", 14)
        
        # --- Total a Pagar (Display Gigante) ---
        frame_top = tk.Frame(self.top, bg=BG_COLOR)
        frame_top.pack(fill="x", pady=(10, 0))
        
        tk.Label(frame_top, text="TOTAL A PAGAR", bg=BG_COLOR, fg="#555", font=self.FONT_TITLE).pack()
        self.lbl_total_gigante = tk.Label(frame_top, text=f"${self.total_final:.2f}", bg=BG_COLOR, fg="#dc3545", font=self.FONT_BIG)
        self.lbl_total_gigante.pack()
        self.lbl_info_recargo = tk.Label(frame_top, text="", bg=BG_COLOR, fg="#b08d00", font=("Segoe UI", 10, "bold"))
        self.lbl_info_recargo.pack()

        # --- Selección de Método de Pago ---
        frame_medio = tk.Frame(self.top, bg=BG_COLOR)
        frame_medio.pack(fill="x", padx=30, pady=5)

        tk.Label(frame_medio, text="MÉTODO:", bg=BG_COLOR, font=("Segoe UI", 10, "bold"), anchor="w").pack(fill="x")
        
        self.var_metodo = tk.StringVar(value="Efectivo")
        self.radio_widgets = {} # Diccionario para guardar los radio buttons.
        opciones = ["Efectivo", "Tarjeta Débito", "Tarjeta Crédito", "Mercado Pago", "Pago Mixto"]
        
        # Crea un Radiobutton por cada método de pago.
        for opcion in opciones:
            rb = tk.Radiobutton(frame_medio, text=opcion, variable=self.var_metodo, 
                                value=opcion, bg=BG_COLOR, activebackground=BG_COLOR,
                                font=self.FONT_OPTION, anchor="w",
                                command=self.actualizar_interfaz)
            rb.pack(fill="x", pady=2) 
            self.radio_widgets[opcion] = rb

        # --- Campo para Ingresar Interés (para Tarjetas) ---
        frame_interes = tk.Frame(frame_medio, bg=BG_COLOR)
        frame_interes.pack(fill="x", pady=(5, 5))
        
        tk.Label(frame_interes, text="Interés %:", bg=BG_COLOR, font=("Segoe UI", 12)).pack(side="left")
        
        self.var_porcentaje = tk.StringVar(value="0")
        self.entry_interes = tk.Entry(frame_interes, textvariable=self.var_porcentaje, 
                                      font=("Segoe UI", 12, "bold"), width=5, justify="center", bd=1)
        self.entry_interes.pack(side="left", padx=10)
        self.entry_interes.bind("<KeyRelease>", self.recalcular_total)
        self.entry_interes.config(state="disabled")

        # --- Contenedor para los Paneles de Pago (Simple y Mixto) ---
        self.frame_contenedor_pagos = tk.Frame(self.top, bg=BG_COLOR)
        self.frame_contenedor_pagos.pack(fill="x", padx=30, pady=10)

        # --- Panel de Pago Simple (Efectivo, Tarjeta, etc.) ---
        self.frame_simple = tk.Frame(self.frame_contenedor_pagos, bg="white", bd=1, relief="solid")
        
        tk.Label(self.frame_simple, text="PAGA CON:", bg="white", fg="#555", font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=10, pady=(10,0))
        self.var_pago_simple = tk.DoubleVar(value=0.0)
        self.entry_pago_simple = tk.Entry(self.frame_simple, textvariable=self.var_pago_simple, font=self.FONT_INPUT, 
                                          justify="center", bd=0, bg="#f9f9f9")
        self.entry_pago_simple.pack(fill="x", padx=10, pady=5)
        self.entry_pago_simple.bind("<KeyRelease>", self.calcular_vuelto_simple)
        self.entry_pago_simple.bind("<Return>", lambda e: self.confirmar_pago())
        
        tk.Frame(self.frame_simple, bg="#ccc", height=1).pack(fill="x", padx=10)
        tk.Label(self.frame_simple, text="SU VUELTO:", bg="white", fg="#555", font=("Segoe UI", 10)).pack(padx=10, pady=(5,0))
        self.lbl_vuelto_simple = tk.Label(self.frame_simple, text="$0.00", bg="white", fg="#28a745", font=("Segoe UI", 20, "bold"))
        self.lbl_vuelto_simple.pack(padx=10, pady=(0,10))

        # --- Panel de Pago Mixto ---
        self.frame_mixto = tk.Frame(self.frame_contenedor_pagos, bg=BG_COLOR)
        
        # Primer método de pago mixto
        f1 = tk.Frame(self.frame_mixto, bg="white", bd=1, relief="solid")
        f1.pack(fill="x", pady=2)
        self.combo_m1 = ttk.Combobox(f1, values=["Efectivo", "Tarjeta", "Mercado Pago"], state="readonly", width=15, font=self.FONT_OPTION)
        self.combo_m1.current(0)
        self.combo_m1.pack(side="left", padx=5, pady=5)
        
        self.var_monto1 = tk.DoubleVar(value=0.0)
        self.entry_monto1 = tk.Entry(f1, textvariable=self.var_monto1, font=self.FONT_INPUT, width=10, justify="right", bd=0)
        self.entry_monto1.pack(side="right", padx=5, pady=5)
        self.entry_monto1.bind("<KeyRelease>", self.calcular_restante_mixto)

        # Segundo método de pago mixto
        f2 = tk.Frame(self.frame_mixto, bg="white", bd=1, relief="solid")
        f2.pack(fill="x", pady=2)
        self.combo_m2 = ttk.Combobox(f2, values=["Tarjeta", "Mercado Pago", "Efectivo"], state="readonly", width=15, font=self.FONT_OPTION)
        self.combo_m2.current(1)
        self.combo_m2.pack(side="left", padx=5, pady=5)
        
        self.var_monto2 = tk.DoubleVar(value=0.0)
        self.entry_monto2 = tk.Entry(f2, textvariable=self.var_monto2, font=self.FONT_INPUT, width=10, justify="right", bd=0)
        self.entry_monto2.pack(side="right", padx=5, pady=5)
        
        self.lbl_info_mixto = tk.Label(self.frame_mixto, text="Falta cubrir: $0.00", bg=BG_COLOR, fg="#dc3545", font=("Segoe UI", 10, "bold"))
        self.lbl_info_mixto.pack(pady=5)

        # --- Botón de Confirmación ---
        self.btn_confirmar = tk.Button(self.top, text="CONFIRMAR PAGO", 
                                  bg="#28a745", fg="white", font=("Segoe UI", 14, "bold"),
                                  activebackground="#218838", activeforeground="white", cursor="hand2",
                                  command=self.confirmar_pago)
        self.btn_confirmar.pack(side="bottom", fill="x", padx=30, pady=20, ipady=15)
        
        # Llama a este método al final para configurar la interfaz según la opción por defecto ("Efectivo").
        self.actualizar_interfaz()

    def actualizar_interfaz(self):
        """
        Actualiza la interfaz de cobro según el método de pago seleccionado.
        Muestra u oculta los campos para pago simple, mixto o con tarjeta, y ajusta sus estados.
        Este método se llama cada vez que el usuario selecciona un método de pago diferente.
        """
        seleccion = self.var_metodo.get()
        
        # Resalta el método de pago seleccionado.
        for texto, widget in self.radio_widgets.items():
            widget.config(fg="#0056b3" if texto == seleccion else "black", 
                          font=self.FONT_SELECTED if texto == seleccion else self.FONT_OPTION)

        # Habilita el campo de interés solo si se selecciona tarjeta.
        if "Tarjeta" in seleccion and seleccion != "Pago Mixto": 
            self.entry_interes.config(state="normal", bg="white")
            if self.var_porcentaje.get() == "0": self.var_porcentaje.set("10") # Sugiere un 10%
        else:
            self.var_porcentaje.set("0")
            self.entry_interes.config(state="disabled", bg="#e3e3e3")
            self.recalcular_total() # Quita cualquier recargo aplicado.

        # Muestra el panel de pago mixto y oculta el simple, o viceversa.
        if seleccion == "Pago Mixto":
            self.frame_simple.pack_forget()
            self.frame_mixto.pack(fill="x")
            self.entry_monto1.focus_set()
            self.calcular_restante_mixto()
        else:
            self.frame_mixto.pack_forget()
            self.frame_simple.pack(fill="x")
            
            # Configura el campo de pago simple según la selección.
            if seleccion == "Efectivo":
                # Para efectivo, el campo está habilitado para ingresar el monto del billete.
                self.entry_pago_simple.config(state="normal", bg="#f9f9f9")
                self.entry_pago_simple.delete(0, tk.END)
                self.entry_pago_simple.focus_set()
            else:
                # Para otros métodos (tarjeta, etc.), se autocompleta con el total a pagar.
                self.entry_pago_simple.config(state="normal")
                self.var_pago_simple.set(self.total_final)
                self.entry_pago_simple.config(state="disabled", bg="#e3e3e3")

    def recalcular_total(self, event=None):
        """
        Recalcula el monto total a pagar si se aplica un porcentaje de interés.
        """
        try:
            porcentaje = float(self.var_porcentaje.get() or "0")
            monto_recargo = self.total_original * (porcentaje / 100)
            self.total_final = self.total_original + monto_recargo
            
            self.lbl_total_gigante.config(text=f"${self.total_final:.2f}")
            self.lbl_info_recargo.config(text=f"+ {porcentaje}% recargo (${monto_recargo:.2f})" if porcentaje > 0 else "")
            
            if self.var_metodo.get() not in ["Efectivo", "Pago Mixto"]:
                 self.entry_pago_simple.config(state="normal")
                 self.var_pago_simple.set(self.total_final)
                 self.entry_pago_simple.config(state="disabled")
            elif self.var_metodo.get() == "Pago Mixto":
                self.calcular_restante_mixto()
        except ValueError: pass

    def calcular_vuelto_simple(self, event):
        """
        Calcula y muestra el vuelto en tiempo real para el modo de pago simple.
        """
        try:
            pago = float(self.entry_pago_simple.get())
            vuelto = pago - self.total_final
            if vuelto < 0:
                self.lbl_vuelto_simple.config(text="Falta dinero", fg="#dc3545")
            else:
                self.lbl_vuelto_simple.config(text=f"${vuelto:.2f}", fg="#28a745")
        except ValueError:
            self.lbl_vuelto_simple.config(text="$0.00")

    def calcular_restante_mixto(self, event=None):
        """
        Calcula automáticamente el segundo monto en el pago mixto basado en el primero.
        """
        try:
            m1 = float(self.entry_monto1.get() or "0")
            resto = self.total_final - m1
            self.var_monto2.set(f"{resto:.2f}")
            
            if resto < 0:
                self.lbl_info_mixto.config(text=f"Sobran: ${abs(resto):.2f} (Vuelto)", fg="green")
            elif resto > 0:
                self.lbl_info_mixto.config(text=f"Faltan cubrir: ${resto:.2f}", fg="#dc3545")
            else:
                self.lbl_info_mixto.config(text="¡Pago cubierto exacto!", fg="#28a745")
        except ValueError: pass

    def confirmar_pago(self):
        """
        Valida los montos ingresados y llama a la función de callback para guardar la venta.
        """
        metodo_guardar = metodo = self.var_metodo.get()
        pago_final, vuelto_final = 0.0, 0.0

        if metodo == "Pago Mixto":
            try:
                m1, m2 = self.var_monto1.get(), self.var_monto2.get()
                if (m1 + m2) < (self.total_final - 0.10):
                    messagebox.showwarning("Error", "Falta cubrir dinero.")
                    return
                metodo_guardar = f"Mixto: {self.combo_m1.get()}(${m1:.0f}) + {self.combo_m2.get()}(${m2:.0f})"
                pago_final = m1 + m2
                vuelto_final = pago_final - self.total_final
            except ValueError:
                messagebox.showerror("Error", "Verifique los montos ingresados")
                return
        else:
            pago_final = float(self.entry_pago_simple.get() or self.total_final)
            if metodo == "Efectivo" and pago_final < (self.total_final - 0.01): 
                messagebox.showwarning("Atención", "El pago es insuficiente.")
                return
            vuelto_final = pago_final - self.total_final
        
        self.top.destroy()
        self.callback(metodo_guardar, pago_final, max(0, vuelto_final), self.total_final)
