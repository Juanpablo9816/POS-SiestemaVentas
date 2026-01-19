# -*- coding: utf-8 -*-

import mysql.connector

class Database:
    def __init__(self, config_db):
        self.config = config_db
        self.connection = None
        self.cursor = None

    def connect(self):
        try:
            self.connection = mysql.connector.connect(**self.config)
            self.cursor = self.connection.cursor(dictionary=True)
            # print("Conexión a la base de datos exitosa.")
        except mysql.connector.Error as err:
            raise Exception(f"Error de conexión a la base de datos: {err}")

    def disconnect(self):
        if self.connection and self.connection.is_connected():
            self.cursor.close()
            self.connection.close()
            # print("Desconexión de la base de datos.")

    def execute(self, query, params=None):
        self.cursor.execute(query, params or ())
        return self.cursor

    def fetchone(self, query, params=None):
        self.cursor.execute(query, params or ())
        return self.cursor.fetchone()

    def fetchall(self, query, params=None):
        self.cursor.execute(query, params or ())
        return self.cursor.fetchall()

    def get_or_create(self, table_name, data):
        """
        Obtiene el ID de una fila si existe, de lo contrario la crea.
        Asume que la tabla tiene una columna 'nombre' o 'valor' que es UNIQUE.
        """
        key_col = 'valor' if table_name == 'valores_atributos' else 'nombre'
        value = data.get(key_col)

        if not value:
            raise ValueError(f"El diccionario de datos debe contener la clave '{key_col}'")

        try:
            # Primero, intentar obtener el ID con una búsqueda insensible a mayúsculas/minúsculas
            select_query = f"SELECT id FROM {table_name} WHERE LOWER({key_col}) = LOWER(%s)"
            result = self.fetchone(select_query, (value,))
            
            if result:
                return result['id']
            else:
                # Si no existe, crearlo
                insert_query = f"INSERT INTO {table_name} ({key_col}) VALUES (%s)"
                self.execute(insert_query, (value,))
                self.connection.commit()
                return self.cursor.lastrowid
        except mysql.connector.Error as err:
            self.connection.rollback()
            raise Exception(f"Error en get_or_create para la tabla {table_name}: {err}")

    def obtener_rubro_id_por_familia(self, familia_id):
        try:
            self.connect()
            query = "SELECT rubro_id FROM familia WHERE id = %s"
            self.cursor.execute(query, (familia_id,))
            resultado = self.cursor.fetchone()
            if resultado:
                return resultado['rubro_id']
            else:
                raise ValueError(f"No se encontró la familia con ID {familia_id}")
        except mysql.connector.Error as err:
            raise Exception(f"Error al obtener el rubro_id: {err}")
        finally:
            self.disconnect()

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
        tablas['rubro'] = """
            CREATE TABLE IF NOT EXISTS rubro (
                id INT AUTO_INCREMENT PRIMARY KEY,
                nombre VARCHAR(50) UNIQUE NOT NULL
            ) ENGINE=InnoDB;
        """
        tablas['familia'] = """
            CREATE TABLE IF NOT EXISTS familia (
                id INT AUTO_INCREMENT PRIMARY KEY,
                rubro_id INT,
                nombre VARCHAR(50) UNIQUE NOT NULL,
                FOREIGN KEY (rubro_id) REFERENCES rubro(id) ON DELETE SET NULL
            ) ENGINE=InnoDB;
        """
        tablas['marca'] = """
            CREATE TABLE IF NOT EXISTS marca (
                id INT AUTO_INCREMENT PRIMARY KEY,
                nombre VARCHAR(50) UNIQUE NOT NULL
            ) ENGINE=InnoDB;
        """
        tablas['valores_atributos'] = """
            CREATE TABLE IF NOT EXISTS valores_atributos (
                id INT AUTO_INCREMENT PRIMARY KEY,
                valor VARCHAR(50) UNIQUE NOT NULL
            ) ENGINE=InnoDB;
        """
        tablas['definicion_atributos'] = """
            CREATE TABLE IF NOT EXISTS definicion_atributos (
                id INT AUTO_INCREMENT PRIMARY KEY,
                familia_id INT UNIQUE,
                label_atributo_1 VARCHAR(50),
                label_atributo_2 VARCHAR(50),
                FOREIGN KEY (familia_id) REFERENCES familia(id) ON DELETE CASCADE
            ) ENGINE=InnoDB;
        """
        tablas['producto_sku'] = """
            CREATE TABLE IF NOT EXISTS producto_sku (
                sku VARCHAR(12) PRIMARY KEY,
                familia_id INT,
                marca_id INT,
                atributo_1_id INT,
                atributo_2_id INT,
                FOREIGN KEY (familia_id) REFERENCES familia(id),
                FOREIGN KEY (marca_id) REFERENCES marca(id),
                FOREIGN KEY (atributo_1_id) REFERENCES valores_atributos(id),
                FOREIGN KEY (atributo_2_id) REFERENCES valores_atributos(id)
            ) ENGINE=InnoDB;
        """
        tablas['productos'] = """
            CREATE TABLE IF NOT EXISTS productos (
                id INT AUTO_INCREMENT PRIMARY KEY,
                codigo_barras VARCHAR(50) UNIQUE NOT NULL,
                nombre VARCHAR(100) NOT NULL,
                precio_venta DECIMAL(10,2) DEFAULT 0.00,
                stock_actual INT DEFAULT 0,
                tipo VARCHAR(10) DEFAULT 'Unidad',
                sku VARCHAR(12) UNIQUE NULL,
                FOREIGN KEY (sku) REFERENCES producto_sku(sku) ON DELETE SET NULL
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

        for nombre_tabla, query in sorted(tablas.items()):
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
