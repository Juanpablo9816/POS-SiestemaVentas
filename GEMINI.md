# GEMINI.md: Contexto del Proyecto

Este documento proporciona una descripción general completa del proyecto "Sistema de Ventas" para guiar el desarrollo y mantenimiento futuros.

## 1. Descripción General del Proyecto

Esta es una aplicación de escritorio de Punto de Venta (POS) con todas las funciones, construida con Python. Está diseñada para un pequeño negocio minorista ("Kiosco Merchi") para gestionar ventas, inventario y reportes.

### Características Principales:

*   **Interfaz de Ventas:** Una interfaz gráfica de usuario para escanear productos (a través de código de barras), agregarlos a un carrito y calcular totales.
*   **Gestión de Inventario:** Una interfaz separada para agregar, ver y editar productos en la base de datos. Incluye funciones para buscar y marcar artículos con bajo stock.
*   **Procesamiento de Pagos:** Una ventana dedicada para manejar varios métodos de pago, incluyendo efectivo, tarjetas de débito/crédito, Mercado Pago y pagos mixtos. También puede calcular y aplicar intereses.
*   **Impresión de Recibos:** Genera e imprime recibos detallados y formateados en una impresora térmica utilizando comandos ESC/POS. Admite la impresión de un logotipo de la tienda en el ticket.
*   **Reporte de Ventas:** Puede exportar los datos de ventas diarias a un archivo de Microsoft Excel (`.xlsx`).
*   **Integración con API Externa:** El módulo de inventario puede consultar las API de OpenFoodFacts y OpenBeautyFacts para obtener automáticamente los nombres de los productos en función de su código de barras.

### Tecnologías Utilizadas:

*   **Lenguaje:** Python 3
*   **GUI:** `tkinter` (biblioteca estándar de Python)
*   **Base de Datos:** MySQL (conectado a través de `mysql-connector-python`)
*   **Bibliotecas:**
    *   `pandas` & `openpyxl`: Para la funcionalidad de exportación a Excel.
    *   `Pillow` (PIL): Para el procesamiento de imágenes (redimensionar logotipos para la interfaz de usuario y los recibos).
    *   `pywin32`: Para la comunicación directa con el sistema de impresión de Windows.
    *   `requests`: Para realizar solicitudes HTTP a API externas.
    *   `configparser`: Para gestionar la configuración externa.
*   **Empaquetado:** Se utiliza `PyInstaller` para empaquetar la aplicación en un ejecutable de Windows independiente (`.exe`).

## 2. Instalación y Configuración

### Base de Datos

La aplicación requiere un servidor MySQL en funcionamiento. La aplicación creará automáticamente el esquema de la base de datos y las tablas (`productos`, `ventas`, `detalle_ventas`) en su primera ejecución.

### Configuración (`config.ini`)

Toda la configuración externa se gestiona en el archivo `config.ini`. Una estructura típica es la siguiente:

```ini
[mysql]
host = localhost
user = root
password = tu_contraseña_de_mysql
database = punto_venta
port = 3306

[impresion]
nombre_impresora = POS-58
```

*   **`[mysql]`**: Contiene las credenciales de conexión para la base de datos MySQL.
*   **`[impresion]`**: Especifica el nombre exacto de la impresora térmica de recibos tal como aparece en Windows.

### Dependencias

Las dependencias de Python del proyecto se enumeran en `requirements.txt`. Se pueden instalar usando pip.

```
mysql-connector-python
requests
pywin32
configparser
pandas
openpyxl
Pillow
```

## 3. Ejecución de la Aplicación

1.  **Configurar el entorno:**
    *   Asegúrese de que un servidor MySQL esté en funcionamiento.
    *   Cree el archivo `config.ini` con los detalles correctos de la base de datos y la impresora.
    *   Se recomienda utilizar un entorno virtual de Python.
2.  **Instalar dependencias:**
    ```shell
    pip install -r requirements.txt
    ```
3.  **Ejecutar la aplicación:**
    ```shell
    python ventas.py
    ```

## 4. Compilación del Ejecutable

El proyecto utiliza PyInstaller para crear un ejecutable independiente. La configuración se define en archivos `.spec` (p. ej., `SistemaVentasFinal.spec`).

Para compilar el ejecutable:

1.  Instale PyInstaller: `pip install pyinstaller`
2.  Ejecute el comando de compilación desde el directorio que contiene el archivo `.spec` (p. ej., `v 1.3/`):
    ```shell
    pyinstaller SistemaVentasFinal.spec
    ```
3.  El archivo `.exe` final se ubicará en la carpeta `dist`.

## 5. Archivos Clave

*   `ventas.py`: El archivo de código fuente principal y único de Python, que contiene toda la lógica de la aplicación y las definiciones de la interfaz de usuario.
*   `config.ini`: Configuración externa para los ajustes de la base de datos y la impresora.
*   `*.spec`: Archivos de configuración de compilación de PyInstaller.
*   `logo.ico`: Icono para la ventana de la aplicación y el ejecutable.
*   `logo.png`: Logotipo que se muestra en la ventana principal de la aplicación.
*   `logo_ticket.png`: Logotipo formateado para ser impreso en los recibos térmicos.
*   `requirements.txt`: Una lista de las bibliotecas de Python utilizadas en el proyecto.
