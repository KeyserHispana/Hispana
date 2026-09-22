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

# Asumimos que la librería database.py existe en tu entorno para el Fuel Forecast
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
        elif not linea.startswith('Flights:') and not linea.startswith('Airlines:') and not linea.startswith('Previsión') and not linea.startswith('Siguiente'):
            nombre_actual = linea
    return fecha_str, datos

def buscar_nombre_alianza(nombre_buscado, diccionario_datos):
    nombre_buscado_limpio = nombre_buscado.strip().lower()
    for nombre_real in diccionario_datos.keys():
        if nombre_buscado_limpio == nombre_real.lower():
            return nombre_real
    nombres_reales = list(diccionario_datos.keys())
    nombres_min = [n.lower() for n in nombres_reales]
    coincidencias = get_close_matches(nombre_buscado_limpio, nombres_min, n=1, cutoff=0.4)
    if coincidencias:
        idx = nombres_min.index(coincidencias[0])
        return nombres_reales[idx]
    return None

def calcular_dias_entre_archivos(fecha_pasada, fecha_actual):
    formato = "%Y-%m-%d"
    try:
        f_pasada = datetime.strptime(fecha_pasada, formato)
        f_actual = datetime.strptime(fecha_actual, formato)
        dias = (f_actual - f_pasada).days
        return max(1, dias)
    except (ValueError, TypeError):
        return 7

# ==========================================
# 3. FUNCIONES Y LÓGICA DE FUEL FORECAST
# ==========================================
def get_discord_time(time):
    clock_emojis = {
        '00:00': '<t:0:t>', '00:30': '<t:1800:t>', '01:00': '<t:3600:t>', '01:30': '<t:5400:t>',
        '02:00': '<t:7200:t>', '02:30': '<t:9000:t>', '03:00': '<t:10800:t>', '03:30': '<t:12600:t>',
        '04:00': '<t:14400:t>', '04:30': '<t:16200:t>', '05:00': '<t:18000:t>', '05:30': '<t:19800:t>',
        '06:00': '<t:21600:t>', '06:30': '<t:23400:t>', '07:00': '<t:25200:t>', '07:30': '<t:27000:t>',
        '08:00': '<t:28800:t>', '08:30': '<t:30600:t>', '09:00': '<t:32400:t>', '09:30': '<t:34200:t>',
        '10:00': '<t:36000:t>', '10:30': '<t:37800:t>', '11:00': '<t:39600:t>', '11:30': '<t:41400:t>',
        '12:00': '<t:43200:t>', '12:30': '<t:45000:t>', '13:00': '<t:46800:t>', '13:30': '<t:48600:t>',
        '14:00': '<t:50400:t>', '14:30': '<t:52200:t>', '15:00': '<t:54000:t>', '15:30': '<t:55800:t>',
        '16:00': '<t:57600:t>', '16:30': '<t:59400:t>', '17:00': '<t:61200:t>', '17:30': '<t:63000:t>',
        '18:00': '<t:64800:t>', '18:30': '<t:66600:t>', '19:00': '<t:68400:t>', '19:30': '<t:70200:t>',
        '20:00': '<t:72000:t>', '20:30': '<t:73800:t>', '21:00': '<t:75600:t>', '21:30': '<t:77400:t>',
        '22:00': '<t:79200:t>', '22:30': '<t:81000:t>', '23:00': '<t:82800:t>', '23:30': '<t:84600:t>',
    }
    return clock_emojis.get(time, '⏰')

def create_embed(data, daily: int = 0, date: int = 1):
    title = f"Fuel & CO2 price forecast for Day {date}" if daily else "Fuel & CO2 price forecast for the next 12 hours"
    color = discord.Color.green() if daily else discord.Color.blurple()
    embed = Embed(title=title, color=color)
    embed.set_author(name="HISPANA Bot")
    embed.set_footer(text="HISPANA Alliance")

    forecast_lines = []
    for entry in data:
        time = entry[0]
        try:
            fuel_price = int(entry[1])
        except ValueError:
            fuel_price = entry[1]
        try:
            co2_price = int(entry[2])
        except ValueError:
            co2_price = entry[2]
        
        discord_time = get_discord_time(time)
        fuel_icon = "🟢" if isinstance(fuel_price, int) and fuel_price < 700 else "⛽"
        co2_icon = "🟢" if isinstance(co2_price, int) and co2_price < 140 else "♻️"
        line = f"🕒 {discord_time}  |  {fuel_icon} {fuel_price}  |  {co2_icon} {co2_price}"
        forecast_lines.append(line)

    embed.description = "\n".join(forecast_lines)
    return embed

# ==========================================
# CONFIGURACIÓN DEL BOT ÚNICO DISCORD
# ==========================================
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f"Bot Unificado HISPANA conectado como {bot.user}")

# --- COMANDOS DE ESTADÍSTICAS ---
@bot.command(name='reporte_semanal')
async def reporte_semanal(ctx):
    alianza_pasada, datos_pasados = cargar_datos_semana('semana_pasada.txt')
    alianza_actual, datos_actuales = cargar_datos_semana('semana_actual.txt')
    
    if not datos_pasados or not datos_actuales:
        await ctx.send("⚠️ Faltan datos de aerolíneas en los archivos de texto.")
        return
        
    if not alianza_actual or 'fecha' not in alianza_actual:
        await ctx.send("⚠️ El archivo `semana_actual.txt` debe incluir la fecha en la línea de la ALIANZA.")
        return

    fecha_reporte_actual = alianza_actual['fecha']
    
    historial_temp = cargar_historial()
    if len(historial_temp) == 0 and alianza_pasada and 'fecha' in alianza_pasada:
        guardar_en_historial(alianza_pasada['fecha'], datos_pasados)
        
    guardar_en_historial(fecha_reporte_actual, datos_actuales)

    f_pasada = alianza_pasada.get('fecha', 'Anterior') if alianza_pasada else 'Anterior'
    f_actual = alianza_actual.get('fecha', 'Actual')

    embed_resumen = Embed(title="📊 Reporte Semanal HISPANA", color=discord.Color.green())
    if alianza_pasada and alianza_actual:
        avance_rank = alianza_pasada['rank'] - alianza_actual['rank']
        icono_rank = "⬆️" if avance_rank > 0 else "⬇️" if avance_rank < 0 else "➖"
        embed_resumen.add_field(name="🏆 Ranking Global", value=f"{f_pasada}: **{alianza_pasada['rank']}**\n{f_actual}: **{alianza_actual['rank']}**\nMovimiento: {icono_rank} **{abs(avance_rank)}**", inline=True)
        
        crecimiento_total = alianza_actual['valor'] - alianza_pasada['valor']
        icono_val = "📈" if crecimiento_total > 0 else "📉"
        embed_resumen.add_field(name="💰 Valor de Alianza", value=f"{f_pasada}: **${alianza_pasada['valor']:,.2f}**\n{f_actual}: **${alianza_actual['valor']:,.2f}**\nCrecimiento: {icono_val} **${crecimiento_total:,.2f}**", inline=True)
        
        diff_crecimiento = alianza_actual['crecimiento_diario'] - alianza_pasada['crecimiento_diario']
        icono_crec = "🚀" if diff_crecimiento > 0 else "⚠️"
        embed_resumen.add_field(name="📊 Crecimiento Diario", value=f"{f_pasada}: **${alianza_pasada['crecimiento_diario']:,.2f}**\n{f_actual}: **${alianza_actual['crecimiento_diario']:,.2f}**\nVariación: {icono_crec} **${diff_crecimiento:,.2f}**", inline=True)
        
    await ctx.send(embed=embed_resumen)

    ranking_pasado = sorted(datos_pasados.items(), key=lambda x: x[1]['eficiencia'], reverse=True)
    ranking_actual = sorted(datos_actuales.items(), key=lambda x: x[1]['eficiencia'], reverse=True)

    pos_pasadas_dict = {nombre: idx + 1 for idx, (nombre, datos) in enumerate(ranking_pasado)}

    lineas_reporte = []
    movimientos_lista = [] 

    for idx, (nombre, datos) in enumerate(ranking_actual):
        pos_actual = idx + 1
        
        if nombre in pos_pasadas_dict:
            pos_pasada = pos_pasadas_dict[nombre]
            diferencia = pos_pasada - pos_actual
            movimientos_lista.append({'nombre': nombre, 'dif': diferencia})
            
            if diferencia > 0: movimiento_str = f"⬆️{diferencia}"
            elif diferencia < 0: movimiento_str = f"⬇️{abs(diferencia)}"
            else: movimiento_str = "➖0"
        else:
            movimiento_str = "➖0"

        prom_fmt = f"{datos['promedio']:,.0f}"
        pot_fmt = f"{datos['potencial']:,.1f}"
        
        linea = f"**{pos_actual}.** {movimiento_str} | **{nombre}** (⚡**{datos['eficiencia']}%**) | Prom:**{prom_fmt}** | Pot:**{pot_fmt}**"
        lineas_reporte.append(linea)

    veteranas_actuales = {
        k: v for k, v in datos_actuales.items() 
        if k in pos_pasadas_dict and k.lower() != 'keyser' and v['eficiencia'] > 0
    }

    ranking_veteranas = sorted(veteranas_actuales.items(), key=lambda x: x[1]['eficiencia'], reverse=True)
    movimientos_sin_keyser = [x for x in movimientos_lista if x['nombre'].lower() != 'keyser' and x['nombre'] in pos_pasadas_dict]

    los_que_subieron = sorted([x for x in movimientos_sin_keyser if x['dif'] > 0], key=lambda x: x['dif'], reverse=True)
    los_que_bajaron = sorted([x for x in movimientos_sin_keyser if x['dif'] < 0], key=lambda x: x['dif']) 

    top3_eficientes = ranking_veteranas[:3]
    top3_menos_eficientes = ranking_veteranas[-3:] if len(ranking_veteranas) >= 3 else ranking_veteranas
    top3_menos_eficientes.reverse() 

    top3_subieron = los_que_subieron[:3]
    top3_bajaron = los_que_bajaron[:3]

    embed_tops = Embed(title=f"🏆 Podios de la Semana ({f_actual})", color=discord.Color.gold())

    txt_top_efi = "".join([f"**{i+1}.** {nom} (**{dat['eficiencia']}%**)\n" for i, (nom, dat) in enumerate(top3_eficientes)])
    embed_tops.add_field(name="🌟 Más Eficientes", value=txt_top_efi if txt_top_efi else "N/A", inline=True)

    txt_bot_efi = "".join([f"**{i+1}.** {nom} (**{dat['eficiencia']}%**)\n" for i, (nom, dat) in enumerate(top3_menos_eficientes)])
    embed_tops.add_field(name="🐌 Menos Eficientes", value=txt_bot_efi if txt_bot_efi else "N/A", inline=True)
    
    embed_tops.add_field(name="\u200b", value="\u200b", inline=False) 

    txt_top_sub = "".join([f"**{i+1}.** {item['nombre']} (⬆️{item['dif']})\n" for i, item in enumerate(top3_subieron)])
    embed_tops.add_field(name="🚀 Más Avanzaron", value=txt_top_sub if txt_top_sub else "Nadie avanzó", inline=True)

    txt_top_baj = "".join([f"**{i+1}.** {item['nombre']} (⬇️{abs(item['dif'])})\n" for i, item in enumerate(top3_bajaron)])
    embed_tops.add_field(name="📉 Más Cayeron", value=txt_top_baj if txt_top_baj else "Nadie cayó", inline=True)

    await ctx.send(embed=embed_tops)

    chunk_size = 15
    for idx_chunk, i in enumerate(range(0, len(lineas_reporte), chunk_size)):
        chunk = lineas_reporte[i:i + chunk_size]
        texto_bloque = "\n\n".join(chunk)
        
        if idx_chunk == 0:
            leyenda = (
                "📖 **Leyenda:** ⬆️/⬇️/➖ Movimiento | ⚡ % Eficiencia\n"
                "📊 **Prom:** Promedio C/D | **Pot:** Potencial C/D\n"
                "__________________________________________\n"
            )
            texto_bloque = leyenda + "\n" + texto_bloque

        embed_chunk = Embed(description=texto_bloque, color=discord.Color.blue())
        await ctx.send(embed=embed_chunk)

@bot.command(name='mi_aerolinea')
async def mi_aerolinea(ctx, *, nombre_buscado: str = None):
    if not nombre_buscado:
        await ctx.send("⚠️ Debes indicar el nombre de la aerolínea. Ejemplo: `!mi_aerolinea Fly Aces`")
        return

    _, datos_actuales = cargar_datos_semana('semana_actual.txt')
    if not datos_actuales:
        await ctx.send("⚠️ No hay datos actuales cargados en el sistema.")
        return

    nombre_encontrado = None
    for nom in datos_actuales.keys():
        if nombre_buscado.strip().lower() == nom.lower():
            nombre_encontrado = nom
            break

    if not nombre_encontrado:
        await ctx.send(f"❌ No se encontró ninguna aerolínea con el nombre **'{nombre_buscado}'** en el registro actual.")
        return

    historial = cargar_historial()
    fechas_ordenadas = sorted(historial.keys())
    ultimas_fechas = fechas_ordenadas[-3:] if len(fechas_ordenadas) >= 3 else fechas_ordenadas

    historial_texto = ""
    for fecha in ultimas_fechas:
        datos_en_fecha = historial[fecha]
        if nombre_encontrado in datos_en_fecha:
            eficiencia_h = datos_en_fecha[nombre_encontrado]['eficiencia']
            ordenados_h = sorted(datos_en_fecha.items(), key=lambda x: x[1]['eficiencia'], reverse=True)
            puesto_h = next((idx + 1 for idx, (nom, _) in enumerate(ordenados_h) if nom == nombre_encontrado), "N/A")
            historial_texto += f"• **{fecha}**: Puesto **#{puesto_h}** | Eficiencia: **{eficiencia_h}%**\n"
        else:
            historial_texto += f"• **{fecha}**: *Sin registro*\n"

    ranking_actual = sorted(datos_actuales.items(), key=lambda x: x[1]['eficiencia'], reverse=True)
    pos_actual = next(idx + 1 for idx, (nom, _) in enumerate(ranking_actual) if nom == nombre_encontrado)
    datos_aerolinea = datos_actuales[nombre_encontrado]

    embed = Embed(title=f"✈️ Reporte Histórico: {nombre_encontrado}", color=discord.Color.blue())
    embed.add_field(name="🏆 Posición Actual", value=f"**#{pos_actual}**", inline=True)
    embed.add_field(name="⚡ Eficiencia Actual", value=f"**{datos_aerolinea['eficiencia']}%**", inline=True)
    embed.add_field(name="\u200b", value="\u200b", inline=True)
    embed.add_field(name="📊 Promedio C/D Actual", value=f"${datos_aerolinea['promedio']:,.0f}", inline=True)
    embed.add_field(name="🚀 Potencial C/D Actual", value=f"${datos_aerolinea['potencial']:,.1f}", inline=True)
    embed.add_field(name="\u200b", value="\u200b", inline=True)
    embed.add_field(name="📈 Evolución (Últimas Semanas)", value=historial_texto if historial_texto else "Aún no hay suficiente historial guardado.", inline=False)

    await ctx.send(embed=embed)

@bot.command(name='enfrentar')
async def enfrentar(ctx, *, texto_duelo: str = None):
    if not texto_duelo or 'vs' not in texto_duelo.lower():
        await ctx.send("⚠️ Formato incorrecto. Debes usar: `!enfrentar Aerolinea A vs Aerolinea B`")
        return

    partes = texto_duelo.split('vs' if 'vs' in texto_duelo else 'VS')
    if len(partes) != 2:
        partes = texto_duelo.lower().split('vs')
        
    if len(partes) != 2:
        await ctx.send("⚠️ No se pudo interpretar el duelo. Usa el formato: `!enfrentar Aerolinea A vs Aerolinea B`")
        return

    busq_a = partes[0].strip()
    busq_b = partes[1].strip()

    _, datos_actuales = cargar_datos_semana('semana_actual.txt')
    if not datos_actuales:
        await ctx.send("⚠️ No hay datos actuales cargados.")
        return

    nom_a = next((nom for nom in datos_actuales.keys() if busq_a.lower() == nom.lower()), None)
    nom_b = next((nom for nom in datos_actuales.keys() if busq_b.lower() == nom.lower()), None)

    if not nom_a or not nom_b:
        await ctx.send(f"❌ No se pudo encontrar a una o ambas aerolíneas en el registro. Asegúrate de escribir bien los nombres.\n- Buscaste: **{busq_a}** y **{busq_b}**")
        return

    ranking_actual = sorted(datos_actuales.items(), key=lambda x: x[1]['eficiencia'], reverse=True)
    pos_a = next(idx + 1 for idx, (nom, _) in enumerate(ranking_actual) if nom == nom_a)
    pos_b = next(idx + 1 for idx, (nom, _) in enumerate(ranking_actual) if nom == nom_b)

    d_a = datos_actuales[nom_a]
    d_b = datos_actuales[nom_b]

    embed = Embed(title=f"⚔️ Duelo Semanal: {nom_a} vs {nom_b}", color=discord.Color.purple())
    embed.add_field(name=f"🛫 {nom_a}", value=f"• Puesto: **#{pos_a}**\n• Eficiencia: **{d_a['eficiencia']}%**\n• Prom: **${d_a['promedio']:,.0f}**\n• Pot: **${d_a['potencial']:,.1f}**", inline=True)
    embed.add_field(name=f"🛫 {nom_b}", value=f"• Puesto: **#{pos_b}**\n• Eficiencia: **{d_b['eficiencia']}%**\n• Prom: **${d_b['promedio']:,.0f}**\n• Pot: **${d_b['potencial']:,.1f}**", inline=True)

    if d_a['eficiencia'] > d_b['eficiencia']:
        ganador_txt = f"🏆 **Ganador en Eficiencia:** {nom_a} (+{d_a['eficiencia'] - d_b['eficiencia']}% vs {nom_b})"
    elif d_b['eficiencia'] > d_a['eficiencia']:
        ganador_txt = f"🏆 **Ganador en Eficiencia:** {nom_b} (+{d_b['eficiencia'] - d_a['eficiencia']}% vs {nom_a})"
    else:
        ganador_txt = "🤝 **Empate técnico** en porcentaje de eficiencia."

    embed.add_field(name="📊 Resultado del Enfrentamiento", value=ganador_txt, inline=False)
    await ctx.send(embed=embed)

@bot.command(name='grafica_eficiencia')
async def grafica_eficiencia(ctx):
    historial = cargar_historial()
    if len(historial) < 2:
        await ctx.send("⚠️ Aún no hay suficientes datos históricos. El bot necesita tener guardadas al menos 2 semanas para comparar.")
        return

    fechas_todas = sorted(historial.keys())
    fechas = fechas_todas[-6:]
    fecha_actual = fechas[-1]
    fecha_anterior = fechas[-2]
    
    rankings_por_fecha = {}
    for fecha in fechas:
        datos_fecha = {a: d['eficiencia'] for a, d in historial[fecha].items() if d is not None}
        ordenados = sorted(datos_fecha.items(), key=lambda x: x[1], reverse=True)
        rankings_por_fecha[fecha] = {item[0]: idx + 1 for idx, item in enumerate(ordenados)}
        
    ranking_actual_ordenado = sorted(rankings_por_fecha[fecha_actual].items(), key=lambda x: x[1])
    aerolineas_actuales = [a for a, r in ranking_actual_ordenado]
    
    altura_figura = max(8, len(aerolineas_actuales) * 0.4) 
    fig, ax = plt.subplots(figsize=(14, altura_figura))
    
    for aerolinea in aerolineas_actuales:
        valores_y = []
        fechas_plot = []
        for fecha in fechas:
            rank = rankings_por_fecha[fecha].get(aerolinea)
            if rank is not None:
                valores_y.append(rank)
                fechas_plot.append(fecha)
        if len(valores_y) > 0:
            ax.plot(fechas_plot, valores_y, marker='o', linewidth=2)

    ax.invert_yaxis() 
    ticks_y = []
    etiquetas_y = []
    
    for aerolinea, rank_actual in ranking_actual_ordenado:
        ticks_y.append(rank_actual)
        rank_anterior = rankings_por_fecha[fecha_anterior].get(aerolinea)
        eficiencia_actual = historial[fecha_actual][aerolinea]['eficiencia'] if aerolinea in historial[fecha_actual] else 0
        if rank_anterior is not None:
            diferencia = rank_anterior - rank_actual
            if diferencia > 0: mov = f"(▲ {diferencia})"
            elif diferencia < 0: mov = f"(▼ {abs(diferencia)})"
            else: mov = "(=)"
        else:
            mov = "(Nuevo)"
        etiquetas_y.append(f"{rank_actual}. {aerolinea}  {mov}  [{eficiencia_actual}%]")
        
    ax.set_yticks(ticks_y)
    ax.set_yticklabels([str(t) for t in ticks_y], fontsize=10, color='gray')
    ax2 = ax.twinx()
    ax2.set_ylim(ax.get_ylim())
    ax2.set_yticks(ticks_y)
    ax2.set_yticklabels(etiquetas_y, fontsize=10, weight='bold')
    
    rango_texto = f"Del {fechas[0]} al {fechas[-1]}" if len(fechas) > 1 else fechas[0]
    plt.title(f'Evolución del Ranking Interno - HISPana ({rango_texto})', fontsize=16, pad=20, weight='bold')
    ax.set_xticks(range(len(fechas)))
    ax.set_xticklabels(fechas, rotation=15, fontsize=10)
    ax.grid(True, linestyle='--', alpha=0.5, axis='x') 
    
    for spine in ['top', 'bottom', 'right', 'left']:
        ax.spines[spine].set_visible(False)
        ax2.spines[spine].set_visible(False)
        
    ax.tick_params(axis='y', length=0)
    ax2.tick_params(axis='y', length=0)
    ax.tick_params(axis='x', color='gray')
    
    plt.tight_layout()
    buffer = io.BytesIO()
    plt.savefig(buffer, format='png', bbox_inches='tight')
    buffer.seek(0)
    plt.close(fig)

    archivo_discord = discord.File(buffer, filename='grafica_posiciones.png')
    await ctx.send("📈 **Evolución Histórica del Ranking Interno (Últimas semanas)**", file=archivo_discord)

# --- COMANDOS DE PROYECCIONES ---
@bot.command(name='comparar')
async def comparar(ctx, h_name: str, *r_names):
    if len(r_names) > 8:
        await ctx.send("⚠️ Por favor, ingresa un máximo de 8 alianzas rivales a comparar.")
        return
    if len(r_names) == 0:
        await ctx.send("⚠️ Debes incluir al menos una alianza rival. Ejemplo: `!comparar Hispana FAME`")
        return

    fecha_pasada, datos_pasados = cargar_datos_desde_txt('pasados.txt')
    fecha_actual, datos_actuales = cargar_datos_desde_txt('actuales.txt')
    
    if not datos_actuales:
        await ctx.send("⚠️ El archivo `actuales.txt` está vacío o no se encuentra en el repositorio.")
        return
    if not fecha_pasada or not fecha_actual:
        await ctx.send("⚠️ Falta la fecha en los archivos. Asegúrate de que la primera línea diga `Fecha: AAAA-MM-DD`.")
        return
        
    h_key = buscar_nombre_alianza(h_name, datos_actuales)
    if not h_key:
        await ctx.send(f"⚠️ No se encontró la alianza base: `{h_name}`.")
        return
    
    rivales_encontrados = []
    rivales_faltantes = []
    for r_name in r_names:
        r_key = buscar_nombre_alianza(r_name, datos_actuales)
        if r_key:
            rivales_encontrados.append(r_key)
        else:
            rivales_faltantes.append(r_name)
    
    if rivales_faltantes:
        await ctx.send(f"⚠️ No se encontraron las siguientes alianzas: `{', '.join(rivales_faltantes)}`")
        if not rivales_encontrados:
            return

    dias_analizados = calcular_dias_entre_archivos(fecha_pasada, fecha_actual)
    ranking_global_valor = sorted(datos_actuales.items(), key=lambda x: x[1], reverse=True)
    
    def obtener_puesto_global(alianza_key):
        return next((i + 1 for i, x in enumerate(ranking_global_valor) if x[0] == alianza_key), "N/A")

    h_val = datos_actuales[h_key]
    h_val_pasado = datos_pasados.get(h_key, h_val)
    h_growth = (h_val - h_val_pasado) / dias_analizados
    h_puesto = obtener_puesto_global(h_key)

    crecimientos_globales = []
    for alianza, val_actual in datos_actuales.items():
        val_pasado = datos_pasados.get(alianza, val_actual)
        crecimiento = (val_actual - val_pasado) / dias_analizados
        crecimientos_globales.append((alianza, crecimiento))
         
    crecimientos_globales.sort(key=lambda x: x[1], reverse=True)
    hispana_rank = next((i + 1 for i, x in enumerate(crecimientos_globales) if x[0] == h_key), "N/A")

    def obtener_ranking_cd(alianza_key):
        return next((i + 1 for i, x in enumerate(crecimientos_globales) if x[0] == alianza_key), "N/A")

    embed = Embed(title=f"📊 Proyección: {h_key} vs Rivales", color=discord.Color.green())
    embed.description = (
        f"📅 Período analizado: **{fecha_pasada}** a **{fecha_actual}** ({dias_analizados} días)\n"
        f"🏆 **Ranking Global CD ({h_key}): #{hispana_rank}**"
    )
    embed.add_field(name=f"🔵 {h_key} (Base) — Puesto #{h_puesto}", value=f"**Valor:** ${h_val:,.2f} \vert{} **CD:** +${h_growth:,.2f}", inline=False)
    
    for r_key in rivales_encontrados:
        r_val = datos_actuales[r_key]
        r_val_pasado = datos_pasados.get(r_key, r_val)
        r_growth = (r_val - r_val_pasado) / dias_analizados
        r_puesto = obtener_puesto_global(r_key)
        r_rank_cd = obtener_ranking_cd(r_key)
        distancia = r_val - h_val
        velocidad_neta = h_growth - r_growth
        
        if distancia > 0: 
            if velocidad_neta > 0: 
                dias_necesarios = distancia / velocidad_neta
                fecha_estimada = datetime.now() + timedelta(days=dias_necesarios)
                resultado = f"📈 Los alcanzaremos en **{dias_necesarios:.1f}** días (Aprox. {fecha_estimada.strftime('%Y-%m-%d')})"
            else:
                resultado = "⚠️ Rival adelante y creciendo más rápido (o igual). Inalcanzable a este ritmo."
        elif distancia < 0: 
            if velocidad_neta < 0: 
                dias_necesarios = abs(distancia) / abs(velocidad_neta)
                fecha_estimada = datetime.now() + timedelta(days=dias_necesarios)
                resultado = f"🚨 Nos alcanzarán en **{dias_necesarios:.1f}** días (Aprox. {fecha_estimada.strftime('%Y-%m-%d')})"
            else:
                resultado = "🛡️ Estamos adelante y ampliando (o manteniendo) la ventaja."
        else: 
            if velocidad_neta > 0:
                resultado = "🚀 Empatados en valor, pero estamos creciendo más rápido."
            elif velocidad_neta < 0:
                resultado = "⚠️ Empatados en valor, pero el rival está creciendo más rápido."
            else:
                resultado = "🤝 Empate total en valor y en crecimiento."
             
        embed.add_field(name=f"🔴 {r_key} — Puesto #{r_puesto}", value=f"**Valor:** ${r_val:,.2f} \vert{} **CD:** +${r_growth:,.2f} (Rank CD: #{r_rank_cd})\n{resultado}", inline=False)

    embed.set_footer(text="⭐ Developed by HISPANA Alliance ⭐")
    await ctx.send(embed=embed)

# --- COMANDOS DE FUEL FORECAST ---
@bot.command()
async def fuel(ctx, message: str = ""):
    if database is None:
        await ctx.send("⚠️ Módulo de base de datos no disponible.")
        return

    if message.upper() == "DAILY":
        data, date = database.getDailyPrice()
        embed = create_embed(data, 1, date)
        sent_message = await ctx.send(embed=embed)
        pins = await bot.get_channel(ctx.channel.id).pins()
        for pin_msg in pins:
            await pin_msg.unpin()
        await sent_message.pin()
    else:
        data = database.getPrice()
        embed = create_embed(data)
        await ctx.send(embed=embed)

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    
    if message.content.startswith('$Fuel&CO2!'):
        if database is None:
            await message.channel.send("⚠️ Módulo de base de datos no disponible.")
            return
        try:
            content = message.content.split(" ")
            fuel = content[1]
            co2 = content[2]
            dbData, table_name = database.getCurrentPrice()
            dbTime = dbData[0]
            dbFuel = dbData[1]
            dbCO2 = dbData[2]
            
            if int(fuel) != int(dbFuel) and int(co2) != int(dbCO2):
                text = database.updateBoth(table_name, dbTime, fuel, co2)
                await message.channel.send(text)
            elif int(fuel) != int(dbFuel):
                text = database.updateFuel(table_name, dbTime, fuel)
                await message.channel.send(text)
            elif int(co2) != int(dbCO2):
                text = database.updateCO2(table_name, dbTime, co2)
                await message.channel.send(text)
        except Exception as e:
            await message.channel.send(f"⚠️ Error actualizando la base de datos. Verifica el formato.")
            
    await bot.process_commands(message)

# --- INICIO DEL BOT ---
keep_alive()

# Usa la variable de entorno que desees (ej: DISCORDKEY o QUINCENAL_BOT_TOKEN)
TOKEN = os.environ.get('DISCORDKEY') or os.environ.get('QUINCENAL_BOT_TOKEN') or os.environ.get('PROJECTION_BOT_TOKEN')
bot.run(TOKEN)
