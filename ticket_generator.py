import io
import qrcode
import hashlib
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader

# Clave secreta del servidor (Solo el backend la conoce, evita falsificaciones)
SECRET_KEY = "Firma_Segura_SO_2026"

def generar_pdf_boleto(folio: int, fecha_hora: str) -> io.BytesIO:
    """
    Genera un boleto en formato PDF directamente en un buffer de memoria RAM,
    incluyendo una firma criptográfica (Hash) para su verificación de autenticidad.
    """
    # 1. Generar la firma criptográfica (Hash SHA-256)
    # Concatenamos los datos sensibles con la clave secreta
    datos_crudos = f"{folio}|{fecha_hora}|Auditorio Plata|{SECRET_KEY}"
    # Generamos el hash y tomamos los primeros 16 caracteres para que luzca estético en el PDF
    firma_hash = hashlib.sha256(datos_crudos.encode('utf-8')).hexdigest()[:16].upper()
    
    # 2. Buffer principal del PDF
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    ancho, alto = letter

    # 3. Renderizado de texto principal
    c.setFont("Helvetica-Bold", 24)
    c.drawString(2 * inch, alto - 2 * inch, "Auditorio Plata")
    
    c.setFont("Helvetica", 18)
    c.drawString(2 * inch, alto - 2.5 * inch, "Concierto Navideño")
    
    c.setFont("Helvetica-Bold", 14)
    c.drawString(2 * inch, alto - 3.5 * inch, f"FOLIO: {folio}")
    
    c.setFont("Helvetica", 12)
    c.drawString(2 * inch, alto - 4 * inch, f"Fecha de emisión: {fecha_hora}")
    
    # 4. Renderizado del Hash de Seguridad (En letra tipo código)
    c.setFont("Courier-Bold", 11)
    c.drawString(2 * inch, alto - 4.5 * inch, f"Firma Digital: {firma_hash}")

    # 5. Generación de código QR en memoria (Ahora incluye la firma)
    qr_data = f"Auditorio Plata | Folio: {folio} | Fecha: {fecha_hora} | Autenticidad: {firma_hash}"
    qr = qrcode.QRCode(version=1, box_size=5, border=2)
    qr.add_data(qr_data)
    qr.make(fit=True)
    img_qr = qr.make_image(fill_color="black", back_color="white")

    # Buffer secundario para la imagen del QR
    qr_buffer = io.BytesIO()
    img_qr.save(qr_buffer, format="PNG")
    qr_buffer.seek(0)

    # Incrustación del QR usando ImageReader (lectura desde RAM)
    qr_image = ImageReader(qr_buffer)
    # Ajustamos un poco la altura 'y' para que no encime con la firma
    c.drawImage(image=qr_image, x=5 * inch, y=alto - 5 * inch, width=2 * inch, height=2 * inch)

    # Cierre y retorno del buffer
    c.showPage()
    c.save()
    buffer.seek(0)

    return buffer
