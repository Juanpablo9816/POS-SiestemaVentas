# -*- coding: utf-8 -*-

import tkinter as tk
from tkinter import ttk, messagebox
import mysql.connector

class VentanaDetalleInventario:
    """
    Crea una ventana que muestra un listado completo de todos los productos en el inventario,
    con la capacidad de buscar y filtrar. El diseño se alinea con el resto del proyecto.
    """
    def __init__(self, master, db_config):
        """
        Inicializa la ventana de detalle de inventario.
        - `master`: La ventana principal.
        - `db_config`: La configuración de la base de datos.
        """
        self.top = tk.Toplevel(master)
        self.top.title("Inventario General")
        self.top.geometry("1200x700")
        self.db_config = db_config
        self.todos_los_productos = []  # Almacenar todos los productos para un filtrado rápido

        # --- Estilos Consistentes ---
        self.COLOR_FONDO = "#e6e6e6"
        self.COLOR_AZUL = "#007bff"
        self.top.configure(bg=self.COLOR_FONDO)

        # --- Frame Superior (Cabecera) ---
        frame_top = tk.Frame(self.top, bg=self.COLOR_AZUL, pady=10, relief="raised", bd=3)
        frame_top.pack(fill="x", side="top")
        tk.Label(frame_top, text="Listado General de Inventario", bg=self.COLOR_AZUL, fg="white", font=("Segoe UI", 18, "bold")).pack()

        # --- Frame de Controles (Búsqueda y Actualización) ---
        frame_controls = tk.Frame(self.top, bg=self.COLOR_FONDO, pady=10)
        frame_controls.pack(fill="x", padx=10)

        tk.Label(frame_controls, text="Buscar por Nombre/Código/SKU:", bg=self.COLOR_FONDO, font=("Segoe UI", 10)).pack(side="left", padx=(0, 5))
        self.entry_buscar = tk.Entry(frame_controls, width=40, font=("Segoe UI", 11))
        self.entry_buscar.pack(side="left", fill="x", expand=True, padx=5)
        self.entry_buscar.bind('<KeyRelease>', self.filtrar_datos)

        tk.Button(frame_controls, text="🔄 Actualizar Lista", font=("Segoe UI", 10, "bold"), bg="#28a745", fg="white", command=self.cargar_datos).pack(side="right", padx=10, ipadx=10)

        # --- Estilo y Creación de la Tabla de Productos (Treeview) ---
        style = ttk.Style()
        style.configure("Treeview.Heading", font=("Segoe UI", 11, "bold"), background="#444", foreground="black")
        style.configure("Treeview", rowheight=30, font=("Segoe UI", 10))
        style.map("Treeview", background=[('selected', self.COLOR_AZUL)])

        frame_tree = tk.Frame(self.top)
        frame_tree.pack(fill="both", expand=True, padx=10, pady=5)

        columns = ("ID", "Codigo", "Producto", "Precio", "Stock", "Valor Total", "SKU")
        self.tree = ttk.Treeview(frame_tree, columns=columns, show='headings')
        
        self.tree.heading("ID", text="ID")
        self.tree.heading("Codigo", text="Cód. Barras")
        self.tree.heading("Producto", text="Descripción")
        self.tree.heading("Precio", text="Precio Venta")
        self.tree.heading("Stock", text="Stock")
        self.tree.heading("Valor Total", text="Valor en Stock")
        self.tree.heading("SKU", text="SKU")

        self.tree.column("ID", width=60, anchor="center")
        self.tree.column("Codigo", width=130, anchor="center")
        self.tree.column("Producto", width=400, anchor="w")
        self.tree.column("Precio", width=100, anchor="e")
        self.tree.column("Stock", width=80, anchor="center")
        self.tree.column("Valor Total", width=120, anchor="e")
        self.tree.column("SKU", width=150, anchor="center")

        scrollbar = ttk.Scrollbar(frame_tree, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)
        
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.tree.tag_configure('low_stock', background='#fff0f0', foreground='#a00000')
        self.tree.tag_configure('normal_stock', background='white')

        # --- Barra de Estado Inferior ---
        frame_stats = tk.Frame(self.top, bg="#444", pady=8)
        frame_stats.pack(fill="x", side="bottom")
        self.lbl_info = tk.Label(frame_stats, text="Cargando...", fg="white", bg="#444", font=("Segoe UI", 10, "bold"))
        self.lbl_info.pack()

        self.cargar_datos()

    def cargar_datos(self):
        """
        Limpia la tabla y vuelve a cargar todos los productos desde la base de datos a una lista local,
        luego llama a `actualizar_treeview` para poblar la tabla.
        """
        try:
            conexion = mysql.connector.connect(**self.db_config)
            cursor = conexion.cursor(dictionary=True)
            cursor.execute("SELECT id, codigo_barras, nombre, precio_venta, stock_actual, sku FROM productos ORDER BY nombre ASC")
            self.todos_los_productos = cursor.fetchall()
            cursor.close()
            conexion.close()
            
            self.entry_buscar.delete(0, tk.END)
            self.actualizar_treeview(self.todos_los_productos)

        except mysql.connector.Error as err:
            messagebox.showerror("Error de Carga", f"No se pudieron cargar los productos: {err}", parent=self.top)

    def filtrar_datos(self, event=None):
        """
        Filtra la lista local de productos `self.todos_los_productos` y actualiza el Treeview.
        """
        busqueda = self.entry_buscar.get().lower()
        if not busqueda:
            productos_filtrados = self.todos_los_productos
        else:
            productos_filtrados = []
            for p in self.todos_los_productos:
                nombre_val = p.get('nombre', '').lower()
                codigo_val = p.get('codigo_barras', '')
                sku_val = p.get('sku', '') or "" # Manejar SKU que pueda ser None
                
                if busqueda in nombre_val or busqueda in codigo_val or busqueda in sku_val.lower():
                    productos_filtrados.append(p)
        
        self.actualizar_treeview(productos_filtrados)

    def actualizar_treeview(self, productos):
        """
        Limpia el Treeview y lo llena con la lista de productos proporcionada.
        Calcula estadísticas y aplica estilos.
        """
        for item in self.tree.get_children():
            self.tree.delete(item)

        total_inventario_dinero = 0
        total_items = len(productos)

        for p in productos:
            valor_stock = p.get('precio_venta', 0) * p.get('stock_actual', 0)
            total_inventario_dinero += valor_stock
            tag = 'low_stock' if p.get('stock_actual', 0) <= 5 else 'normal_stock'

            self.tree.insert("", "end", values=(
                p.get('id', ''),
                p.get('codigo_barras', ''),
                p.get('nombre', ''),
                f"${p.get('precio_venta', 0):.2f}",
                p.get('stock_actual', 0),
                f"${valor_stock:,.2f}",
                p.get('sku', '')
            ), tags=(tag,))

        # Formateo con separadores de miles
        total_inventario_str = f"${total_inventario_dinero:,.2f}"
        self.lbl_info.config(text=f"Mostrando: {total_items} productos  |  Valor Total del Inventario Filtrado: {total_inventario_str}")
