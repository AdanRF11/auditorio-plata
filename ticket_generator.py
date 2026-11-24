import io
import math
import hashlib
import qrcode
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader

SECRET_KEY = "AUDITORIO_PLATA_SECRETO_2026"

# ---------------------------------------------------------------------------
# Temas por zona: cada tipo de boleto tiene su propia paleta navideña
# ---------------------------------------------------------------------------
TEMAS = {
    "VIP": {
        "primario":   colors.HexColor("#7a1f2b"),   # Vino / burdeos
        "acento":     colors.HexColor("#d4af37"),   # Dorado
        "fondo":      colors.HexColor("#fff8e1"),   # Crema dorada
        "arbol":      colors.HexColor("#14532d"),
        "adorno_a":   colors.HexColor("#d4af37"),
        "adorno_b":   colors.HexColor("#b91c1c"),
        "texto_acento": colors.HexColor("#3b0d14"),
        "lema":       "Experiencia VIP",
    },
    "PLATA": {
        "primario":   colors.HexColor("#1e3a5f"),   # Azul invierno
        "acento":     colors.HexColor("#94a3b8"),   # Plateado
        "fondo":      colors.HexColor("#f1f5f9"),   # Hielo
        "arbol":      colors.HexColor("#2f5d8a"),
        "adorno_a":   colors.HexColor("#cbd5e1"),
        "adorno_b":   colors.HexColor("#60a5fa"),
        "texto_acento": colors.HexColor("#0f172a"),
        "lema":       "Noche de Plata",
    },
    "GENERAL": {
        "primario":   colors.HexColor("#14532d"),   # Verde bosque
        "acento":     colors.HexColor("#c62828"),   # Rojo navideño
        "fondo":      colors.HexColor("#f0fdf4"),   # Verde muy claro
        "arbol":      colors.HexColor("#15803d"),
        "adorno_a":   colors.HexColor("#c62828"),
        "adorno_b":   colors.HexColor("#e8c547"),
        "texto_acento": colors.white,
        "lema":       "Felices Fiestas",
    },
}


# ---------------------------------------------------------------------------
# Elementos decorativos dibujados con vectores (no requieren imágenes)
# ---------------------------------------------------------------------------
def dibujar_estrella(c, cx, cy, r, color, puntas=5):
    """Estrella de varias puntas rellena."""
    c.setFillColor(color)
    p = c.beginPath()
    for i in range(puntas * 2):
        ang = math.pi / 2 + i * math.pi / puntas
        rad = r if i % 2 == 0 else r * 0.42
        x, y = cx + rad * math.cos(ang), cy + rad * math.sin(ang)
        p.moveTo(x, y) if i == 0 else p.lineTo(x, y)
    p.close()
    c.drawPath(p, fill=1, stroke=0)


def dibujar_copo(c, cx, cy, r, color, grosor=0.8):
    """Copo de nieve de 6 brazos con ramitas."""
    c.setStrokeColor(color)
    c.setLineWidth(grosor)
    for i in range(6):
        ang = i * math.pi / 3
        dx, dy = math.cos(ang), math.sin(ang)
        c.line(cx, cy, cx + r * dx, cy + r * dy)
        # ramitas en V a 60% del brazo
        bx, by = cx + 0.6 * r * dx, cy + 0.6 * r * dy
        for lado in (-1, 1):
            a2 = ang + lado * math.pi / 6
            c.line(bx, by, bx + 0.35 * r * math.cos(a2), by + 0.35 * r * math.sin(a2))


def dibujar_esfera(c, cx, cy, r, color):
    """Esfera navideña con casquillo y brillo."""
    c.setFillColor(colors.HexColor("#9ca3af"))
    c.rect(cx - r * 0.3, cy + r * 0.9, r * 0.6, r * 0.35, fill=1, stroke=0)
    c.setFillColor(color)
    c.circle(cx, cy, r, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFillAlpha(0.45)
    c.circle(cx - r * 0.35, cy + r * 0.35, r * 0.25, fill=1, stroke=0)
    c.setFillAlpha(1)


def dibujar_arbol(c, cx, base_y, alto, color_arbol, color_estrella, colores_luces):
    """Arbolito de tres niveles con estrella y luces."""
    c.setFillColor(colors.HexColor("#6b4423"))
    c.rect(cx - alto * 0.06, base_y, alto * 0.12, alto * 0.14, fill=1, stroke=0)
    c.setFillColor(color_arbol)
    niveles = [(0.14, 0.50, 0.26), (0.38, 0.40, 0.21), (0.60, 0.30, 0.16)]
    for y0, ancho, h in niveles:
        yb = base_y + alto * y0
        p = c.beginPath()
        p.moveTo(cx - alto * ancho / 2, yb)
        p.lineTo(cx + alto * ancho / 2, yb)
        p.lineTo(cx, yb + alto * (h + 0.14))
        p.close()
        c.drawPath(p, fill=1, stroke=0)
    # luces
    posiciones = [(-0.12, 0.22), (0.10, 0.28), (-0.06, 0.46), (0.09, 0.50), (0.0, 0.66)]
    for i, (dx, dy) in enumerate(posiciones):
        c.setFillColor(colores_luces[i % len(colores_luces)])
        c.circle(cx + alto * dx, base_y + alto * dy, alto * 0.025, fill=1, stroke=0)
    dibujar_estrella(c, cx, base_y + alto * 0.93, alto * 0.09, color_estrella)


def dibujar_acebo(c, cx, cy, escala=1.0):
    """Hojas de acebo con bayas rojas."""
    c.setFillColor(colors.HexColor("#166534"))
    for ang in (35, 145):
        c.saveState()
        c.translate(cx, cy)
        c.rotate(ang)
        c.scale(escala, escala)
        c.ellipse(0, -3, 16, 3, fill=1, stroke=0)
        c.restoreState()
    c.setFillColor(colors.HexColor("#b91c1c"))
    for dx, dy in ((0, 0), (-3, -3), (3, -3)):
        c.circle(cx + dx * escala, cy + dy * escala, 2.6 * escala, fill=1, stroke=0)


def dibujar_guirnalda(c, x_ini, x_fin, y, tema):
    """Guirnalda con esferas colgando a lo largo de un borde."""
    paso = 26
    n = int((x_fin - x_ini) / paso)
    c.setStrokeColor(tema["acento"])
    c.setLineWidth(1.6)
    p = c.beginPath()
    for i in range(n + 1):
        x = x_ini + i * paso
        # onda suave
        yy = y - 5 * math.sin(i * math.pi)
        p.moveTo(x, yy) if i == 0 else p.lineTo(x, yy)
    c.drawPath(p, fill=0, stroke=1)
    for i in range(n + 1):
        x = x_ini + i * paso
        color = tema["adorno_a"] if i % 2 == 0 else tema["adorno_b"]
        dibujar_esfera(c, x, y - 17 - (i % 2) * 4, 5.5, color)


# ---------------------------------------------------------------------------
# Generador del boleto
# ---------------------------------------------------------------------------
def generar_boleto_pdf(folio: int, fecha_emision: str, zona: str = "GENERAL", asiento: str = "GENERAL-00001") -> io.BytesIO:
    zona = zona.upper()
    tema = TEMAS.get(zona, TEMAS["GENERAL"])

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    # Firma criptográfica vinculada al folio, zona, asiento y fecha
    datos_firma = f"{folio}|{zona}|{asiento}|{fecha_emision}|{SECRET_KEY}"
    firma_sha256 = hashlib.sha256(datos_firma.encode("utf-8")).hexdigest()

    # Geometría del boleto
    x0, ancho = 40, width - 80
    top = height - 40
    alto = 360
    y0 = top - alto

    # --- Fondo del boleto con tinte de la zona ---
    c.setFillColor(tema["fondo"])
    c.roundRect(x0, y0, ancho, alto, 14, fill=1, stroke=0)

    # Nieve de fondo (suave) en la zona libre del boleto
    c.setFillAlpha(0.55)
    puntos_nieve = [
        (80, top - 270, 7), (150, top - 300, 5), (230, top - 262, 6), (310, top - 295, 8),
        (395, top - 268, 5), (470, top - 300, 7), (545, top - 262, 6),
        (62, top - 160, 4), (555, top - 105, 4), (545, top - 245, 5),
    ]
    for sx, sy, sr in puntos_nieve:
        dibujar_copo(c, sx, sy, sr, tema["acento"], 0.9)
    c.setFillAlpha(1)

    # --- Banda superior ---
    c.setFillColor(tema["primario"])
    c.saveState()
    clip = c.beginPath()
    clip.roundRect(x0, y0, ancho, alto, 14)
    c.clipPath(clip, stroke=0, fill=0)
    c.rect(x0, top - 78, ancho, 78, fill=1, stroke=0)
    # Banda inferior
    c.rect(x0, y0, ancho, 56, fill=1, stroke=0)
    c.restoreState()

    # Filetes de acento junto a las bandas
    c.setFillColor(tema["acento"])
    c.rect(x0, top - 82, ancho, 4, fill=1, stroke=0)
    c.rect(x0, y0 + 56, ancho, 4, fill=1, stroke=0)

    # --- Marco exterior (color de zona) + marco interior punteado ---
    c.setStrokeColor(tema["acento"])
    c.setLineWidth(4)
    c.roundRect(x0, y0, ancho, alto, 14, fill=0, stroke=1)
    c.setStrokeColor(colors.white)
    c.setLineWidth(0.8)
    c.setDash(3, 3)
    c.roundRect(x0 + 8, y0 + 8, ancho - 16, alto - 16, 10, fill=0, stroke=1)
    c.setDash()

    # --- Encabezado ---
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 24)
    c.drawString(x0 + 70, top - 38, "AUDITORIO PLATA")
    c.setFillColor(tema["acento"] if zona != "GENERAL" else colors.HexColor("#fde68a"))
    c.setFont("Helvetica-Oblique", 13)
    c.drawString(x0 + 70, top - 60, "Gran Concierto Navideño 2026")

    # Estrellas y copos en los extremos del encabezado
    dibujar_estrella(c, x0 + 36, top - 40, 16, tema["acento"] if zona != "GENERAL" else colors.HexColor("#fde68a"))
    dibujar_estrella(c, x0 + ancho - 36, top - 40, 16, tema["acento"] if zona != "GENERAL" else colors.HexColor("#fde68a"))
    dibujar_copo(c, x0 + 330, top - 30, 7, colors.white)
    dibujar_copo(c, x0 + 372, top - 52, 5, colors.white)
    dibujar_copo(c, x0 + 418, top - 28, 6, colors.white)

    # Guirnalda colgando bajo la banda
    dibujar_guirnalda(c, x0 + 26, x0 + ancho - 20, top - 86, tema)

    # --- Etiqueta de zona ---
    c.setFillColor(tema["acento"])
    c.roundRect(x0 + 25, top - 160, 190, 32, 8, fill=1, stroke=0)
    c.setFillColor(tema["texto_acento"])
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(x0 + 120, top - 150, f"AREA: {zona}")
    c.setFillColor(tema["primario"])
    c.setFont("Helvetica-Oblique", 10)
    c.drawString(x0 + 225, top - 150, tema["lema"])

    # --- Datos del boleto ---
    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(x0 + 25, top - 188, f"Asiento Asignado: {asiento}")

    c.setFont("Helvetica-Bold", 12)
    c.drawString(x0 + 25, top - 212, f"Folio Único: #{folio:06d}")

    c.setFont("Helvetica", 11)
    c.drawString(x0 + 25, top - 233, f"Fecha y Hora de Emisión: {fecha_emision}")

    c.setFillColor(colors.HexColor("#475569"))
    c.setFont("Helvetica", 8)
    c.drawString(x0 + 25, top - 252, f"Firma SHA-256: {firma_sha256[:48]}...")

    # --- Código QR con folio, zona, asiento y firma ---
    contenido_qr = f"AUDITORIO_PLATA|FOLIO:{folio}|ZONA:{zona}|ASIENTO:{asiento}|FECHA:{fecha_emision}|HASH:{firma_sha256[:16]}"
    qr_img = qrcode.make(contenido_qr)
    qr_buffer = io.BytesIO()
    qr_img.save(qr_buffer, format="PNG")
    qr_buffer.seek(0)

    qr_size = 130
    qr_x = x0 + ancho - qr_size - 32
    qr_y = top - 126 - qr_size
    # Marco blanco con borde de acento alrededor del QR
    c.setFillColor(colors.white)
    c.setStrokeColor(tema["acento"])
    c.setLineWidth(2)
    c.roundRect(qr_x - 8, qr_y - 8, qr_size + 16, qr_size + 16, 8, fill=1, stroke=1)
    c.drawImage(ImageReader(qr_buffer), qr_x, qr_y, width=qr_size, height=qr_size)

    # --- Pie del boleto: arbolitos, acebo y mensaje ---
    luces = [tema["adorno_a"], tema["adorno_b"], colors.white]
    for ax in (x0 + 40, x0 + 95, x0 + ancho - 95, x0 + ancho - 40):
        dibujar_arbol(c, ax, y0 + 8, 46, tema["arbol"] if zona != "GENERAL" else colors.HexColor("#22c55e"),
                      tema["acento"] if zona != "GENERAL" else colors.HexColor("#fde68a"), luces)
    dibujar_acebo(c, x0 + 150, y0 + 22, 1.1)
    dibujar_acebo(c, x0 + ancho - 150, y0 + 22, 1.1)

    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(x0 + ancho / 2, y0 + 30, "¡Feliz Navidad y Próspero 2027!")
    c.setFont("Helvetica", 8)
    c.drawCentredString(x0 + ancho / 2, y0 + 15, "Presenta este boleto con su código QR en el acceso")

    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer


if __name__ == "__main__":
    # Prueba rápida: genera un boleto de cada zona
    for i, z in enumerate(("VIP", "PLATA", "GENERAL"), start=1):
        pdf = generar_boleto_pdf(i, "2026-12-20 19:00", z, f"{z}-0000{i}")
        with open(f"boleto_{z.lower()}.pdf", "wb") as f:
            f.write(pdf.read())
