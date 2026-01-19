# -*- coding: utf-8 -*-

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import mysql.connector
from database import Database

class DialogoNuevaFamilia(tk.Toplevel):
    def __init__(self, master, db_config, rubros, callback):
        super().__init__(master)
        self.title("Nueva Familia")
        self.geometry("400x200")
        self.db_config = db_config
        self.rubros = rubros
        self.callback = callback

        self.var_rubro = tk.StringVar()
        self.var_familia = tk.StringVar()

        tk.Label(self, text="Seleccione un Rubro:").pack(pady=5)
        self.combo_rubro = ttk.Combobox(self, textvariable=self.var_rubro, values=[r[1] for r in self.rubros], state="readonly")
        self.combo_rubro.pack(pady=5)

        tk.Label(self, text="Nombre de la Nueva Familia:").pack(pady=5)
        self.entry_familia = tk.Entry(self, textvariable=self.var_familia, width=40)
        self.entry_familia.pack(pady=5)

        tk.Button(self, text="Guardar", command=self.guardar).pack(pady=10)

    def guardar(self):
        rubro_nombre = self.var_rubro.get()
        familia_nombre = self.var_familia.get()

        if not rubro_nombre or not familia_nombre:
            messagebox.showerror("Error", "Debe seleccionar un rubro e ingresar un nombre de familia.")
            return

        rubro_id = next((r[0] for r in self.rubros if r[1] == rubro_nombre), None)
        if rubro_id is None:
            messagebox.showerror("Error", "Rubro no válido.")
            return
        
        try:
            db = Database(self.db_config)
            db.connect()
            query = "INSERT INTO familia (rubro_id, nombre) VALUES (%s, %s)"
            db.cursor.execute(query, (rubro_id, familia_nombre))
            db.connection.commit()
            db.disconnect()
            messagebox.showinfo("Éxito", "Familia agregada correctamente.")
            if self.callback:
                self.callback()
            self.destroy()
        except mysql.connector.Error as err:
            messagebox.showerror("Error", f"No se pudo agregar la nueva familia: {err}")

class VentanaGestionAtributos(tk.Toplevel):
    def __init__(self, master, db_config, callback_refrescar=None):
        super().__init__(master)
        self.title("Gestionar Atributos")
        self.geometry("400x350")
        self.db_config = db_config
        self.callback_refrescar = callback_refrescar

        self.configure(bg="#e6e6e6")

        tk.Label(self, text="Seleccione qué desea agregar:", bg="#e6e6e6", font=("Segoe UI", 12, "bold")).pack(pady=10)

        btn_style = {"font": ("Segoe UI", 10), "pady": 5, "padx": 10, "cursor": "hand2", "width": 25}

        tk.Button(self, text="Nuevo Rubro", command=lambda: self._abrir_dialogo_nuevo_atributo("rubro"), **btn_style).pack(pady=5)
        tk.Button(self, text="Nueva Familia", command=self.abrir_dialogo_nueva_familia, **btn_style).pack(pady=5)
        tk.Button(self, text="Nueva Marca", command=lambda: self._abrir_dialogo_nuevo_atributo("marca"), **btn_style).pack(pady=5)
        tk.Button(self, text="Nuevo Valor de Atributo", command=lambda: self._abrir_dialogo_nuevo_atributo("valores_atributos", "valor"), **btn_style).pack(pady=5)

        tk.Label(self, text="Nota: Después de agregar un nuevo valor,\ncierre y vuelva a abrir la ventana 'Nuevo Producto'\npara que aparezca en las listas.", 
                 bg="#e6e6e6", fg="blue", font=("Segoe UI", 9)).pack(pady=20)

    def _abrir_dialogo_nuevo_atributo(self, tabla, columna_valor='nombre'):
        nuevo_valor = simpledialog.askstring("Nuevo Valor", f"Ingrese el nombre del nuevo {tabla.replace('_', ' ').title()}:")
        if nuevo_valor:
            try:
                db = Database(self.db_config)
                db.connect()
                query = f"INSERT INTO {tabla} ({columna_valor}) VALUES (%s)"
                db.cursor.execute(query, (nuevo_valor,))
                db.connection.commit()
                db.disconnect()
                messagebox.showinfo("Éxito", f"{tabla.replace('_', ' ').title()} agregado correctamente.")
                if self.callback_refrescar:
                    self.callback_refrescar()
            except mysql.connector.Error as err:
                messagebox.showerror("Error", f"No se pudo agregar el nuevo valor: {err}")

    def abrir_dialogo_nueva_familia(self):
        try:
            db = Database(self.db_config)
            db.connect()
            db.cursor.execute("SELECT id, nombre FROM rubro")
            rubros = [(row['id'], row['nombre']) for row in db.cursor.fetchall()]
            db.disconnect()
            DialogoNuevaFamilia(self, self.db_config, rubros, self.callback_refrescar)
        except Exception as e:
            messagebox.showerror("Error de BD", f"No se pudieron cargar los rubros: {e}")
