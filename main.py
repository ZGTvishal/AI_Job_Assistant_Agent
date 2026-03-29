from openai import OpenAI
import re
client = OpenAI()




model="gpt-4o-mini"

@datalass
class AgentMessage:
    role:str
    content = str

@dataclass
class BaseAgent:
    name: str
    systeem_prompt: str

    def call_openAI(
            self, messages: list[AgentMessage],
                    model: str = MODEL, temperature: int = 0.45, max_tokens: int = 2000) -> str:
        payload = [{"role": m.role, "content": m.content} for m in messages]
        payload.insert(0, {"role": "system", "content": self.system_prompt})
        completion = client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=payload,
                    )
        return completion.choices[0].message.content.strip()

class CoverLetterAgent(BaseAgent):
    def run(self, cv_text:str, jd:dict[str,str], candidate:dict[str,str], output:str= "pdf" ) -> dict[str,any]:
        prompt = f""" You are an expert career storyteller and professional cover letter writer. Your style is persuasive, authentic, and laser-focused on connecting a candidate's achievements to a company's needs. You avoid corporate jargon and clichés.

          Your mission is to write a compelling, concise cover letter that makes the hiring manager excited to interview this candidate.

          First, perform this internal analysis (do not write this part in the output):
          1.  **Deconstruct the Role:** What are the top 3 most critical responsibilities and qualifications listed in the job description? What is the core problem this role solves?
          2.  **Map the Candidate:** For each critical point, find the strongest piece of evidence (a specific project, skill, or quantified achievement) from the candidate's CV.
          3.  **Find the Narrative:** What is the core story here? Is it about someone with deep domain knowledge, someone with similar experience, or someone pivoting their skills in a unique way? The letter must tell this story.

          Now, using your analysis, write the cover letter. It must have atleast:
          - A clear contact header.
          - An opening paragraph that hooks the reader and states the specific role.
          - A body paragraph that provides concrete, quantified evidence of how the candidate's skills solve the company's needs. Focus on the 2-3 most impactful points you identified.
          - A closing paragraph that conveys genuine enthusiasm for the company's mission and includes a clear call to action.

          Candidate CV:
          {cv_text}

          Job Posting:
          Title: {job.get('title_raw','')}
          URL: {job.get('url','')}
          Description: {job.get('description','')}

          Candidate Details for Header:
          Name: {candidate.get('name','Candidate')}
          Email: {candidate.get('email','')}
          Phone: {candidate.get('phone','')}
          Location: {candidate.get('location','')}

          Output ONLY the full, final letter text, starting with the header."""
        
        letter = self.call_openAI([AgentMessage("user", prompt)], max_tokens= 3000)
        safe = re.sub(r"[^A-Za-z0-9]+","_", candidate.get("name","Candidate")).strip("_") or "Candidate"
        pdf_path = str(pathlib.Path(tempfile.gettempdir()) / f"{safe}_{uuid.uuid4().hex[:8]}_Cover_Letter.pdf")
        save_cover_letter_pdf(letter, pdf_path)

        return {"letter": letter, "pdf_path": pdf_path}
    
    def revise_cover_letter_FB(self, original_letter: str, feedback: str, cv_text: str, jd: dict[str,str], candidate: dict[str,str]) -> str:
        prompt = f"""
                  Revise the following cover letter to address the user's feedback while preserving facts.
                 Improve clarity, specificity, and impact; avoid clichés.

                  User feedback: {feedback.strip() or "(none provided)"}

                  CV:
                  {cv_text}

                  Original letter:
                  {original_letter}

                  Output:
                  Return ONLY the revised full letter starting with the contact header. No commentary.
                 """
        return self.call_openAI([AgentMessage("user", prompt)], max_tokens= 3000)


class NetworkingAgent(BaseAgent):

    @staticmethod
    def _clip(s:str, n:int) -> str:
        return (s or "")[:n]
    
    @staticmethod   
    def _safe_json(s:str) -> dict[str,any]:
        s = (s or "").strip()
        try:
            return json.loads(s)
        except Exception:
            pass

        m = re.search(r"\{[\s\S]*\}\s*$", s)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                return {}
        return {}
    
    @staticmethod
    def subject(text:str) -> str:

        t = (text or "").strip()
        if not re.match(r"(?i)^subject\s*:", t):
            t = "Subject: A quick question about {{role}} at {{company}}" + t
            lines = t.splitlines()
            cleaned = [lines[0]] + [ln for ln in lines[1:] if not re.match(r"(?i)^subject\s*:",ln)]
            return "\n".join(cleaned).strip()
        
    @staticmethod
    def _wc(txt: str) -> int:
        return len(re.findall(r"\w+", txt or ""))

    def _fallback_messages(self, job_url: str = "") -> dict[str, str]:
        """
        High-quality, neutral fallbacks used only if the model output is unusable.
        Keeps placeholders for personalization and stays within length targets.
        
        """
        dm = (
            "Hi {{recipient_name}}, I’m exploring the {{role}} role at {{company}} ({{job_link}}). "
            "I’ve shipped results in similar problem spaces and would value your perspective. "
            "If you have 10–15 minutes this week, could I ask two focused questions about the team’s priorities "
            "and what success looks like in the first 90 days? Happy to keep it brief. — {{your_name}}"
        )
        email = (
            "Subject: Quick question about {{role}} at {{company}}\n\n"
            "Hi {{recipient_name}},\n\n"
            "I’m preparing to apply for the {{role}} role at {{company}} ({{job_link}}). From my background, I’ve led work that "
            "maps closely to the challenges your team tackles and I’m keen to understand how you approach them.\n\n"
            "Would you be open to a 10–15 minute chat, or a quick reply to two specific questions about the role’s priorities and metrics for success? "
            "I’ll keep it concise and come prepared.\n\n"
            "Thanks,\n{{your_name}}"
        )
        return {"referral_request": dm, "cold_email": email}

    def _guided_retry(self, reason: str) -> dict[str, any]:
        """
        Ask the model once to return a clean JSON object with the required keys.
        This keeps output model-authored without injecting generic content unless still missing.
        """
        fix_msg = f"""
              Your last reply violated the requirement: {reason}.
              Return ONE valid JSON object ONLY (no markdown, no commentary) with EXACTLY these keys:
              "referral_request": "<LinkedIn DM text>"
              "cold_email": "Subject: ...\\n\\n<Email body>"
                   """.strip()
        raw2 = self.call_openai([AgentMessage("user", fix_msg)], max_tokens=400)
        return self._safe_json(raw2)

    def run(
        self,
        cv_text: str,
        job: dict[str, str],
        company_hint: str = "",
        tone: str = "Neutral professional",
    ) -> dict[str, any]:
        """
        Generate initial outreach messages.
        """
        cv = self._clip(cv_text, 6000)
        jd = self._clip(job.get("description", "") or "", 4000)
        title = (job.get("title_raw") or "").strip()
        company = company_hint or (title.split(" at ")[-1].split("|")[0].strip() if " at " in title else "")

        prompt = f"""
              You are a principal networking strategist. Generate TWO messages that start a relationship with an employee at {{company}} about the {{role}} role—aim for a brief chat or advice, NOT a referral ask.

              Tone: {tone}. Concise, specific, respectful of time. Avoid region-specific idioms unless tone requests it.

              Constraints
              - Use placeholders where helpful: {{{{recipient_name}}}}, {{{{your_name}}}}, {{{{role}}}}, {{{{company}}}}, {{{{job_link}}}}.
              - LinkedIn DM (“referral_request”): 4-10 sentences max, no Subject line.
              - Cold email (“cold_email”): 100–250 words max. FIRST LINE MUST be: "Subject: ...".
              - Use ONE concrete hook from the JD/company (recent work, product, problem space) to signal research.
              - Make ONE easy CTA (10–15 min chat or 1–2 specific questions). No begging, no “please refer me”.

              Banned
              - “I hope this finds you well”, emojis, excessive exclamation, generic praise, apologies.
              - Inventing specifics not implied by the JD/CV.

              Structure for each message
              1) Hook (specific to {{company}}/role via JD),
              2) Bridge (candidate’s most relevant result/skill—quantify once if possible),
              3) CTA (single, low-friction ask).
              4) Show genuine interest in the user,company and role.

              Context
              - CV (excerpt): {cv}
              - Job title: {title}
              - Job link: {job.get('url','')}
              - JD (excerpt): {jd}
              - Target company: "{company or 'the company'}"

              Output
              Return ONE valid JSON object ONLY (no markdown, no commentary) with EXACTLY these keys:
              "referral_request": "<LinkedIn DM text>"
              "cold_email": "Subject: ...\\n\\n<Email body>"
              """.strip()


        raw = self.call_openai([AgentMessage("user", prompt)], temperature=0.4, max_tokens=3000)
        data = self._safe_json(raw)

        rr = (data.get("referral_request") or "").strip()
        ce = (data.get("cold_email") or "").strip()

        # guided retry if missing/empty
        reasons = []
        if not rr: reasons.append("missing 'referral_request'")
        if not ce: reasons.append("missing 'cold_email'")
        if reasons:
            data2 = self._guided_retry(", ".join(reasons))
            rr = (data2.get("referral_request") or rr).strip()
            ce = (data2.get("cold_email") or ce).strip()

        # final fallback to quality templates if still empty
        if not rr or not ce:
            fb = self._fallback_messages(job.get("url", ""))
            rr = rr or fb["referral_request"]
            ce = ce or fb["cold_email"]

        # enforce subject + soft caps
        ce = self._ensure_subject(ce)
        if self._wc(rr) > 160: rr = " ".join(rr.split()[:160])
        if self._wc(ce) > 220: ce = " ".join(ce.split()[:220])

        return {"referral_request": rr, "cold_email": ce}

    def revise(
        self,
        original_msgs: dict[str, str],
        feedback: str,
        cv_text: str,
        job: dict[str, str],
        candidate_name: str,
        tone: str = "Neutral professional",
    ) -> dict[str, str]:
        """
        Improve the latest messages per user feedback (relationship-first; no direct referral ask).
        """
        cv = self._clip(cv_text, 6000)
        jd = self._clip(job.get("description", "") or "", 4000)
        fb = (feedback or "Make it sharper, more specific, and keep one clear, low-friction CTA.").strip()

        prompt = f"""
                    You are a principal outreach editor. Improve the TWO messages based on the user’s feedback
                    while keeping the relationship-first approach (advice/insight or brief chat; do NOT ask for a referral).

                    Keep the format similar unless user asks for a different tone. Give heavy importance to the user feedback
                    and whatever the user asks to change or add/remove.

                    Tone: {tone}. Concise, specific, respectful of time.

                    User feedback
                    {fb}

                    Original messages (JSON)
                    {json.dumps(original_msgs, ensure_ascii=False, indent=2)}

                    Support context
                    - Candidate: {candidate_name}
                    - CV (excerpt): {cv}
                    - JD (excerpt): {jd}


                    Output
                    Return ONE valid JSON object ONLY (no markdown, no commentary) with EXACTLY these keys:
                    "referral_request": "<LinkedIn DM text>"
                    "cold_email": "Subject: ...\\n\\n<Email body>"
                  """.strip()

        raw = self.call_openai([AgentMessage("user", prompt)], max_tokens=1000)
        data = self._safe_json(raw)

        rr = (data.get("referral_request") or "").strip()
        ce = (data.get("cold_email") or "").strip()

        # guided retry if missing/empty
        reasons = []
        if not rr: reasons.append("missing 'referral_request'")
        if not ce: reasons.append("missing 'cold_email'")
        if reasons:
            data2 = self._guided_retry(", ".join(reasons))
            rr = (data2.get("referral_request") or rr).strip()
            ce = (data2.get("cold_email") or ce).strip()

        # If still empty after retry, preserve last good content;
        # if even that is empty (first pass was broken), fall back to templates.
        if not rr:
            rr = (original_msgs.get("referral_request") or "").strip()
        if not ce:
            ce = (original_msgs.get("cold_email") or "").strip()

        if not rr or not ce:
            fb_msgs = self._fallback_messages(job.get("url", ""))
            rr = rr or fb_msgs["referral_request"]
            ce = ce or fb_msgs["cold_email"]

        # enforce subject + soft caps
        ce = self._ensure_subject(ce)
        if self._wc(rr) > 160: rr = " ".join(rr.split()[:160])
        if self._wc(ce) > 220: ce = " ".join(ce.split()[:220])

        return {"referral_request": rr, "cold_email": ce}
        
    




        
    





