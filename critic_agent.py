from helper_functions import save_cover_letter_pdf

class ReviewCoordinator:
    def __init__(self, cover_agent, net_agent):
        self.cover = cover_agent
        self.net = net_agent

    def handle(self, state: dict, satisfaction: str, feedback: str) -> dict:
        """
        Yes  -> end loop (done=True)
        No   -> revise the LATEST content (letter/messages) with feedback
        """
        if not state or not state.get("type"):
            return {**(state or {}), "message": "Run a generator first.", "done": False}

        # Treat anything other than explicit "Yes" as a request to iterate
        if satisfaction == "Yes":
            return {**state, "message": "✅ Saved.", "done": True}

        fb = (feedback or "").strip()
        fb = fb or "Please make it clearer, more specific, and better aligned to the role."

        try:
            if state["type"] == "cover_letter":
              improved = self.cover.revise(...)
              import re, tempfile, pathlib, uuid
              safe = re.sub(r"[^A-Za-z0-9]+","_", state.get("candidate",{}).get("name","Candidate")).strip("_") or "Candidate"
              pdf_path = str(pathlib.Path(tempfile.gettempdir()) / f"{safe}_{uuid.uuid4().hex[:8]}_Cover_Letter.pdf")
              save_cover_letter_pdf(improved, pdf_path)

              return {**state, "letter": improved, "pdf_path": pdf_path,
                      "message": "🔁 Updated per your feedback.", "done": False}


            elif state["type"] == "networking":
                # Revise from current messages (latest)
                improved = self.net.revise(
                    original_msgs=state.get("messages", {}),
                    feedback=fb,
                    cv_text=state.get("cv_text", ""),
                    job=state.get("job", {}),
                    candidate_name=state.get("candidate", {}).get("name", "Candidate"),
                )
                state["messages"] = improved
                return {**state, "message": "🔁 Updated per your feedback.", "done": False}

            else:
                return {**state, "message": "Unknown state.", "done": False}

        except Exception as e:
            # Don’t break the loop—return the previous content with an error note
            return {**state, "message": f"⚠️ Couldn’t apply revision: {e}", "done": False}

# Instantiate after you've built `orch` (which holds your agents)
REVIEW = ReviewCoordinator(cover_agent=orch.cover, net_agent=orch.net)
print("REVIEW coordinator ready ✔️")