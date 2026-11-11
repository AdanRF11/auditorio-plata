import threading
import requests
import time
import random
import os

# Configuración de la prueba
URL_API = "http://localhost:8000/solicitar_boleto"
TOTAL_PETICIONES = 100
VENTANA_TIEMPO_SEG = 60.0
CARPETA_DESTINO = "boletos_test"

# Contadores de métricas
exitos = 0
fallos = 0
lock_metricas = threading.Lock()

def realizar_peticion(id_hilo):
    """Función que ejecuta cada hilo para solicitar un boleto."""
    global exitos, fallos
    try:
        inicio = time.time()
        respuesta = requests.post(URL_API, timeout=30) # Timeout alto por si el semáforo los encola
        tiempo_respuesta = time.time() - inicio
        
        if respuesta.status_code == 200:
            with lock_metricas:
                exitos += 1
            # Extraer el nombre del archivo del header o generar uno genérico
            disp = respuesta.headers.get("Content-Disposition", "")
            if "filename=" in disp:
                filename = disp.split("filename=")[1].strip('"')
            else:
                filename = f"Boleto_hilo_{id_hilo}.pdf"
                
            filepath = os.path.join(CARPETA_DESTINO, filename)
            with open(filepath, "wb") as f:
                f.write(respuesta.content)
                
            print(f"[Hilo {id_hilo}] OK - Tiempo: {tiempo_respuesta:.2f}s - Guardado: {filename}")
        else:
            with lock_metricas:
                fallos += 1
            print(f"[Hilo {id_hilo}] RECHAZO - Código: {respuesta.status_code} - Error: {respuesta.text}")
    except Exception as e:
        with lock_metricas:
            fallos += 1
        print(f"[Hilo {id_hilo}] ERROR DE RED - {str(e)}")

def disparar_hilo(id_hilo):
    """Envuelve la petición en un hilo demonio para no bloquear el bucle principal."""
    t = threading.Thread(target=realizar_peticion, args=(id_hilo,))
    t.start()

def modo_uniforme():
    """Distribuye las 100 peticiones uniformemente (1 petición cada 0.6 segundos)"""
    print(f"\n--- INICIANDO MODO UNIFORME ({TOTAL_PETICIONES} peticiones en {VENTANA_TIEMPO_SEG}s) ---")
    intervalo = VENTANA_TIEMPO_SEG / TOTAL_PETICIONES
    for i in range(1, TOTAL_PETICIONES + 1):
        disparar_hilo(i)
        time.sleep(intervalo)

def modo_rafagas():
    """Lanza 5 ráfagas de 20 peticiones simultáneas, esperando 12 segundos entre cada ráfaga."""
    print(f"\n--- INICIANDO MODO RÁFAGAS (5 ráfagas de 20 peticiones) ---")
    rafagas = 5
    peticiones_por_rafaga = TOTAL_PETICIONES // rafagas
    intervalo = VENTANA_TIEMPO_SEG / rafagas
    
    hilo_id = 1
    for r in range(rafagas):
        print(f"\n[!] Disparando Ráfaga {r+1}/{rafagas}...")
        for _ in range(peticiones_por_rafaga):
            disparar_hilo(hilo_id)
            hilo_id += 1
        # Esperar al siguiente ciclo de ráfaga
        if r < rafagas - 1:
            time.sleep(intervalo)

def modo_aleatorio():
    """Lanza las 100 peticiones en momentos aleatorios dentro de la ventana de 60 segundos."""
    print(f"\n--- INICIANDO MODO ALEATORIO ({TOTAL_PETICIONES} peticiones estocásticas) ---")
    # Pre-calcular los 100 instantes de disparo
    tiempos_disparo = [random.uniform(0, VENTANA_TIEMPO_SEG) for _ in range(TOTAL_PETICIONES)]
    tiempos_disparo.sort() # Ordenar cronológicamente
    
    tiempo_inicio = time.time()
    for i, tiempo_objetivo in enumerate(tiempos_disparo, 1):
        tiempo_actual = time.time() - tiempo_inicio
        espera = tiempo_objetivo - tiempo_actual
        if espera > 0:
            time.sleep(espera)
        disparar_hilo(i)

if __name__ == "__main__":
    print("Selecciona el algoritmo de distribución de carga:")
    print("1. Uniforme (Constante)")
    print("2. Ráfagas (Burst)")
    print("3. Aleatorio (Estocástico)")
    
    opcion = input("Elige una opción (1/2/3): ")
    
    tiempo_inicio_prueba = time.time()
    
    if opcion == '1':
        modo_uniforme()
    elif opcion == '2':
        modo_rafagas()
    elif opcion == '3':
        modo_aleatorio()
    else:
        print("Opción inválida.")
        exit()
        
    # Esperar un poco a que los últimos hilos terminen de descargar su PDF
    print("\nVentana de 60s finalizada. Esperando 5 segundos a que cierren las últimas conexiones TCP...")
    time.sleep(5)
    
    tiempo_total = time.time() - tiempo_inicio_prueba
    
    print("\n=============================================")
    print("REPORTE DE RENDIMIENTO (FASE 3)")
    print("=============================================")
    print(f"Tiempo total de ejecución: {tiempo_total:.2f} segundos")
    print(f"Peticiones Exitosa (200 OK): {exitos}")
    print(f"Peticiones Fallidas/Rechazos: {fallos}")
    print("=============================================")
