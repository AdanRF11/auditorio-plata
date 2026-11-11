import threading
import requests
import time

URL_API = "http://localhost:8000/solicitar_boleto"
TOTAL_HILOS = 100

# La Barrera retiene a los hilos hasta que los 100 estén listos
barrera = threading.Barrier(TOTAL_HILOS)

# Contadores de métricas
exitos = 0
rechazos = 0
errores = 0
lock_metricas = threading.Lock()

def asalto_coordinado(id_hilo):
    global exitos, rechazos, errores
    
    # El hilo llega y se bloquea esperando a los demás
    barrera.wait()
    
    # ¡PUM! Todos cruzan la barrera en el mismo nanosegundo
    try:
        respuesta = requests.post(URL_API, timeout=30)
        
        with lock_metricas:
            if respuesta.status_code == 200:
                exitos += 1
            elif respuesta.status_code == 400: # HTTP 400: Aforo Lleno
                rechazos += 1
            else:
                errores += 1
    except Exception as e:
        with lock_metricas:
            errores += 1

print(f"--- PREPARANDO ATAQUE CERO-DAY ({TOTAL_HILOS} hilos) ---")
print("Alineando hilos en la barrera...")
tiempo_inicio = time.time()

# Desplegamos el ejército de hilos
lista_hilos = []
for i in range(TOTAL_HILOS):
    t = threading.Thread(target=asalto_coordinado, args=(i,))
    lista_hilos.append(t)
    t.start()

# Esperamos a que todos terminen
for t in lista_hilos:
    t.join()

tiempo_total = time.time() - tiempo_inicio

print("\n=============================================")
print("REPORTE DE ESTRÉS: BARRERA Y LÍMITE DE AFORO")
print("=============================================")
print(f"Tiempo total del ataque: {tiempo_total:.2f} segundos")
print(f"Boletos Emitidos (200 OK): {exitos} (Esperado: 50)")
print(f"Boletos Rechazados por Sold Out (400): {rechazos} (Esperado: 50)")
print(f"Errores de Red/Caídas (500): {errores} (Esperado: 0)")
print("=============================================")
