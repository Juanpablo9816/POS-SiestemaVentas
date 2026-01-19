# -*- coding: utf-8 -*-

from database import Database

class Rubro:
    def __init__(self, nombre):
        self.nombre = nombre

class Familia:
    def __init__(self, rubro_id, nombre):
        self.rubro_id = rubro_id
        self.nombre = nombre

class Marca:
    def __init__(self, nombre):
        self.nombre = nombre

class ValoresAtributos:
    def __init__(self, valor):
        self.valor = valor

class DefinicionAtributos:
    def __init__(self, familia_id, label_atributo_1, label_atributo_2):
        self.familia_id = familia_id
        self.label_atributo_1 = label_atributo_1
        self.label_atributo_2 = label_atributo_2

class ProductoSKU:
    def __init__(self, db_config, familia_id, marca_id, atributo_1_id, atributo_2_id):
        self.db = Database(db_config)
        self.familia_id = familia_id
        self.marca_id = marca_id
        self.atributo_1_id = atributo_1_id
        self.atributo_2_id = atributo_2_id
        self.sku = None # Se generará antes de guardar

    def generar_sku(self):
        rubro_id = self.db.obtener_rubro_id_por_familia(self.familia_id)
        
        if rubro_id >= 100 or self.familia_id >= 100 or self.marca_id >= 1000 or self.atributo_1_id >= 100 or self.atributo_2_id >= 1000:
            raise ValueError("ID excede la longitud permitida para la generación de SKU")

        sku_parts = [
            str(rubro_id).zfill(2),
            str(self.familia_id).zfill(2),
            str(self.marca_id).zfill(3),
            str(self.atributo_1_id).zfill(2),
            str(self.atributo_2_id).zfill(3)
        ]
        self.sku = "".join(sku_parts)
        return self.sku
