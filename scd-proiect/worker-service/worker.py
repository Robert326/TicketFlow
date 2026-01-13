"""
PDF Processor Worker
Consumes orders from RabbitMQ, generates PDF tickets, and sends emails via MailHog.
"""
import pika
import json
import os
import time
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
from fpdf import FPDF
import socket
import psycopg2

# Environment Variables
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "guest")
RABBITMQ_PASS = os.getenv("RABBITMQ_PASS", "guest")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@db:5432/ticketflow")
SMTP_HOST = os.getenv("SMTP_HOST", "mailhog")
SMTP_PORT = int(os.getenv("SMTP_PORT", "1025"))
QUEUE_NAME = "order_queue"

def get_db_connection():
    """Create database connection from URL"""
    # Parse DATABASE_URL: postgresql://user:password@host:port/dbname
    url = DATABASE_URL.replace("postgresql://", "")
    user_pass, host_db = url.split("@")
    user, password = user_pass.split(":")
    host_port, dbname = host_db.split("/")
    host, port = host_port.split(":")
    
    return psycopg2.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        dbname=dbname
    )

def generate_pdf_ticket(order_data):
    """Generate a PDF ticket for the order"""
    pdf = FPDF()
    pdf.add_page()
    
    # Header
    pdf.set_font("Arial", "B", 24)
    pdf.cell(0, 20, "TicketFlow", ln=True, align="C")
    pdf.set_font("Arial", "B", 18)
    pdf.cell(0, 15, "E-TICKET", ln=True, align="C")
    
    pdf.ln(10)
    
    # Ticket Details
    pdf.set_font("Arial", "", 12)
    pdf.cell(0, 10, f"Order ID: {order_data['order_id']}", ln=True)
    pdf.cell(0, 10, f"Event: {order_data.get('event_name', 'N/A')}", ln=True)
    pdf.cell(0, 10, f"Seat: {order_data['seat_id']}", ln=True)
    pdf.cell(0, 10, f"User: {order_data['user_id']}", ln=True)
    
    pdf.ln(10)
    
    # QR Code placeholder
    pdf.set_font("Arial", "I", 10)
    pdf.cell(0, 10, "[QR CODE PLACEHOLDER]", ln=True, align="C")
    
    pdf.ln(10)
    
    # Footer
    pdf.set_font("Arial", "I", 8)
    pdf.cell(0, 10, "This ticket was generated automatically by TicketFlow", ln=True, align="C")
    
    # Save to temp file
    filename = f"/tmp/ticket_{order_data['order_id']}.pdf"
    pdf.output(filename)
    return filename

def send_email_with_ticket(order_data, pdf_path):
    """Send email with PDF ticket attached via MailHog"""
    try:
        # Create message
        msg = MIMEMultipart()
        msg['From'] = 'tickets@ticketflow.com'
        msg['To'] = order_data.get('email', f"{order_data['user_id']}@example.com")
        msg['Subject'] = f"Your Ticket - Order #{order_data['order_id']}"
        
        # Body
        body = f"""
Hello {order_data['user_id']},

Your ticket purchase has been confirmed!

Order Details:
- Order ID: {order_data['order_id']}
- Event: {order_data.get('event_name', 'N/A')}
- Seat: {order_data['seat_id']}

Please find your e-ticket attached to this email.

Thank you for using TicketFlow!
        """
        msg.attach(MIMEText(body, 'plain'))
        
        # Attach PDF
        if os.path.exists(pdf_path):
            file_size = os.path.getsize(pdf_path)
            print(f"Attaching PDF: {pdf_path} (Size: {file_size} bytes)", flush=True)
            with open(pdf_path, 'rb') as attachment:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(attachment.read())
        else:
            print(f"ERROR: PDF file not found at {pdf_path}", flush=True)
            return False
        
        encoders.encode_base64(part)
        part.add_header(
            'Content-Disposition',
            f'attachment; filename="ticket_{order_data["order_id"]}.pdf"'
        )
        msg.attach(part)
        
        # Send via MailHog (no auth required)
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.send_message(msg)
        
        print(f"Email sent for order {order_data['order_id']}", flush=True)
        return True
        
    except Exception as e:
        print(f"Email failed for order {order_data['order_id']}: {e}", flush=True)
        return False

def update_order_status(order_id, status):
    """Update order status in database"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "UPDATE orders_new SET status = %s WHERE id = %s",
            (status, order_id)
        )
        conn.commit()
        cur.close()
        conn.close()
        print(f"Order {order_id} status updated to '{status}'", flush=True)
    except Exception as e:
        print(f"Failed to update order {order_id}: {e}", flush=True)

def callback(ch, method, properties, body):
    """Process incoming order message"""
    try:
        order_data = json.loads(body)
        order_id = order_data['order_id']
        
        print(f"Processing Order #{order_id}...", flush=True)
        
        # Step 1: Generate PDF
        pdf_path = generate_pdf_ticket(order_data)
        print(f"PDF generated: {pdf_path}", flush=True)
        
        # Step 2: Send Email
        email_sent = send_email_with_ticket(order_data, pdf_path)
        
        # Step 3: Update DB Status
        if email_sent:
            update_order_status(order_id, "completed")
        else:
            update_order_status(order_id, "email_failed")
        
        # Acknowledge message
        ch.basic_ack(delivery_tag=method.delivery_tag)
        print(f"Order #{order_id} processed successfully!\n", flush=True)
        
    except Exception as e:
        print(f"Error processing message: {e}", flush=True)
        # Reject and requeue on error
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

def main():

    connection = None
    for attempt in range(30):
        try:
            credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
            connection = pika.BlockingConnection(
                pika.ConnectionParameters(host=RABBITMQ_HOST, credentials=credentials)
            )
            break
        except pika.exceptions.AMQPConnectionError:
            time.sleep(2)
    
    if not connection:
        return
    
    channel = connection.channel()
    
    # Declare queue
    channel.queue_declare(queue=QUEUE_NAME, durable=True)
    
    # Fair dispatch
    channel.basic_qos(prefetch_count=1)
    
    # Start consuming
    channel.basic_consume(queue=QUEUE_NAME, on_message_callback=callback)
    
    try:
        channel.start_consuming()
    except KeyboardInterrupt:
        channel.stop_consuming()
    
    connection.close()

if __name__ == "__main__":
    main()
