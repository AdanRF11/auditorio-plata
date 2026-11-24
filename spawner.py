import threading
import requests
import time
import random
import os
import csv
from datetime import datetime

# Configuración de la prueba
# Opción A: Pruebas públicas por internet o desde varias PCs (usa tu enlace activo)
# URL_API = "https://daily-symantec-tube-mail.trycloudflare.com/solicitar_boleto"

# Opción B: Pruebas locales y código base para GitHub (por defecto)
URL_API = "http://localhost:8000/solicitar_boleto"
URL_API = "http://localhost:8000/solicitar_boleto"
TOTAL_PETICIONES = 100
VENTANA_TIEMPO_SEG = 60.0
CARPETA_DESTINO = "boletos_test"
ARCHIVO_BITACORA = "bitacora_spawner.csv"

# Asegurar que exista la carpeta de destino en instalaciones nuevas
os.makedirs(CARPETA_DESTINO, exist_ok=True)

# Contadores y estructuras protegidas por Mutex
exitos = 0
fallos = 0
tiempos_respuesta = []
bitacora = []
hilos_lanzados = []
lock_metricas = threading.Lock()


def realizar_peticion(id_hilo: int, zona_asignada: str):
    """Función que ejecuta cada hilo para solicitar un boleto en la zona indicada."""
    global exitos, fallos
    hora_envio = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    inicio = time.time()

    try:
        respuesta = requests.post(
            URL_API,
            params={"zona": zona_asignada},
            timeout=30
        )
        duracion = time.time() - inicio
        hora_respuesta = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

        if respuesta.status_code == 200:
            disp = respuesta.headers.get("Content-Disposition", "")
            if "filename=" in disp:
                filename = disp.split("filename=")[1].strip('"')
            else:
                filename = f"Boleto_{zona_asignada}_hilo_{id_hilo}.pdf"

            filepath = os.path.join(CARPETA_DESTINO, filename)
            with open(filepath, "wb") as f:
                f.write(respuesta.content)

            with lock_metricas:
                exitos += 1
                tiempos_respuesta.append(duracion)
                bitacora.append([id_hilo, zona_asignada, hora_envio, hora_respuesta, f"{duracion:.4f}", filename, "EXITO (200)"])

            print(f"[Hilo {id_hilo:03d}] OK ({zona_asignada}) - Tiempo: {duracion:.2f}s - Archivo: {filename}")
        else:
            detalle_error = respuesta.text.strip()
            with lock_metricas:
                fallos += 1
                tiempos_respuesta.append(duracion)
                bitacora.append([id_hilo, zona_asignada, hora_envio, hora_respuesta, f"{duracion:.4f}", "N/A", f"RECHAZO ({respuesta.status_code})"])

            print(f"[Hilo {id_hilo:03d}] RECHAZO ({zona_asignada}) - Código: {respuesta.status_code} - {detalle_error}")

    except Exception as e:
        duracion = time.time() - inicio
        hora_respuesta = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        with lock_metricas:
            fallos += 1
            bitacora.append([id_hilo, zona_asignada, hora_envio, hora_respuesta, f"{duracion:.4f}", "N/A", f"ERROR_RED: {str(e)}"])

        print(f"[Hilo {id_hilo:03d}] ERROR DE RED - {str(e)}")


def disparar_hilo(id_hilo: int, modo_zona: str):
    """Crea y lanza un hilo por solicitante registrándolo para su sincronización final."""
    zona = random.choice(["VIP", "PLATA", "GENERAL"]) if modo_zona == "MIXTO" else modo_zona
    t = threading.Thread(target=realizar_peticion, args=(id_hilo, zona))
    hilos_lanzados.append(t)
    t.start()


def modo_uniforme(modo_zona: str):
    """Distribuye las 100 peticiones uniformemente (1 petición cada 0.6 segundos)."""
    print(f"\n--- INICIANDO MODO UNIFORME ({TOTAL_PETICIONES} peticiones en {VENTANA_TIEMPO_SEG}s | Zona: {modo_zona}) ---")
    intervalo = VENTANA_TIEMPO_SEG / TOTAL_PETICIONES
    for i in range(1, TOTAL_PETICIONES + 1):
        disparar_hilo(i, modo_zona)
        time.sleep(intervalo)


def modo_rafagas(modo_zona: str):
    """Lanza 5 ráfagas de 20 peticiones simultáneas, esperando 12 segundos entre cada ráfaga."""
    print(f"\n--- INICIANDO MODO RÁFAGAS (5 ráfagas de 20 peticiones | Zona: {modo_zona}) ---")
    rafagas = 5
    peticiones_por_rafaga = TOTAL_PETICIONES // rafagas
    intervalo = VENTANA_TIEMPO_SEG / rafagas

    hilo_id = 1
    for r in range(rafagas):
        print(f"\n[!] Disparando Ráfaga {r + 1}/{rafagas}...")
        for _ in range(peticiones_por_rafaga):
            disparar_hilo(hilo_id, modo_zona)
            hilo_id += 1
        if r < rafagas - 1:
            time.sleep(intervalo)


def modo_aleatorio(modo_zona: str):
    """Lanza las 100 peticiones en momentos aleatorios dentro de la ventana de 60 segundos."""
    print(f"\n--- INICIANDO MODO ALEATORIO ({TOTAL_PETICIONES} peticiones estocásticas | Zona: {modo_zona}) ---")
    tiempos_disparo = sorted(random.uniform(0, VENTANA_TIEMPO_SEG) for _ in range(TOTAL_PETICIONES))

    tiempo_inicio = time.time()
    for i, tiempo_objetivo in enumerate(tiempos_disparo, 1):
        espera = tiempo_objetivo - (time.time() - tiempo_inicio)
        if espera > 0:
            time.sleep(espera)
        disparar_hilo(i, modo_zona)


def guardar_bitacora():
    """Exporta los registros de todos los hilos a un archivo CSV ordenado por ID de hilo."""
    bitacora.sort(key=lambda fila: fila[0])
    with open(ARCHIVO_BITACORA, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["id_hilo", "zona", "hora_envio", "hora_respuesta", "duracion_seg", "archivo_boleto", "estado"])
        writer.writerows(bitacora)


if __name__ == "__main__":
    print("=== SPAWNER CONCURRENTE - AUDITORIO PLATA ===")
    print("Selecciona la zona objetivo:")
    print("1. VIP (500 lugares)")
    print("2. PLATA (1,500 lugares)")
    print("3. GENERAL (18,000 lugares)")
    print("4. MIXTO (Distribución aleatoria entre las 3 zonas)")
    op_zona = input("Elige una zona (1/2/3/4) [Por defecto 4]: ").strip()

    mapa_zonas = {"1": "VIP", "2": "PLATA", "3": "GENERAL", "4": "MIXTO", "": "MIXTO"}
    zona_elegida = mapa_zonas.get(op_zona)
    if not zona_elegida:
        print("Zona inválida.")
        exit()

    print("\nSelecciona el algoritmo de distribución de carga:")
    print("1. Uniforme (Constante)")
    print("2. Ráfagas (Burst)")
    print("3. Aleatorio (Estocástico)")
    opcion = input("Elige una opción (1/2/3): ").strip()

    tiempo_inicio_prueba = time.time()

    if opcion == "1":
        modo_uniforme(zona_elegida)
    elif opcion == "2":
        modo_rafagas(zona_elegida)
    elif opcion == "3":
        modo_aleatorio(zona_elegida)
    else:
        print("Opción inválida.")
        exit()

    print("\nEsperando a que finalicen todas las conexiones activas...")
    for t in hilos_lanzados:
        t.join()

    tiempo_total = time.time() - tiempo_inicio_prueba
    promedio_resp = (sum(tiempos_respuesta) / len(tiempos_respuesta)) if tiempos_respuesta else 0.0
    throughput = exitos / tiempo_total if tiempo_total > 0 else 0.0
    cumple_meta = "SÍ (<= 60s)" if (exitos == TOTAL_PETICIONES and tiempo_total <= 65.0) else "PARCIAL / REVISAR"

    guardar_bitacora()

    print("\n=============================================")
    print("REPORTE DE RENDIMIENTO (FASE 3)")
    print("=============================================")
    print(f"Zona evaluada:               {zona_elegida}")
    print(f"Tiempo total de ejecución:   {tiempo_total:.2f} segundos")
    print(f"Boletos Emitidos (200 OK):   {exitos} / {TOTAL_PETICIONES}")
    print(f"Rechazos / Fallos:           {fallos}")
    print(f"Tiempo promedio respuesta:   {promedio_resp:.3f} segundos")
    print(f"Rendimiento (Throughput):    {throughput:.2f} boletos/seg")
    print(f"Meta (100 en ~60s):          {cumple_meta}")
    print(f"Bitácora guardada en:        {ARCHIVO_BITACORA}")
    print("=============================================")
