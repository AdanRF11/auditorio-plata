import threading
import requests
import time

URL_API = "http://localhost:8000/solicitar_boleto"
TOTAL_HILOS = 100

print("=== PRUEBA DE CONTENCIÓN EXTREMA CON BARRERA (SOLD OUT) ===")
print("Selecciona la zona a atacar:")
print("1. VIP")
print("2. PLATA")
print("3. GENERAL (Por defecto - coincide con Caso B de database_setup.sql)")
op = input("Elige una opción (1/2/3) [Enter para GENERAL]: ").strip()

mapa_zonas = {"1": "VIP", "2": "PLATA", "3": "GENERAL", "": "GENERAL"}
ZONA_OBJETIVO = mapa_zonas.get(op, "GENERAL")

# La Barrera retiene a los hilos hasta que los 100 estén listos
barrera = threading.Barrier(TOTAL_HILOS)

# Contadores de métricas
exitos = 0
rechazos = 0
errores = 0
latencias = []
lock_metricas = threading.Lock()


def asalto_coordinado(id_hilo: int):
    global exitos, rechazos, errores

    # El hilo llega y se bloquea esperando a los demás
    barrera.wait()

    # Todos cruzan la barrera en el mismo instante
    inicio = time.time()
    try:
        respuesta = requests.post(
            URL_API,
            params={"zona": ZONA_OBJETIVO},
            timeout=30
        )
        duracion = time.time() - inicio

        with lock_metricas:
            latencias.append(duracion)
            if respuesta.status_code == 200:
                exitos += 1
            elif respuesta.status_code == 400:  # HTTP 400: Zona Agotada (Sold Out)
                rechazos += 1
            else:
                errores += 1
    except Exception:
        with lock_metricas:
            errores += 1


print(f"\n--- PREPARANDO ATAQUE SIMULTÁNEO A ZONA '{ZONA_OBJETIVO}' ({TOTAL_HILOS} hilos) ---")
print("Alineando hilos en la barrera...")
tiempo_inicio = time.time()

lista_hilos = []
for i in range(TOTAL_HILOS):
    t = threading.Thread(target=asalto_coordinado, args=(i,))
    lista_hilos.append(t)
    t.start()

for t in lista_hilos:
    t.join()

tiempo_total = time.time() - tiempo_inicio
latencia_prom = (sum(latencias) / len(latencias)) if latencias else 0.0

print("\n=============================================")
print("REPORTE DE ESTRÉS: BARRERA Y LÍMITE DE AFORO")
print("=============================================")
print(f"Zona atacada:                        {ZONA_OBJETIVO}")
print(f"Tiempo total del ataque:             {tiempo_total:.2f} segundos")
print(f"Latencia promedio por hilo:          {latencia_prom:.3f} segundos")
print(f"Boletos Emitidos (200 OK):           {exitos}")
print(f"Rechazos por Sold Out (HTTP 400):    {rechazos}")
print(f"Errores de Red / Caídas (HTTP 500):  {errores} (Esperado: 0)")
print("=============================================")
