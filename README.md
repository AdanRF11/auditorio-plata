# 🎟️ Auditorio Plata - Sistema Concurrente de Boletaje

Sistema backend de alta concurrencia desarrollado para la gestión y emisión segura de boletos electrónicos para el **"Concierto Navideño"**. Implementa mecanismos de exclusión mutua a nivel de base de datos, control de recursos de CPU y firmas criptográficas SHA-256.

---

## 🚀 Tecnologías Utilizadas

- **Lenguaje:** Python 3.10+
- **Framework Web:** FastAPI (Uvicorn ASGI).
- **Base de Datos:** Oracle AI Database Free (Docker Container).
- **Procesamiento Gráfico:** ReportLab, qrcode y Pillow (generación de PDF y códigos QR en memoria RAM).
- **Control de Concurrencia:** `threading` (Locks, Semaphores y Barriers).
- **Transacciones:** Propiedades ACID mediante `SELECT ... FOR UPDATE`.

---

## 📁 Estructura del Repositorio

| Archivo | Descripción |
|---|---|
| `main.py` | Servidor FastAPI, endpoints REST y Landing Page navideña. |
| `ticket_generator.py` | Módulo de generación de PDFs con firma digital SHA-256. |
| `spawner.py` | Orquestador de pruebas de estrés (modos uniforme, ráfagas y aleatorio). |
| `ataque_barrera.py` | Script de prueba de límite extremo (*Sold Out*) mediante barreras de sincronización. |
| `database_setup.sql` | Esquema relacional, secuencias y procedimientos almacenados en PL/SQL. |
| `.gitignore` | Configuración para excluir entornos virtuales, caché y archivos temporales. |

---

## ⚙️ Instrucciones de Instalación y Ejecución

### 1. Levantar la Base de Datos (Oracle)

Ejecutar el siguiente comando para iniciar el contenedor de Oracle AI Database Free:

```bash
sudo docker run -d \
  --name oracle-free \
  -p 1521:1521 \
  -e ORACLE_PASSWORD=Admin1234 \
  container-registry.oracle.com/database/free:latest
```

### 2. Configurar el Entorno Virtual de Python

Crear y activar un entorno virtual:

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

---

## 🌐 Endpoints e Interfaces Disponibles

Una vez que el servidor esté en ejecución, se puede acceder a los siguientes módulos desde el navegador:

**Dirección principal:** `http://localhost:8000`

| Módulo | URL | Descripción |
|---|---|---|
| 🏠 Landing Page Pública | `http://localhost:8000/` | Interfaz gráfica interactiva con temática navideña y efecto cristal. Cuenta con un botón de compra segura que procesa la solicitud y descarga automáticamente el PDF del boleto. |
| 📊 Monitor en Tiempo Real | `http://localhost:8000/dashboard` | Panel visual con actualización automática (*polling* cada 200 ms) que muestra el número de boletos emitidos y los lugares disponibles. |
| 📡 Consulta de Estado | `http://localhost:8000/estado` | Endpoint RESTful que retorna el estado actual del aforo y los contadores en formato JSON. |
| 📚 Documentación Interactiva | `http://localhost:8000/docs` | Interfaz Swagger UI / OpenAPI autogenerada por FastAPI para probar los endpoints HTTP y la emisión manual de folios. |

---

## 🧪 Ejecución de Pruebas de Estrés

Para ejecutar las pruebas, es necesario abrir una terminal independiente y activar el entorno virtual de Python.

### Fase 3: Prueba de distribución de carga (Spawner)

Ejecutar el siguiente comando:

```bash
python spawner.py
```

Este script permite realizar pruebas de carga utilizando diferentes patrones de distribución de solicitudes:

- Distribución uniforme.
- Solicitudes en ráfagas.
- Distribución aleatoria.

### Fase 4: Prueba de límite extremo y Sold Out (Barreras)

Ejecutar:

```bash
python ataque_barrera.py
```

Esta prueba utiliza barreras de sincronización para coordinar solicitudes concurrentes y comprobar que el sistema respete el límite máximo de boletos disponibles, evitando la sobreventa (*overselling*).

---

## 🔐 Características Principales

- **Concurrencia:** Gestión de múltiples solicitudes simultáneas.
- **Exclusión mutua:** Protección de los registros mediante bloqueos a nivel de base de datos.
- **Integridad transaccional:** Uso de transacciones ACID para garantizar la consistencia de los datos.
- **Seguridad criptográfica:** Generación de firmas SHA-256 para verificar la integridad de los boletos.
- **Generación dinámica:** Creación de boletos electrónicos en formato PDF con códigos QR.
- **Monitoreo:** Visualización del estado del aforo en tiempo real.
- **Pruebas de estrés:** Simulación de múltiples compradores para evaluar el comportamiento del sistema bajo condiciones de alta demanda.

---
