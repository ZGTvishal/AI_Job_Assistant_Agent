from main import BaseAgent
from main import AgentMessage
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
from helper_functions import extract_text_from_pdf, sniff_contact

@dataclass
class Orchestrator:
    cover: "CoverLetterAgent"
    net: "NetworkingAgent"
    review: "CVReviewAgent"

    def route(
            self,
            option:str,
            cv_pdf_path:str,
            job_url:str,
            jd_text_optional:str = "",
    ) -> dict[str, any]:
        
        cv_text = extract_text_from_pdf(cv_pdf_path)
        candidate = sniff_contact(cv_text)
        job = RoleScraper.scrape(job_url)