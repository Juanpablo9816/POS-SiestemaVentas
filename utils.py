# -*- coding: utf-8 -*-

import sys
import os

def resolver_ruta(ruta_relativa):
    """
    Obtiene la ruta absoluta a un recurso, para que funcione tanto en desarrollo (.py) como en producción (.exe).
    PyInstaller crea una carpeta temporal llamada _MEIPASS donde almacena los archivos.
    """
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, ruta_relativa)
    return os.path.join(os.path.abspath("."), ruta_relativa)
