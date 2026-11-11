from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse, HTMLResponse
from contextlib import asynccontextmanager
import threading
import oracledb
import ticket_generator

DB_USER = "system"
DB_PASSWORD = "Admin1234"
DB_DSN = "localhost:1521/FREEPDB1"

pool = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global pool
    # Pool de conexiones optimizado y simplificado
    pool = oracledb.create_pool(
        user=DB_USER, 
        password=DB_PASSWORD, 
        dsn=DB_DSN, 
        min=2, 
        max=100, 
        increment=1
    )
    yield
    pool.close()

app = FastAPI(title="Auditorio Plata - Emisor de Boletos", lifespan=lifespan)

# Semáforo simple para controlar el uso de CPU al generar los PDFs (máximo 5 simultáneos)
MAX_PDF_WORKERS = 5
pdf_semaphore = threading.Semaphore(MAX_PDF_WORKERS)

@app.post("/solicitar_boleto")
def solicitar_boleto():
    global pool
    folio_asignado = 0
    fecha_asignada = ""
    mensaje_out = ""

    # 1. Transacción en Base de Datos (Delegación de Exclusión Mutua con FOR UPDATE)
    try:
        with pool.acquire() as connection:
            with connection.cursor() as cursor:
                folio_var = cursor.var(oracledb.NUMBER)
                mensaje_var = cursor.var(oracledb.DB_TYPE_VARCHAR)
                fecha_var = cursor.var(oracledb.DB_TYPE_VARCHAR)

                cursor.callproc("emitir_boleto", [1, folio_var, mensaje_var, fecha_var])

                folio_asignado = int(folio_var.getvalue() or 0)
                mensaje_out = str(mensaje_var.getvalue())
                fecha_asignada = str(fecha_var.getvalue())

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno DB: {str(e)}")

    if folio_asignado == 0 or "RECHAZO" in mensaje_out:
        raise HTTPException(status_code=400, detail=mensaje_out)

    # 2. Control de Recursos de Hardware (Semáforo Simple para los PDFs)
    pdf_semaphore.acquire()
    try:
        pdf_buffer = ticket_generator.generar_pdf_boleto(folio_asignado, fecha_asignada)
    finally:
        pdf_semaphore.release()

    return StreamingResponse(
        pdf_buffer, 
        media_type="application/pdf", 
        headers={"Content-Disposition": f"attachment; filename=Boleto_{folio_asignado}.pdf"}
    )

@app.get("/estado")
def estado():
    global pool
    try:
        with pool.acquire() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT aforo_total, boletos_emitidos FROM Evento WHERE id_evento = 1")
                row = cursor.fetchone()
                if row:
                    aforo, emitidos = row
                    return {
                        "aforo_total": aforo,
                        "boletos_emitidos": emitidos,
                        "disponibles": aforo - emitidos
                    }
                else:
                    raise HTTPException(status_code=404, detail="Evento no encontrado")
    except Exception as e:
        print(f"ERROR DETALLADO EN ORACLE: {str(e)}")  # <-- Esto lo imprimirá en tu terminal
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard_tiempo_real():
    return """
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <title>Monitor - Auditorio Plata</title>
        <style>
            body { font-family: Arial, sans-serif; text-align: center; margin-top: 50px; background-color: #f4f4f9; }
            .contador { font-size: 3em; font-weight: bold; color: #2c3e50; }
            .emitidos { color: #e74c3c; }
            .disponibles { color: #27ae60; }
        </style>
        <script>
            async function actualizarEstado() {
                try {
                    const response = await fetch('/estado');
                    const data = await response.json();
                    // Verificamos que los datos lleguen correctamente
                    document.getElementById('emitidos').innerText = data.boletos_emitidos !== undefined ? data.boletos_emitidos : 0;
                    document.getElementById('disponibles').innerText = data.disponibles !== undefined ? data.disponibles : 20000;
                } catch (error) { 
                    console.error("Error conectando con el servidor:", error); 
                }
            }
            setInterval(actualizarEstado, 200);
            window.onload = actualizarEstado;
        </script>
    </head>
    <body>
        <h1>Auditorio Plata - Monitor de Aforo</h1>
        <p>Aforo Total: 20,000</p>
        <div>
            <h2>Boletos Emitidos: <span id="emitidos" class="contador emitidos">0</span></h2>
            <h2>Lugares Disponibles: <span id="disponibles" class="contador disponibles">20000</span></h2>
        </div>
    </body>
    </html>
    """

@app.get("/", response_class=HTMLResponse)
def pagina_inicio():
    """Interfaz pública Navideña para solicitar boletos"""
    return """
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Auditorio Plata - Concierto Navideño</title>
        <style>
            /* Fondo de Noche de Invierno */
            body { 
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
                background: linear-gradient(135deg, #0b172a 0%, #1a2a40 100%);
                color: #fff; 
                text-align: center; 
                padding: 50px 20px; 
                margin: 0; 
                overflow-x: hidden;
            }
            
            /* Efecto Cristal (Glassmorphism) Verde Pino con borde dorado */
            .container { 
                max-width: 600px; 
                margin: 0 auto; 
                background: rgba(15, 56, 30, 0.7); 
                backdrop-filter: blur(10px);
                padding: 40px; 
                border-radius: 20px; 
                border: 2px solid #d4af37;
                box-shadow: 0 15px 35px rgba(0,0,0,0.5), 0 0 20px rgba(212, 175, 55, 0.2); 
                position: relative;
                z-index: 10;
            }
            
            h1 { color: #f9d77e; font-size: 2.8em; margin-bottom: 5px; text-shadow: 2px 2px 4px rgba(0,0,0,0.5); }
            p { font-size: 1.3em; color: #e0e0e0; margin-bottom: 30px; font-weight: 300; }
            
            /* Botón Rojo Nochebuena */
            .btn { 
                background: linear-gradient(45deg, #b31217, #e52d27); 
                color: white; 
                border: 2px solid #f9d77e; 
                padding: 15px 30px; 
                font-size: 1.3em; 
                font-weight: bold; 
                border-radius: 10px; 
                cursor: pointer; 
                transition: all 0.3s ease; 
                box-shadow: 0 5px 15px rgba(179, 18, 23, 0.4);
            }
            .btn:hover { background: linear-gradient(45deg, #e52d27, #b31217); transform: translateY(-2px); box-shadow: 0 8px 20px rgba(179, 18, 23, 0.6); }
            .btn:active { transform: scale(0.95); }
            .btn:disabled { background: #555; border-color: #777; cursor: not-allowed; box-shadow: none; transform: none; }
            
            .loader { display: none; margin: 20px auto; border: 4px solid rgba(255,255,255,0.1); border-top: 4px solid #f9d77e; border-radius: 50%; width: 40px; height: 40px; animation: spin 1s linear infinite; }
            @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
            #mensaje { margin-top: 20px; font-weight: bold; font-size: 1.2em; text-shadow: 1px 1px 2px rgba(0,0,0,0.8); }

            /* Animación de Nieve CSS Puro */
            .snowflakes { position: fixed; top: 0; left: 0; width: 100%; height: 100%; pointer-events: none; z-index: 1; }
            .snowflake { color: #fff; font-size: 1.5em; position: absolute; top: -10%; animation: fall linear infinite, sway ease-in-out infinite alternate; text-shadow: 0 0 5px rgba(255,255,255,0.8); }
            .snowflake:nth-child(1) { left: 10%; animation-duration: 10s, 3s; animation-delay: 0s, 0s; font-size: 2em; }
            .snowflake:nth-child(2) { left: 30%; animation-duration: 12s, 4s; animation-delay: 2s, 1s; }
            .snowflake:nth-child(3) { left: 50%; animation-duration: 8s, 2s; animation-delay: 4s, 2s; font-size: 2.5em; }
            .snowflake:nth-child(4) { left: 70%; animation-duration: 15s, 5s; animation-delay: 1s, 3s; }
            .snowflake:nth-child(5) { left: 90%; animation-duration: 11s, 3s; animation-delay: 3s, 1.5s; font-size: 1.8em; }
            .snowflake:nth-child(6) { left: 20%; animation-duration: 9s, 3.5s; animation-delay: 5s, 0.5s; }
            .snowflake:nth-child(7) { left: 80%; animation-duration: 13s, 4.5s; animation-delay: 0.5s, 2.5s; font-size: 2.2em; }
            @keyframes fall { 0% { top: -10%; } 100% { top: 110%; } }
            @keyframes sway { 0% { transform: translateX(-20px) rotate(0deg); } 100% { transform: translateX(20px) rotate(360deg); } }
        </style>
    </head>
    <body>
        <!-- Nieve de fondo -->
        <div class="snowflakes" aria-hidden="true">
            <div class="snowflake">❅</div><div class="snowflake">❆</div><div class="snowflake">❄</div>
            <div class="snowflake">❅</div><div class="snowflake">❆</div><div class="snowflake">❄</div>
            <div class="snowflake">❅</div>
        </div>

        <div class="container">
            <h1>Auditorio Plata</h1>
            <p>Gran Concierto Navideño 2026</p>
            
            <button id="btnSolicitar" class="btn" onclick="solicitarBoleto()">COMPRAR AHORA!!</button>
            <div id="loader" class="loader"></div>
            <div id="mensaje"></div>
        </div>

        <script>
            async function solicitarBoleto() {
                const btn = document.getElementById("btnSolicitar");
                const loader = document.getElementById("loader");
                const mensaje = document.getElementById("mensaje");

                btn.disabled = true;
                loader.style.display = "block";
                mensaje.innerHTML = "Generando folio y firmando boleto...";
                mensaje.style.color = "#f9d77e";

                try {
                    const response = await fetch('/solicitar_boleto', { method: 'POST' });
                    
                    if (response.ok) {
                        const blob = await response.blob();
                        const url = window.URL.createObjectURL(blob);
                        const a = document.createElement('a');
                        
                        let filename = "Boleto_Navideno.pdf";
                        const disposition = response.headers.get('Content-Disposition');
                        if (disposition && disposition.includes('filename=')) {
                            filename = disposition.split('filename=')[1].replace(/"/g, '');
                        }

                        a.href = url;
                        a.download = filename;
                        document.body.appendChild(a);
                        a.click();
                        a.remove();
                        window.URL.revokeObjectURL(url);

                        mensaje.innerHTML = "Tu compra se ha realizado con éxito";
                        mensaje.style.color = "#4ade80"; 
                    } else {
                        const errorData = await response.json();
                        mensaje.innerHTML = (errorData.detail || "Error al solicitar boleto.");
                        mensaje.style.color = "#f87171"; 
                    }
                } catch (error) {
                    mensaje.innerHTML = "Error de conexión con el servidor.";
                    mensaje.style.color = "#f87171";
                } finally {
                    btn.disabled = false;
                    loader.style.display = "none";
                }
            }
        </script>
    </body>
    </html>
    """
