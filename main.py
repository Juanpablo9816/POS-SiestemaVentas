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
import win32print
from PIL import Image, ImageTk
import ctypes

from database import inicializar_base_datos
from utils import resolver_ruta

# Importaciones de las ventanas
from windows.listado_inventario import VentanaDetalleInventario
from windows.inventario import VentanaInventario
from windows.busqueda import VentanaBusquedaProducto
from windows.cobro import VentanaCobro
from windows.granel import VentanaVentaGranel
from windows.no_encontrado import VentanaProductoNoEncontrado
from windows.gestion_atributos import VentanaGestionAtributos

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
            
        # --- Definición de Estilos ---
        self.COLOR_FONDO = "#e6e6e6"
        self.COLOR_VERDE = "#28a745"
        self.COLOR_AZUL = "#007bff"
        self.FONT_BOLD = ("Segoe UI", 14, "bold")
        self.FONT_BIG = ("Segoe UI", 18, "bold")
        self.FONT_HUGE = ("Segoe UI", 30, "bold")

        # Asegura que la base de datos y las tablas existan antes de continuar.
        self.inicializar_base_datos_segura()
        
        # Llama al método que crea todos los elementos visuales de la ventana principal.
        self.construir_interfaz()

    def construir_interfaz(self):
        """
        Crea y organiza todos los widgets (elementos visuales) de la ventana principal.
        Define la apariencia de la aplicación, desde los botones hasta la tabla del carrito.
        """
        self.root.configure(bg=self.COLOR_FONDO)

        # --- Frame Superior (Cabecera) ---
        frame_top = tk.Frame(self.root, bg=self.COLOR_AZUL, pady=5, relief="raised", bd=5)
        frame_top.pack(fill="x", side="top")

        # Carga y muestra el logo de la tienda en la cabecera.
        try:
            img_pil = Image.open(resolver_ruta("logo.png")).resize((70, 70), Image.LANCZOS)
            self.logo_img = ImageTk.PhotoImage(img_pil)
            lbl_logo = tk.Label(frame_top, image=self.logo_img, bg=self.COLOR_AZUL)
            lbl_logo.pack(side="left", padx=(10, 5)) 
            lbl_logo.image = self.logo_img 
        except Exception as e:
            print(f"No se pudo cargar el logo: {e}")

        # Título principal de la aplicación.
        tk.Label(frame_top, text="SISTEMA DE VENTAS", bg=self.COLOR_AZUL, fg="white", font=("Arial", 24, "bold")).pack(side="left")
        
        # --- Frame de Acciones (Botones de Inventario y Exportación) ---
        frame_acciones = tk.Frame(self.root, bg=self.COLOR_FONDO, pady=10)
        frame_acciones.pack(fill="x", side="top")

        # Botones para abrir las ventanas de inventario y para exportar ventas.
        tk.Button(frame_acciones, text="📦 Inventario", font=self.FONT_BOLD, relief="raised", bd=4, bg="white", command=self.abrir_lista_inventario).pack(side="left", padx=5)
        tk.Button(frame_acciones, text="➕ Nuevo Producto", font=self.FONT_BOLD, relief="raised", bd=4, bg="white", command=self.abrir_inventario).pack(side="left", padx=5)
        tk.Button(frame_acciones, text="🔍 Buscar Producto", font=self.FONT_BOLD, relief="raised", bd=4, bg="#ffc107", command=self.abrir_busqueda_producto).pack(side="left", padx=5)
        tk.Button(frame_acciones, text="📊 Exportar Ventas Hoy", font=self.FONT_BOLD, bg="#217346", fg="white", relief="raised", bd=4, command=self.exportar_ventas_excel).pack(side="left", padx=5, ipady=5)
        tk.Button(frame_acciones, text="⚙️ Gestionar Atributos", font=self.FONT_BOLD, bg="#6c757d", fg="white", relief="raised", bd=4, command=self.abrir_gestion_atributos).pack(side="left", padx=5, ipady=5)

        # --- Frame de Escaneo de Productos ---
        frame_scan = tk.Frame(self.root, bg=self.COLOR_FONDO, pady=10)
        frame_scan.pack(fill="x", side="top", padx=20)

        tk.Label(frame_scan, text="Escanea el Código:", bg=self.COLOR_FONDO, font=self.FONT_BIG).pack(anchor="w")
        # Campo de entrada para el código de barras del producto.
        self.entry_codigo = tk.Entry(frame_scan, font=("Courier New", 20, "bold"), bg="#fff9c4", justify="center", bd=2, relief="sunken")
        self.entry_codigo.pack(fill="x", ipady=10)
        self.entry_codigo.bind('<Return>', self.buscar_producto) # Al presionar Enter, busca el producto.
        self.entry_codigo.focus_set() # Pone el foco en este campo al iniciar.

        # --- Frame Inferior (Botón de Cobro y Total) ---
        frame_bottom = tk.Frame(self.root, bg="#333", pady=20, relief="raised", bd=5)
        frame_bottom.pack(fill="x", side="bottom")
        
        # Botón principal para iniciar el proceso de cobro.
        tk.Button(frame_bottom, text="✅ COBRAR (F5)", bg=self.COLOR_VERDE, fg="white", font=("Arial", 18, "bold"), relief="raised", bd=5, command=self.guardar_venta).pack(side="left", padx=30, ipady=10, ipadx=20) 
        # Etiqueta para mostrar el total acumulado de la venta.
        self.lbl_total = tk.Label(frame_bottom, text="TOTAL: $0.00", fg=self.COLOR_VERDE, bg="#333", font=self.FONT_HUGE)
        self.lbl_total.pack(side="right", padx=30)
        
        # --- Estilo y Creación de la Tabla del Carrito (Treeview) ---
        style = ttk.Style()
        style.configure("Treeview", background="white", rowheight=40, fieldbackground="white", font=("Arial", 14))
        style.configure("Treeview.Heading", font=("Arial", 14, "bold"), background="#444", foreground="black")
        style.map("Treeview", background=[('selected',self.COLOR_AZUL)])


        # Frame que contendrá la tabla del carrito.
        frame_tabla = tk.Frame(self.root, bg=self.COLOR_FONDO)
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

        # Etiqueta para filas normales
        self.tree.tag_configure('normal_row', background='white')

        # Barra de desplazamiento para la tabla.
        scrollbar = ttk.Scrollbar(frame_tabla, orient="vertical", command=self.tree.yview)
        scrollbar.pack(side="right", fill="y")
        self.tree.configure(yscroll=scrollbar.set)
        
        # Atajo de teclado: F5 para abrir la ventana de cobro.
        self.root.bind('<F5>', lambda event: self.guardar_venta())

    def abrir_gestion_atributos(self):
        """Abre la ventana para gestionar rubros, familias, marcas y atributos."""
        VentanaGestionAtributos(self.root, self.db_config)

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
            # Una vez creada la BD (si no existía), se inicializan/actualizan las tablas
            inicializar_base_datos(self.db_config)
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
            'tipo': producto_bd.get('tipo', 'Unidad'), 'sku': producto_bd.get('sku', '')
        }
        self.carrito.append(nuevo_item)
        self.actualizar_carrito_visual()
        self.entry_codigo.delete(0, tk.END)

    def buscar_producto(self, event=None):
        """
        Busca un producto por código de barras. Si existe, lo procesa.
        Si no existe, busca por SKU. Si aún no lo encuentra, abre un diálogo con opciones para el usuario.
        """
        codigo = self.entry_codigo.get().strip()
        if not codigo: return

        producto_bd = None
        try:
            conexion = mysql.connector.connect(**self.db_config)
            cursor = conexion.cursor(dictionary=True)

            # 1. Search by codigo_barras
            cursor.execute("SELECT * FROM productos WHERE codigo_barras = %s", (codigo,))
            producto_bd = cursor.fetchone()

            # 2. If not found by barcode, search by SKU
            if not producto_bd:
                cursor.execute("SELECT * FROM productos WHERE sku = %s", (codigo,))
                producto_bd = cursor.fetchone()

            cursor.close()
            conexion.close()
        except mysql.connector.Error as err:
            messagebox.showerror("Error de Base de Datos", f"No se pudo consultar: {err}")
            return

        self.entry_codigo.delete(0, tk.END)

        if not producto_bd:
            dialog = VentanaProductoNoEncontrado(self.root, codigo)
            self.root.wait_window(dialog.top)

            if dialog.result == 'add':
                self.abrir_inventario(codigo)
            elif dialog.result == 'search':
                self.abrir_busqueda_producto()

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
            ), tags=('normal_row',))
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
            if bytes_logo:
                ticket_bytes += bytes_logo + b"\n"
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

        if (producto_bd.get('tipo') or 'Unidad').lower().startswith('granel'):
            VentanaVentaGranel(self.root, producto_bd, self.agregar_producto_granel)
        elif producto_bd['stock_actual'] <= 0:
            messagebox.showwarning("Stock Agotado", f"No queda stock para el producto:\n{producto_bd['nombre']}")
        else:
            encontrado = next((item for item in self.carrito if item['id'] == producto_bd['id']), None)
            if encontrado:
                encontrado['cantidad'] += 1
                encontrado['subtotal'] = encontrado['cantidad'] * encontrado['precio']
            else:
                nuevo_item = {
                    'id': producto_bd['id'],
                    'codigo': producto_bd['codigo_barras'],
                    'nombre': producto_bd['nombre'],
                    'precio': float(producto_bd['precio_venta']),
                    'cantidad': 1,
                    'subtotal': float(producto_bd['precio_venta']),
                    'tipo': producto_bd.get('tipo', 'Unidad'),
                    'sku': producto_bd.get('sku', '')
                }
                self.carrito.append(nuevo_item)
            
            self.actualizar_carrito_visual()
        
        self.entry_codigo.focus_set()

    def abrir_inventario(self,codigo=None):
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
