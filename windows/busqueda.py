# -*- coding: utf-8 -*-

import tkinter as tk
from tkinter import ttk, messagebox
import mysql.connector
from database import Database
from windows.searchable_combobox import SearchableCombobox

class VentanaBusquedaProducto:
    """
    Ventana emergente para buscar productos por nombre y/o atributos de SKU y agregarlos al carrito.
    """
    def __init__(self, master, db_config, callback_agregar):
        self.top = tk.Toplevel(master)
        self.top.title("Búsqueda Avanzada de Producto")
        self.top.geometry("1000x700")
        self.top.grab_set()

        self.db_config = db_config
        self.callback_agregar = callback_agregar
        
        # --- Variables de SKU ---
        self.var_rubro = tk.StringVar()
        self.var_familia = tk.StringVar()
        self.COLOR_AZUL = "#007bff"
        # --- Build UI ---
        self._build_ui()
        
        # --- Cargar datos iniciales ---
        self.cargar_opciones_combobox()

    def _build_ui(self):
        """Construye la interfaz de usuario de la ventana de búsqueda."""
        
        # --- Frame de Filtros ---
        filter_frame = tk.LabelFrame(self.top, text="Filtros de Búsqueda", padx=10, pady=10, font=("Segoe UI", 10, "bold"))
        filter_frame.pack(fill="x", padx=10, pady=5)
        
        # Configurar columnas para el layout de filtros
        for i in range(6):
            filter_frame.columnconfigure(i, weight=1, uniform="group1")

        # Fila 1: Rubro y Familia
        tk.Label(filter_frame, text="Rubro:").grid(row=0, column=0, sticky="w", padx=5, pady=2)
        self.combo_rubro = ttk.Combobox(filter_frame, textvariable=self.var_rubro, state="readonly")
        self.combo_rubro.grid(row=0, column=1, sticky="ew", padx=5, pady=2)
        self.combo_rubro.bind("<<ComboboxSelected>>", self.cargar_familias_por_rubro)

        tk.Label(filter_frame, text="Familia:").grid(row=0, column=2, sticky="w", padx=5, pady=2)
        self.combo_familia = ttk.Combobox(filter_frame, textvariable=self.var_familia, state="readonly")
        self.combo_familia.grid(row=0, column=3, sticky="ew", padx=5, pady=2)
        
        # Fila 2: Marca y Atributos
        tk.Label(filter_frame, text="Marca:").grid(row=1, column=0, sticky="w", padx=5, pady=2)
        self.combo_marca = SearchableCombobox(filter_frame)
        self.combo_marca.grid(row=1, column=1, sticky="ew", padx=5, pady=2)

        tk.Label(filter_frame, text="Atributo 1:").grid(row=1, column=2, sticky="w", padx=5, pady=2)
        self.combo_atributo_1 = SearchableCombobox(filter_frame)
        self.combo_atributo_1.grid(row=1, column=3, sticky="ew", padx=5, pady=2)

        tk.Label(filter_frame, text="Atributo 2:").grid(row=1, column=4, sticky="w", padx=5, pady=2)
        self.combo_atributo_2 = SearchableCombobox(filter_frame)
        self.combo_atributo_2.grid(row=1, column=5, sticky="ew", padx=5, pady=2)

        # Fila 3: Búsqueda por texto y botón de filtrar
        tk.Label(filter_frame, text="Nombre/Código:").grid(row=2, column=0, sticky="w", padx=5, pady=5)
        self.entry_buscar = tk.Entry(filter_frame, font=("Segoe UI", 10))
        self.entry_buscar.grid(row=2, column=1, columnspan=3, sticky="ew", padx=5, pady=5)
        self.entry_buscar.focus_set()
        
        btn_filtrar = tk.Button(filter_frame, text="🔍 Filtrar", font=("Segoe UI", 10, "bold"), bg="#007bff", fg="white", command=self.filtrar_productos)
        btn_filtrar.grid(row=2, column=4, sticky="ew", padx=5, pady=5, ipady=3)
        
        btn_limpiar = tk.Button(filter_frame, text="Limpiar", font=("Segoe UI", 10), command=self.limpiar_filtros)
        btn_limpiar.grid(row=2, column=5, sticky="ew", padx=5, pady=5, ipady=3)


        # --- Treeview para resultados ---
        frame_tree = tk.Frame(self.top)
        frame_tree.pack(fill="both", expand=True, padx=10, pady=5)
        
        style = ttk.Style()
        style.configure("Treeview", background="white", rowheight=40, fieldbackground="white", font=("Arial", 14))
        style.configure("Treeview.Heading", font=("Arial", 14, "bold"), background="#444", foreground="black")
        style.map("Treeview", background=[('selected',self.COLOR_AZUL)])


        columns = ("ID", "Nombre", "Precio", "Stock", "SKU")
        self.tree = ttk.Treeview(frame_tree, columns=columns, show='headings')
        self.tree.heading("ID", text="ID"); self.tree.column("ID", width=60)
        self.tree.heading("Nombre", text="Nombre del Producto"); self.tree.column("Nombre", width=450)
        self.tree.heading("Precio", text="Precio"); self.tree.column("Precio", width=100, anchor="e")
        self.tree.heading("Stock", text="Stock"); self.tree.column("Stock", width=80, anchor="center")
        self.tree.heading("SKU", text="SKU"); self.tree.column("SKU", width=150)

        self.tree.pack(side="left", fill="both", expand=True)
        self.tree.bind("<Double-1>", self.seleccionar_y_cerrar)
        self.tree.bind("<Return>", self.seleccionar_y_cerrar)

        scrollbar = ttk.Scrollbar(frame_tree, orient="vertical", command=self.tree.yview)
        scrollbar.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        # --- Botón de Agregar ---
        btn_frame = tk.Frame(self.top, pady=10)
        btn_frame.pack(fill="x")
        tk.Button(btn_frame, text="✔ Agregar Producto Seleccionado", bg="#28a745", fg="white", font=("Segoe UI", 12, "bold"), command=self.seleccionar_y_cerrar).pack(ipadx=10, ipady=5)

    def _get_db_options(self, table_name, value_column_name='nombre'):
        """Helper para obtener opciones de una tabla simple (id, nombre/valor)."""
        options = []
        try:
            db = Database(self.db_config)
            db.connect()
            db.cursor.execute(f"SELECT id, {value_column_name} FROM {table_name} ORDER BY {value_column_name}")
            for row in db.cursor.fetchall():
                options.append((row['id'], row[value_column_name]))
            db.disconnect()
        except Exception as e:
            messagebox.showerror("Error de BD", f"No se pudieron cargar las opciones para {table_name}: {e}")
        return options

    def cargar_opciones_combobox(self):
        """Carga las opciones iniciales para los filtros."""
        self.rubros = self._get_db_options("rubro")
        self.combo_rubro['values'] = [""] + [r[1] for r in self.rubros]

        self.marcas = self._get_db_options("marca")
        self.combo_marca.values = [""] + [m[1] for m in self.marcas]

        self.valores_atributos = self._get_db_options("valores_atributos", "valor")
        attr_values = [""] + [v[1] for v in self.valores_atributos]
        self.combo_atributo_1.values = attr_values
        self.combo_atributo_2.values = attr_values
        
        self.limpiar_filtros()

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
        
        self.combo_familia['values'] = [""] + [f[1] for f in self.familias]
        self.var_familia.set("")

    def limpiar_filtros(self):
        """Limpia todos los campos de filtro a su estado inicial."""
        self.var_rubro.set("")
        self.var_familia.set("")
        self.combo_familia['values'] = [""]
        self.combo_marca.set("")
        self.combo_atributo_1.set("")
        self.combo_atributo_2.set("")
        self.entry_buscar.delete(0, tk.END)

    def filtrar_productos(self):
        """Construye una consulta SQL basada en los filtros y actualiza el Treeview."""
        # Limpiar resultados anteriores
        for item in self.tree.get_children():
            self.tree.delete(item)

        # Construcción de la consulta SQL
        base_query = """
            SELECT p.id, p.codigo_barras, p.nombre, p.precio_venta, p.stock_actual, p.tipo, p.sku
            FROM productos p
            LEFT JOIN producto_sku ps ON p.sku = ps.sku
            LEFT JOIN familia f ON ps.familia_id = f.id
            LEFT JOIN rubro r ON f.rubro_id = r.id
            LEFT JOIN marca m ON ps.marca_id = m.id
            LEFT JOIN valores_atributos va1 ON ps.atributo_1_id = va1.id
            LEFT JOIN valores_atributos va2 ON ps.atributo_2_id = va2.id
        """
        conditions = []
        params = []

        # Filtro por texto (nombre o código de barras)
        texto_busqueda = self.entry_buscar.get()
        if texto_busqueda:
            conditions.append("(p.nombre LIKE %s OR p.codigo_barras LIKE %s)")
            params.extend([f"%{texto_busqueda}%", f"%{texto_busqueda}%"])

        # Filtros de SKU
        if self.var_rubro.get():
            conditions.append("r.nombre = %s")
            params.append(self.var_rubro.get())
        if self.var_familia.get():
            conditions.append("f.nombre = %s")
            params.append(self.var_familia.get())
        if self.combo_marca.get():
            conditions.append("m.nombre = %s")
            params.append(self.combo_marca.get())
        if self.combo_atributo_1.get():
            conditions.append("va1.valor = %s")
            params.append(self.combo_atributo_1.get())
        if self.combo_atributo_2.get():
            conditions.append("va2.valor = %s")
            params.append(self.combo_atributo_2.get())

        if conditions:
            base_query += " WHERE " + " AND ".join(conditions)
        
        base_query += " ORDER BY p.nombre ASC"

        try:
            db = Database(self.db_config)
            db.connect()
            self.productos_filtrados = db.fetchall(base_query, tuple(params))
            db.disconnect()
            
            for p in self.productos_filtrados:
                self.tree.insert("", "end", values=(
                    p['id'], p['nombre'], f"${p['precio_venta']:.2f}", p['stock_actual'], p.get('sku', '')
                ))
        except mysql.connector.Error as err:
            messagebox.showerror("Error de Búsqueda", f"No se pudieron filtrar los productos: {err}", parent=self.top)

    def seleccionar_y_cerrar(self, event=None):
        """Obtiene el producto seleccionado, lo pasa al callback y cierra la ventana."""
        seleccion = self.tree.selection()
        if not seleccion:
            messagebox.showwarning("Sin Selección", "Por favor, selecciona un producto de la lista.", parent=self.top)
            return

        try:
            item_id = int(self.tree.item(seleccion[0])['values'][0])
            producto_seleccionado = next((p for p in self.productos_filtrados if p['id'] == item_id), None)
            
            if producto_seleccionado:
                self.callback_agregar(producto_seleccionado)
                self.top.destroy()
            else:
                messagebox.showerror("Error", "No se pudo encontrar el producto seleccionado.", parent=self.top)
        
        except (ValueError, IndexError):
            messagebox.showerror("Error", "No se pudo obtener el ID del producto seleccionado.", parent=self.top)
