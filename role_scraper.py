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

        desc, company = "", ""
        for tag in soup.select('script[type="application/ld+json"]'):
            try:
                data = json.loads(tag.string or "")
            except Exception:
                continue
            objs = data if isinstance(data, list) else [data]
            for obj in objs:
                if isinstance(obj, dict) and "JobPosting" in str(obj.get("@type", "")):
                    if isinstance(obj.get("description"), str) and len(obj["description"]) > len(desc):
                        desc = obj["description"]
                    org = obj.get("hiringOrganization") or {}
                    nm = (org.get("name") if isinstance(org, dict) else org) or ""
                    if isinstance(nm, str) and len(nm) > len(company):
                        company = nm.strip()

        if desc:
            desc = re.sub(r"", "\n", desc, flags=re.I)
            desc = re.sub(r"<[^>]+>", "", desc)

        # --- if still thin (scraped JD is limited), collect biggest text block (ATS selectors first) ---
        if len(desc) < 200:
            selectors = [
                ".opening .content", ".opening .description",
                ".posting .section", ".posting .content",
                "article#job-application", ".job-body", ".job__description",
                "[data-ashby-job-posting-description]",
                "section", "article", "div"
            ]
            blocks, seen = [], set()
            for sel in selectors:
                for node in soup.select(sel):
                    txt = node.get_text("\n", strip=True)
                    if txt and len(txt) > 200:
                        h = hash(txt)
                        if h in seen:
                            continue
                        seen.add(h); blocks.append(txt)
            if blocks:
                desc = max(blocks, key=len)
            else:
                desc = soup.get_text("\n", strip=True)

        # normalize desc
        desc = re.sub(r"[ \t]+\n", "\n", desc or "")
        desc = re.sub(r"\n{3,}", "\n\n", desc).strip()[:20000]

        # --- company fallback: meta → host → regex ---
        if not company:
            for sel in ['meta[name="company"]','meta[property="og:site_name"]','meta[name="twitter:site"]']:
                el = soup.select_one(sel)
                if el and el.get("content"):
                    company = el["content"].strip().lstrip("@"); break
        if not company:
            host = dom.split(":")[0].lower().removeprefix("www.")
            core = (host.split(".")[-2] if "." in host else host).replace("-", " ").title()
            company = core

        # last-ditch from title/desc if host is generic
        if company in {"Jobs", "Careers", ""}:
            m = re.search(r"(?:company|client|organization)\s*:\s*([\w&\-\.\s,]+)", desc, re.I) \
                or re.search(r"[-–—]\s*([A-Za-z0-9&\-\.\s]{2,})\s*(?:\(|$)", title)
            if m: company = m.group(1).strip(" ,|·-()")

        return {
            "url": url,
            "title_raw": title,
            "description": desc,
            "company_name": company[:200],
            "gated": len(desc) < 200,   # your orchestrator already uses description length / needs_jd_text
        }