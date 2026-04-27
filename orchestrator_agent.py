from main import BaseAgent, CoverLetterAgent, NetworkingAgent
from cv_review import CVReviewAgent
from role_scraper import RoleScraper
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
        option: str,
        cv_pdf_path: str,
        job_url: str,
        jd_text_optional: str = "",
    ) -> Dict[str, Any]:
        """
        Fan-out to the requested agent and return a payload the UI can use.
        NOTE: We no longer support an 'output_mode' toggle. For cover letters we always
        return both the rendered text AND a generated PDF path.

        Returns (per option):

        - cover_letter:
            {
              "type": "cover_letter",
              "cv_text": , "job": , "candidate": ,
              "letter": , "orig_letter": , "pdf_path": ,
              "messages": None, "orig_messages": None,
              "needs_jd_text": 
            }

        - networking:
            {
              "type": "networking",
              "cv_text": , "job": , "candidate": ,
              "letter": None, "orig_letter": None, "pdf_path": None,
              "messages": {"referral_request": , "cold_email": },
              "orig_messages": { ...copy of messages... },
              "needs_jd_text": 
            }

        - cv_review:
            {
              "type": "cv_review",
              "cv_text": , "job": , "candidate": ,
              "review": ,
              "letter": None, "orig_letter": None, "pdf_path": None,
              "messages": None, "orig_messages": None,
              "needs_jd_text": 
            }
        """

        # Helper functions
        cv_text = extract_text_from_pdf(cv_pdf_path)
        candidate = sniff_contact(cv_text)  # best-effort name/email/phone
        job = RoleScraper.scrape(job_url)

        # Detect thin/gated pages (e.g., LinkedIn or JS-heavy boards)
        raw_desc = (job.get("description") or "").strip()
        needs_jd = len(raw_desc) < 200 and not (jd_text_optional and jd_text_optional.strip())

        # If the user supplied JD text and scrape looked thin, use it
        if jd_text_optional and len(raw_desc) < 200:
            job["description"] = jd_text_optional

        opt = (option or "").lower().strip()

        # Route
        if opt == "cover_letter":
            # New flow: CoverLetterAgent always returns both text + pdf_path
            result = self.cover.run(
                cv_text=cv_text,
                job=job,
                candidate=candidate,
            )
            return {
                "type": "cover_letter",
                "cv_text": cv_text, "job": job, "candidate": candidate,
                "letter": result["letter"],            # current draft shown in UI
                "orig_letter": result["letter"],       # keep original for optional "reset" features
                "pdf_path": result.get("pdf_path"),    # used by Download button
                "messages": None, "orig_messages": None,
                "needs_jd_text": needs_jd,
            }

        elif opt == "networking":
            msgs = self.net.run(cv_text=cv_text, job=job)  # {"referral_request","cold_email"}
            return {
                "type": "networking",
                "cv_text": cv_text, "job": job, "candidate": candidate,
                "letter": None, "orig_letter": None, "pdf_path": None,
                "messages": msgs,                        # for UI preview
                "orig_messages": dict(msgs),             # preserve first draft for optional "reset"
                "needs_jd_text": needs_jd,
            }

        elif opt == "cv_review":
            rev = self.review.run(cv_text=cv_text, job=job)
            return {
                "type": "cv_review",
                "cv_text": cv_text,
                "job": job,
                "candidate": candidate,
                "review": rev,
                "letter": None,
                "orig_letter": None,
                "pdf_path": None,
                "messages": None,
                "orig_messages": None,
                "needs_jd_text": needs_jd,
            }

        else:
            raise ValueError("Unknown option. Use one of: cover_letter, networking, cv_review.")


orch = Orchestrator(
    cover=CoverLetterAgent(name="cover_letter", system_prompt="You write precise, authentic cover letters tailored to the role."),
    net=NetworkingAgent(name="networking", system_prompt="You craft concise, human referral messages that get responses."),
    review=CVReviewAgent(name="cv_review", system_prompt="You are an ATS-savvy reviewer who gives actionable, minimal edits.")
)
