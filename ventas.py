import pandas as pd
from tkinter import filedialog
import tkinter as tk
from tkinter import ttk, messagebox
import mysql.connector
from datetime import datetime,timedelta
import os
import configparser
import requests
import win32print
from PIL import Image, ImageTk
from openpyxl.utils import get_column_letter

import mysql.connector
from mysql.connector import errorcode

import sys
import os

def ruta_recursos(ruta_relativa):
    """ Obtiene la ruta absoluta al recurso, funcione como script o como exe """
    try:
        # PyInstaller crea una carpeta temporal en _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        # Si estamos en modo normal (desarrollo)
        base_path = os.path.abspath(".")

    return os.path.join(base_path, ruta_relativa)

def inicializar_base_datos(config_ini):
    # 1. Conectarse a MySQL "en general" (sin especificar base de datos)
    #    para poder crearla si no existe.
    try:
        conexion = mysql.connector.connect(
            host=config_ini['host'],
            user=config_ini['user'],
            password=config_ini['password'],
            port=config_ini['port']
        )
        cursor = conexion.cursor()
        
        # 2. Crear la Base de Datos si no existe
        db_name = config_ini['database']
        try:
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {db_name}")
            print(f"✅ Base de datos '{db_name}' verificada/creada.")
        except mysql.connector.Error as err:
            print(f"❌ Error creando BD: {err}")
            return

        # 3. Conectarse ahora sí a la base de datos específica
        conexion.database = db_name
        
        # 4. Definir las tablas (Copia aquí tus CREATE TABLE de DBeaver)
        #    Es MUY IMPORTANTE usar "IF NOT EXISTS"
        tablas = {}
        
        tablas['productos'] = """
            CREATE TABLE IF NOT EXISTS productos (
                id INT AUTO_INCREMENT PRIMARY KEY,
                codigo_barras VARCHAR(50) UNIQUE NOT NULL,
                nombre VARCHAR(100) NOT NULL,
                precio_venta DECIMAL(10,2) DEFAULT 0.00,
                stock_actual INT DEFAULT 0
            ) ENGINE=InnoDB;
        """
        
        tablas['ventas'] = """
            CREATE TABLE IF NOT EXISTS ventas (
                id INT AUTO_INCREMENT PRIMARY KEY,
                fecha DATETIME DEFAULT CURRENT_TIMESTAMP,
                total DECIMAL(10,2),
                metodo_pago VARCHAR(20) DEFAULT 'Efectivo'
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

        # 5. Ejecutar la creación de tablas
        for nombre_tabla, query in tablas.items():
            try:
                cursor.execute(query)
                print(f"✅ Tabla '{nombre_tabla}' verificada.")
            except mysql.connector.Error as err:
                print(f"❌ Error creando tabla {nombre_tabla}: {err.msg}")

        # 6. (Opcional) Cargar datos iniciales básicos si está vacío
        #    Ejemplo: Un producto de prueba o un usuario Admin
        cursor.execute("SELECT COUNT(*) FROM productos")
        if cursor.fetchone()[0] == 0:
            print("📦 Base de datos nueva detectada. Insertando producto de ejemplo...")
            cursor.execute("INSERT INTO productos (codigo_barras, nombre, precio_venta, stock_actual) VALUES ('12345', 'Producto Prueba', 100.00, 10)")
            conexion.commit()

        cursor.close()
        conexion.close()
        print("🚀 Inicialización completa.")

    except mysql.connector.Error as err:
        print(f"Error de conexión crítico: {err}")

class VentanaDetalleInventario:
    def __init__(self, master, db_config):
        self.top = tk.Toplevel(master)
        self.top.title("Listado General de Inventario")
        self.top.geometry("1000x600")
        self.db_config = db_config

        # --- PANEL SUPERIOR (Buscador) ---
        frame_top = tk.Frame(self.top, bg="#f8f9fa", pady=10)
        frame_top.pack(fill="x")

        tk.Label(frame_top, text="Buscar por Nombre:", bg="#f8f9fa").pack(side="left", padx=10)
        
        self.entry_buscar = tk.Entry(frame_top, width=40, font=("Arial", 11))
        self.entry_buscar.pack(side="left", padx=5)
        # Buscar mientras escribe (Evento KeyRelease)
        self.entry_buscar.bind('<KeyRelease>', self.filtrar_datos) 

        tk.Button(frame_top, text="🔄 Actualizar Lista", command=self.cargar_datos).pack(side="right", padx=20)

        # --- TABLA DE DATOS ---
        # Definimos las columnas
        columns = ("ID", "Codigo", "Producto", "Precio", "Stock", "Valor Total")
        self.tree = ttk.Treeview(self.top, columns=columns, show='headings')
        
        # Configurar encabezados
        self.tree.heading("ID", text="ID")
        self.tree.heading("Codigo", text="Cód. Barras")
        self.tree.heading("Producto", text="Descripción")
        self.tree.heading("Precio", text="Precio Venta")
        self.tree.heading("Stock", text="Stock")
        self.tree.heading("Valor Total", text="Valor en Stock") # Stock * Precio

        # Configurar anchos
        self.tree.column("ID", width=50, anchor="center")
        self.tree.column("Codigo", width=120, anchor="center")
        self.tree.column("Producto", width=400, anchor="w")
        self.tree.column("Precio", width=100, anchor="e")
        self.tree.column("Stock", width=80, anchor="center")
        self.tree.column("Valor Total", width=120, anchor="e")

        # Scrollbar vertical
        scrollbar = ttk.Scrollbar(self.top, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)
        
        self.tree.pack(side="left", fill="both", expand=True, padx=10, pady=10)
        scrollbar.pack(side="right", fill="y", pady=10)

        # --- ESTILOS (El Semáforo) ---
        # Configuramos una etiqueta llamada 'low_stock' para pintar de rojo
        self.tree.tag_configure('low_stock', background='#ffcccc', foreground='red') # Fondo rojo suave
        self.tree.tag_configure('normal_stock', background='white')

        # --- PANEL INFERIOR (Estadísticas) ---
        frame_stats = tk.Frame(self.top, bg="#333", pady=10)
        frame_stats.pack(fill="x", side="bottom")

        self.lbl_info = tk.Label(frame_stats, text="Cargando...", fg="white", bg="#333", font=("Arial", 10, "bold"))
        self.lbl_info.pack()

        # Cargar datos al iniciar
        self.cargar_datos()

    def cargar_datos(self):
        # Limpiar tabla actual
        for item in self.tree.get_children():
            self.tree.delete(item)

        try:
            conexion = mysql.connector.connect(**self.db_config)
            cursor = conexion.cursor(dictionary=True)
            
            # Traemos todo ordenado por nombre
            cursor.execute("SELECT * FROM productos ORDER BY nombre ASC")
            productos = cursor.fetchall()

            total_inventario_dinero = 0
            total_items = 0

            for p in productos:
                valor_stock = p['precio_venta'] * p['stock_actual']
                total_inventario_dinero += valor_stock
                total_items += 1

                # Determinar si el stock es bajo (menor a 5 unidades)
                tag = 'normal_stock'
                if p['stock_actual'] <= 5:
                    tag = 'low_stock'

                self.tree.insert("", "end", values=(
                    p['id'],
                    p['codigo_barras'],
                    p['nombre'],
                    f"${p['precio_venta']}",
                    p['stock_actual'],
                    f"${valor_stock:.2f}"
                ), tags=(tag,)) # Aplicamos el color aquí

            # Actualizar barra inferior
            self.lbl_info.config(text=f"Productos Registrados: {total_items}  |  Valor Total del Inventario: ${total_inventario_dinero:,.2f}")

            cursor.close()
            conexion.close()

        except mysql.connector.Error as err:
            messagebox.showerror("Error", str(err))

    def filtrar_datos(self, event):
        # Buscador simple en memoria (filtra lo que ya está en la tabla para no saturar la BD)
        busqueda = self.entry_buscar.get().lower()
        
        # Primero borramos todo lo visual
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        # Volvemos a cargar desde la BD y filtramos
        # (Nota: Para bases de datos gigantes, esto se hace con "WHERE nombre LIKE %s" en SQL, 
        # pero para empezar, filtrar en Python es más fácil)
        try:
            conexion = mysql.connector.connect(**self.db_config)
            cursor = conexion.cursor(dictionary=True)
            cursor.execute("SELECT * FROM productos ORDER BY nombre ASC")
            productos = cursor.fetchall()
            
            for p in productos:
                # Si lo que escribí está en el nombre O en el código
                if busqueda in p['nombre'].lower() or busqueda in p['codigo_barras']:
                    
                    valor_stock = p['precio_venta'] * p['stock_actual']
                    tag = 'low_stock' if p['stock_actual'] <= 5 else 'normal_stock'

                    self.tree.insert("", "end", values=(
                        p['id'],
                        p['codigo_barras'],
                        p['nombre'],
                        f"${p['precio_venta']}",
                        p['stock_actual'],
                        f"${valor_stock:.2f}"
                    ), tags=(tag,))
            
            cursor.close()
            conexion.close()
        except Exception as e:
            pass


class VentanaCobro:
    def __init__(self, master, total_a_pagar, callback_finalizar):
        self.top = tk.Toplevel(master)
        self.top.title("Procesar Pago")
        self.top.geometry("400x350")
        
        # Variables
        self.total = total_a_pagar
        self.callback = callback_finalizar # Esta es la función que guardará en la BD
        self.var_pago = tk.DoubleVar(value=0.0)
        self.var_vuelto = tk.StringVar(value="$0.00")

        # Hacer la ventana MODAL (Bloquea la ventana de atrás hasta que cierres esta)
        self.top.grab_set()
        
        # --- UI ---
        tk.Label(self.top, text="TOTAL A PAGAR", font=("Arial", 12)).pack(pady=10)
        tk.Label(self.top, text=f"${self.total:.2f}", font=("Arial", 30, "bold"), fg="#d9534f").pack()

        tk.Label(self.top, text="Paga con ($):", font=("Arial", 12)).pack(pady=(20, 5))
        
        self.entry_pago = tk.Entry(self.top, textvariable=self.var_pago, font=("Arial", 20), justify='center')
        self.entry_pago.pack(pady=5)
        self.entry_pago.bind('<KeyRelease>', self.calcular_vuelto) # Calcula cada vez que escribes
        self.entry_pago.bind('<Return>', self.confirmar_pago)      # Enter para confirmar
        self.entry_pago.focus_set()
        self.entry_pago.select_range(0, tk.END)

        tk.Label(self.top, text="Su Vuelto:", font=("Arial", 12)).pack(pady=(20, 5))
        self.lbl_vuelto = tk.Label(self.top, textvariable=self.var_vuelto, font=("Arial", 25, "bold"), fg="green")
        self.lbl_vuelto.pack()

        self.btn_confirmar = tk.Button(self.top, text="CONFIRMAR VENTA (Enter)", 
                                       bg="#28a745", fg="white", font=("Arial", 12, "bold"),
                                       state="disabled", # Desactivado hasta que el pago alcance
                                       command=self.confirmar_pago)
        self.btn_confirmar.pack(fill="x", side="bottom", padx=20, pady=20)

    def calcular_vuelto(self, event=None):
        try:
            pago = self.var_pago.get()
            
            # Lógica del vuelto
            vuelto = pago - self.total
            
            # Actualizar etiqueta
            self.var_vuelto.set(f"${vuelto:.2f}")

            # Validar si alcanza el dinero
            if vuelto >= 0:
                self.lbl_vuelto.config(fg="green")
                self.btn_confirmar.config(state="normal", bg="#28a745") # Habilitar botón
            else:
                self.lbl_vuelto.config(fg="red") # Poner rojo si falta plata
                self.btn_confirmar.config(state="disabled", bg="#cccccc") # Deshabilitar botón
                
        except tk.TclError:
            # Si el usuario escribe letras o deja vacío
            self.var_vuelto.set("---")
            self.btn_confirmar.config(state="disabled")

    def confirmar_pago(self, event=None):
        # Solo procedemos si el botón está habilitado (el pago alcanza)
        if self.btn_confirmar['state'] == 'normal':
            pago_real = self.var_pago.get()
            vuelto_real = pago_real - self.total
            
            self.top.destroy() # Cierra la ventana de cobro
            
            # LLAMAMOS A LA FUNCIÓN DE GUARDAR DE LA CLASE PRINCIPAL
            # Le pasamos el pago y el vuelto para que salgan en el ticket
            self.callback(pago_real, vuelto_real)

class VentanaInventario:
    def __init__(self, master, db_config):
        self.master = master
        self.db_config = db_config
        
        self.top = tk.Toplevel(master)
        self.top.title("Gestión de Producto")
        self.top.geometry("600x650") # Ventana más alta y cómoda
        self.top.state('normal')     # No maximizada, pero flotante grande
        
        # --- ESTILOS COMPARTIDOS ---
        self.COLOR_FONDO = "#e6e6e6"
        self.COLOR_BLANCO = "#ffffff"
        self.COLOR_AZUL = "#007bff"
        self.COLOR_VERDE = "#28a745"
        self.COLOR_AMARILLO = "#fff9c4" # Color para escanear
        
        self.FONT_LABEL = ("Segoe UI", 12, "bold")
        self.FONT_ENTRY = ("Segoe UI", 14)
        self.FONT_BTN = ("Segoe UI", 12, "bold")
        
        self.top.configure(bg=self.COLOR_FONDO)
        
        # Variables
        self.var_codigo = tk.StringVar()
        self.var_nombre = tk.StringVar()
        self.var_precio = tk.DoubleVar(value=0.0)
        self.var_stock = tk.IntVar(value=0)
        self.producto_existente = False
        self.placeholder_text = "Escribe aquí el nombre del nuevo producto..."

        # ==========================================
        # 1. ENCABEZADO (Banner Azul)
        # ==========================================
        frame_header = tk.Frame(self.top, bg=self.COLOR_AZUL, pady=15, relief="raised", bd=5)
        frame_header.pack(fill="x")
        tk.Label(frame_header, text="FICHA DE PRODUCTO", bg=self.COLOR_AZUL, fg="white", 
                 font=("Arial", 18, "bold")).pack()

        # ==========================================
        # 2. ÁREA DE ESCANEO (Destacada)
        # ==========================================
        frame_scan = tk.Frame(self.top, bg=self.COLOR_FONDO, pady=20)
        frame_scan.pack(fill="x", padx=40)

        tk.Label(frame_scan, text="1. Escanea o escribe el Código:", bg=self.COLOR_FONDO, font=self.FONT_LABEL).pack(anchor="w")
        
        # Entry Amarillo Grande (Igual que en ventas)
        self.entry_codigo = tk.Entry(frame_scan, textvariable=self.var_codigo, 
                                     font=("Courier New", 18, "bold"), 
                                     bg=self.COLOR_AMARILLO, justify="center", relief="sunken", bd=2)
        self.entry_codigo.pack(fill="x", ipady=8, pady=5)
        self.entry_codigo.bind('<Return>', self.buscar_y_configurar)
        self.entry_codigo.focus_set()

        # ==========================================
        # 3. DATOS DEL PRODUCTO (Formulario)
        # ==========================================
        self.frame_datos = tk.Frame(self.top, bg=self.COLOR_BLANCO, relief="groove", bd=2)
        self.frame_datos.pack(fill="both", expand=True, padx=20, pady=10)
        
        # Usamos Grid para organizar bonito dentro del marco blanco
        self.frame_datos.columnconfigure(1, weight=1) # Columna derecha elástica

        # --- NOMBRE ---
        tk.Label(self.frame_datos, text="Nombre del Producto:", bg=self.COLOR_BLANCO, font=self.FONT_LABEL).grid(row=0, column=0, sticky="w", padx=20, pady=(20,5))
        
        # Creamos los dos widgets (Label fijo y Entry editable) pero no los mostramos aún (.grid_forget)
        self.lbl_nombre_fijo = tk.Label(self.frame_datos, text="", font=("Segoe UI", 16, "bold"), 
                                        fg=self.COLOR_AZUL, bg=self.COLOR_BLANCO, wraplength=500, justify="left")
        
        self.entry_nombre = tk.Entry(self.frame_datos, textvariable=self.var_nombre, font=self.FONT_ENTRY, fg="grey", relief="solid", bd=1)
        # Eventos Placeholder
        self.entry_nombre.bind("<FocusIn>", self.on_entry_focus_in)
        self.entry_nombre.bind("<FocusOut>", self.on_entry_focus_out)

        # --- PRECIO Y STOCK (Lado a Lado para ahorrar espacio vertical) ---
       # --- REGISTRO DE VALIDADORES ---
        # Registramos las funciones en el sistema de Tcl/Tk
        validate_stock = self.top.register(self.solo_numeros)
        validate_price = self.top.register(self.solo_decimales)

        # --- PRECIO (Con validación decimal) ---
        tk.Label(self.frame_datos, text="Precio Venta ($):", bg=self.COLOR_BLANCO, font=self.FONT_LABEL).grid(row=2, column=0, sticky="w", padx=20, pady=(20,5))
        
        self.entry_precio = tk.Entry(self.frame_datos, textvariable=self.var_precio, 
                                     font=self.FONT_ENTRY, justify="right", relief="solid", bd=1,
                                     validate="key", validatecommand=(validate_price, '%P')) # <--- CAMBIO AQUÍ
        self.entry_precio.grid(row=3, column=0, sticky="ew", padx=20, ipady=5)

        # --- STOCK (Con validación entera) ---
        tk.Label(self.frame_datos, text="Stock Actual (Unidades):", bg=self.COLOR_BLANCO, font=self.FONT_LABEL).grid(row=2, column=1, sticky="w", padx=20, pady=(20,5))
        
        self.entry_stock = tk.Entry(self.frame_datos, textvariable=self.var_stock, 
                                    font=self.FONT_ENTRY, justify="center", relief="solid", bd=1,
                                    validate="key", validatecommand=(validate_stock, '%P')) # <--- CAMBIO AQUÍ
        self.entry_stock.grid(row=3, column=1, sticky="ew", padx=20, ipady=5)

        # Ayuda visual debajo de los campos
        tk.Label(self.frame_datos, text="Use punto para decimales (ej: 1500.50)", bg=self.COLOR_BLANCO, fg="grey", font=("Arial", 9)).grid(row=4, column=0, sticky="w", padx=20)

        # ==========================================
        # 4. BOTONES DE ACCIÓN (Grandes)
        # ==========================================
        frame_btns = tk.Frame(self.top, bg=self.COLOR_FONDO, pady=20)
        frame_btns.pack(fill="x")

        self.btn_guardar = tk.Button(frame_btns, text="💾 GUARDAR DATOS (Enter)", 
                                     font=("Arial", 14, "bold"), bg=self.COLOR_VERDE, fg="white",
                                     relief="raised", bd=5, cursor="hand2",
                                     command=self.guardar_producto)
        self.btn_guardar.pack(side="right", padx=20, ipadx=20, ipady=5)

        # Etiqueta para mensajes de estado (Éxito / Error) sin bloquear
        self.lbl_mensaje = tk.Label(frame_btns, text="", font=("Arial", 12), bg=self.COLOR_FONDO)
        self.lbl_mensaje.pack(side="left", padx=20)
        
        # Vincular Enter en los campos de precio/stock para guardar rápido
        self.entry_precio.bind('<Return>', lambda e: self.guardar_producto())
        self.entry_stock.bind('<Return>', lambda e: self.guardar_producto())
        self.entry_nombre.bind('<Return>', lambda e: self.entry_precio.focus_set()) # Del nombre pasa al precio

    # ---------------- LÓGICA DE PLACEHOLDER ----------------

    def reset_ui(self):
        """Limpia todo y espera un nuevo escaneo"""
        self.var_codigo.set("")
        self.var_nombre.set("")
        self.var_precio.set(0.0)
        self.var_stock.set(0)
        self.lbl_nombre_fijo.pack_forget() # Ocultar label
        self.entry_nombre.pack_forget()    # Ocultar entry
        self.entry_cod.focus_set()

    def animar_no_encontrado(self):
        """
        Hace un parpadeo suave en rojo en el campo de nombre 
        para indicar visualmente que no se encontró en la web.
        """
        # 1. Guardamos el color original (blanco o el que use tu tema)
        color_original = self.entry_nombre.cget("bg")
        
        # 2. Cambiamos a rojo suave (Relleno de alerta)
        self.entry_nombre.config(bg="#ffdddd") # Un rosado pálido
        
        # 3. Cambiamos el texto del placeholder para ser más explícitos
        self.var_nombre.set("No encontrado en web. Ingrese nombre...")
        self.entry_nombre.config(fg="#d9534f") # Texto rojo oscuro para el aviso
        
        # 4. Programamos volver a la normalidad en 500 milisegundos (medio segundo)
        def restaurar():
            self.entry_nombre.config(bg=color_original)
            # Volvemos el texto a gris (estilo placeholder normal)
            self.entry_nombre.config(fg="grey")
            
        self.top.after(600, restaurar)
    def on_entry_focus_in(self, event):
        if self.var_nombre.get() == self.placeholder_text:
            self.var_nombre.set("")
            self.entry_nombre.config(fg="black")

    def on_entry_focus_out(self, event):
        if self.var_nombre.get() == "":
            self.var_nombre.set(self.placeholder_text)
            self.entry_nombre.config(fg="grey")

    def animar_no_encontrado(self):
        color_original = "white" # Ahora sabemos que el fondo es blanco
        self.entry_nombre.config(bg="#ffdddd") 
        self.var_nombre.set("Producto nuevo. Ingrese nombre...")
        self.entry_nombre.config(fg="#d9534f")
        
        def restaurar():
            self.entry_nombre.config(bg=color_original)
            self.entry_nombre.config(fg="grey")
            
        self.top.after(600, restaurar)
    
    def consultar_api(self, codigo):
        """
        Busca en Alimentos y Cosmética. 
        Devuelve: "Nombre + Marca + Cantidad"
        """
        fuentes = [
            ("Alimentos", f"https://world.openfoodfacts.org/api/v0/product/{codigo}.json"),
            ("Cosmética", f"https://world.openbeautyfacts.org/api/v0/product/{codigo}.json")
        ]
        
        headers = { 'User-Agent': 'SistemaVentasPython/1.0 (tu_email@ejemplo.com)' }
        
        for nombre_fuente, url in fuentes:
            print(f"--- Consultando {nombre_fuente}... ---")
            
            try:
                respuesta = requests.get(url, headers=headers, timeout=3)
                if respuesta.status_code == 200:
                    datos = respuesta.json()
                    
                    if datos.get('status') == 1:
                        p = datos['product'] # Abreviamos para escribir menos
                        
                        # 1. Obtener NOMBRE (Prioridad Español > Genérico > Inglés)
                        nombre = p.get('product_name_es') or p.get('product_name') or p.get('product_name_en') or ""
                        
                        # 2. Obtener MARCA
                        marca = p.get('brands', "")
                        
                        # 3. Obtener CANTIDAD (Peso/Volumen)
                        cantidad = p.get('quantity', "")
                        
                        # --- LIMPIEZA Y CONSTRUCCIÓN DEL TEXTO ---
                        
                        # A veces la marca viene con comas extra (ej: "Coca-Cola,Coca Cola Company")
                        if "," in marca:
                            marca = marca.split(",")[0] # Nos quedamos solo con la primera parte
                            
                        # Construimos el nombre final uniendo las partes que existan
                        # Usamos una lista para filtrar los vacíos y unirlos con espacios
                        partes = [nombre, marca, cantidad]
                        
                        # Filtramos los vacíos (si no tiene marca, no pone nada)
                        nombre_final = " - ".join([x for x in partes if x])
                        
                        if nombre_final:
                            print(f"¡ÉXITO! Datos completos: {nombre_final}")
                            return nombre_final

            except Exception as e:
                print(f"Error en {nombre_fuente}: {e}")
                continue
        # Si terminó el ciclo y no retornó nada, es que no existe en ninguna
        print("Producto no encontrado en ninguna base de datos pública.")
        return None

    #---------------- BÚSQUEDA Y LÓGICA PRINCIPAL ----------------

    def buscar_y_configurar(self, event):
        codigo = self.var_codigo.get()
        if not codigo: return

        self.top.config(cursor="watch")
        self.top.update()

        try:
            conexion = mysql.connector.connect(**self.db_config)
            cursor = conexion.cursor(dictionary=True)
            cursor.execute("SELECT * FROM productos WHERE codigo_barras = %s", (codigo,))
            producto_local = cursor.fetchone()
            
            # Limpieza visual (Ocultamos ambos widgets primero)
            self.lbl_nombre_fijo.grid_forget()
            self.entry_nombre.grid_forget()

            if producto_local:
                # --- MODO EDICIÓN ---
                self.producto_existente = True
                self.btn_guardar.config(text="🔄 ACTUALIZAR STOCK/PRECIO", bg=self.COLOR_AZUL)
                
                # Mostramos Label Fijo
                self.lbl_nombre_fijo.config(text=producto_local['nombre'])
                self.lbl_nombre_fijo.grid(row=1, column=0, columnspan=2, sticky="ew", padx=20, pady=10)
                
                self.var_nombre.set(producto_local['nombre'])
                self.var_precio.set(producto_local['precio_venta'])
                self.var_stock.set(producto_local['stock_actual'])
                
                self.entry_precio.focus_set()
                self.entry_precio.select_range(0, tk.END)
                
            else:
                # --- MODO NUEVO ---
                self.producto_existente = False
                self.btn_guardar.config(text="💾 GUARDAR NUEVO", bg=self.COLOR_VERDE)
                
                # Mostramos Entry Editable
                self.entry_nombre.grid(row=1, column=0, columnspan=2, sticky="ew", padx=20, pady=10, ipady=5)
                
                # Consultar API (Asegúrate de tener el método consultar_api en la clase)
                nombre_api = self.consultar_api(codigo) 
                
                if nombre_api:
                    self.var_nombre.set(nombre_api)
                    self.entry_nombre.config(fg="black", bg="#d4edda") # Verde suave éxito
                    self.top.after(500, lambda: self.entry_nombre.config(bg="white"))
                else:
                    self.animar_no_encontrado()

                self.var_precio.set(0.0)
                self.var_stock.set(0)
                self.entry_nombre.focus_set()

            cursor.close()
            conexion.close()

        except mysql.connector.Error as err:
            messagebox.showerror("Error", str(err))
        finally:
            self.top.config(cursor="")

    '''def buscar_y_configurar(self, event):
        codigo = self.var_codigo.get()
        if not codigo: return

        try:
            conexion = mysql.connector.connect(**self.db_config)
            cursor = conexion.cursor(dictionary=True)
            cursor.execute("SELECT * FROM productos WHERE codigo_barras = %s", (codigo,))
            producto = cursor.fetchone()
            
            # Limpiamos UI previa del nombre
            self.lbl_nombre_fijo.pack_forget()
            self.entry_nombre.pack_forget()

            if producto:
                # --- ESCENARIO A: PRODUCTO EXISTE ---
                self.producto_existente = True
                
                # 1. Mostrar nombre como TEXTO FIJO (no editable)
                self.lbl_nombre_fijo.config(text=producto['nombre'], fg="green")
                self.lbl_nombre_fijo.pack(fill="x", pady=5)
                
                # 2. Cargar datos actuales
                self.var_nombre.set(producto['nombre']) # Guardamos en variable aunque no se edite
                self.var_precio.set(producto['precio_venta'])
                self.var_stock.set(producto['stock_actual'])
                
                # 3. Mover foco DIRECTO al PRECIO (Saltamos el nombre)
                self.entry_precio.focus_set()
                self.entry_precio.select_range(0, tk.END) # Seleccionar todo para sobreescribir rápido
                
            else:
                # --- ESCENARIO B: PRODUCTO NUEVO ---
                self.producto_existente = False
                
                # 1. Mostrar CAMPO EDITABLE
                self.entry_nombre.pack(fill="x", pady=5)
                
                # AQUI EL CAMBIO: Seteamos el placeholder por defecto
                self.var_nombre.set(self.placeholder_text)
                self.entry_nombre.config(fg="grey")
                
                self.var_precio.set(0.0)
                self.var_stock.set(0)
                
            cursor.close()
            conexion.close()

        except mysql.connector.Error as err:
            messagebox.showerror("Error", str(err))'''

    def solo_numeros(self, char):
        """
        Validador para STOCK: Solo permite dígitos (0-9).
        """
        # %P es el valor propuesto (texto_nuevo).
        # Permitimos borrar todo ("") o que sean dígitos
        return char.isdigit() or char == ""

    def solo_decimales(self, char):
        """
        Validador para PRECIO: Permite números y un solo punto.
        """
        if char == "": return True
        try:
            float(char)
            return True
        except ValueError:
            return False        

    def guardar_producto(self):
        # 1. Obtener datos (Validaciones igual que antes...)
        codigo = self.var_codigo.get()
        nombre = self.var_nombre.get()
        txt_precio = self.entry_precio.get()
        txt_stock = self.entry_stock.get()

        # --- VALIDACIONES (Resumidas para ahorrar espacio visual aquí) ---
        if not codigo: 
            self.mostrar_mensaje("Falta el código", "red"); return
        if not nombre or nombre == self.placeholder_text: 
            self.mostrar_mensaje("Falta el nombre", "red"); return
        if not txt_precio: 
            self.mostrar_mensaje("Falta el precio", "red"); return

        try:
            precio_final = float(txt_precio)
            stock_final = int(txt_stock) if txt_stock else 0
        except ValueError:
            self.mostrar_mensaje("Error en números", "red")
            return

        # --- GUARDAR EN BD ---
        try:
            conexion = mysql.connector.connect(**self.db_config)
            cursor = conexion.cursor()
            
            if self.producto_existente:
                sql = "UPDATE productos SET nombre=%s, precio_venta=%s, stock_actual=%s WHERE codigo_barras=%s"
                cursor.execute(sql, (nombre, precio_final, stock_final, codigo))
                texto_exito = "✅ Producto Actualizado"
            else:
                sql = "INSERT INTO productos (codigo_barras, nombre, precio_venta, stock_actual) VALUES (%s, %s, %s, %s)"
                cursor.execute(sql, (codigo, nombre, precio_final, stock_final))
                texto_exito = "✅ Producto Nuevo Registrado"
            
            conexion.commit()
            cursor.close()
            conexion.close()

            # --- AQUÍ ESTÁ EL CAMBIO (FLUJO CONTINUO) ---
            
            # 1. Mostrar mensaje de éxito en la propia ventana
            self.mostrar_mensaje(texto_exito, "#28a745") # Verde éxito

            # 2. Limpiar todo para el siguiente producto
            self.limpiar_formulario()
            
            # 3. Volver el foco al inicio para escanear de nuevo inmediatamente
            self.entry_codigo.focus_set()
            
        except mysql.connector.Error as err:
            self.mostrar_mensaje(f"Error BD: {err}", "red")

    # --- FUNCIONES AUXILIARES PARA LIMPIEZA Y MENSAJES ---

    def mostrar_mensaje(self, texto, color):
        """Muestra un mensaje temporal abajo y lo borra a los 3 segundos"""
        self.lbl_mensaje.config(text=texto, fg=color)
        # Programar que se borre solo en 3000 milisegundos (3 segundos)
        self.top.after(3000, lambda: self.lbl_mensaje.config(text=""))

    def limpiar_formulario(self):
        """Deja la ventana lista para el siguiente escaneo"""
        self.var_codigo.set("")
        self.var_nombre.set(self.placeholder_text)
        self.entry_nombre.config(fg="grey")
        self.var_precio.set(0)
        self.var_stock.set(0)
        
        # Ocultar paneles de edición y volver al estado inicial
        self.lbl_nombre_fijo.grid_forget()
        self.entry_nombre.grid_forget()
        
        # Resetear estado
        self.producto_existente = False
        self.btn_guardar.config(text="💾 GUARDAR (Enter)", bg=self.COLOR_VERDE)

    def on_entry_focus_in(self, event):
        """Al hacer clic, si está el texto fantasma, lo borra y pone letra negra"""
        texto_actual = self.var_nombre.get()
        if texto_actual == self.placeholder_text:
            self.var_nombre.set("")
            self.entry_nombre.config(fg="black") # Color normal

    def on_entry_focus_out(self, event):
        """Al salir, si lo dejó vacío, vuelve a poner el texto fantasma en gris"""
        texto_actual = self.var_nombre.get()
        if texto_actual == "":
            self.var_nombre.set(self.placeholder_text)
            self.entry_nombre.config(fg="grey") # Color gris bajito

class SistemaVentas:
    def __init__(self, root):
        self.root = root
        self.root.title("PUNTO DE VENTA")
        self.root.state('zoomed') 
        
        self.carrito = []
        self.db_config = self.cargar_configuracion()

        # --- CONFIGURACIÓN DE ESTILO ---
        COLOR_FONDO = "#e6e6e6"
        COLOR_VERDE = "#28a745"
        COLOR_AZUL = "#007bff"
        
        FONT_BOLD = ("Segoe UI", 14, "bold")
        FONT_BIG = ("Segoe UI", 18, "bold")
        FONT_HUGE = ("Segoe UI", 30, "bold")

        self.root.configure(bg=COLOR_FONDO)

        # ---------------------------------------------------------
        # 1. PAN DE ARRIBA (Encabezado y Buscador)
        # ---------------------------------------------------------
        # ---------------------------------------------------------
        # 1. PAN DE ARRIBA (Encabezado con LOGO)
        # ---------------------------------------------------------
        
        # Frame azul superior (Contenedor principal)
        frame_top = tk.Frame(self.root, bg=COLOR_AZUL, pady=5, relief="raised", bd=5)
        frame_top.pack(fill="x", side="top")

        # --- LOGO ---
        try:
            # 1. Cargar la imagen con Pillow
            # Asegúrate que 'logo.png' esté en la carpeta del proyecto
            img_pil = Image.open("logo.png")
            
            # 2. Redimensionar (IMPORTANTE: para que no quede gigante)
            # Probamos con 60x60 pixeles. Ajusta este número si tu logo es muy ancho o alto.
            # Image.LANCZOS es un filtro para que al achicarla se vea nítida.
            img_resized = img_pil.resize((70, 70), Image.LANCZOS)
            
            # 3. Convertir a formato compatible con Tkinter
            self.logo_img = ImageTk.PhotoImage(img_resized)
            
            # 4. Crear un Label para mostrar la imagen
            # Lo ponemos en el frame azul, con fondo azul
            lbl_logo = tk.Label(frame_top, image=self.logo_img, bg=COLOR_AZUL)
            
            # 5. Empaquetar a la IZQUIERDA, con un poco de margen
            lbl_logo.pack(side="left", padx=(10, 5)) 
            
            # --- ¡TRUCO VITAL DE TKINTER! ---
            # Si no guardas una referencia a la imagen en una variable de la clase (self),
            # el "recolector de basura" de Python la borra y no se ve nada.
            lbl_logo.image = self.logo_img 

        except Exception as e:
            print(f"No se pudo cargar el logo: {e}")
            # Si falla (ej: no encuentra el archivo), el programa sigue funcionando sin logo.

        # --- TÍTULO DE TEXTO ---
        # Ahora el título se empaqueta también a la IZQUIERDA, justo después del logo.
        tk.Label(frame_top, text="SISTEMA DE VENTAS", bg=COLOR_AZUL, fg="white", 
                 font=("Arial", 24, "bold")).pack(side="left")
        # Botones de Acción
        frame_acciones = tk.Frame(self.root, bg=COLOR_FONDO, pady=10)
        frame_acciones.pack(fill="x", side="top") # Pegado debajo del banner

        btn_inv = tk.Button(frame_acciones, text="📦 Inventario", font=FONT_BOLD, relief="raised", bd=4, bg="white", 
                            command=self.abrir_lista_inventario)
        btn_inv.pack(side="left", padx=5)

        btn_cargar = tk.Button(frame_acciones, text="➕ Nuevo Producto", font=FONT_BOLD, relief="raised", bd=4, bg="white", 
                               command=self.abrir_inventario)
        btn_cargar.pack(side="left", padx=5)

        btn_excel = tk.Button(frame_acciones, text="📊 Exportar Ventas Hoy", 
                              font=FONT_BOLD, bg="#217346", fg="white", # Color Excel oficial
                              relief="raised", bd=4, cursor="hand2",
                              command=self.exportar_ventas_excel)
        btn_excel.pack(side="left", padx=5, ipady=5)

        # Zona de Escaneo
        frame_scan = tk.Frame(self.root, bg=COLOR_FONDO, pady=10)
        frame_scan.pack(fill="x", side="top", padx=20) # Pegado debajo de botones

        tk.Label(frame_scan, text="Escanea el Código:", bg=COLOR_FONDO, font=FONT_BIG).pack(anchor="w")
        
        self.entry_codigo = tk.Entry(frame_scan, font=("Courier New", 20, "bold"), 
                                     bg="#fff9c4", justify="center", bd=2, relief="sunken")
        self.entry_codigo.pack(fill="x", ipady=10)
        self.entry_codigo.bind('<Return>', self.buscar_producto)
        self.entry_codigo.focus_set()

        # ---------------------------------------------------------
        # 2. PAN DE ABAJO (Aquí estaba el problema)
        # Lo creamos AHORA para reservar su espacio abajo de todo.
        # ---------------------------------------------------------
        frame_bottom = tk.Frame(self.root, bg="#333", pady=20, relief="raised", bd=5)
        frame_bottom.pack(fill="x", side="bottom") # <--- CLAVE: side="bottom"
        
        # Botón COBRAR
        btn_cobrar = tk.Button(frame_bottom, text="✅ COBRAR (F5)", 
                               bg=COLOR_VERDE, fg="white", 
                               font=("Arial", 18, "bold"),
                               relief="raised", bd=5, cursor="hand2",
                               command=self.guardar_venta)
        btn_cobrar.pack(side="left", padx=30, ipady=10, ipadx=20) 
        
        self.root.bind('<F5>', lambda event: self.guardar_venta())

        # Total
        self.lbl_total = tk.Label(frame_bottom, text="TOTAL: $0.00", 
                                  fg=COLOR_VERDE, bg="#333", font=FONT_HUGE)
        self.lbl_total.pack(side="right", padx=30)
        self.total_acumulado = 0.0

        # ---------------------------------------------------------
        # 3. EL RELLENO (La Tabla)
        # La ponemos al final y le decimos "ocupa TODO lo que sobró en el medio"
        # ---------------------------------------------------------
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Treeview", background="white", rowheight=40, fieldbackground="white", font=("Arial", 14))
        style.configure("Treeview.Heading", font=("Arial", 14, "bold"), background="#444", foreground="white")
        style.map("Treeview", background=[('selected', COLOR_AZUL)])

        frame_tabla = tk.Frame(self.root, bg=COLOR_FONDO)
        # CLAVE: side="top", fill="both", expand=True
        # Esto hace que se estire entre el panel de arriba y el de abajo
        frame_tabla.pack(side="top", fill="both", expand=True, padx=20, pady=10) 

        self.tree = ttk.Treeview(frame_tabla, columns=("ID", "Producto", "Precio", "Cantidad", "Subtotal"), show='headings')
        
        self.tree.heading("ID", text="ID"); self.tree.column("ID", width=50, anchor="center")
        self.tree.heading("Producto", text="PRODUCTO"); self.tree.column("Producto", width=400)
        self.tree.heading("Precio", text="PRECIO"); self.tree.column("Precio", width=100, anchor="e")
        self.tree.heading("Cantidad", text="CANT"); self.tree.column("Cantidad", width=80, anchor="center")
        self.tree.heading("Subtotal", text="TOTAL"); self.tree.column("Subtotal", width=100, anchor="e")
        
        self.tree.pack(side="left", fill="both", expand=True)
        self.tree.bind("<Delete>", self.eliminar_producto)

        scrollbar = ttk.Scrollbar(frame_tabla, orient="vertical", command=self.tree.yview)
        scrollbar.pack(side="right", fill="y")
        self.tree.configure(yscroll=scrollbar.set)
        
        # Atajo F5
        self.root.bind('<F5>', lambda event: self.guardar_venta())


        self.total_acumulado = 0.0



    '''def __init__(self, root):
        self.root = root
        self.root.title("Punto de Venta - Python + MySQL")
        self.root.geometry("900x600")

        # --- CARGAR CONFIGURACIÓN EXTERNA ---
        self.db_config = self.cargar_configuracion()
        
        # Si la configuración falló, el root ya fue destruido, salir inmediatamente
        if self.db_config is None:
            return
        
        # Lista para manejar los datos lógicos de la venta actual
        self.carrito = [] # ### NUEVO: Aquí guardaremos los objetos completos
        
        self.db_config = {
            'host': 'localhost',
            'user': 'root',
            'password': '', # <--- RECUERDA PONER TU PASSWORD
            'database': 'punto_ventas'
        }

        # --- INTERFAZ GRÁFICA ---
        
        # 1. Panel Superior
        frame_top = tk.Frame(self.root, bg="#f0f0f0", pady=20)
        frame_top.pack(fill="x")
        
        tk.Label(frame_top, text="Código de Barras:", bg="#f0f0f0", font=("Arial", 12)).pack(side="left", padx=20)
        
        self.entry_codigo = tk.Entry(frame_top, font=("Arial", 14), width=20)
        self.entry_codigo.pack(side="left")
        self.entry_codigo.bind('<Return>', self.buscar_producto)
        self.entry_codigo.focus_set()
        style = ttk.Style()
        style.theme_use("default") # Usamos 'default' o 'clam' para poder cambiar colores facil
        style.map("Treeview", 
              background=[('selected', '#d9534f')], # Rojo suave al seleccionar
              foreground=[('selected', 'white')]
              )
        # 2. Panel Central
        self.tree = ttk.Treeview(self.root, columns=("ID", "Producto", "Precio", "Cantidad", "Subtotal"), show='headings')
        self.tree.heading("ID", text="ID") # ### NUEVO: Columna ID (aunque podríamos ocultarla)
        self.tree.column("ID", width=50)
        self.tree.heading("Producto", text="Producto")
        self.tree.heading("Precio", text="Precio")
        self.tree.heading("Cantidad", text="Cantidad")
        self.tree.heading("Subtotal", text="Subtotal")
        self.tree.pack(fill="both", expand=True, padx=20, pady=20)
        self.tree.bind("<Delete>", self.eliminar_producto)

        # 3. Panel Inferior
        frame_bottom = tk.Frame(self.root, bg="#333", pady=15)
        frame_bottom.pack(fill="x", side="bottom")

        btn_ver_inventario = tk.Button(self.root, text="Ver Todo el Inventario", bg="#17a2b8", fg="white", 
                                       command=self.abrir_lista_inventario)
        btn_ver_inventario.pack(side="top", anchor="ne", pady=5)

        # Dentro de __init__ de SistemaVentas:
        btn_inventario = tk.Button(frame_bottom, text="Gestión Inventario", command=self.abrir_inventario)
        btn_inventario.pack(side="left", padx=20)
        
        # ### NUEVO: Botón de Cobrar
        btn_cobrar = tk.Button(frame_bottom, text="FINALIZAR VENTA (F5)", bg="#28a745", fg="white", font=("Arial", 12, "bold"), command=self.guardar_venta)
        btn_cobrar.pack(side="left", padx=20)
        # Atajo de teclado para cobrar
        self.root.bind('<F5>', lambda event: self.guardar_venta())
        
        self.lbl_total = tk.Label(frame_bottom, text="TOTAL: $0.00", fg="white", bg="#333", font=("Arial", 24, "bold"))
        self.lbl_total.pack(side="right", padx=30)

        self.total_acumulado = 0.0'''


    def cargar_configuracion(self):
        config = configparser.ConfigParser()
        
        # Intenta leer el archivo 'config.ini'
        # Si ya compilaste a .exe, busca el archivo en la misma carpeta que el ejecutable
        try:
            config.read('config.ini')
            
            db_conf = {
                'host': config['mysql']['host'],
                'user': config['mysql']['user'],
                'password': config['mysql']['password'], # Lee lo que esté escrito en el archivo
                'database': config['mysql']['database'],
                'port': config['mysql'].getint('port')
            }
            # 2. Configuración de Impresora (NUEVO)
            # Guardamos el nombre en una variable de la clase para usarlo luego
            self.nombre_impresora_config = config['impresion']['nombre_impresora']
            return db_conf
            
        except Exception as e:
            # Si alguien borró el archivo .ini o está mal escrito
            messagebox.showerror("Error Fatal", f"No se pudo leer config.ini: {e}")
            self.root.destroy() # Cierra el programa
            return None
    def buscar_producto(self, event):
        codigo = self.entry_codigo.get().strip()
        if not codigo:
            return

        # 1. Buscar en Base de Datos
        try:
            conexion = mysql.connector.connect(**self.db_config)
            cursor = conexion.cursor(dictionary=True)
            cursor.execute("SELECT * FROM productos WHERE codigo_barras = %s", (codigo,))
            producto_bd = cursor.fetchone()
            conexion.close()
        except Exception as e:
            messagebox.showerror("Error", f"Error al buscar: {e}")
            return

        if producto_bd:
            # 2. VALIDAR STOCK (Opcional pero recomendado)
            if producto_bd['stock_actual'] <= 0:
                messagebox.showwarning("Sin Stock", f"El producto '{producto_bd['nombre']}' no tiene stock.")
                self.entry_codigo.delete(0, tk.END)
                return

            # --- AQUÍ EMPIEZA LA MAGIA DE LA SUMA ---
            
            encontrado_en_carrito = False
            
            # Recorremos el carrito actual para ver si YA existe este producto
            for item in self.carrito:
                if item['id'] == producto_bd['id']:
                    # ¡YA EXISTE! Solo sumamos la cantidad
                    item['cantidad'] += 1
                    item['subtotal'] = item['cantidad'] * item['precio']
                    encontrado_en_carrito = True
                    break # Dejamos de buscar
            
            # Si NO estaba en el carrito, lo agregamos como nuevo
            if not encontrado_en_carrito:
                nuevo_item = {
                    'id': producto_bd['id'],
                    'codigo': producto_bd['codigo_barras'],
                    'nombre': producto_bd['nombre'],
                    'precio': float(producto_bd['precio_venta']),
                    'cantidad': 1, # Empieza con 1
                    'subtotal': float(producto_bd['precio_venta'])
                }
                self.carrito.append(nuevo_item)

            # ----------------------------------------

            # 3. Limpiar input y actualizar tabla visual
            self.entry_codigo.delete(0, tk.END)
            self.actualizar_carrito_visual()

        else:
            messagebox.showwarning("No encontrado", "Producto no registrado")
            self.entry_codigo.delete(0, tk.END)


    def actualizar_carrito_visual(self):
        # 1. Limpiar tabla actual
        for i in self.tree.get_children():
            self.tree.delete(i)
            
        # 2. Rellenar con los datos actualizados del carrito
        self.total_acumulado = 0.0
        
        for item in self.carrito:
            self.tree.insert("", "end", values=(
                item['codigo'],
                item['nombre'],
                f"${item['precio']:.2f}",
                item['cantidad'],       # <--- Ahora verás 2, 3, 4, etc.
                f"${item['subtotal']:.2f}"
            ))
            self.total_acumulado += item['subtotal']
            
        # 3. Actualizar el Label de TOTAL GIGANTE
        self.lbl_total.config(text=f"TOTAL: ${self.total_acumulado:.2f}")

    def agregar_a_venta(self, producto):
        cantidad = 1
        # Verificamos si ya está en el carrito para sumar cantidad en vez de agregar fila nueva (Lógica básica)
        # Por simplicidad, hoy agregaremos filas nuevas siempre.
        
        subtotal = producto['precio_venta'] * cantidad
        
       # 1. Agregar a la lista lógica (Memoria)
        item_carrito = {
            "id": producto['id'],
            "nombre": producto['nombre'], # <--- ¡AGREGA ESTA LÍNEA!
            "precio": producto['precio_venta'],
            "cantidad": cantidad,
            "subtotal": subtotal
        }
        self.carrito.append(item_carrito)
        
        # 2. Agregar a la tabla visual (GUI)
        self.tree.insert("", "end", values=(producto['id'], producto['nombre'], f"${producto['precio_venta']}", cantidad, f"${subtotal}"))
        
        self.total_acumulado += float(subtotal)
        self.lbl_total.config(text=f"TOTAL: ${self.total_acumulado:.2f}")

    def guardar_venta(self):
        if not self.carrito:
            messagebox.showinfo("Vacío", "No hay productos para cobrar.")
            return

        # Abrimos la ventana de cobro y le pasamos:
        # 1. Quien es el padre (self.root)
        # 2. El total a pagar
        # 3. La función que debe ejecutar si el pago es exitoso (self.registrar_venta_db)
        VentanaCobro(self.root, self.total_acumulado, self.registrar_venta_db)

    def registrar_venta_db(self, pago, vuelto):
        try:
            conexion = mysql.connector.connect(**self.db_config)
            conexion.autocommit = False 
            cursor = conexion.cursor()

            # 1. Insertar Cabecera (Ahora guardamos también con cuánto pagó si quisieras agregar esa columna en el futuro)
            sql_venta = "INSERT INTO ventas (total, metodo_pago) VALUES (%s, %s)"
            cursor.execute(sql_venta, (self.total_acumulado, 'Efectivo'))
            id_venta = cursor.lastrowid 

            # 2. Insertar Detalles y Restar Stock (Igual que antes)
            sql_detalle = "INSERT INTO detalle_ventas (id_venta, id_producto, cantidad, precio_unitario, subtotal) VALUES (%s, %s, %s, %s, %s)"
            sql_update_stock = "UPDATE productos SET stock_actual = stock_actual - %s WHERE id = %s"

            for item in self.carrito:
                # ... dentro del bucle for item in self.carrito ...
        
                sql_detalle = """INSERT INTO detalle_ventas 
                                (id_venta, id_producto, cantidad, precio_unitario, subtotal) 
                                VALUES (%s, %s, %s, %s, %s)"""
                                
                # ¡OJO AQUÍ! El tercer valor debe ser item['cantidad']
                val_detalle = (id_venta, item['id'], item['cantidad'], item['precio'], item['subtotal'])
                
                cursor.execute(sql_detalle, val_detalle)
                
                # También RESTAR esa cantidad al stock
                sql_update_stock = "UPDATE productos SET stock_actual = stock_actual - %s WHERE id = %s"
                cursor.execute(sql_update_stock, (item['cantidad'], item['id']))

            # 3. Confirmar
            conexion.commit()
            
            # --- IMPRIMIR TICKET (Ahora con datos del vuelto) ---
            self.generar_ticket(id_venta, pago, vuelto) 
            # ----------------------------------------------------

            # messagebox.showinfo("Éxito", f"Vuelto: ${vuelto:.2f}") # Opcional, ya lo vio en la ventana anterior
            self.limpiar_pantalla()

        except mysql.connector.Error as err:
            conexion.rollback()
            messagebox.showerror("Error Crítico", f"No se pudo guardar la venta: {err}")
        finally:
            if conexion.is_connected():
                cursor.close()
                conexion.close()
    # ### NUEVO: La función crítica ###
    '''def guardar_venta(self):
        if not self.carrito:
            messagebox.showinfo("Vacío", "No hay productos para cobrar.")
            return

        try:
            conexion = mysql.connector.connect(**self.db_config)
            conexion.autocommit = False # ¡IMPORTANTE! Desactivamos el guardado automático para usar Transacciones
            cursor = conexion.cursor()

            # 1. Insertar Cabecera (Tabla Ventas)
            sql_venta = "INSERT INTO ventas (total, metodo_pago) VALUES (%s, %s)"
            cursor.execute(sql_venta, (self.total_acumulado, 'Efectivo'))
            id_venta = cursor.lastrowid # Obtenemos el ID de la venta recién creada

            # 2. Insertar Detalles y Restar Stock
            sql_detalle = "INSERT INTO detalle_ventas (id_venta, id_producto, cantidad, precio_unitario, subtotal) VALUES (%s, %s, %s, %s, %s)"
            sql_update_stock = "UPDATE productos SET stock_actual = stock_actual - %s WHERE id = %s"

            for item in self.carrito:
                # Guardar detalle
                datos_detalle = (id_venta, item['id'], item['cantidad'], item['precio'], item['subtotal'])
                cursor.execute(sql_detalle, datos_detalle)
                
                # Restar stock
                cursor.execute(sql_update_stock, (item['cantidad'], item['id']))

            # 3. Confirmar todo (Commit)
            conexion.commit()
            
            # --- NUEVO: IMPRIMIR TICKET ---
            # Pasamos el id_venta que obtuvimos de la BD
            self.generar_ticket(id_venta) 
            # ------------------------------

            messagebox.showinfo("Éxito", "Venta registrada e imprimiendo...")
            self.limpiar_pantalla()

        except mysql.connector.Error as err:
            # Si algo falla, deshacemos todo (Rollback)
            conexion.rollback()
            messagebox.showerror("Error Crítico", f"No se pudo guardar la venta: {err}")
        finally:
            if conexion.is_connected():
                cursor.close()
                conexion.close()'''
    def eliminar_producto(self, event):
        # 1. Obtener qué fila está seleccionada
        seleccion = self.tree.selection()
        
        if not seleccion:
            return # No hay nada seleccionado, no hacemos nada

        # Por seguridad, tomamos solo el primer ítem seleccionado (en caso de selección múltiple)
        item_id = seleccion[0]
        
        # 2. Buscar el índice (posición) de esa fila en la tabla visual
        # Esto es vital para saber qué borrar de la lista 'self.carrito'
        index = self.tree.index(item_id)
        
        # 3. Borrar de la LÓGICA (self.carrito) y actualizar Total
        # Restamos el subtotal de ese ítem del total general
        item_a_borrar = self.carrito[index]
        self.total_acumulado = self.total_acumulado - float(item_a_borrar['subtotal'])
        
        # Evitar errores de redondeo (ej: -0.0000001)
        if self.total_acumulado < 0: self.total_acumulado = 0.0
        
        # Borramos el ítem de la lista
        del self.carrito[index]
        
        # 4. Borrar de la VISUAL (Treeview)
        self.tree.delete(item_id)
        
        # 5. Actualizar el Label del Total
        self.lbl_total.config(text=f"TOTAL: ${self.total_acumulado:.2f}")
        
        # Devolver foco al buscador para seguir escaneando rápido
        self.entry_codigo.focus_set()

    def mostrar_ticket_virtual(self, contenido_texto, ruta_imagen_logo=None):
        """
        Simulación visual del ticket en pantalla, incluyendo imagen.
        """
        # Ventana estrecha y alta para simular el papel
        ventana_ticket = tk.Toplevel(self.root)
        ventana_ticket.title("Vista Previa Ticket (Simulación)")
        ventana_ticket.geometry("420x700") 
        ventana_ticket.configure(bg="#333") # Fondo oscuro de contraste

        # --- MARCO "PAPEL" ---
        # Este frame blanco es el rollo de papel
        frame_papel = tk.Frame(ventana_ticket, bg="white", bd=10, relief="flat")
        frame_papel.pack(pady=20, padx=20, fill="both", expand=True)

        # --- 1. ZONA DE LOGO (Arriba) ---
        if ruta_imagen_logo and os.path.exists(ruta_imagen_logo):
            try:
                # Cargamos la imagen original de la carpeta
                pil_img = Image.open(ruta_imagen_logo)
                
                # Redimensionamos visualmente para que quepa en el "papel" en pantalla
                # (Aprox 350px de ancho para simular 58mm)
                ancho_destino = 150
                porcentaje = (ancho_destino / float(pil_img.size[0]))
                alto_destino = int((float(pil_img.size[1]) * float(porcentaje)))
                pil_img = pil_img.resize((ancho_destino, alto_destino), Image.Resampling.LANCZOS)
                
                tk_img = ImageTk.PhotoImage(pil_img)

                lbl_logo_ticket = tk.Label(frame_papel, image=tk_img, bg="white")
                lbl_logo_ticket.pack(pady=(10, 0)) # Un poco de margen arriba
                
                # ¡IMPORTANTE! Guardar referencia para que no se borre
                lbl_logo_ticket.image = tk_img

            except Exception as e:
                tk.Label(frame_papel, text=f"[Error cargando imagen: {e}]", fg="red", bg="white").pack()
        else:
             # Si no hay logo, un espacio vacío
             tk.Label(frame_papel, text="[Sin Logo]", fg="grey", bg="white").pack(pady=5)

        # --- 2. ZONA DE TEXTO (Abajo) ---
        # Usamos un Label con fuente monoespaciada (Courier) para que se alineen los números
        lbl_texto = tk.Label(frame_papel, text=contenido_texto, 
                             font=("Courier New", 11), # Tamaño 11 se ve bien para 58mm
                             bg="white", fg="black", justify="left", anchor="nw")
        lbl_texto.pack(pady=10, padx=5, fill="both", expand=True)

        # Botón para cerrar
        tk.Button(ventana_ticket, text="Cerrar Vista Previa", command=ventana_ticket.destroy,
                  bg="#dc3545", fg="white", font=("Arial", 10, "bold")).pack(pady=5)

    def generar_ticket(self, id_venta, pago, vuelto):
        # 1. Variables para construir las DOS versiones
        texto_visual = ""  # Lo que veremos en pantalla
        ticket_bytes = b"" # Lo que mandamos a la impresora
        
        # Comandos (Solo para la versión bytes)
        CMD_INIT = b'\x1b@'; CMD_CENTER = b'\x1b\x61\x01'; CMD_LEFT = b'\x1b\x61\x00'
        CMD_CUT = b'\x1d\x56\x00'

        # --- CONSTRUCCIÓN DEL CONTENIDO ---
        
        # Encabezado
        texto_visual += "      KIOSCO MERCHI      \n"
        texto_visual += "--------------------------------\n"
        texto_visual += f"Fecha: {datetime.now().strftime('%d/%m/%Y %H:%M')}\n"
        texto_visual += f"Ticket Nro: {id_venta}\n"
        texto_visual += "--------------------------------\n"

        ticket_bytes += CMD_INIT + CMD_CENTER + b"SUPERMERCADO PYTHON\n" + CMD_LEFT
        ticket_bytes += b"--------------------------------\n"
        ticket_bytes += f"Fecha: {datetime.now().strftime('%d/%m/%Y %H:%M')}\n".encode('latin-1')
        ticket_bytes += f"Ticket Nro: {id_venta}\n".encode('latin-1')
        ticket_bytes += b"--------------------------------\n"

        # Productos
        for item in self.carrito:
            nombre = item['nombre'][:32].upper()
            linea_precio = f"{item['cantidad']} x ${item['precio']:.2f}    ${item['subtotal']:.2f}"
            
            # Versión Visual
            texto_visual += f"{nombre}\n{linea_precio}\n"
            
            # Versión Impresora
            ticket_bytes += f"{nombre}\n".encode('latin-1')
            ticket_bytes += f"{linea_precio}\n".encode('latin-1')

        # Totales
        texto_visual += "--------------------------------\n"
        texto_visual += f"TOTAL:  ${self.total_acumulado:.2f}\n"
        texto_visual += f"PAGO:   ${pago:.2f}\n"
        texto_visual += f"VUELTO: ${vuelto:.2f}\n"
        texto_visual += "\n     GRACIAS POR SU COMPRA     \n"

        ticket_bytes += b"--------------------------------\n"
        ticket_bytes += CMD_CENTER + f"TOTAL: ${self.total_acumulado:.2f}\n".encode('latin-1') + CMD_LEFT
        ticket_bytes += f"PAGO:   ${pago:.2f}\n".encode('latin-1')
        ticket_bytes += f"VUELTO: ${vuelto:.2f}\n".encode('latin-1')
        ticket_bytes += b"\n" + CMD_CENTER + b"GRACIAS POR SU COMPRA\n" + b"\n\n\n" + CMD_CUT

        # --- MOMENTO DE DECISIÓN ---
        try:
            # Intentamos imprimir REALMENTE
            NOMBRE_IMPRESORA = self.nombre_impresora_config # O self.config...
            hPrinter = win32print.OpenPrinter(NOMBRE_IMPRESORA)
            
            #hPrinter = win32print.OpenPrinter(NOMBRE_IMPRESORA)
            try:
                hJob = win32print.StartDocPrinter(hPrinter, 1, ("Ticket Agrupado", None, "RAW"))
                try:
                    win32print.StartPagePrinter(hPrinter)
                    win32print.WritePrinter(hPrinter, ticket_bytes)
                    win32print.EndPagePrinter(hPrinter)
                finally:
                    win32print.EndDocPrinter(hPrinter)
            finally:
                win32print.ClosePrinter(hPrinter)
            
            win32print.ClosePrinter(hPrinter)
            
        except Exception as e:
            # SI FALLA (o estamos probando), mostramos la PREVISUALIZACIÓN VISUAL
            print(f"Impresión física omitida: {e}")
            
            # Nombre del archivo que usas para el logo en blanco y negro
            RUTA_LOGO_TICKET = "logo_ticket.png" 
            print(RUTA_LOGO_TICKET)
            
            # Llamamos a la nueva función pasando el texto Y la ruta de la imagen
            self.mostrar_ticket_virtual(texto_visual, RUTA_LOGO_TICKET)
    '''def generar_ticket(self, id_venta, pago, vuelto):
        NOMBRE_IMPRESORA = "POS-58" # <--- Asegúrate que este sea el nombre correcto

        # --- 1. LÓGICA DE AGRUPACIÓN (OPTIMIZACIÓN) ---
        # Creamos un diccionario temporal para sumar repetidos por ID
        items_resumidos = {}

        for item in self.carrito:
            id_prod = item['id']
            
            if id_prod in items_resumidos:
                # Si ya existe, sumamos cantidad y precio acumulado
                items_resumidos[id_prod]['cantidad'] += item['cantidad']
                items_resumidos[id_prod]['subtotal'] += item['subtotal']
            else:
                # Si es nuevo, lo agregamos (usamos .copy() para no romper el carrito original)
                items_resumidos[id_prod] = item.copy()

        # --- 2. CONFIGURACIÓN ESC/POS ---
        CMD_INIT = b'\x1b@'
        CMD_CENTER = b'\x1b\x61\x01'
        CMD_LEFT = b'\x1b\x61\x00'
        CMD_BOLD_ON = b'\x1b\x45\x01'
        CMD_BOLD_OFF = b'\x1b\x45\x00'
        CMD_CUT = b'\x1d\x56\x00'

        ticket = b""
        
        # --- [NUEVO] AGREGAR LOGO ---
        # Asegúrate de tener un archivo 'logo_ticket.png' en la carpeta
        # O usa el mismo 'logo.png' si ya es blanco y negro
        bytes_logo = self.obtener_bytes_imagen("logo_ticket.png")
        ticket += bytes_logo
        ticket += b"\n" # Un salto de línea después del logo
        # ----------------------------
        # Encabezado
        ticket += CMD_INIT + CMD_CENTER + CMD_BOLD_ON
        ticket += b"KIOSCO MERCHI\n"
        ticket += CMD_BOLD_OFF
        ticket += b"--------------------------------\n" # 32 guiones
        ticket += CMD_LEFT
        ticket += f"Fecha: {datetime.now().strftime('%d/%m/%Y %H:%M')}\n".encode('latin-1')
        ticket += f"Ticket Nro: {id_venta}\n".encode('latin-1')
        ticket += b"--------------------------------\n"

        # --- 3. IMPRESIÓN DEL RESUMEN ---
        # Iteramos sobre nuestro diccionario agrupado
        for item in items_resumidos.values():
            # Nombre: Cortamos a 32 chars y a mayúsculas
            nombre = item['nombre'][:32].upper()
            
            # Imprimimos Nombre en una línea
            ticket += f"{nombre}\n".encode('latin-1')
            
            # Imprimimos Cantidad y Precios en la siguiente
            # Lógica: {cantidad} x {precio_unitario} ...... {subtotal_sumado}
            
            cant = item['cantidad']
            # Calculamos el unitario de nuevo para mostrarlo (Subtotal / Cantidad)
            # Esto maneja el caso de que hayas cambiado precios, usa el promedio de esta venta
            precio_unit = item['subtotal'] / cant 
            subtotal = item['subtotal']

            linea_detalles = f"{cant} x ${precio_unit:.2f}     ${subtotal:.2f}"
            
            ticket += f"{linea_detalles}\n".encode('latin-1')

        # Totales
        ticket += b"--------------------------------\n"
        ticket += CMD_CENTER + CMD_BOLD_ON
        ticket += f"TOTAL: ${self.total_acumulado:.2f}\n".encode('latin-1')
        ticket += CMD_BOLD_OFF + CMD_LEFT
        ticket += b"--------------------------------\n"
        ticket += f"PAGO:   ${pago:.2f}\n".encode('latin-1')
        ticket += f"VUELTO: ${vuelto:.2f}\n".encode('latin-1')
        ticket += b"\n"
        ticket += CMD_CENTER
        ticket += b"GRACIAS POR SU COMPRA\n"
        ticket += b"\n\n\n" + CMD_CUT

        # --- 4. ENVÍO A LA IMPRESORA ---
        try:
            hPrinter = win32print.OpenPrinter(NOMBRE_IMPRESORA)
            try:
                hJob = win32print.StartDocPrinter(hPrinter, 1, ("Ticket Agrupado", None, "RAW"))
                try:
                    win32print.StartPagePrinter(hPrinter)
                    win32print.WritePrinter(hPrinter, ticket)
                    win32print.EndPagePrinter(hPrinter)
                finally:
                    win32print.EndDocPrinter(hPrinter)
            finally:
                win32print.ClosePrinter(hPrinter)
        except Exception as e:
            # Usamos print en consola para no interrumpir al cajero con popups si falla la impresión
            print(f"Error imprimiendo: {e}")'''

    def obtener_bytes_imagen(self, ruta_imagen):
        """
        Convierte una imagen a comandos ESC/POS para impresora térmica.
        Usa la librería Pillow que ya instalamos.
        """
        try:
            from PIL import Image
            
            # 1. Abrir imagen
            # DESPUÉS (Funciona siempre):
            ruta_segura = ruta_recursos("logo_ticket.png")
            im = Image.open(ruta_segura)
            
            # 2. Redimensionar para 58mm (Máximo 384 puntos de ancho)
            ancho_max = 370 # Dejamos un margen pequeño
            
            # Calculamos la altura proporcional
            porcentaje = (ancho_max / float(im.size[0]))
            alto_nuevo = int((float(im.size[1]) * float(porcentaje)))
            im = im.resize((ancho_max, alto_nuevo), Image.Resampling.LANCZOS)
            
            # 3. Convertir a Blanco y Negro puro (1-bit)
            im = im.convert("1")

            # 4. Convertir la imagen a bytes ESC/POS (Comando GS v 0)
            # No te asustes con esta matemática, es el estándar de las impresoras
            ancho_bytes = (im.width + 7) // 8
            datos_imagen = b""
            
            # Recorremos la imagen pixel a pixel y empaquetamos bits
            datos_pixels = list(im.getdata())
            
            for y in range(im.height):
                fila_bytes = bytearray(ancho_bytes)
                for x in range(im.width):
                    if datos_pixels[y * im.width + x] == 0: # 0 es Negro en PIL '1' mode
                        # Encendemos el bit correspondiente
                        fila_bytes[x // 8] |= (1 << (7 - (x % 8)))
                datos_imagen += fila_bytes

            # 5. Construir el comando final
            # Cabecera: GS v 0 (Modo Raster)
            comando = b'\x1d\x76\x30\x00' 
            # Ancho en bytes (Little Endian format)
            comando += (ancho_bytes % 256).to_bytes(1, 'little')
            comando += (ancho_bytes // 256).to_bytes(1, 'little')
            # Alto en puntos (Little Endian format)
            comando += (im.height % 256).to_bytes(1, 'little')
            comando += (im.height // 256).to_bytes(1, 'little')
            # Los datos de la imagen
            comando += datos_imagen
            
            return comando

        except Exception as e:
            print(f"No se pudo procesar la imagen del ticket: {e}")
            return b"" # Si falla, devuelve vacío y no rompe nada



    def limpiar_pantalla(self):
        self.carrito = []
        self.total_acumulado = 0.0
        self.lbl_total.config(text="TOTAL: $0.00")
        for item in self.tree.get_children():
            self.tree.delete(item)

    def exportar_ventas_excel(self):
        try:
            # 1. Calcular el "Día Comercial"
            ahora = datetime.now()
            
            # CONFIGURACIÓN: ¿A qué hora empieza tu "nuevo día"?
            # Si pones 6, el día va de 06:00 AM de hoy a 05:59 AM de mañana.
            HORA_CORTE = 6 
            
            if ahora.hour < HORA_CORTE:
                # Si son las 3 AM, estamos procesando el cierre de "ayer"
                fecha_fin = ahora
                # La fecha de inicio fue ayer a las 6 AM
                fecha_inicio = (ahora - timedelta(days=1)).replace(hour=HORA_CORTE, minute=0, second=0)
            else:
                # Si son las 4 PM, estamos en el día actual normal
                fecha_inicio = ahora.replace(hour=HORA_CORTE, minute=0, second=0)
                fecha_fin = ahora # Hasta el momento actual

            # 2. Conectar a BD
            conexion = mysql.connector.connect(**self.db_config)
            
            # 3. Query con Rango de Fechas (BETWEEN)
            # Ya no usamos CURDATE(), usamos los parámetros que calculamos
            query = """
                SELECT 
                    v.id AS 'Nro Ticket',
                    v.fecha_venta AS 'Fecha Hora',
                    p.codigo_barras AS 'Código',
                    p.nombre AS 'Producto',
                    dv.cantidad AS 'Cantidad',
                    dv.precio_unitario AS 'Precio Unit.',
                    dv.subtotal AS 'Subtotal',
                    v.metodo_pago AS 'Método Pago'
                FROM ventas v
                JOIN detalle_ventas dv ON v.id = dv.id_venta
                JOIN productos p ON dv.id_producto = p.id
                WHERE v.fecha_venta BETWEEN %s AND %s
                ORDER BY v.id DESC
            """
            
            # Pandas necesita los parámetros en una tupla o lista
            df = pd.read_sql(query, conexion, params=(fecha_inicio, fecha_fin))
            conexion.close()

            if df.empty:
                messagebox.showinfo("Reporte", "No hay ventas en este turno.")
                return

            # 4. Guardar (Igual que antes)
            nombre_archivo = f"Cierre_Caja_{fecha_inicio.strftime('%d-%m-%Y')}.xlsx"
            
            filename = filedialog.asksaveasfilename(
                initialfile=nombre_archivo,
                defaultextension=".xlsx",
                filetypes=[("Archivos de Excel", "*.xlsx")]
            )

            if filename:
                # --- GUARDADO CON AUTO-AJUSTE DE COLUMNAS ---
                
                # Usamos un 'writer' para poder editar el excel antes de guardarlo
                with pd.ExcelWriter(filename, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False, sheet_name='Ventas')
                    
                    # Accedemos a la hoja de cálculo
                    worksheet = writer.sheets['Ventas']
                    
                    # Recorremos todas las columnas para ajustar el ancho
                    for i, column in enumerate(df.columns):
                        # Calculamos el ancho basándonos en el largo del texto más largo
                        # (Encabezado vs Contenido)
                        max_len = max(
                            df[column].astype(str).map(len).max(), # Largo del contenido
                            len(column) # Largo del título
                        )
                        
                        # Le sumamos 2 puntitos extra de margen para que no quede apretado
                        col_letter = get_column_letter(i + 1)
                        worksheet.column_dimensions[col_letter].width = max_len + 2
                
                messagebox.showinfo("Éxito", f"Reporte generado y formateado en:\n{filename}")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo exportar: {e}")

    def abrir_inventario(self):
        VentanaInventario(self.root, self.db_config)
    
    def abrir_lista_inventario(self):
        VentanaDetalleInventario(self.root, self.db_config)
   


# --- ARRANQUE ---
if __name__ == "__main__":
    root = tk.Tk()
    app = SistemaVentas(root)
    # --- MAGIA AQUÍ ---
    # Leemos la config y corremos el setup automático
    config = app.cargar_configuracion() 
    if config:
        # Llamamos a la función que acabamos de crear arriba
        inicializar_base_datos(config)
    # ------------------
    root.mainloop()