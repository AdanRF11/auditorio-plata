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
def solicitar_boleto(zona: str = "GENERAL"):
    zona_limpia = zona.strip().upper()
    if zona_limpia not in ("VIP", "PLATA", "GENERAL"):
        raise HTTPException(status_code=400, detail="Zona inválida. Elige VIP, PLATA o GENERAL.")

    with pool.acquire() as conn:
        with conn.cursor() as cursor:
            folio_var = cursor.var(int)
            asiento_var = cursor.var(str)
            mensaje_var = cursor.var(str)
            fecha_var = cursor.var(str)

            cursor.callproc("emitir_boleto", [1, zona_limpia, folio_var, asiento_var, mensaje_var, fecha_var])

            folio = folio_var.getvalue()
            asiento = asiento_var.getvalue()
            mensaje = mensaje_var.getvalue()
            fecha = fecha_var.getvalue()

            if not folio or folio == 0:
                raise HTTPException(status_code=400, detail=mensaje)

    with pdf_semaphore:
        pdf_buffer = ticket_generator.generar_boleto_pdf(
            folio=folio, 
            fecha_emision=fecha, 
            zona=zona_limpia, 
            asiento=asiento
        )

    filename = f"Boleto_{asiento}_Folio_{folio:06d}.pdf"
    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )

@app.get("/estado")
def obtener_estado():
    """Retorna el estado global y desglosado por zonas desde Oracle"""
    try:
        with pool.acquire() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT id_zona, nombre, aforo_total, boletos_emitidos 
                    FROM Zona 
                    ORDER BY CASE id_zona 
                        WHEN 'VIP' THEN 1 
                        WHEN 'PLATA' THEN 2 
                        ELSE 3 
                    END
                """)
                filas = cursor.fetchall()

                zonas = []
                total_aforo = 0
                total_emitidos = 0

                for id_z, nombre, aforo, emitidos in filas:
                    disponibles = aforo - emitidos
                    total_aforo += aforo
                    total_emitidos += emitidos
                    zonas.append({
                        "id_zona": id_z,
                        "nombre": nombre,
                        "aforo_total": aforo,
                        "boletos_emitidos": emitidos,
                        "disponibles": disponibles
                    })

                return {
                    "aforo_total": total_aforo,
                    "boletos_emitidos": total_emitidos,
                    "disponibles": total_aforo - total_emitidos,
                    "zonas": zonas
                }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error de base de datos: {str(e)}")


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard():
    """Panel de monitoreo en tiempo real con desglose por zonas"""
    return """
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Dashboard - Auditorio Plata</title>
        <style>
            body {
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background-color: #0f172a;
                color: #f8fafc;
                margin: 0;
                padding: 30px 20px;
                text-align: center;
            }
            .header { margin-bottom: 30px; }
            .header h1 { color: #f9d77e; margin: 0 0 8px 0; font-size: 2.2em; }
            .header p { color: #94a3b8; margin: 0; }
            
            .resumen-global {
                max-width: 900px;
                margin: 0 auto 30px auto;
                background: #1e293b;
                border: 2px solid #d4af37;
                border-radius: 14px;
                padding: 25px;
                display: grid;
                grid-template-columns: repeat(3, 1fr);
                gap: 15px;
            }
            .metrica-valor { font-size: 2.2em; font-weight: bold; color: #38bdf8; }
            .metrica-label { font-size: 0.9em; color: #cbd5e1; text-transform: uppercase; letter-spacing: 1px; }

            .zonas-container {
                max-width: 900px;
                margin: 0 auto;
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
                gap: 20px;
            }
            .zona-box {
                background: #1e293b;
                border-radius: 14px;
                padding: 22px;
                border: 1px solid #334155;
                text-align: left;
            }
            .zona-box h2 { margin: 0 0 12px 0; font-size: 1.3em; color: #f9d77e; }
            .dato-fila { display: flex; justify-content: space-between; margin: 8px 0; font-size: 1em; }
            .barra-fondo {
                width: 100%;
                height: 12px;
                background: #0f172a;
                border-radius: 6px;
                overflow: hidden;
                margin-top: 14px;
            }
            .barra-progreso {
                height: 100%;
                background: linear-gradient(90deg, #22c55e, #eab308);
                width: 0%;
                transition: width 0.3s ease;
            }
        </style>
    </head>
    <body>
        <div class="header">
            <h1>Monitor de Aforo en Tiempo Real</h1>
            <p>Auditorio Plata - Gran Concierto Navideño 2026</p>
        </div>

        <div class="resumen-global">
            <div>
                <div class="metrica-valor" id="global-total">20,000</div>
                <div class="metrica-label">Aforo Total</div>
            </div>
            <div>
                <div class="metrica-valor" id="global-emitidos" style="color: #4ade80;">0</div>
                <div class="metrica-label">Boletos Emitidos</div>
            </div>
            <div>
                <div class="metrica-valor" id="global-disponibles" style="color: #facc15;">20,000</div>
                <div class="metrica-label">Disponibles</div>
            </div>
        </div>

        <div class="zonas-container" id="zonas-grid"></div>

        <script>
            async function actualizarDashboard() {
                try {
                    const res = await fetch('/estado');
                    if (!res.ok) return;
                    const data = await res.json();

                    document.getElementById('global-total').innerText = data.aforo_total.toLocaleString();
                    document.getElementById('global-emitidos').innerText = data.boletos_emitidos.toLocaleString();
                    document.getElementById('global-disponibles').innerText = data.disponibles.toLocaleString();

                    const grid = document.getElementById('zonas-grid');
                    grid.innerHTML = '';

                    data.zonas.forEach(z => {
                        const porcentaje = z.aforo_total > 0 ? ((z.boletos_emitidos / z.aforo_total) * 100).toFixed(1) : 0;
                        const colorBarra = porcentaje >= 100 ? '#ef4444' : '#22c55e';

                        grid.innerHTML += `
                            <div class="zona-box">
                                <h2>${z.nombre}</h2>
                                <div class="dato-fila"><span>Capacidad:</span><strong>${z.aforo_total.toLocaleString()}</strong></div>
                                <div class="dato-fila"><span>Emitidos:</span><strong style="color:#4ade80;">${z.boletos_emitidos.toLocaleString()}</strong></div>
                                <div class="dato-fila"><span>Disponibles:</span><strong style="color:#facc15;">${z.disponibles.toLocaleString()}</strong></div>
                                <div class="dato-fila"><span>Ocupación:</span><strong>${porcentaje}%</strong></div>
                                <div class="barra-fondo">
                                    <div class="barra-progreso" style="width: ${porcentaje}%; background: ${colorBarra};"></div>
                                </div>
                            </div>
                        `;
                    });
                } catch (err) {
                    console.error("Error consultando /estado:", err);
                }
            }

            setInterval(actualizarDashboard, 400);
            actualizarDashboard();
        </script>
    </body>
    </html>
    """

@app.get("/", response_class=HTMLResponse)
def pagina_inicio():
    """Interfaz pública Navideña dividida por zonas para solicitar boletos"""
    return """
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Auditorio Plata - Concierto Navideño</title>
        <style>
            body { 
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
                background: linear-gradient(135deg, #0b172a 0%, #1a2a40 100%);
                color: #fff; 
                text-align: center; 
                padding: 40px 20px; 
                margin: 0; 
                overflow-x: hidden;
            }
            .container { 
                max-width: 820px; 
                margin: 0 auto; 
                background: rgba(15, 56, 30, 0.75); 
                backdrop-filter: blur(10px);
                padding: 40px 30px; 
                border-radius: 20px; 
                border: 2px solid #d4af37;
                box-shadow: 0 15px 35px rgba(0,0,0,0.5), 0 0 20px rgba(212, 175, 55, 0.2); 
                position: relative;
                z-index: 10;
            }
            h1 { color: #f9d77e; font-size: 2.6em; margin-bottom: 5px; text-shadow: 2px 2px 4px rgba(0,0,0,0.5); }
            .subtitulo { font-size: 1.2em; color: #e0e0e0; margin-bottom: 30px; font-weight: 300; }

            /* División en 3 columnas para las zonas */
            .zonas-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
                gap: 18px;
                margin-bottom: 30px;
            }
            .zona-card {
                background: rgba(11, 23, 42, 0.7);
                border: 2px solid rgba(212, 175, 55, 0.35);
                border-radius: 14px;
                padding: 20px 15px;
                cursor: pointer;
                transition: all 0.25s ease;
                text-align: center;
            }
            .zona-card:hover {
                border-color: #f9d77e;
                transform: translateY(-3px);
            }
            .zona-card.seleccionada {
                border-color: #f9d77e;
                background: rgba(179, 18, 23, 0.35);
                box-shadow: 0 0 18px rgba(249, 215, 126, 0.45);
            }
            .zona-titulo {
                font-size: 1.3em;
                font-weight: bold;
                color: #f9d77e;
                margin-bottom: 6px;
            }
            .zona-aforo {
                font-size: 0.95em;
                color: #cbd5e1;
                margin-bottom: 8px;
            }
            .zona-desc {
                font-size: 0.85em;
                color: #94a3b8;
            }

            .btn { 
                background: linear-gradient(45deg, #b31217, #e52d27); 
                color: white; 
                border: 2px solid #f9d77e; 
                padding: 15px 35px; 
                font-size: 1.2em; 
                font-weight: bold; 
                border-radius: 10px; 
                cursor: pointer; 
                transition: all 0.3s ease; 
                box-shadow: 0 5px 15px rgba(179, 18, 23, 0.4);
            }
            .btn:hover { background: linear-gradient(45deg, #e52d27, #b31217); transform: translateY(-2px); }
            .btn:disabled { background: #555; border-color: #777; cursor: not-allowed; transform: none; }

            .loader { display: none; margin: 20px auto; border: 4px solid rgba(255,255,255,0.1); border-top: 4px solid #f9d77e; border-radius: 50%; width: 40px; height: 40px; animation: spin 1s linear infinite; }
            @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
            #mensaje { margin-top: 20px; font-weight: bold; font-size: 1.15em; text-shadow: 1px 1px 2px rgba(0,0,0,0.8); }

            /* Nieve */
            .snowflakes { position: fixed; top: 0; left: 0; width: 100%; height: 100%; pointer-events: none; z-index: 1; }
            .snowflake { color: #fff; font-size: 1.5em; position: absolute; top: -10%; animation: fall linear infinite, sway ease-in-out infinite alternate; }
            .snowflake:nth-child(1) { left: 10%; animation-duration: 10s, 3s; font-size: 2em; }
            .snowflake:nth-child(2) { left: 30%; animation-duration: 12s, 4s; animation-delay: 2s, 1s; }
            .snowflake:nth-child(3) { left: 50%; animation-duration: 8s, 2s; animation-delay: 4s, 2s; font-size: 2.5em; }
            .snowflake:nth-child(4) { left: 70%; animation-duration: 15s, 5s; animation-delay: 1s, 3s; }
            .snowflake:nth-child(5) { left: 90%; animation-duration: 11s, 3s; animation-delay: 3s, 1.5s; }
            @keyframes fall { 0% { top: -10%; } 100% { top: 110%; } }
            @keyframes sway { 0% { transform: translateX(-20px) rotate(0deg); } 100% { transform: translateX(20px) rotate(360deg); } }
        </style>
    </head>
    <body>
        <div class="snowflakes" aria-hidden="true">
            <div class="snowflake">❅</div><div class="snowflake">❆</div><div class="snowflake">❄</div>
            <div class="snowflake">❅</div><div class="snowflake">❆</div>
        </div>

        <div class="container">
            <h1>Auditorio Plata</h1>
            <p class="subtitulo">Gran Concierto Navideño 2026 - Selecciona tu Área</p>
            
            <div class="zonas-grid">
                <div class="zona-card" id="card-VIP" onclick="seleccionarZona('VIP')">
                    <div class="zona-titulo">ZONA VIP</div>
                    <div class="zona-aforo">Capacidad: 500 lugares</div>
                    <div class="zona-desc">Primera fila frente al escenario</div>
                </div>

                <div class="zona-card" id="card-PLATA" onclick="seleccionarZona('PLATA')">
                    <div class="zona-titulo">ZONA PLATA</div>
                    <div class="zona-aforo">Capacidad: 1,500 lugares</div>
                    <div class="zona-desc">Sección preferente central</div>
                </div>

                <div class="zona-card seleccionada" id="card-GENERAL" onclick="seleccionarZona('GENERAL')">
                    <div class="zona-titulo">GENERAL</div>
                    <div class="zona-aforo">Capacidad: 18,000 lugares</div>
                    <div class="zona-desc">Acceso general al auditorio</div>
                </div>
            </div>

            <button id="btnSolicitar" class="btn" onclick="solicitarBoleto()">COMPRAR BOLETO (GENERAL)</button>
            <div id="loader" class="loader"></div>
            <div id="mensaje"></div>
        </div>

        <script>
            let zonaActual = "GENERAL";

            function seleccionarZona(zona) {
                zonaActual = zona;
                document.querySelectorAll('.zona-card').forEach(card => card.classList.remove('seleccionada'));
                document.getElementById('card-' + zona).classList.add('seleccionada');
                document.getElementById('btnSolicitar').innerText = "COMPRAR BOLETO (" + zona + ")";
                document.getElementById('mensaje').innerHTML = "";
            }

            async function solicitarBoleto() {
                const btn = document.getElementById("btnSolicitar");
                const loader = document.getElementById("loader");
                const mensaje = document.getElementById("mensaje");

                btn.disabled = true;
                loader.style.display = "block";
                mensaje.innerHTML = "Generando folio y firmando boleto para " + zonaActual + "...";
                mensaje.style.color = "#f9d77e";

                try {
                    const response = await fetch('/solicitar_boleto?zona=' + encodeURIComponent(zonaActual), { method: 'POST' });
                    
                    if (response.ok) {
                        const blob = await response.blob();
                        const url = window.URL.createObjectURL(blob);
                        const a = document.createElement('a');
                        
                        let filename = "Boleto_" + zonaActual + ".pdf";
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

                        mensaje.innerHTML = "Tu compra en " + zonaActual + " se ha realizado con éxito";
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
