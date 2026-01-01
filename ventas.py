# -*- coding: utf-8 -*-

import sys
import traceback
import mysql.connector.plugins.caching_sha2_password
import pandas as pd
from tkinter import filedialog
import tkinter as tk
from tkinter import ttk, messagebox
import mysql.connector
from datetime import datetime, timedelta
import os
import configparser
import requests
import win32print
from PIL import Image, ImageTk
from openpyxl.utils import get_column_letter
import ctypes
from mysql.connector import errorcode

def resolver_ruta(ruta_relativa):
    """
    Obtiene la ruta absoluta a un recurso, para que funcione tanto en desarrollo (.py) como en producción (.exe).
    PyInstaller crea una carpeta temporal llamada _MEIPASS donde almacena los archivos.
    """
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, ruta_relativa)
    return os.path.join(os.path.abspath("."), ruta_relativa)

def inicializar_base_datos(config_ini):
    """
    Se conecta al servidor MySQL, crea la base de datos y las tablas necesarias si no existen.
    También actualiza la estructura de las tablas si se detectan versiones antiguas.
    """
    conexion = None
    cursor = None
    try:
        conexion = mysql.connector.connect(
            host=config_ini['host'],
            user=config_ini['user'],
            password=config_ini['password'],
            port=config_ini['port']
        )
        cursor = conexion.cursor()
        
        db_name = config_ini['database']
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {db_name}")
        conexion.database = db_name
        
        tablas = {}
        tablas['productos'] = """
            CREATE TABLE IF NOT EXISTS productos (
                id INT AUTO_INCREMENT PRIMARY KEY,
                codigo_barras VARCHAR(50) UNIQUE NOT NULL,
                nombre VARCHAR(100) NOT NULL,
                precio_venta DECIMAL(10,2) DEFAULT 0.00,
                stock_actual INT DEFAULT 0,
                tipo VARCHAR(10) DEFAULT 'Unidad'
            ) ENGINE=InnoDB;
        """
        tablas['ventas'] = """
            CREATE TABLE IF NOT EXISTS ventas (
                id INT AUTO_INCREMENT PRIMARY KEY,
                fecha DATETIME DEFAULT CURRENT_TIMESTAMP,
                total DECIMAL(10,2),
                metodo_pago VARCHAR(50) DEFAULT 'Efectivo'
            ) ENGINE=InnoDB;
        """
        tablas['detalle_ventas'] = """
            CREATE TABLE IF NOT EXISTS detalle_ventas (
                id INT AUTO_INCREMENT PRIMARY KEY,
                id_venta INT,
                id_producto INT,
                cantidad INT,
                precio_unitario DECIMAL(10,2),
                subtotal DECIMAL(10,2),
                FOREIGN KEY (id_venta) REFERENCES ventas(id),
                FOREIGN KEY (id_producto) REFERENCES productos(id)
            ) ENGINE=InnoDB;
        """

        for nombre_tabla, query in tablas.items():
            cursor.execute(query)

        # Actualizaciones de estructura de tablas para versiones antiguas
        try:
            cursor.execute("ALTER TABLE ventas MODIFY COLUMN metodo_pago VARCHAR(50) DEFAULT 'Efectivo'")
        except mysql.connector.Error:
            pass

        try:
            cursor.execute("SHOW COLUMNS FROM ventas LIKE 'pago_con'")
            if not cursor.fetchone():
                cursor.execute("ALTER TABLE ventas ADD COLUMN pago_con DECIMAL(10,2) DEFAULT 0.00")
        except mysql.connector.Error:
            pass

        try:
            cursor.execute("SHOW COLUMNS FROM ventas LIKE 'vuelto'")
            if not cursor.fetchone():
                cursor.execute("ALTER TABLE ventas ADD COLUMN vuelto DECIMAL(10,2) DEFAULT 0.00")
        except mysql.connector.Error:
            pass

        try:
            cursor.execute("SHOW COLUMNS FROM ventas LIKE 'fecha_venta'")
            if not cursor.fetchone():
                cursor.execute("ALTER TABLE ventas ADD COLUMN fecha_venta DATETIME DEFAULT CURRENT_TIMESTAMP")
        except mysql.connector.Error:
            pass
        
        print("🚀 Inicialización de base de datos completa.")
        return True

    except mysql.connector.Error as err:
        print(f"❌ Error de conexión crítico: {err}")
        return False
    finally:
        if cursor:
            cursor.close()
        if conexion and conexion.is_connected():
            conexion.close()

class VentanaDetalleInventario:
    """
    Crea una ventana que muestra un listado completo de todos los productos en el inventario,
    con la capacidad de buscar y filtrar en tiempo real.
    """
    def __init__(self, master, db_config):
        """
        Inicializa la ventana de detalle de inventario, que muestra todos los productos.
        - `master`: La ventana principal.
        - `db_config`: La configuración de la base de datos.
        """
        self.top = tk.Toplevel(master)
        self.top.title("Listado General de Inventario")
        self.top.geometry("1000x600")
        self.db_config = db_config

        # --- Frame Superior (Búsqueda y Actualización) ---
        frame_top = tk.Frame(self.top, bg="#f8f9fa", pady=10)
        frame_top.pack(fill="x")

        tk.Label(frame_top, text="Buscar por Nombre:", bg="#f8f9fa").pack(side="left", padx=10)
        
        # Campo de entrada para buscar productos en tiempo real.
        self.entry_buscar = tk.Entry(frame_top, width=40, font=("Arial", 11))
        self.entry_buscar.pack(side="left", padx=5)
        self.entry_buscar.bind('<KeyRelease>', self.filtrar_datos) # Llama a filtrar con cada tecla liberada.

        # Botón para recargar la lista de productos desde la base de datos.
        tk.Button(frame_top, text="🔄 Actualizar Lista", command=self.cargar_datos).pack(side="right", padx=20)

        # --- Tabla de Productos (Treeview) ---
        columns = ("ID", "Codigo", "Producto", "Precio", "Stock", "Valor Total")
        self.tree = ttk.Treeview(self.top, columns=columns, show='headings')
        
        # Definición de las cabeceras de la tabla.
        self.tree.heading("ID", text="ID")
        self.tree.heading("Codigo", text="Cód. Barras")
        self.tree.heading("Producto", text="Descripción")
        self.tree.heading("Precio", text="Precio Venta")
        self.tree.heading("Stock", text="Stock")
        self.tree.heading("Valor Total", text="Valor en Stock")

        # Configuración del ancho y alineación de cada columna.
        self.tree.column("ID", width=50, anchor="center")
        self.tree.column("Codigo", width=120, anchor="center")
        self.tree.column("Producto", width=400, anchor="w")
        self.tree.column("Precio", width=100, anchor="e")
        self.tree.column("Stock", width=80, anchor="center")
        self.tree.column("Valor Total", width=120, anchor="e")

        # Barra de desplazamiento para la tabla.
        scrollbar = ttk.Scrollbar(self.top, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)
        
        self.tree.pack(side="left", fill="both", expand=True, padx=10, pady=10)
        scrollbar.pack(side="right", fill="y", pady=10)

        # --- Estilos para las Filas de la Tabla ---
        # Etiqueta para productos con bajo stock (fondo rojo).
        self.tree.tag_configure('low_stock', background='#ffcccc', foreground='red')
        # Etiqueta para productos con stock normal.
        self.tree.tag_configure('normal_stock', background='white')

        # --- Barra de Estado Inferior ---
        frame_stats = tk.Frame(self.top, bg="#333", pady=10)
        frame_stats.pack(fill="x", side="bottom")

        # Etiqueta para mostrar estadísticas (total de productos, valor del inventario).
        self.lbl_info = tk.Label(frame_stats, text="Cargando...", fg="white", bg="#333", font=("Arial", 10, "bold"))
        self.lbl_info.pack()

        # Carga inicial de los datos en la tabla.
        self.cargar_datos()

    def cargar_datos(self):
        """
        Limpia la tabla y vuelve a cargar todos los productos desde la base de datos,
        calculando estadísticas y aplicando estilos según el nivel de stock.
        """
        for item in self.tree.get_children():
            self.tree.delete(item)

        try:
            conexion = mysql.connector.connect(**self.db_config)
            cursor = conexion.cursor(dictionary=True)
            
            cursor.execute("SELECT * FROM productos ORDER BY nombre ASC")
            productos = cursor.fetchall()

            total_inventario_dinero = 0
            total_items = 0

            for p in productos:
                valor_stock = p['precio_venta'] * p['stock_actual']
                total_inventario_dinero += valor_stock
                total_items += 1
                tag = 'low_stock' if p['stock_actual'] <= 5 else 'normal_stock'

                self.tree.insert("", "end", values=(
                    p['id'], p['codigo_barras'], p['nombre'],
                    f"${p['precio_venta']}", p['stock_actual'], f"${valor_stock:.2f}"
                ), tags=(tag,))

            self.lbl_info.config(text=f"Productos Registrados: {total_items}  |  Valor Total del Inventario: ${total_inventario_dinero:,.2f}")
            cursor.close()
            conexion.close()
        except mysql.connector.Error as err:
            messagebox.showerror("Error", str(err))

    def filtrar_datos(self, event):
        """
        Filtra los datos mostrados en la tabla según el texto ingresado en el campo de búsqueda.
        La búsqueda se realiza por nombre y código de barras.
        """
        busqueda = self.entry_buscar.get().lower()
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        try:
            conexion = mysql.connector.connect(**self.db_config)
            cursor = conexion.cursor(dictionary=True)
            cursor.execute("SELECT * FROM productos ORDER BY nombre ASC")
            productos = cursor.fetchall()
            
            for p in productos:
                if busqueda in p['nombre'].lower() or busqueda in p['codigo_barras']:
                    valor_stock = p['precio_venta'] * p['stock_actual']
                    tag = 'low_stock' if p['stock_actual'] <= 5 else 'normal_stock'
                    self.tree.insert("", "end", values=(
                        p['id'], p['codigo_barras'], p['nombre'],
                        f"${p['precio_venta']}", p['stock_actual'], f"${valor_stock:.2f}"
                    ), tags=(tag,))
            
            cursor.close()
            conexion.close()
        except Exception as e:
            pass

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

class VentanaInventario:
    """
    Ventana para la gestión de productos (crear y editar).
    Permite escanear un código de barras para buscar un producto o registrar uno nuevo.
    """
    def __init__(self, master, db_config, codigo_inicial=None):
        """
        Inicializa la ventana de gestión de inventario (crear y editar productos).
        - `master`: La ventana principal de la que depende esta.
        - `db_config`: La configuración para conectarse a la base de datos.
        - `codigo_inicial`: (Opcional) Un código de barras para precargar en el formulario.
        """
        self.master = master
        self.db_config = db_config
        self.top = tk.Toplevel(master) # Crea una ventana secundaria.
        self.top.title("Gestión de Producto")
        self.top.geometry("600x650")
        
        # --- Estilos y Variables ---
        self.COLOR_FONDO = "#e6e6e6"
        self.COLOR_VERDE = "#28a745"
        self.COLOR_AMARILLO = "#fff9c4"
        self.FONT_LABEL = ("Segoe UI", 12, "bold")
        self.FONT_ENTRY = ("Segoe UI", 14)
        
        self.top.configure(bg=self.COLOR_FONDO)
        
        self.placeholder_text = "Escribe aquí el nombre del nuevo producto..."
        # Variables de Tkinter para vincular a los campos de entrada.
        self.var_codigo = tk.StringVar()
        self.var_nombre = tk.StringVar(value=self.placeholder_text)
        self.var_precio = tk.DoubleVar(value=0.0)
        self.var_stock = tk.IntVar(value=0)
        self.var_tipo = tk.StringVar(value="Unidad")
        self.producto_existente = False # Flag para saber si se está editando o creando.
        
        # --- Frame para Escanear Código ---
        frame_scan = tk.Frame(self.top, bg=self.COLOR_FONDO, pady=20)
        frame_scan.pack(fill="x", padx=40)

        tk.Label(frame_scan, text="1. Escanea o escribe el Código:", bg=self.COLOR_FONDO, font=self.FONT_LABEL).pack(anchor="w")
        
        # Campo de entrada para el código de barras.
        self.entry_codigo = tk.Entry(frame_scan, textvariable=self.var_codigo, font=("Courier New", 18, "bold"), 
                                     bg=self.COLOR_AMARILLO, justify="center", relief="sunken", bd=2)
        self.entry_codigo.pack(fill="x", ipady=8, pady=5)
        self.entry_codigo.bind('<Return>', self.buscar_y_configurar) # Al presionar Enter, busca el producto.
        self.entry_codigo.focus_set() # Foco inicial en este campo.

        # --- Frame para los Datos del Producto ---
        self.frame_datos = tk.Frame(self.top, bg="#ffffff", relief="groove", bd=2)
        self.frame_datos.pack(fill="both", expand=True, padx=20, pady=10)
        self.frame_datos.columnconfigure(1, weight=1)
        
        # --- Campos del Formulario (Nombre, Precio, Stock) ---
        tk.Label(self.frame_datos, text="Nombre del Producto:", bg="#ffffff", font=self.FONT_LABEL).grid(row=0, column=0, sticky="w", padx=20, pady=(20,5))
        
        self.entry_nombre = tk.Entry(self.frame_datos, textvariable=self.var_nombre, font=self.FONT_ENTRY, fg="black", relief="solid", bd=1)
        self.entry_nombre.bind("<FocusIn>", self.on_entry_focus_in)
        self.entry_nombre.bind("<FocusOut>", self.on_entry_focus_out)
        self.entry_nombre.bind("<KeyPress>", self.on_entry_key_press)
        
        validate_price = self.top.register(self.solo_decimales) # Validador para permitir solo números y un punto.
        tk.Label(self.frame_datos, text="Precio Venta ($):", bg="#ffffff", font=self.FONT_LABEL).grid(row=2, column=0, sticky="w", padx=20, pady=(20,5))
        self.entry_precio = tk.Entry(self.frame_datos, textvariable=self.var_precio, font=self.FONT_ENTRY, justify="right", 
                                     relief="solid", bd=1, validate="key", validatecommand=(validate_price, '%P'))
        self.entry_precio.grid(row=3, column=0, sticky="ew", padx=20, ipady=5)

        validate_stock = self.top.register(self.solo_numeros) # Validador para permitir solo números enteros.
        tk.Label(self.frame_datos, text="Stock Actual (Unidades):", bg="#ffffff", font=self.FONT_LABEL).grid(row=2, column=1, sticky="w", padx=20, pady=(20,5))
        self.entry_stock = tk.Entry(self.frame_datos, textvariable=self.var_stock, font=self.FONT_ENTRY, justify="center", 
                                    relief="solid", bd=1, validate="key", validatecommand=(validate_stock, '%P'))
        self.entry_stock.grid(row=3, column=1, sticky="ew", padx=20, ipady=5)

        # --- Selección de Tipo de Producto (Unidad o Granel) ---
        frame_tipo = tk.Frame(self.frame_datos, bg="#ffffff")
        frame_tipo.grid(row=6, column=0, columnspan=2, sticky="w", padx=20, pady=(10,5))

        tk.Label(frame_tipo, text="Tipo:", bg="#ffffff", font=self.FONT_LABEL).pack(side="left")
        
        self.combo_tipo = ttk.Combobox(frame_tipo, textvariable=self.var_tipo, values=["Unidad", "Granel"], 
                                       state="readonly", width=15, font=self.FONT_ENTRY)
        self.combo_tipo.pack(side="left", padx=10)
        self.combo_tipo.set("Unidad")
        
        # --- Botones de Acción (Guardar) ---
        frame_btns = tk.Frame(self.top, bg=self.COLOR_FONDO, pady=20)
        frame_btns.pack(fill="x")
        self.btn_guardar = tk.Button(frame_btns, text="💾 GUARDAR DATOS (Enter)", font=("Arial", 14, "bold"), 
                                     bg=self.COLOR_VERDE, fg="white", relief="raised", bd=5, command=self.guardar_producto)
        self.btn_guardar.pack(side="right", padx=20, ipadx=20, ipady=5)
        self.lbl_mensaje = tk.Label(frame_btns, text="", font=("Arial", 12), bg=self.COLOR_FONDO)
        self.lbl_mensaje.pack(side="left", padx=20)
        
        # Atajos de teclado para navegar y guardar.
        self.entry_precio.bind('<Return>', lambda e: self.guardar_producto())
        self.entry_stock.bind('<Return>', lambda e: self.guardar_producto())
        self.entry_nombre.bind('<Return>', lambda e: self.entry_precio.focus_set())
        
        # Si se pasó un código inicial, lo carga y busca automáticamente.
        if codigo_inicial:
            self.var_codigo.set(codigo_inicial)
            self.top.after(100, lambda: self.buscar_y_configurar(None))
        
    def on_entry_focus_in(self, event):
        """Borra el texto placeholder del campo de nombre cuando el usuario hace clic."""
        if self.var_nombre.get() == self.placeholder_text or "Producto nuevo" in self.var_nombre.get():
            self.var_nombre.set("")
            self.entry_nombre.config(fg="black")

    def on_entry_focus_out(self, event):
        """Vuelve a poner el texto placeholder si el campo de nombre queda vacío."""
        if not self.var_nombre.get():
            self.var_nombre.set(self.placeholder_text)
            self.entry_nombre.config(fg="grey")
    
    def on_entry_key_press(self, event):
        """Borra el texto placeholder al empezar a escribir."""
        if self.var_nombre.get() == self.placeholder_text or "Producto nuevo" in self.var_nombre.get():
            self.var_nombre.set("")
            self.entry_nombre.config(fg="black")

    def animar_no_encontrado(self):
        """Anima el campo de nombre para indicar que el producto no fue encontrado en la API externa."""
        color_original = "white"
        self.entry_nombre.config(bg="#ffdddd") 
        self.var_nombre.set("Producto nuevo. Ingrese nombre...")
        self.entry_nombre.config(fg="#d9534f")
        self.top.after(600, lambda: (self.entry_nombre.config(bg=color_original, fg="grey")))
    
    def consultar_api(self, codigo):
        """
        Consulta las APIs de OpenFoodFacts y OpenBeautyFacts para obtener el nombre de un producto por su código.
        """
        fuentes = [
            ("Alimentos", f"https://world.openfoodfacts.org/api/v0/product/{codigo}.json"),
            ("Cosmética", f"https://world.openbeautyfacts.org/api/v0/product/{codigo}.json")
        ]
        headers = { 'User-Agent': 'SistemaVentasPython/1.0' }
        
        for nombre_fuente, url in fuentes:
            try:
                respuesta = requests.get(url, headers=headers, timeout=3)
                if respuesta.status_code == 200 and respuesta.json().get('status') == 1:
                    p = respuesta.json()['product']
                    nombre = p.get('product_name_es') or p.get('product_name') or p.get('product_name_en') or ""
                    marca = p.get('brands', "").split(",")[0]
                    cantidad = p.get('quantity', "")
                    nombre_final = " - ".join(filter(None, [nombre, marca, cantidad]))
                    if nombre_final:
                        return nombre_final
            except Exception as e:
                print(f"Error en API {nombre_fuente}: {e}")
        return None

    def buscar_y_configurar(self, event):
        """
        Busca un producto en la BD local por su código. Si existe, carga sus datos para edición.
        Si no existe, consulta la API externa y prepara el formulario para un nuevo registro.
        """
        codigo = self.var_codigo.get()
        if not codigo: return

        self.top.config(cursor="watch")
        self.top.update()

        try:
            conexion = mysql.connector.connect(**self.db_config)
            cursor = conexion.cursor(dictionary=True)
            cursor.execute("SELECT * FROM productos WHERE codigo_barras = %s", (codigo,))
            producto_local = cursor.fetchone()
            
            self.entry_nombre.grid_forget()

            if producto_local:
                self.producto_existente = True
                self.entry_nombre.grid(row=1, column=0, columnspan=2, sticky="ew", padx=20, pady=10, ipady=5)
                self.var_nombre.set(producto_local['nombre'])
                self.var_precio.set(producto_local['precio_venta'])
                self.var_stock.set(producto_local['stock_actual'])
                self.var_tipo.set(producto_local.get('tipo', 'Unidad'))
                self.entry_precio.focus_set()
                self.entry_precio.select_range(0, tk.END)
            else:
                self.producto_existente = False
                self.btn_guardar.config(text="💾 GUARDAR NUEVO", bg=self.COLOR_VERDE)
                self.entry_nombre.grid(row=1, column=0, columnspan=2, sticky="ew", padx=20, pady=10, ipady=5)
                nombre_api = self.consultar_api(codigo) 
                
                if nombre_api:
                    self.var_nombre.set(nombre_api)
                    self.entry_nombre.config(fg="black", bg="#d4edda")
                    self.top.after(500, lambda: self.entry_nombre.config(bg="white"))
                else:
                    self.animar_no_encontrado()

                self.var_precio.set(0.0)
                self.var_stock.set(0)
                self.var_tipo.set("Unidad")
                self.entry_nombre.focus_set()

            cursor.close()
            conexion.close()
        except mysql.connector.Error as err:
            messagebox.showerror("Error", str(err))
        finally:
            self.top.config(cursor="")

    def solo_numeros(self, char):
        """Validador para Tkinter que solo permite caracteres numéricos."""
        return char.isdigit() or char == ""

    def solo_decimales(self, char):
        """Validador para Tkinter que permite números y un solo punto decimal."""
        if char == "": return True
        try:
            float(char)
            return True
        except ValueError:
            return False        

    def guardar_producto(self):
        """
        Valida los datos del formulario y guarda (inserta o actualiza) el producto en la base de datos.
        """
        codigo = self.var_codigo.get()
        nombre = self.var_nombre.get()
        tipo = self.var_tipo.get()
        txt_precio = self.entry_precio.get()
        txt_stock = self.entry_stock.get()

        if not codigo or not nombre or nombre == self.placeholder_text or not txt_precio: 
            self.mostrar_mensaje("Faltan datos obligatorios", "red"); return

        try:
            precio_final = float(txt_precio)
            stock_final = int(txt_stock) if txt_stock else 0
        except ValueError:
            self.mostrar_mensaje("Precio o stock inválido", "red"); return

        try:
            conexion = mysql.connector.connect(**self.db_config)
            cursor = conexion.cursor()
            
            if self.producto_existente:
                sql = "UPDATE productos SET nombre=%s, precio_venta=%s, stock_actual=%s, tipo=%s WHERE codigo_barras=%s"
                cursor.execute(sql, (nombre, precio_final, stock_final, tipo, codigo))
                texto_exito = "✅ Producto Actualizado"
            else:
                sql = "INSERT INTO productos (codigo_barras, nombre, precio_venta, stock_actual, tipo) VALUES (%s, %s, %s, %s, %s)"
                cursor.execute(sql, (codigo, nombre, precio_final, stock_final, tipo))
                texto_exito = "✅ Producto Nuevo Registrado"
            
            conexion.commit()
            cursor.close()
            conexion.close()

            self.mostrar_mensaje(texto_exito, "#28a745")
            self.limpiar_formulario()
            self.entry_codigo.focus_set()
        except mysql.connector.Error as err:
            self.mostrar_mensaje(f"Error BD: {err}", "red")

    def mostrar_mensaje(self, texto, color):
        """Muestra un mensaje temporal en la parte inferior de la ventana."""
        self.lbl_mensaje.config(text=texto, fg=color)
        self.top.after(3000, lambda: self.lbl_mensaje.config(text=""))

    def limpiar_formulario(self):
        """Limpia todos los campos del formulario para prepararlo para el siguiente producto."""
        self.var_codigo.set("")
        self.var_nombre.set(self.placeholder_text)
        self.entry_nombre.config(fg="grey")
        self.var_precio.set(0)
        self.var_stock.set(0)
        self.entry_nombre.grid_forget()
        self.producto_existente = False
        self.btn_guardar.config(text="💾 GUARDAR (Enter)", bg=self.COLOR_VERDE)

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

class VentanaBusquedaProducto:
    """
    Ventana emergente para buscar productos por nombre y agregarlos al carrito.
    """
    def __init__(self, master, db_config, callback_agregar):
        self.top = tk.Toplevel(master)
        self.top.title("Buscar Producto por Nombre")
        self.top.geometry("800x500")
        self.top.grab_set()

        self.db_config = db_config
        self.callback_agregar = callback_agregar
        self.todos_los_productos = []

        # --- Widgets ---
        frame_top = tk.Frame(self.top, pady=10)
        frame_top.pack(fill="x", padx=10)

        tk.Label(frame_top, text="Buscar:", font=("Segoe UI", 12)).pack(side="left")
        self.entry_buscar = tk.Entry(frame_top, font=("Segoe UI", 12), width=50)
        self.entry_buscar.pack(side="left", fill="x", expand=True, padx=10)
        self.entry_buscar.bind('<KeyRelease>', self.filtrar_lista)
        self.entry_buscar.focus_set()

        # --- Treeview ---
        frame_tree = tk.Frame(self.top)
        frame_tree.pack(fill="both", expand=True, padx=10, pady=5)
        
        columns = ("ID", "Nombre", "Precio", "Stock")
        self.tree = ttk.Treeview(frame_tree, columns=columns, show='headings')
        self.tree.heading("ID", text="ID"); self.tree.column("ID", width=50)
        self.tree.heading("Nombre", text="Nombre del Producto"); self.tree.column("Nombre", width=400)
        self.tree.heading("Precio", text="Precio"); self.tree.column("Precio", width=100, anchor="e")
        self.tree.heading("Stock", text="Stock"); self.tree.column("Stock", width=80, anchor="center")

        self.tree.pack(side="left", fill="both", expand=True)
        self.tree.bind("<Double-1>", self.seleccionar_y_cerrar)
        self.tree.bind("<Return>", self.seleccionar_y_cerrar)

        scrollbar = ttk.Scrollbar(frame_tree, orient="vertical", command=self.tree.yview)
        scrollbar.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        # --- Botón ---
        btn_frame = tk.Frame(self.top, pady=10)
        btn_frame.pack(fill="x", padx=10)
        tk.Button(btn_frame, text="✔ Agregar Producto Seleccionado", bg="#28a745", fg="white", font=("Segoe UI", 12, "bold"), command=self.seleccionar_y_cerrar).pack(ipadx=10, ipady=5)

        self.cargar_productos()

    def cargar_productos(self):
        """Carga todos los productos de la BD en una lista local y en el Treeview."""
        try:
            conexion = mysql.connector.connect(**self.db_config)
            cursor = conexion.cursor(dictionary=True)
            cursor.execute("SELECT id, codigo_barras, nombre, precio_venta, stock_actual, tipo FROM productos ORDER BY nombre ASC")
            self.todos_los_productos = cursor.fetchall()
            cursor.close()
            conexion.close()
            self.filtrar_lista()
        except mysql.connector.Error as err:
            messagebox.showerror("Error de Carga", f"No se pudieron cargar los productos: {err}", parent=self.top)

    def filtrar_lista(self, event=None):
        """Filtra y muestra los productos en el Treeview sin consultar la BD de nuevo."""
        busqueda = self.entry_buscar.get().lower()
        
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        for p in self.todos_los_productos:
            # Se usan checks defensivos para evitar errores si los datos son None.
            nombre_val = p.get('nombre') or ""
            codigo_val = p.get('codigo_barras') or ""

            if busqueda in nombre_val.lower() or busqueda in str(codigo_val):
                self.tree.insert("", "end", values=(
                    p['id'], p['nombre'], f"${p['precio_venta']:.2f}", p['stock_actual']
                ))

    def seleccionar_y_cerrar(self, event=None):
        """Obtiene el producto seleccionado, lo pasa al callback y cierra la ventana."""
        seleccion = self.tree.selection()
        if not seleccion:
            messagebox.showwarning("Sin Selección", "Por favor, selecciona un producto de la lista.", parent=self.top)
            return

        try:
            # El ID del Treeview es un string, hay que convertirlo a entero para comparar.
            item_id = int(self.tree.item(seleccion[0])['values'][0])
            
            # Busca el diccionario completo del producto en la lista cargada en memoria.
            producto_seleccionado = next((p for p in self.todos_los_productos if p['id'] == item_id), None)
            
            if producto_seleccionado:
                self.callback_agregar(producto_seleccionado)
                self.top.destroy()
            else:
                messagebox.showerror("Error", "No se pudo encontrar el producto seleccionado en la lista interna (el ID no coincide).", parent=self.top)
        
        except (ValueError, IndexError):
            messagebox.showerror("Error", "No se pudo obtener el ID del producto seleccionado en la tabla.", parent=self.top)


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


class SistemaVentas:
    """
    Clase principal que gestiona la ventana de ventas, el carrito y la interacción con las demás ventanas.
    """
    def __init__(self, root):
        """
        Inicializa la aplicación principal, carga la configuración y construye la interfaz gráfica.
        Este es el constructor de la clase principal de la aplicación.
        - `root`: Es la ventana principal de Tkinter.
        """
        self.root = root
        self.root.title("PUNTO DE VENTA")
        self.root.state('zoomed') # Maximiza la ventana al iniciar.
        self.carrito = [] # Lista para almacenar los productos de la venta actual.
        self.total_acumulado = 0.0 # Variable para llevar la suma del total de la venta.
        
        # Configuración del ícono de la aplicación para la barra de tareas de Windows.
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('mi_empresa.sistema_ventas.v1.0')
            self.root.iconbitmap(resolver_ruta("logo.ico"))
        except Exception as e:
            print(f"No se pudo cargar el icono: {e}")
        
        # Carga la configuración desde 'config.ini' (base de datos, impresora).
        self.db_config = self.cargar_configuracion()
        if self.db_config is None:
            self.root.destroy() # Cierra la app si no se puede cargar la config.
            return
            
        # Asegura que la base de datos y las tablas existan antes de continuar.
        self.inicializar_base_datos_segura()
        inicializar_base_datos(self.db_config)
        
        # Llama al método que crea todos los elementos visuales de la ventana principal.
        self.construir_interfaz()

    def construir_interfaz(self):
        """
        Crea y organiza todos los widgets (elementos visuales) de la ventana principal.
        Define la apariencia de la aplicación, desde los botones hasta la tabla del carrito.
        """
        # --- Definición de Estilos ---
        COLOR_FONDO = "#e6e6e6"
        COLOR_VERDE = "#28a745"
        COLOR_AZUL = "#007bff"
        FONT_BOLD = ("Segoe UI", 14, "bold")
        FONT_BIG = ("Segoe UI", 18, "bold")
        FONT_HUGE = ("Segoe UI", 30, "bold")
        self.root.configure(bg=COLOR_FONDO)

        # --- Frame Superior (Cabecera) ---
        frame_top = tk.Frame(self.root, bg=COLOR_AZUL, pady=5, relief="raised", bd=5)
        frame_top.pack(fill="x", side="top")

        # Carga y muestra el logo de la tienda en la cabecera.
        try:
            img_pil = Image.open(resolver_ruta("logo.png")).resize((70, 70), Image.LANCZOS)
            self.logo_img = ImageTk.PhotoImage(img_pil)
            lbl_logo = tk.Label(frame_top, image=self.logo_img, bg=COLOR_AZUL)
            lbl_logo.pack(side="left", padx=(10, 5)) 
            lbl_logo.image = self.logo_img 
        except Exception as e:
            print(f"No se pudo cargar el logo: {e}")

        # Título principal de la aplicación.
        tk.Label(frame_top, text="SISTEMA DE VENTAS", bg=COLOR_AZUL, fg="white", font=("Arial", 24, "bold")).pack(side="left")
        
        # --- Frame de Acciones (Botones de Inventario y Exportación) ---
        frame_acciones = tk.Frame(self.root, bg=COLOR_FONDO, pady=10)
        frame_acciones.pack(fill="x", side="top")

        # Botones para abrir las ventanas de inventario y para exportar ventas.
        tk.Button(frame_acciones, text="📦 Inventario", font=FONT_BOLD, relief="raised", bd=4, bg="white", command=self.abrir_lista_inventario).pack(side="left", padx=5)
        tk.Button(frame_acciones, text="➕ Nuevo Producto", font=FONT_BOLD, relief="raised", bd=4, bg="white", command=self.abrir_inventario).pack(side="left", padx=5)
        tk.Button(frame_acciones, text="🔍 Buscar Producto", font=FONT_BOLD, relief="raised", bd=4, bg="#ffc107", command=self.abrir_busqueda_producto).pack(side="left", padx=5)
        tk.Button(frame_acciones, text="📊 Exportar Ventas Hoy", font=FONT_BOLD, bg="#217346", fg="white", relief="raised", bd=4, command=self.exportar_ventas_excel).pack(side="left", padx=5, ipady=5)

        # --- Frame de Escaneo de Productos ---
        frame_scan = tk.Frame(self.root, bg=COLOR_FONDO, pady=10)
        frame_scan.pack(fill="x", side="top", padx=20)

        tk.Label(frame_scan, text="Escanea el Código:", bg=COLOR_FONDO, font=FONT_BIG).pack(anchor="w")
        # Campo de entrada para el código de barras del producto.
        self.entry_codigo = tk.Entry(frame_scan, font=("Courier New", 20, "bold"), bg="#fff9c4", justify="center", bd=2, relief="sunken")
        self.entry_codigo.pack(fill="x", ipady=10)
        self.entry_codigo.bind('<Return>', self.buscar_producto) # Al presionar Enter, busca el producto.
        self.entry_codigo.focus_set() # Pone el foco en este campo al iniciar.

        # --- Frame Inferior (Botón de Cobro y Total) ---
        frame_bottom = tk.Frame(self.root, bg="#333", pady=20, relief="raised", bd=5)
        frame_bottom.pack(fill="x", side="bottom")
        
        # Botón principal para iniciar el proceso de cobro.
        tk.Button(frame_bottom, text="✅ COBRAR (F5)", bg=COLOR_VERDE, fg="white", font=("Arial", 18, "bold"), relief="raised", bd=5, command=self.guardar_venta).pack(side="left", padx=30, ipady=10, ipadx=20) 
        # Etiqueta para mostrar el total acumulado de la venta.
        self.lbl_total = tk.Label(frame_bottom, text="TOTAL: $0.00", fg=COLOR_VERDE, bg="#333", font=FONT_HUGE)
        self.lbl_total.pack(side="right", padx=30)
        
        # --- Estilo y Creación de la Tabla del Carrito (Treeview) ---
        style = ttk.Style()
        style.configure("Treeview", background="white", rowheight=40, fieldbackground="white", font=("Arial", 14))
        style.configure("Treeview.Heading", font=("Arial", 14, "bold"), background="#444", foreground="white")
        style.map("Treeview", background=[('selected', COLOR_AZUL)])

        # Frame que contendrá la tabla del carrito.
        frame_tabla = tk.Frame(self.root, bg=COLOR_FONDO)
        frame_tabla.pack(side="top", fill="both", expand=True, padx=20, pady=10) 

        # Creación de la tabla (Treeview) para mostrar los productos del carrito.
        self.tree = ttk.Treeview(frame_tabla, columns=("ID", "Producto", "Precio", "Cantidad", "Subtotal"), show='headings')
        self.tree.heading("ID", text="ID"); self.tree.column("ID", width=50, anchor="center")
        self.tree.heading("Producto", text="PRODUCTO"); self.tree.column("Producto", width=400)
        self.tree.heading("Precio", text="PRECIO"); self.tree.column("Precio", width=100, anchor="e")
        self.tree.heading("Cantidad", text="CANT"); self.tree.column("Cantidad", width=80, anchor="center")
        self.tree.heading("Subtotal", text="TOTAL"); self.tree.column("Subtotal", width=100, anchor="e")
        self.tree.pack(side="left", fill="both", expand=True)
        self.tree.bind("<Delete>", self.eliminar_producto) # Permite eliminar productos con la tecla Supr.

        # Barra de desplazamiento para la tabla.
        scrollbar = ttk.Scrollbar(frame_tabla, orient="vertical", command=self.tree.yview)
        scrollbar.pack(side="right", fill="y")
        self.tree.configure(yscroll=scrollbar.set)
        
        # Atajo de teclado: F5 para abrir la ventana de cobro.
        self.root.bind('<F5>', lambda event: self.guardar_venta())

    def inicializar_base_datos_segura(self):
        """Se conecta solo al servidor MySQL para verificar que la BD exista, y si no, la crea."""
        config_servidor = self.db_config.copy()
        nombre_bd = config_servidor.pop('database', 'punto_venta')
        try:
            conexion_temp = mysql.connector.connect(**config_servidor)
            cursor = conexion_temp.cursor()
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {nombre_bd}")
            conexion_temp.commit()
            cursor.close()
            conexion_temp.close()
        except mysql.connector.Error as err:
            messagebox.showerror("Error Crítico de Base de Datos", f"No se pudo conectar al servidor MySQL.\nVerifique que XAMPP u otro servidor esté activo.\nDetalle: {err}")
            self.root.destroy()
            sys.exit(1)

    def cargar_configuracion(self):
        """Lee el archivo config.ini y devuelve un diccionario con la configuración de la BD y la impresora."""
        config = configparser.ConfigParser()
        try:
            config.read('config.ini')
            db_conf = dict(config['mysql'])
            db_conf['port'] = int(db_conf['port'])
            self.nombre_impresora_config = config['impresion']['nombre_impresora']
            return db_conf
        except Exception as e:
            messagebox.showerror("Error Fatal", f"No se pudo leer el archivo 'config.ini' o está incompleto: {e}")
            return None

    def agregar_producto_granel(self, producto_bd, precio_venta):
        """Agrega un producto vendido a granel (por precio) al carrito de compras."""
        nuevo_item = {
            'id': producto_bd['id'], 'codigo': producto_bd['codigo_barras'], 'nombre': producto_bd['nombre'],
            'precio': float(precio_venta), 'cantidad': 1, 'subtotal': float(precio_venta),
            'tipo': producto_bd.get('tipo', 'Unidad'),
        }
        self.carrito.append(nuevo_item)
        self.actualizar_carrito_visual()
        self.entry_codigo.delete(0, tk.END)

    def buscar_producto(self, event=None):
        """
        Busca un producto por código de barras. Si existe, lo procesa.
        Si no existe, abre un diálogo con opciones para el usuario.
        """
        codigo = self.entry_codigo.get().strip()
        if not codigo: return

        try:
            conexion = mysql.connector.connect(**self.db_config)
            cursor = conexion.cursor(dictionary=True)
            cursor.execute("SELECT * FROM productos WHERE codigo_barras = %s", (codigo,))
            producto_bd = cursor.fetchone()
            conexion.close()
        except mysql.connector.Error as err:
            messagebox.showerror("Error de Base de Datos", f"No se pudo consultar: {err}")
            return

        self.entry_codigo.delete(0, tk.END)

        if not producto_bd:
            # En lugar de un simple aviso, abrimos el nuevo diálogo de opciones.
            dialog = VentanaProductoNoEncontrado(self.root, codigo)
            self.root.wait_window(dialog.top) # Espera a que el usuario elija una opción.

            if dialog.result == 'add':
                self.abrir_inventario(codigo)
            elif dialog.result == 'search':
                self.abrir_busqueda_producto()
            # Si es 'cancel', no se hace nada.

        elif (producto_bd.get('tipo') or 'Unidad').lower().startswith('granel'):
            VentanaVentaGranel(self.root, producto_bd, self.agregar_producto_granel)
        elif producto_bd['stock_actual'] <= 0:
            messagebox.showwarning("Stock Agotado", "No queda stock para este producto.")
        else:
            encontrado = next((item for item in self.carrito if item['id'] == producto_bd['id']), None)
            if encontrado:
                encontrado['cantidad'] += 1
                encontrado['subtotal'] = encontrado['cantidad'] * encontrado['precio']
            else:
                nuevo_item = {
                    'id': producto_bd['id'], 'codigo': producto_bd['codigo_barras'], 'nombre': producto_bd['nombre'],
                    'precio': float(producto_bd['precio_venta']), 'cantidad': 1, 'subtotal': float(producto_bd['precio_venta']),
                    'tipo': producto_bd.get('tipo', 'Unidad')
                }
                self.carrito.append(nuevo_item)
            self.actualizar_carrito_visual()

    def actualizar_carrito_visual(self):
        """Limpia y redibuja la tabla del carrito con los datos actuales y actualiza el total."""
        for i in self.tree.get_children():
            self.tree.delete(i)
        self.total_acumulado = 0.0
        for item in self.carrito:
            self.tree.insert("", "end", values=(
                item['codigo'], item['nombre'], f"${item['precio']:.2f}",
                item['cantidad'], f"${item['subtotal']:.2f}"
            ))
            self.total_acumulado += item['subtotal']
        self.lbl_total.config(text=f"TOTAL: ${self.total_acumulado:.2f}")

    def guardar_venta(self):
        """Inicia el proceso de cobro abriendo la VentanaCobro si el carrito no está vacío."""
        if not self.carrito:
            messagebox.showinfo("Vacío", "No hay productos para cobrar.")
            return
        VentanaCobro(self.root, self.total_acumulado, self.guardar_venta_bd)

    def guardar_venta_bd(self, metodo_pago, pago_cliente, vuelto, total_cobrado=None):
        """
        Guarda la venta en la base de datos (tablas ventas y detalle_ventas) y actualiza el stock.
        Luego, pregunta si se desea imprimir el ticket y limpia la interfaz.
        """
        if total_cobrado is None: total_cobrado = self.total_acumulado
        try:
            conexion = mysql.connector.connect(**self.db_config)
            cursor = conexion.cursor()

            sql_venta = "INSERT INTO ventas (total, pago_con, vuelto, metodo_pago, fecha_venta) VALUES (%s, %s, %s, %s, NOW())"
            cursor.execute(sql_venta, (total_cobrado, pago_cliente, vuelto, metodo_pago))
            id_venta_generado = cursor.lastrowid

            sql_detalle = "INSERT INTO detalle_ventas (id_venta, id_producto, cantidad, precio_unitario, subtotal) VALUES (%s, %s, %s, %s, %s)"
            sql_stock = "UPDATE productos SET stock_actual = stock_actual - %s WHERE id = %s"

            for item in self.carrito:
                cursor.execute(sql_detalle, (id_venta_generado, item['id'], item['cantidad'], item['precio'], item['subtotal']))
                if item.get('tipo', 'Unidad').lower().startswith('unidad'):
                    cursor.execute(sql_stock, (item['cantidad'], item['id']))

            conexion.commit()
            cursor.close()
            conexion.close()

            if messagebox.askquestion("Imprimir", "¿Desea imprimir el ticket?") == 'yes':
                self.generar_ticket(id_venta_generado, pago_cliente, vuelto)
            
            self.limpiar_pantalla()
        except Exception as e:
            messagebox.showerror("Error Crítico", f"No se pudo guardar la venta: {e}")

    def eliminar_producto(self, event):
        """Elimina el producto seleccionado del carrito de compras."""
        seleccion = self.tree.selection()
        if not seleccion: return
        
        index = self.tree.index(seleccion[0])
        del self.carrito[index]
        self.actualizar_carrito_visual()
        self.entry_codigo.focus_set()

    def generar_ticket(self, id_venta, pago, vuelto):
        """
        Genera el contenido del ticket en formato ESC/POS y lo envía a la impresora configurada.
        """
        CMD_INIT = b'\x1b@'; CMD_CENTER = b'\x1b\x61\x01'; CMD_LEFT = b'\x1b\x61\x00'; CMD_CUT = b'\x1d\x56\x00'
        ticket_bytes = b""
        
        try:
            bytes_logo = self.obtener_bytes_imagen("logo_ticket.png")
            if bytes_logo: ticket_bytes += bytes_logo + b"\n"
        except Exception as e:
            print(f"No se pudo agregar el logo al ticket: {e}")

        ticket_bytes += CMD_INIT + CMD_CENTER + b"B Sefair Mna F Casa 1\n" + CMD_LEFT
        ticket_bytes += CMD_INIT + CMD_CENTER + b"Calle Juan Jufre pasando Alem\n" + CMD_LEFT
        ticket_bytes += CMD_INIT + CMD_CENTER + b"Villa del Salvador Angaco\n" + CMD_LEFT
        ticket_bytes += b"--------------------------------\n"
        ticket_bytes += f"Fecha: {datetime.now().strftime('%d/%m/%Y %H:%M')}\n".encode('latin-1')
        ticket_bytes += f"Ticket Nro: {id_venta}\n".encode('latin-1')
        ticket_bytes += b"--------------------------------\n"

        for item in self.carrito:
            nombre = item['nombre'][:32].upper()
            linea_precio = f"{item['cantidad']} x ${item['precio']:.2f}    ${item['subtotal']:.2f}"
            ticket_bytes += f"{nombre}\n".encode('latin-1')
            ticket_bytes += f"{linea_precio}\n".encode('latin-1')

        ticket_bytes += b"--------------------------------\n"
        ticket_bytes += CMD_CENTER + f"TOTAL: ${self.total_acumulado:.2f}\n".encode('latin-1') + CMD_LEFT
        ticket_bytes += f"PAGO:   ${pago:.2f}\n".encode('latin-1')
        ticket_bytes += f"VUELTO: ${vuelto:.2f}\n".encode('latin-1')
        ticket_bytes += b"\n" + CMD_CENTER + b"GRACIAS POR SU COMPRA\n\n\n" + CMD_CUT

        try:
            hPrinter = win32print.OpenPrinter(self.nombre_impresora_config)
            hJob = win32print.StartDocPrinter(hPrinter, 1, ("Ticket", None, "RAW"))
            win32print.WritePrinter(hPrinter, ticket_bytes)
            win32print.EndDocPrinter(hJob)
            win32print.ClosePrinter(hPrinter)
        except Exception as e:
            messagebox.showerror("Error de Impresión", f"No se pudo imprimir el ticket:\n{e}")

    def obtener_bytes_imagen(self, ruta_imagen):
        """Convierte un archivo de imagen a bytes en formato ESC/POS para impresoras térmicas."""
        try:
            img = Image.open(resolver_ruta(ruta_imagen)).resize((370, int(370 * Image.open(resolver_ruta(ruta_imagen)).size[1] / Image.open(resolver_ruta(ruta_imagen)).size[0])), Image.LANCZOS).convert("1")
            ancho_bytes = (img.width + 7) // 8
            datos_imagen = b""
            datos_pixels = list(img.getdata())
            
            for y in range(img.height):
                fila_bytes = bytearray(ancho_bytes)
                for x in range(img.width):
                    if datos_pixels[y * img.width + x] == 0:
                        fila_bytes[x // 8] |= (1 << (7 - (x % 8)))
                datos_imagen += fila_bytes

            comando = b'\x1d\x76\x30\x00' + (ancho_bytes % 256).to_bytes(1, 'little') + (ancho_bytes // 256).to_bytes(1, 'little') + (img.height % 256).to_bytes(1, 'little') + (img.height // 256).to_bytes(1, 'little') + datos_imagen
            return comando
        except Exception as e:
            print(f"No se pudo procesar la imagen del ticket: {e}")
            return b""

    def limpiar_pantalla(self):
        """Limpia el carrito de compras, la tabla visual y el total, preparando para una nueva venta."""
        self.carrito = []
        self.total_acumulado = 0.0
        self.lbl_total.config(text="TOTAL: $0.00")
        for item in self.tree.get_children():
            self.tree.delete(item)

    def exportar_ventas_excel(self):
        """Exporta los detalles de las ventas del día comercial actual a un archivo Excel."""
        try:
            ahora = datetime.now()
            HORA_CORTE = 6 
            fecha_inicio = (ahora - timedelta(days=1)).replace(hour=HORA_CORTE, minute=0, second=0) if ahora.hour < HORA_CORTE else ahora.replace(hour=HORA_CORTE, minute=0, second=0)
            
            conexion = mysql.connector.connect(**self.db_config)
            query = "SELECT v.id AS 'Nro Ticket', v.fecha_venta AS 'Fecha Hora', p.codigo_barras AS 'Código', p.nombre AS 'Producto', dv.cantidad AS 'Cantidad', dv.precio_unitario AS 'Precio Unit.', dv.subtotal AS 'Subtotal', v.metodo_pago AS 'Método Pago', v.pago_con AS 'Pago Con', v.vuelto AS 'Vuelto' FROM ventas v JOIN detalle_ventas dv ON v.id = dv.id_venta JOIN productos p ON dv.id_producto = p.id WHERE v.fecha_venta BETWEEN %s AND %s ORDER BY v.id DESC"
            df = pd.read_sql(query, conexion, params=(fecha_inicio, ahora))
            conexion.close()

            if df.empty:
                messagebox.showinfo("Sin Datos", "No hay ventas para exportar en el período actual.")
                return

            fecha_str = ahora.strftime("%Y-%m-%d")
            ruta_guardado = filedialog.asksaveasfilename(defaultextension=".xlsx", initialfile=f"Cierre_Caja_{fecha_str}.xlsx", filetypes=[("Excel files", "*.xlsx")])
            if not ruta_guardado: return
            
            with pd.ExcelWriter(ruta_guardado, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='VentasDetallado')
                
                resumen = df.groupby('Método Pago')['Subtotal'].sum().reset_index()
                resumen.to_excel(writer, index=False, sheet_name='ResumenMetodoPago')

                total_ventas = pd.DataFrame([{'Total General Vendido': df['Subtotal'].sum()}])
                total_ventas.to_excel(writer, index=False, sheet_name='TotalGeneral')

            messagebox.showinfo("Éxito", f"Archivo Excel exportado con éxito en:\n{ruta_guardado}")

        except Exception as e:
            messagebox.showerror("Error de Exportación", f"No se pudo generar el archivo Excel: {e}")

    def abrir_busqueda_producto(self):
        """Abre la ventana de búsqueda de productos para agregar al carrito."""
        VentanaBusquedaProducto(self.root, self.db_config, self.agregar_producto_al_carrito_desde_busqueda)

    def agregar_producto_al_carrito_desde_busqueda(self, producto_bd):
        """
        Callback que se ejecuta desde la ventana de búsqueda. Agrega el producto seleccionado
        al carrito de la venta principal.
        """
        if not producto_bd:
            return

        # Si el producto es a granel, abre la ventana para ingresar el precio.
        if (producto_bd.get('tipo') or 'Unidad').lower().startswith('granel'):
            VentanaVentaGranel(self.root, producto_bd, self.agregar_producto_granel)
        # Si no hay stock, muestra una advertencia.
        elif producto_bd['stock_actual'] <= 0:
            messagebox.showwarning("Stock Agotado", f"No queda stock para el producto:\n{producto_bd['nombre']}")
        # Si todo está bien, agrega el producto al carrito.
        else:
            # Busca si el producto ya está en el carrito para aumentar la cantidad.
            encontrado = next((item for item in self.carrito if item['id'] == producto_bd['id']), None)
            if encontrado:
                encontrado['cantidad'] += 1
                encontrado['subtotal'] = encontrado['cantidad'] * encontrado['precio']
            else:
                # Si no está, lo agrega como un nuevo item.
                nuevo_item = {
                    'id': producto_bd['id'],
                    'codigo': producto_bd['codigo_barras'],
                    'nombre': producto_bd['nombre'],
                    'precio': float(producto_bd['precio_venta']),
                    'cantidad': 1,
                    'subtotal': float(producto_bd['precio_venta']),
                    'tipo': producto_bd.get('tipo', 'Unidad')
                }
                self.carrito.append(nuevo_item)
            
            # Actualiza la tabla visual del carrito y el total.
            self.actualizar_carrito_visual()
        
        # Devuelve el foco al campo de escaneo principal.
        self.entry_codigo.focus_set()

    def abrir_inventario(self,codigo):
        """Abre la ventana de gestión de productos."""
        VentanaInventario(self.root, self.db_config,codigo)

    def abrir_lista_inventario(self):
        """Abre la ventana que muestra el listado completo del inventario."""
        VentanaDetalleInventario(self.root, self.db_config)

if __name__ == "__main__":
    try:
        root = tk.Tk()
        app = SistemaVentas(root)
        root.mainloop()
    except Exception as e:
        with open("error_fatal.txt", "w") as f:
            f.write("Error no controlado en el main loop:\n")
            f.write(traceback.format_exc())
        messagebox.showerror("Error Fatal", f"Ocurrió un error irrecuperable. Revisa 'error_fatal.txt'.\n{e}")
        sys.exit(1)