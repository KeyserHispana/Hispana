from flask import Flask
from threading import Thread
import os
import json
import io
from datetime import datetime, timedelta
from difflib import get_close_matches

import discord
from discord.ext import commands
from discord import Embed

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# Importar el módulo de base de datos para Fuel Forecast
try:
    import database
except ImportError:
    database = None

# --- Servidor Flask Único para UptimeRobot / Keep Alive ---
app = Flask('')

@app.route('/')
def home():
    return "Bot Unificado HISPANA (Estadísticas, Proyecciones y Fuel) activo 24/7"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# ==========================================
# 1. FUNCIONES Y LÓGICA DE ESTADÍSTICAS
# ==========================================
ARCHIVO_HISTORIAL = 'historial_eficiencia.json'

def cargar_historial():
    if not os.path.exists(ARCHIVO_HISTORIAL):
        return {}
    with open(ARCHIVO_HISTORIAL, 'r', encoding='utf-8') as f:
        return json.load(f)

def guardar_en_historial(fecha, datos_actuales):
    historial = cargar_historial()
    datos_guardar = {}
    for nombre, datos in datos_actuales.items():
        datos_guardar[nombre] = {
            'eficiencia': datos['eficiencia'],
            'promedio': datos['promedio'],
            'potencial': datos['potencial']
        }
    historial[fecha] = datos_guardar
    fechas_ordenadas = sorted(historial.keys())
    if len(fechas_ordenadas) > 6:
        fechas_a_borrar = fechas_ordenadas[:-6]
        for f in fechas_a_borrar:
            del historial[f]
    with open(ARCHIVO_HISTORIAL, 'w', encoding='utf-8') as f:
        json.dump(historial, f, indent=4)

def cargar_datos_semana(nombre_archivo):
    datos_aerolineas = {}
    datos_alianza = None
    if not os.path.exists(nombre_archivo):
        return datos_alianza, datos_aerolineas
    with open(nombre_archivo, 'r', encoding='utf-8') as f:
        for linea in f:
            if not linea.strip() or linea.startswith('AEROLINEA'):
                continue
            partes = linea.strip().split(',')
            if partes[0].strip().upper() == 'ALIANZA' and len(partes) >= 5:
                try:
                    datos_alianza = {
                        'fecha': partes[1].strip(),
                        'rank': int(partes[2]),
                        'valor': float(partes[3]),
                        'crecimiento_diario': float(partes[4])
                    }
                except ValueError:
                    pass
                continue
            if len(partes) >= 4:
                nombre = partes[0].strip()
                try:
                    eficiencia = int(partes[1])
                    promedio = float(partes[2])
                    potencial = float(partes[3])
                    datos_aerolineas[nombre] = {
                        'eficiencia': eficiencia,
                        'promedio': promedio,
                        'potencial': potencial
                    }
                except ValueError:
                    continue
    return datos_alianza, datos_aerolineas

# ==========================================
# 2. FUNCIONES Y LÓGICA DE PROYECCIONES
# ==========================================
def cargar_datos_desde_txt(nombre_archivo):
    datos = {}
    fecha_str = None
    if not os.path.exists(nombre_archivo):
        return fecha_str, datos
    with open(nombre_archivo, 'r', encoding='utf-8') as f:
        lineas = f.readlines()
    nombre_actual = None
    for linea in lineas:
        linea = linea.strip()
        if not linea:
            continue
        if linea.lower().startswith('fecha:'):
            fecha_str = linea.split(':')[1].strip()
            continue
        if linea.startswith('$'):
            try:
                valor_limpio = float(linea.replace('$', '').replace(',', ''))
                if nombre_actual:
                    datos[nombre_actual] = valor_limpio
            except ValueError:
                pass
        elif not linea.startswith('Flights:') and not linea.startswith('Airlines:') and not linea.startswith('Previsión')
