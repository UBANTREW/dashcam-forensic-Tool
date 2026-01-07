from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from datetime import datetime
import os

def generate_report(output_path, video_name, timestamps, tamper_results, investigator="Admin"):
    c = canvas.Canvas(output_path, pagesize=A4)
    width, height = A4

    # Title
    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(width/2, height-50, "Dashcam Footage Analysis Report")

    # Metadata
    c.setFont("Helvetica", 12)
    c.drawString(50, height-100, f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    c.drawString(50, height-120, f"Investigator: {investigator}")
    c.drawString(50, height-140, f"Video File: {video_name}")

    # Section: Timestamps
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, height-180, "Extracted Timestamps:")
    c.setFont("Helvetica", 12)
    y = height-200
    for ts in timestamps:
        c.drawString(70, y, f"- {ts}")
        y -= 20
        if y < 100:
            c.showPage()
            y = height - 50

    # Section: Tamper Detection
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, y-20, "Tamper Detection Results:")
    c.setFont("Helvetica", 12)
    y -= 40
    for tr in tamper_results:
        c.drawString(70, y, f"- {tr}")
        y -= 20
        if y < 100:
            c.showPage()
            y = height - 50

    c.save()
    return output_path
