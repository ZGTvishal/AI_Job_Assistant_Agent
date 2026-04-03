import os, re, json, requests
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass, field
from getpass import getpass
from urllib.parse import urlparse
import pathlib, tempfile, uuid, json
from bs4 import BeautifulSoup


class RoleScraper:
    UA = "Mozilla/5.0 (JobAgents/1.0)"

    @staticmethod
    def scrape(url:str, timeout: int=12) -> dict[str,str]:
        dom = (urlparse(url).netloc or "").lower()
        try:
            html = requests.get(url, timeout=timeout, headers={"User_Agent":RoleScraper.UA}).text

        except Exception:
            return {"url":url, "title_raw":"", "description":"", "Company_name":"", "gated":True}

        try:
            soup = BeautifulSoup(html, "lxml")
        except Exception:
            soup = BeautifulSoup(html, "html.parser")
        
        ogt = soup.select_one('meta[property="og:title"], meta[name="og:title"]')
        title = (ogt.get("content") or "").strip() if ogt and ogt.get("content") else (soup.title.get_text(strip=True) if soup.title else "")

        title = title[:300]

        # rest implementation is pending 