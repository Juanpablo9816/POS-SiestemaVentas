# -*- coding: utf-8 -*-

import tkinter as tk
from tkinter import ttk, messagebox
import mysql.connector
import requests
from database import Database
from models import ProductoSKU
from windows.searchable_combobox import SearchableCombobox

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
        self.top.geometry("800x600") # Ancho aumentado, altura reducida
        
        # --- Estilos y Variables ---
        self.COLOR_FONDO = "#e6e6e6"
        self.COLOR_VERDE = "#28a745"
        self.COLOR_AMARILLO = "#fff9c4"
        self.FONT_LABEL = ("Segoe UI", 10, "bold") # Reducir fuente para que quepa
        self.FONT_ENTRY = ("Segoe UI", 11) # Reducir fuente para que quepa
        
        self.top.configure(bg=self.COLOR_FONDO)
        
        self.placeholder_text = "Escribe aquí el nombre del nuevo producto..."
        # Variables de Tkinter para vincular a los campos de entrada.
        self.var_codigo = tk.StringVar()
        self.var_nombre = tk.StringVar(value=self.placeholder_text)
        self.var_precio = tk.DoubleVar(value=0.0)
        self.var_stock = tk.IntVar(value=0)
        self.var_tipo = tk.StringVar(value="Unidad")
        self.var_sku_generado = tk.StringVar(value="Se generará automáticamente")

        # Variables para los nuevos campos de SKU
        self.var_rubro = tk.StringVar()
        self.var_familia = tk.StringVar()
        self.producto_existente = False # Flag para saber si se está editando o creando.
        
        # --- Frame para Escanear Código ---
        frame_scan = tk.Frame(self.top, bg=self.COLOR_FONDO, pady=10) # Reducir pady
        frame_scan.pack(fill="x", padx=20)

        tk.Label(frame_scan, text="1. Escanea o escribe el Código:", bg=self.COLOR_FONDO, font=self.FONT_LABEL).pack(anchor="w")
        
        self.entry_codigo = tk.Entry(frame_scan, textvariable=self.var_codigo, font=("Courier New", 16, "bold"), 
                                     bg=self.COLOR_AMARILLO, justify="center", relief="sunken", bd=2)
        self.entry_codigo.pack(fill="x", ipady=6, pady=5)
        self.entry_codigo.bind('<Return>', self.buscar_y_configurar)
        self.entry_codigo.focus_set()

        # --- Frame para los Datos del Producto ---
        self.frame_datos = tk.Frame(self.top, bg="#ffffff", relief="groove", bd=2)
        self.frame_datos.pack(fill="both", expand=True, padx=20, pady=10)
        # Configurar 4 columnas para un layout más ancho
        self.frame_datos.columnconfigure(1, weight=1)
        self.frame_datos.columnconfigure(3, weight=1)

        # --- Fila 0: Nombre del Producto ---
        tk.Label(self.frame_datos, text="Nombre del Producto:", bg="#ffffff", font=self.FONT_LABEL).grid(row=0, column=0, sticky="w", padx=10, pady=5)
        self.entry_nombre = tk.Entry(self.frame_datos, textvariable=self.var_nombre, font=self.FONT_ENTRY, fg="black", relief="solid", bd=1)
        self.entry_nombre.bind("<FocusIn>", self.on_entry_focus_in)
        self.entry_nombre.bind("<FocusOut>", self.on_entry_focus_out)
        self.entry_nombre.bind("<KeyPress>", self.on_entry_key_press)
        # El grid para entry_nombre se gestiona en buscar_y_configurar

        # --- Fila 1: Precio y Stock ---
        validate_price = self.top.register(self.solo_decimales)
        tk.Label(self.frame_datos, text="Precio Venta ($):", bg="#ffffff", font=self.FONT_LABEL).grid(row=1, column=0, sticky="w", padx=10, pady=5)
        self.entry_precio = tk.Entry(self.frame_datos, textvariable=self.var_precio, font=self.FONT_ENTRY, justify="right", 
                                     relief="solid", bd=1, validate="key", validatecommand=(validate_price, '%P'))
        self.entry_precio.grid(row=1, column=1, sticky="ew", padx=10, ipady=4)

        validate_stock = self.top.register(self.solo_numeros)
        tk.Label(self.frame_datos, text="Stock Actual:", bg="#ffffff", font=self.FONT_LABEL).grid(row=1, column=2, sticky="w", padx=10, pady=5)
        self.entry_stock = tk.Entry(self.frame_datos, textvariable=self.var_stock, font=self.FONT_ENTRY, justify="center", 
                                    relief="solid", bd=1, validate="key", validatecommand=(validate_stock, '%P'))
        self.entry_stock.grid(row=1, column=3, sticky="ew", padx=10, ipady=4)
        
        # --- Fila 2: Tipo de Producto ---
        tk.Label(self.frame_datos, text="Tipo:", bg="#ffffff", font=self.FONT_LABEL).grid(row=2, column=0, sticky="w", padx=10, pady=5)
        self.combo_tipo = ttk.Combobox(self.frame_datos, textvariable=self.var_tipo, values=["Unidad", "Granel"], 
                                       state="readonly", font=self.FONT_ENTRY)
        self.combo_tipo.grid(row=2, column=1, sticky="ew", padx=10)
        self.combo_tipo.set("Unidad")

        # --- Separador para la sección de SKU ---
        ttk.Separator(self.frame_datos, orient='horizontal').grid(row=3, columnspan=4, sticky='ew', pady=10, padx=10)
        tk.Label(self.frame_datos, text="Definición de SKU (para productos nuevos)", bg="#ffffff", font=self.FONT_LABEL).grid(row=4, column=0, columnspan=4, sticky="w", padx=10)

        # --- Fila 5: Rubro y Familia ---
        tk.Label(self.frame_datos, text="Rubro:", bg="#ffffff", font=self.FONT_LABEL).grid(row=5, column=0, sticky="w", padx=10, pady=5)
        self.combo_rubro = ttk.Combobox(self.frame_datos, textvariable=self.var_rubro, state="readonly", font=self.FONT_ENTRY)
        self.combo_rubro.grid(row=5, column=1, sticky="ew", padx=10, ipady=4)
        self.combo_rubro.bind("<<ComboboxSelected>>", self.cargar_familias_por_rubro)

        tk.Label(self.frame_datos, text="Familia:", bg="#ffffff", font=self.FONT_LABEL).grid(row=5, column=2, sticky="w", padx=10, pady=5)
        self.combo_familia = ttk.Combobox(self.frame_datos, textvariable=self.var_familia, state="readonly", font=self.FONT_ENTRY)
        self.combo_familia.grid(row=5, column=3, sticky="ew", padx=10, ipady=4)
        self.combo_familia.bind("<<ComboboxSelected>>", self.cargar_atributos_por_familia)

        # --- Fila 6: Marca y Atributo 1 ---
        tk.Label(self.frame_datos, text="Marca:", bg="#ffffff", font=self.FONT_LABEL).grid(row=6, column=0, sticky="w", padx=10, pady=5)
        self.combo_marca = SearchableCombobox(self.frame_datos)
        self.combo_marca.grid(row=6, column=1, sticky="ew", padx=10)
        self.combo_marca.set_callback(self.generar_sku_preview)

        self.lbl_atributo_1 = tk.Label(self.frame_datos, text="Atributo 1:", bg="#ffffff", font=self.FONT_LABEL)
        self.lbl_atributo_1.grid(row=6, column=2, sticky="w", padx=10, pady=5)
        self.combo_atributo_1 = SearchableCombobox(self.frame_datos)
        self.combo_atributo_1.grid(row=6, column=3, sticky="ew", padx=10)
        self.combo_atributo_1.set_callback(self.generar_sku_preview)
        
        # --- Fila 7: Atributo 2 ---
        self.lbl_atributo_2 = tk.Label(self.frame_datos, text="Atributo 2:", bg="#ffffff", font=self.FONT_LABEL)
        self.lbl_atributo_2.grid(row=7, column=0, sticky="w", padx=10, pady=5)
        self.combo_atributo_2 = SearchableCombobox(self.frame_datos)
        self.combo_atributo_2.grid(row=7, column=1, sticky="ew", padx=10)
        self.combo_atributo_2.set_callback(self.generar_sku_preview)
        
        # --- Fila 8: SKU Generado ---
        tk.Label(self.frame_datos, text="SKU Generado:", bg="#ffffff", font=self.FONT_LABEL).grid(row=8, column=0, sticky="w", padx=10, pady=15)
        self.lbl_sku = tk.Label(self.frame_datos, textvariable=self.var_sku_generado, bg="#ffffff", font=("Courier New", 12, "bold"), fg="blue")
        self.lbl_sku.grid(row=8, column=1, columnspan=3, sticky="w", padx=10, pady=15)

        # Cargar opciones para los comboboxes al iniciar
        self.cargar_opciones_combobox()
        
        # --- Botones de Acción (Guardar) ---
        frame_btns = tk.Frame(self.top, bg=self.COLOR_FONDO, pady=10)
        frame_btns.pack(fill="x", side="bottom") # Fijar en la parte inferior
        self.btn_guardar = tk.Button(frame_btns, text="💾 GUARDAR DATOS", font=("Arial", 12, "bold"), 
                                     bg=self.COLOR_VERDE, fg="white", relief="raised", bd=3, command=self.guardar_producto)
        self.btn_guardar.pack(side="right", padx=20, ipadx=15, ipady=4)
        self.lbl_mensaje = tk.Label(frame_btns, text="", font=("Arial", 11), bg=self.COLOR_FONDO)
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
            self.entry_nombre.config(fg="black")
    
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
        self.top.after(600, lambda: (self.entry_nombre.config(bg=color_original, fg="black")))
    
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
            
            self.entry_nombre.grid(row=0, column=1, columnspan=3, sticky="ew", padx=10, ipady=4)

            if producto_local:
                self.producto_existente = True
                self.btn_guardar.config(text="💾 ACTUALIZAR DATOS", bg="#007bff")
                self.var_nombre.set(producto_local['nombre'])
                self.var_precio.set(producto_local['precio_venta'])
                self.var_stock.set(producto_local['stock_actual'])
                self.var_tipo.set(producto_local.get('tipo', 'Unidad'))
                self.var_sku_generado.set(producto_local.get('sku', "No disponible")) # Cargar SKU existente

                # Cargar y seleccionar los valores de Rubro, Familia, Marca, Atributos si el SKU existe
                if producto_local.get('sku'):
                    try:
                        db = Database(self.db_config)
                        db.connect()
                        query = """
                            SELECT 
                                r.nombre as rubro_nombre, 
                                f.nombre as familia_nombre, 
                                m.nombre as marca_nombre, 
                                va1.valor as atributo1_valor, 
                                va2.valor as atributo2_valor
                            FROM producto_sku ps
                            JOIN familia f ON ps.familia_id = f.id
                            JOIN rubro r ON f.rubro_id = r.id
                            JOIN marca m ON ps.marca_id = m.id
                            JOIN valores_atributos va1 ON ps.atributo_1_id = va1.id
                            JOIN valores_atributos va2 ON ps.atributo_2_id = va2.id
                            WHERE ps.sku = %s
                        """
                        db.cursor.execute(query, (producto_local['sku'],))
                        sku_details = db.cursor.fetchone()
                        db.disconnect()

                        if sku_details:
                            self.var_rubro.set(sku_details['rubro_nombre'])
                            self.cargar_familias_por_rubro() # Actualiza las familias disponibles para el rubro
                            self.var_familia.set(sku_details['familia_nombre'])
                            self.cargar_atributos_por_familia() # Actualiza los labels de atributos
                            self.combo_marca.set(sku_details['marca_nombre'])
                            self.combo_atributo_1.set(sku_details['atributo1_valor'])
                            self.combo_atributo_2.set(sku_details['atributo2_valor'])
                        
                    except Exception as e:
                        print(f"Error al cargar detalles del SKU: {e}")
                
                self.entry_precio.focus_set()
                self.entry_precio.select_range(0, tk.END)
            else:
                self.producto_existente = False
                self.btn_guardar.config(text="💾 GUARDAR NUEVO", bg=self.COLOR_VERDE)
                
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
                self.var_sku_generado.set("Se generará automáticamente") # Reset SKU preview for new product
                self.entry_nombre.focus_set()

            cursor.close()
            conexion.close()
            self.generar_sku_preview() # Asegurarse de que el SKU se muestre o se genere si es un producto nuevo.
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
        sku_generado = self.var_sku_generado.get()

        if not codigo or not nombre or nombre == self.placeholder_text or not txt_precio: 
            self.mostrar_mensaje("Faltan datos obligatorios", "red"); return
        
        # Validar si el SKU fue generado correctamente, si es un producto nuevo.
        if not self.producto_existente and (sku_generado == "Se generará automáticamente" or "Error SKU" in sku_generado or "Faltan selecciones" in sku_generado):
            self.mostrar_mensaje("Debe seleccionar todos los atributos para generar el SKU", "red")
            return

        try:
            precio_final = float(txt_precio)
            stock_final = int(txt_stock) if txt_stock else 0
        except ValueError:
            self.mostrar_mensaje("Precio o stock inválido", "red"); return

        try:
            conexion = mysql.connector.connect(**self.db_config)
            cursor = conexion.cursor()
            
            if self.producto_existente:
                sql = "UPDATE productos SET nombre=%s, precio_venta=%s, stock_actual=%s, tipo=%s, sku=%s WHERE codigo_barras=%s"
                cursor.execute(sql, (nombre, precio_final, stock_final, tipo, sku_generado, codigo))
                texto_exito = "✅ Producto Actualizado"
            else:
                sql = "INSERT INTO productos (codigo_barras, nombre, precio_venta, stock_actual, tipo, sku) VALUES (%s, %s, %s, %s, %s, %s)"
                cursor.execute(sql, (codigo, nombre, precio_final, stock_final, tipo, sku_generado))
                
                # Usar la misma lógica de get_or_create que en la vista previa para asegurar consistencia
                db_temp = Database(self.db_config)
                db_temp.connect()
                
                familia_id = next((f[0] for f in self.familias if f[1] == self.var_familia.get()), None)
                
                marca_nombre = self.combo_marca.get()
                marca_id = db_temp.get_or_create('marca', {'nombre': marca_nombre})
                
                attr1_nombre = self.combo_atributo_1.get()
                attr1_id = db_temp.get_or_create('valores_atributos', {'valor': attr1_nombre})
                
                attr2_nombre = self.combo_atributo_2.get()
                attr2_id = db_temp.get_or_create('valores_atributos', {'valor': attr2_nombre})
                
                db_temp.disconnect()

                if all([sku_generado, familia_id, marca_id, attr1_id, attr2_id]):
                    sql_sku = "INSERT IGNORE INTO producto_sku (sku, familia_id, marca_id, atributo_1_id, atributo_2_id) VALUES (%s, %s, %s, %s, %s)"
                    cursor.execute(sql_sku, (sku_generado, familia_id, marca_id, attr1_id, attr2_id))

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
        self.limpiar_formulario_sku()
        self.entry_nombre.grid_forget()
        self.producto_existente = False
        self.btn_guardar.config(text="💾 GUARDAR DATOS", bg=self.COLOR_VERDE)
    
    def limpiar_formulario_sku(self):
        self.var_rubro.set(self.rubros[0][1] if self.rubros else "")
        self.cargar_familias_por_rubro()
        self.combo_marca.set(self.marcas[0][1] if self.marcas else "")
        self.combo_atributo_1.set(self.valores_atributos[0][1] if self.valores_atributos else "")
        self.combo_atributo_2.set(self.valores_atributos[0][1] if self.valores_atributos else "")
        self.var_sku_generado.set("Se generará automáticamente")


    def _get_db_options(self, table_name, value_column_name='nombre'):
        """Helper para obtener opciones de una tabla simple (id,      ││     nombre/valor), asegurando que el ID 1 esté al principio."""
        options = []
        try:
            db = Database(self.db_config)
            db.connect()
            # Fetch the ID=1 option first, if it exists               ││ 418 -         default_option = db.fetchone(f"SELECT id,                 ││     {value_column_name} FROM {table_name} WHERE id = 1")                ││ 419 -         if default_option:                                        ││ 420 -             options.append((default_option['id'],                 ││     default_option[value_column_name]))                                 ││ 421 -                                                                   ││ 422 -         # Fetch all other options, excluding ID=1, and sort them  ││ 423 -         query = f"SELECT id, {value_column_name} FROM             ││     {table_name} WHERE id != 1 ORDER BY {value_column_name}"            ││ 424 -         db.cursor.execute(query) 
            default_option = db.fetchone(f"SELECT id, {value_column_name} FROM {table_name} WHERE id = 1")
            if default_option:
                options.append((default_option['id'], default_option[value_column_name]))

            # Fetch all other options, excluding ID=1, and sort them
            query = f"SELECT id, {value_column_name} FROM {table_name} WHERE id != 1 ORDER BY {value_column_name}"
            db.cursor.execute(query)
            for row in db.cursor.fetchall():
                options.append((row['id'], row[value_column_name]))
            db.disconnect()
        except Exception as e:
            messagebox.showerror("Error de BD", f"No se pudieron cargar las opciones para {table_name}: {e}")
        return options

    def cargar_opciones_combobox(self):
        """Carga las opciones iniciales para los comboboxes de Rubro, Marca y Atributos."""
        self.rubros = self._get_db_options("rubro")
        self.combo_rubro['values'] = [r[1] for r in self.rubros]

        self.marcas = self._get_db_options("marca")
        self.combo_marca.values = [m[1] for m in self.marcas]

        self.valores_atributos = self._get_db_options("valores_atributos", "valor")
        attr_values = [v[1] for v in self.valores_atributos]
        self.combo_atributo_1.values = attr_values
        self.combo_atributo_2.values = attr_values
        
        self.limpiar_formulario_sku()

    def cargar_familias_por_rubro(self, event=None):
        """Carga las familias según el rubro seleccionado."""
        rubro_seleccionado_nombre = self.var_rubro.get()
        rubro_id = next((r[0] for r in self.rubros if r[1] == rubro_seleccionado_nombre), None)
        
        self.familias = []
        if rubro_id:
            try:
                db = Database(self.db_config)
                db.connect()
                db.cursor.execute("SELECT id, nombre FROM familia WHERE rubro_id = %s ORDER BY nombre", (rubro_id,))
                for row in db.cursor.fetchall():
                    self.familias.append((row['id'], row['nombre']))
                db.disconnect()
            except Exception as e:
                messagebox.showerror("Error de BD", f"No se pudieron cargar las familias: {e}")
        
        self.combo_familia['values'] = [f[1] for f in self.familias]
        if self.familias:
            self.var_familia.set(self.familias[0][1])
        else:
            self.var_familia.set("")
        
        self.cargar_atributos_por_familia()

    def cargar_atributos_por_familia(self, event=None):
        """Carga las etiquetas de los atributos para la familia seleccionada y actualiza los labels."""
        familia_seleccionada_nombre = self.var_familia.get()
        familia_id = next((f[0] for f in self.familias if f[1] == familia_seleccionada_nombre), None)
        
        label1, label2 = "Atributo 1", "Atributo 2"
        if familia_id:
            try:
                db = Database(self.db_config)
                db.connect()
                resultado = db.fetchone("SELECT label_atributo_1, label_atributo_2 FROM definicion_atributos WHERE familia_id = %s", (familia_id,))
                if resultado:
                    if resultado['label_atributo_1']: label1 = resultado['label_atributo_1']
                    if resultado['label_atributo_2']: label2 = resultado['label_atributo_2']
                db.disconnect()
            except Exception as e:
                messagebox.showerror("Error de BD", f"No se pudieron cargar las etiquetas de atributos: {e}")

        self.lbl_atributo_1.config(text=f"{label1}:")
        self.lbl_atributo_2.config(text=f"{label2}:")
        self.generar_sku_preview()

    def generar_sku_preview(self, event=None):
        """Genera un SKU de prueba y lo muestra en el Label."""
        # Se enlaza a los eventos de selección de los combobox para que se actualice en tiempo real
        try:
            familia_id = next((f[0] for f in self.familias if f[1] == self.var_familia.get()), None)
            marca_nombre = self.combo_marca.get()
            attr1_nombre = self.combo_atributo_1.get()
            attr2_nombre = self.combo_atributo_2.get()
            
            # Validar que los campos editables no estén vacíos
            if not all([familia_id, marca_nombre, attr1_nombre, attr2_nombre]):
                self.var_sku_generado.set("Faltan selecciones para generar SKU")
                return

            # Obtener IDs de tablas de atributos (o crearlos si no existen)
            db = Database(self.db_config)
            db.connect()
            
            marca_id = db.get_or_create('marca', {'nombre': marca_nombre})
            attr1_id = db.get_or_create('valores_atributos', {'valor': attr1_nombre})
            attr2_id = db.get_or_create('valores_atributos', {'valor': attr2_nombre})

            producto_sku_gen = ProductoSKU(self.db_config, familia_id, marca_id, attr1_id, attr2_id)
            self.var_sku_generado.set(producto_sku_gen.generar_sku())
            db.disconnect()

        except Exception as e:
            self.var_sku_generado.set(f"Error SKU: {e}")
