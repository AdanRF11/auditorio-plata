# 🎟️ Auditorio Plata - Sistema Concurrente de Boletaje

Sistema backend de alta concurrencia desarrollado para la gestión, asignación de asientos y emisión segura de boletos electrónicos para el **Concierto Navideño 2026**.

Gestiona un aforo total de **20,000 asientos**, divididas en tres áreas independientes (**VIP**, **Plata** y **General**), implementando exclusión mutua en cada área a nivel de base de datos, control de recursos de CPU y firmas criptográficas SHA-256.

---

## 🚀 Tecnologías Utilizadas

- **Lenguaje:** Python 3.10+
- **Framework Web:** FastAPI (Uvicorn ASGI).
- **Base de Datos:** Oracle AI Database Free (Docker Container `FREEPDB1`).
- **Procesamiento Gráfico:** ReportLab, `qrcode` y Pillow (generación dinámica de PDF y códigos QR en memoria RAM).
- **Control de Concurrencia:** `threading` (`Lock`, `Semaphore` y `Barrier`).
- **Transacciones:** Propiedades ACID y bloqueo granular por fila mediante `SELECT ... FOR UPDATE`.
- **Exposición Pública:** Cloudflare Tunnel (`cloudflared`) con cifrado HTTPS automático.

---

## 📁 Estructura del Repositorio

| Archivo | Descripción |
|---|---|
| `main.py` | Servidor FastAPI, endpoints REST, Landing Page navideña con selección de áreas y Dashboard en tiempo real por zona. |
| `ticket_generator.py` | Generador unificado de boletos PDF en memoria RAM con diseño adaptativo por zona, asignación de asiento, código QR y firma digital SHA-256. |
| `spawner.py` | Orquestador de pruebas de estrés multihilo (modos uniforme, ráfagas y aleatorio). |
| `ataque_barrera.py` | Script de prueba de contención extrema (*Sold Out*) mediante barreras de sincronización (`threading.Barrier`). |
| `database_setup.sql` | Esquema relacional (`Evento`, `Zona`, `Boleto`), secuencia atómica `seq_folio`, procedimiento almacenado PL/SQL y utilidades de reinicio. |
| `.gitignore` | Configuración para excluir entornos virtuales (`venv`), caché y archivos temporales. |

---

## ⚙️ Instrucciones de Instalación y Ejecución

### 1. Levantar la Base de Datos (Oracle)

**Primera ejecución (creación e inicialización del contenedor):**

```bash
sudo docker run -d \
  --name oracle-free \
  -p 1521:1521 \
  -e ORACLE_PASSWORD=Admin1234 \
  container-registry.oracle.com/database/free:latest
```

Tenemos que esperar a que Oracle termine de inicializarse. Para comprobar el estado del contenedor debemos escribir el siguiente comando:

```bash
sudo docker ps
```

Una vez que el contenedor muestre el estado `healthy`, debemos cargar el esquema de la base de datos ejecutando `database_setup.sql` mediante SQL*Plus:

```bash
sqlplus system/Admin1234@FREEPDB1
```

**Ejecuciones posteriores (encender el contenedor existente):**

Ahora que el contenedor ya fue creado e inicializado anteriormente, solamente es necesario iniciarlo con este siguiente comando:

```bash
sudo docker start oracle-free
```

### 2. Configurar el Entorno Virtual de Python

Crear y activar el entorno virtual con los siguientes dos comandos:

```bash
python3 -m venv venv
source venv/bin/activate
```

Instalar las dependencias necesarias:

```bash
pip install fastapi uvicorn reportlab qrcode pillow pydantic oracledb requests
```

### 3. Ejecutar el Servidor Web

Iniciar el servidor FastAPI con Uvicorn:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

### 4. Exponer el Servidor a Internet (Túnel de Cloudflare)

En una terminal independiente, iniciamos un túnel seguro hacia el puerto local `8000`, utilizando `http://` como origen local:

```bash
cloudflared tunnel --url http://localhost:8000
```

Cloudflare generará una URL pública con certificado SSL:

```text
https://<subdominio-aleatorio>.trycloudflare.com
```

Esta dirección permitirá acceder al servidor desde cualquier red externa mientras el túnel permanezca activo.

---

## 🏟️ Distribución de Zonas y Aforo (20,000 asientos)

El auditorio cuenta con tres zonas independientes, cada una con una capacidad y formato de identificación de asientos específico.

| Zona | Capacidad | Formato de Asiento | Distintivo Visual |
|---|---:|---|---|
| **VIP** | 500 lugares | `VIP-001` a `VIP-500` | Dorado (`#d4af37`) |
| **Plata** | 1,500 lugares | `PLATA-0001` a `PLATA-1500` | Plateado (`#94a3b8`) |
| **General** | 18,000 lugares | `GENERAL-00001` a `GENERAL-18000` | Verde (`#15803d`) |
| **TOTAL** | **20,000 lugares** | | |

---

## 🌐 Endpoints e Interfaces Disponibles

Una vez que el servidor esté en ejecución, se puede acceder a los siguientes módulos desde el navegador. También es posible sustituir `http://localhost:8000` por la URL pública generada por Cloudflare.

| Módulo | Ruta / Endpoint | Descripción |
|---|---|---|
| 🏠 **Landing Page Pública** | `GET /` | Interfaz web navideña dividida en tres tarjetas seleccionables (**VIP**, **Plata** y **General**) que solicita el boleto del área elegida y descarga automáticamente el PDF. |
| 🎟️ **Emisión de Boletos** | `POST /solicitar_boleto?zona=VIP` | Procesa la compra única para la zona indicada (`VIP`, `PLATA` o `GENERAL`; por defecto `GENERAL`), asigna folio y asiento consecutivo, y devuelve el PDF. |
| 📊 **Monitor en Tiempo Real** | `GET /dashboard` | Panel visual con actualización automática (*polling* cada 400 ms) que muestra el aforo global y barras de ocupación individuales por cada zona. |
| 📡 **Consulta de Estado** | `GET /estado` | Endpoint REST que retorna en formato JSON la disponibilidad global y el desglose detallado de boletos emitidos por área. |
| 📚 **Documentación Interactiva** | `GET /docs` | Interfaz Swagger UI / OpenAPI autogenerada por FastAPI para probar los endpoints HTTP y la emisión manual por zona. |

---

## 🧪 Ejecución de Pruebas de Estrés

Para ejecutar las pruebas, abrimos una terminal independiente y activamos el entorno virtual de Python:

```bash
source venv/bin/activate
```

### Fase 3: Prueba de distribución de carga (Spawner)

Ejecutamos el siguiente comando:

```bash
python spawner.py
```

Permite inyectar **100 solicitudes concurrentes** dentro de una ventana de **60 segundos**, utilizando tres algoritmos de tráfico que son los siguientes:

- **Distribución uniforme:** solicitudes distribuidas de manera constante durante el periodo de prueba.
- **Solicitudes en ráfagas:** múltiples solicitudes enviadas en intervalos cortos.
- **Distribución aleatoria:** solicitudes generadas en momentos aleatorios.

### Fase 4: Prueba de límite extremo y Sold Out (Barreras)

Ejecutamos este comando para generar el ataque a la página de la venta de boletos:

```bash
python ataque_barrera.py
```

Utiliza barreras de sincronización (`threading.Barrier`) para liberar todos los hilos en el mismo instante, comprobando que la exclusión mutua en Oracle rechace de forma determinista cualquier solicitud que exceda el cupo de la zona o del auditorio.

El objetivo es garantizar que no exista sobreventa de asientos (*overselling*), incluso bajo condiciones de concurrencia extrema.

---
