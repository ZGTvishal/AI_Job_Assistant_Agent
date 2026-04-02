from main import BaseAgent
from main import AgentMessage
import json
import re

class CVReviewAgent(BaseAgent):

    def run(self, cv_text:str, job: dict[str, str]) -> dict[str,any]:
        prompt = f"""You are an executive recruiter and career coach with deep expertise in both human psychology and Applicant Tracking Systems (ATS). Your advice is strategic, prioritizing the 20% of changes that will yield 80% of the impact.

    Your goal is to analyze the provided CV against the job description and give the candidate a clear, actionable plan.

    First, conduct this internal analysis:
    1.  **ATS Screen:** Scan for critical keyword alignment between the CV and the job description. Are there glaring omissions?
    2.  **Human Screen (6-Second Test):** Could a human recruiter, in 6 seconds, understand the candidate's value proposition for this specific role? Is the impact clear and quantified?
    3.  **Strategic Fit:** Does the candidate's experience logically lead to this role? Is it a step up, a pivot, or a lateral move? How should the CV be framed to tell the right story?

    Based on your analysis, produce a STRICT JSON output with the following enhanced schema. Be direct, insightful, and encouraging.

    Job Posting:
    Title: {job.get('title_raw','')}
    Description: {job.get('description','')}

    Candidate CV:
    {cv_text}

    JSON Output Schema:
    {{
      "verdict": "Strong Fit - Apply Now" | "Good Fit - Minor Revisions Recommended" | "Potential Fit - Strategic Repositioning Needed" | "Poor Fit - Reconsider",
      "overall_confidence": number, // A score from 0.0 to 1.0
      "summary_analysis": {{
          "strengths": "What works well in the CV for this specific role. Be specific.",
          "weaknesses": "What is currently holding the CV back from being truly compelling.",
          "strategic_angle": "The core narrative the candidate should emphasize to stand out (e.g., 'Leverage your project management skills to pivot from backend to a full-stack leadership role')."
      }},
      "keyword_optimization": {{
          "missing_keywords": ["List of critical, context-aware keywords missing from the CV."],
          "overused_keywords": ["List of keywords that might be seen as 'stuffing' and should be used more naturally."]
      }},
      "prioritized_edits": [
        {{
          "priority": "High" | "Medium" | "Low",
          "section": "Summary" | "Experience > Role at Company" | "Projects" | "Skills",
          "suggestion": "A clear, actionable suggestion for this section.",
          "reasoning": "Briefly explain WHY this change is important (e.g., 'To pass the ATS screen' or 'To catch the hiring manager's eye').",
          "example_bullets": [
            "A rewritten bullet point demonstrating the suggestion.",
            "Another example bullet."
          ]
        }}
      ]
    }}"""
        

        raw = self.call_openAI(
            [AgentMessage(role="user", content=prompt)], temperature=0.25, max_tokens=1200
        )

        try:
            data.json.loads(raw)
        except Exception:
            try:
                m = re.search(r"\{[\s\S]*\}\s*$", raw)
                data = json.loads(m.group(0)) if m else {}
            except Exception:
                data = {}
        
        if not isinstance(data, dict) or "dicision" not in data:
            data = {
                "decision":"revise_cv",
                "rationale": (raw or "Model returned a non-Json response. returning to 'revise_cv'.")[:600],
                "missing_keywords":[],
                "edits":[],
                "confidence": 0.5
            }
        
        data.setdefault("missing_keywords", [])
        data.setdefault("edits", [])
        try:
            c = float(data.get("confidence", 0.5))
            data["confidence"] = max(0.0, min(1.0, c))
        except Exception:
            data["confidence"] = 0.5

        return data

        