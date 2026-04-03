from openai import OpenAI
import os, re, json, requests
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass, field
from bs4 import BeautifulSoup
from getpass import getpass
from urllib.parse import urlparse
import pathlib, tempfile, uuid, json
# PDF scraping of CVs
from pdfminer.high_level import extract_text as pdf_extract_text

# PDF generation
from reportlab.lib.pagesizes import LETTER
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_JUSTIFY, TA_LEFT

# Extract CV content
def extract_text_from_pdf(pdf_path:str) -> str:
    text = pdf_extract_text(pdf_path) or ""
    text = re.sub(r"[\t]+", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text[:200000]

# Extract contact from CV

def sniff_contact(cv_text: str) -> dict[str, str]:
    email = re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z{2,}]", cv_text)
    phone = re.search(r"(\+?\d[\d \-()]{7,})", cv_text)
    first_lines = [ln.strip() for ln in cv_text.splitlines()[:10] if ln.strip()]
    name = ""
    for ln in first_lines:
        if (email and email.group(0) in ln) or (phone and phone.group(0) in ln):
            continue
        if len(ln.split()) <=6:
            name = ln
            break
    return {
        "name": name or "Candidate",
        "email": email.group(0) if email else "",
        "phone": phone.group(0) if phone else "",
        "location": ""
    }

def save_cover_letter_pdf(letter_text: str, file_path:str) -> str:
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    doc = SimpleDocTemplate(file_path, pagesize=LETTER, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=72)
    styles = getSampleStyleSheet()
    base = ParagraphStyle('Body', parent=styles['Normal'], fontName='Times-Roman', fontSize=11, leading=15, alignment=TA_JUSTIFY)
    header = ParagraphStyle('Header', parent=styles['Normal'], fontName='Times-Bold', fontSize=14, leading=18, alignment=TA_LEFT, spaceAfter=12)
    chunks = letter_text.strip().splitlines()
    header_lines, body_lines, hit_blank = [], [], False

    for line in chunks:
        if not hit_blank and line.strip() =="":
            hit_blank = True
            continue
    (header_lines if not hit_blank else body_lines).append(line)

    flow = []

    if header_lines:
        flow.append(Paragraph("".join([e for e in header_lines if e.strip()]), header))
        flow.append(Spacer(1, 0.2 * inch))
    
    body = "\n".join(body_lines) if body_lines else letter_text

    for p in [p.strip() for p in re.split(r"\ns*\n", body) if p.strip()]:
        flow.append(Paragraph(p.replace("\n", ""), base))
        flow.append(Spacer(1, 0.18 * inch))

    doc.build(flow)
    return file_path


