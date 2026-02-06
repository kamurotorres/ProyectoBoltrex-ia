"""
Módulo para generación de tickets PDF en formato térmico
"""
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph
from io import BytesIO
from datetime import datetime
import textwrap

class TicketPDFGenerator:
    """Generador de tickets PDF para impresoras térmicas"""
    
    # Tamaños de ticket (en mm)
    TICKET_58MM = (58 * mm, 297 * mm)  # Ancho x Alto máximo
    TICKET_80MM = (80 * mm, 297 * mm)
    
    def __init__(self, ticket_width=80):
        """
        Inicializar generador
        ticket_width: 58 o 80 (mm)
        """
        self.width = ticket_width * mm
        self.max_height = 400 * mm  # Altura máxima
        self.margin = 3 * mm
        self.line_height = 4 * mm
        self.current_y = None
        
    def generate_ticket(self, invoice_data, company_config):
        """
        Generar ticket PDF
        
        invoice_data: dict con datos de la factura
        company_config: dict con configuración de empresa
        
        Returns: BytesIO object con el PDF
        """
        buffer = BytesIO()
        
        # Calcular altura dinámica basada en items y devoluciones
        num_items = len(invoice_data.get('items', []))
        returns = invoice_data.get('returns', [])
        num_return_items = sum(len(r.get('items', [])) for r in returns)
        
        # Más altura si hay devoluciones
        extra_height = 30 if returns else 0
        estimated_height = (100 + (num_items * 15) + (num_return_items * 15) + extra_height + 50) * mm
        page_height = min(estimated_height, self.max_height)
        
        c = canvas.Canvas(buffer, pagesize=(self.width, page_height))
        
        # Posición inicial (desde arriba)
        self.current_y = page_height - self.margin
        
        # 1. Encabezado de empresa
        self._draw_company_header(c, company_config)
        
        # 2. Línea separadora
        self._draw_line(c)
        
        # 3. Información de factura
        self._draw_invoice_info(c, invoice_data)
        
        # 4. Línea separadora
        self._draw_line(c)
        
        # 5. Cliente (si existe)
        if invoice_data.get('client_name'):
            self._draw_client_info(c, invoice_data)
            self._draw_line(c)
        
        # 6. Encabezado de productos
        self._draw_products_header(c)
        
        # 7. Productos
        self._draw_products(c, invoice_data.get('items', []))
        
        # 8. Devoluciones (si existen)
        if returns:
            self._draw_returns(c, returns)
        
        # 9. Línea separadora
        self._draw_line(c)
        
        # 10. Totales
        self._draw_totals(c, invoice_data)
        
        # 11. Pie de página
        self._draw_footer(c)
        
        c.save()
        buffer.seek(0)
        return buffer
    
    def _draw_company_header(self, c, config):
        """Dibujar encabezado de empresa"""
        c.setFont("Helvetica-Bold", 10)
        self._draw_centered_text(c, config.get('company_name', 'EMPRESA'))
        
        c.setFont("Helvetica", 7)
        if config.get('nit'):
            self._draw_centered_text(c, f"NIT: {config['nit']}")
        if config.get('phone'):
            self._draw_centered_text(c, f"Tel: {config['phone']}")
        if config.get('email'):
            self._draw_centered_text(c, config['email'])
        if config.get('address'):
            # Wrap long addresses
            wrapped = textwrap.fill(config['address'], width=35)
            for line in wrapped.split('\n'):
                self._draw_centered_text(c, line)
    
    def _draw_invoice_info(self, c, invoice_data):
        """Dibujar información de factura"""
        c.setFont("Helvetica-Bold", 8)
        self._draw_centered_text(c, f"FACTURA: {invoice_data.get('invoice_number', 'N/A')}")
        
        c.setFont("Helvetica", 7)
        # Fecha y hora
        created_at = invoice_data.get('created_at')
        if isinstance(created_at, str):
            try:
                dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                date_str = dt.strftime('%d/%m/%Y %H:%M')
            except:
                date_str = created_at
        else:
            date_str = created_at.strftime('%d/%m/%Y %H:%M') if created_at else 'N/A'
        
        self._draw_centered_text(c, date_str)
        
        # Usuario que vendió
        if invoice_data.get('created_by'):
            self._draw_centered_text(c, f"Vendedor: {invoice_data['created_by']}")
    
    def _draw_client_info(self, c, invoice_data):
        """Dibujar información del cliente"""
        c.setFont("Helvetica", 7)
        self._draw_left_text(c, f"Cliente: {invoice_data.get('client_name', 'N/A')}")
        if invoice_data.get('client_document'):
            self._draw_left_text(c, f"Doc: {invoice_data['client_document']}")
    
    def _draw_products_header(self, c):
        """Dibujar encabezado de tabla de productos"""
        c.setFont("Helvetica-Bold", 7)
        self.current_y -= self.line_height
        
        # Columnas: Cant | Producto | Total
        x_cant = self.margin
        x_prod = self.margin + 8 * mm
        x_total = self.width - self.margin - 15 * mm
        
        c.drawString(x_cant, self.current_y, "CANT")
        c.drawString(x_prod, self.current_y, "PRODUCTO")
        c.drawRightString(self.width - self.margin, self.current_y, "TOTAL")
    
    def _draw_products(self, c, items):
        """Dibujar productos"""
        c.setFont("Helvetica", 7)
        
        for item in items:
            self.current_y -= self.line_height
            
            # Cantidad
            c.drawString(self.margin, self.current_y, str(item.get('quantity', 0)))
            
            # Nombre del producto (truncado si es muy largo)
            product_name = item.get('product_name', 'Producto')
            if len(product_name) > 25:
                product_name = product_name[:22] + '...'
            c.drawString(self.margin + 8 * mm, self.current_y, product_name)
            
            # Total
            total = item.get('total', 0)
            c.drawRightString(self.width - self.margin, self.current_y, f"${total:,.2f}")
            
            # Precio unitario (línea adicional más pequeña)
            self.current_y -= 3 * mm
            c.setFont("Helvetica", 6)
            unit_price = item.get('unit_price', 0)
            c.drawString(self.margin + 8 * mm, self.current_y, f"  @${unit_price:,.2f} c/u")
            c.setFont("Helvetica", 7)
    
    def _draw_totals(self, c, invoice_data):
        """Dibujar totales"""
        c.setFont("Helvetica", 8)
        
        subtotal = invoice_data.get('subtotal', 0)
        total_tax = invoice_data.get('total_tax', 0)
        total = invoice_data.get('total', 0)
        
        # Subtotal
        self.current_y -= self.line_height * 1.5
        c.drawString(self.margin, self.current_y, "SUBTOTAL:")
        c.drawRightString(self.width - self.margin, self.current_y, f"${subtotal:,.2f}")
        
        # IVA
        self.current_y -= self.line_height
        c.drawString(self.margin, self.current_y, "IVA:")
        c.drawRightString(self.width - self.margin, self.current_y, f"${total_tax:,.2f}")
        
        # Total
        self.current_y -= self.line_height * 1.2
        c.setFont("Helvetica-Bold", 10)
        c.drawString(self.margin, self.current_y, "TOTAL:")
        c.drawRightString(self.width - self.margin, self.current_y, f"${total:,.2f}")
    
    def _draw_footer(self, c):
        """Dibujar pie de página"""
        self.current_y -= self.line_height * 2
        c.setFont("Helvetica", 6)
        self._draw_centered_text(c, "¡Gracias por su compra!")
        self._draw_centered_text(c, "Sistema Boltrex")
    
    def _draw_line(self, c):
        """Dibujar línea separadora"""
        self.current_y -= self.line_height * 0.5
        c.line(self.margin, self.current_y, self.width - self.margin, self.current_y)
        self.current_y -= self.line_height * 0.5
    
    def _draw_centered_text(self, c, text):
        """Dibujar texto centrado"""
        text_width = c.stringWidth(text, c._fontname, c._fontsize)
        x = (self.width - text_width) / 2
        c.drawString(x, self.current_y, text)
        self.current_y -= self.line_height
    
    def _draw_left_text(self, c, text):
        """Dibujar texto alineado a la izquierda"""
        c.drawString(self.margin, self.current_y, text)
        self.current_y -= self.line_height
