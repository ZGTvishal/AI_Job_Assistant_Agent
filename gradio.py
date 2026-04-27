import gradio as gr

# pretty formatters
def format_networking(msgs: dict) -> str:
    rr = msgs.get("referral_request", "").strip()
    ce = msgs.get("cold_email", "").strip()
    parts = []
    if rr:
        parts.append(f"### Referral request (DM)\n{rr}")
    if ce:
        parts.append(f"### Cold email\n{ce}")
    return "\n\n".join(parts) if parts else "_No messages returned._"

def format_review(r: dict) -> str:
    decision = r.get("decision","")
    badge = "✅ Apply now" if decision == "apply_now" else "🛠️ Revise CV first"
    md = [f"**Decision:** {badge}",
          f"**Confidence:** {r.get('confidence','—')}",
          "",
          f"**Why:** {r.get('rationale','').strip() or '—'}"]
    kws = r.get("missing_keywords") or []
    if kws:
        md += ["", "**Add these keywords (where genuine):**", "- " + "\n- ".join(kws)]
    edits = r.get("edits") or []
    if edits:
        md += ["", "**Targeted edits:**"]
        for e in edits:
            sec = e.get("section","(section)")
            sug = e.get("suggestion","")
            bullets = e.get("example_bullets") or []
            md += [f"- *{sec}*: {sug}"]
            for b in bullets[:3]:
                md += [f"    • {b}"]
    return "\n".join(md)

# state helpers
def clear_state():
    return {
        "type": None,
        "cv_text": "", "job": {}, "candidate": {},
        "letter": None, "orig_letter": None, "pdf_path": None,
        "messages": None, "orig_messages": None
    }

def big_notice(title: str, body: str) -> str:
    return f"""

  {title}
  {body}

""".strip()


def run_flow(cv_pdf, job_url, option, jd_text, state):
    if cv_pdf is None:
        return "Please upload a PDF CV.", None, clear_state(), gr.update(value=None), gr.update(value="")
    if not job_url:
        return "Please paste a job URL.", None, clear_state(), gr.update(value=None), gr.update(value="")

    # Call orchestrator
    out = orch.route(
        option=option,
        cv_pdf_path=cv_pdf.name,
        job_url=job_url,
        jd_text_optional=jd_text or ""
    )
    '''
    # Ask for JD paste if the page was gated/empty
    if out.get("needs_jd_text"):
        msg = ("The job page looks gated/empty. Paste the job description into "
               "the 'Optional JD text' box and click Generate again.")
        return msg, None, clear_state(), gr.update(value=None), gr.update(value="")
    # Prompt user to paste JD if the page was gated/empty
    '''

    if out.get("needs_jd_text"):
        alert_html = big_notice(
            "Job page looks gated or empty",
            "Paste the job description into the Optional JD text box and click Generate again."
        )
        return (
            alert_html,
            gr.update(value=None),
            gr.update(value=None),
            clear_state(),
            gr.update(value=None),
            gr.update(value="")
        )


    if out["type"] == "cover_letter":
        display = out["letter"]
        file_path = out.get("pdf_path")  # always present for cover letters
        new_state = {
            "type": "cover_letter",
            "cv_text": out["cv_text"], "job": out["job"], "candidate": out["candidate"],
            "letter": out["letter"], "orig_letter": out["letter"],
            "pdf_path": out.get("pdf_path"),
            "messages": None, "orig_messages": None
        }
        return display, file_path, new_state, gr.update(value=None), gr.update(value="")

    elif out["type"] == "networking":
        pretty = format_networking(out["messages"])
        md_path = str(pathlib.Path(tempfile.gettempdir()) / "networking_messages.md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(pretty)
        new_state = {
            "type": "networking",
            "cv_text": out["cv_text"], "job": out["job"], "candidate": out["candidate"],
            "letter": None, "orig_letter": None, "pdf_path": None,
            "messages": out["messages"], "orig_messages": dict(out["messages"])
        }
        return pretty, md_path, new_state, gr.update(value=None), gr.update(value="")

    else:  # cv_review
        pretty = format_review(out["review"])
        md_path = str(pathlib.Path(tempfile.gettempdir()) / "cv_review.md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(pretty)
        return pretty, md_path, clear_state(), gr.update(value=None), gr.update(value="")

def review_step(satisfaction, feedback, state):
    if not state or not state.get("type"):
        return "Run one of the generators first.", None, state, gr.update(value=None), gr.update(value="")

    updated = REVIEW.handle(state, satisfaction, feedback)

    # ended?
    if updated.get("done"):
        if updated["type"] == "cover_letter":
            disp = f"✅ Saved.\n\n{updated['letter']}"
            fpath = updated.get("pdf_path")
            return disp, fpath, clear_state(), gr.update(value=None), gr.update(value="")
        elif updated["type"] == "networking":
            pretty = format_networking(updated["messages"])
            md_path = str(pathlib.Path(tempfile.gettempdir()) / "networking_messages.md")
            with open(md_path, "w", encoding="utf-8") as f:
                f.write(pretty)
            return f"✅ Saved.\n\n{pretty}", md_path, clear_state(), gr.update(value=None), gr.update(value="")
        else:
            return "✅ Saved.", None, clear_state(), gr.update(value=None), gr.update(value="")

    # still iterating
    if updated["type"] == "cover_letter":
        fpath = updated.get("pdf_path")
        return updated["letter"], fpath, updated, gr.update(value=None), gr.update(value="")
    if updated["type"] == "networking":
        pretty = format_networking(updated["messages"])
        md_path = str(pathlib.Path(tempfile.gettempdir()) / "networking_messages.md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(pretty)
        return pretty, md_path, updated, gr.update(value=None), gr.update(value="")

    return updated.get("message","Unknown state."), None, updated, gr.update(value=None), gr.update(value="")

# ---------- UI ----------
with gr.Blocks(title="Job Hunt Agents") as demo:
    gr.Markdown("## Job Hunt Agents\nUpload your CV (PDF) + job link → choose what to generate.")

    with gr.Row():
        cv_pdf = gr.File(label="CV (PDF)", file_types=[".pdf"])
        job_url = gr.Textbox(label="Job link", placeholder="https://...")

    jd_text = gr.Textbox(
        label="Optional JD text (if the link is gated/login-only)",
        lines=5,
        placeholder="Paste the job description here if the page is behind login."
    )

    option = gr.Radio(
        choices=[
            ("Cover letter", "cover_letter"),
            ("Referral outreach (DM + cold email)", "networking"),
            ("CV review & tips", "cv_review"),
        ],
        value="cover_letter",
        label="What do you want?"
    )

    run_btn = gr.Button("Generate", variant="primary")

    output_md = gr.Markdown(label="Result")
    file_out = gr.File(label="Download (PDF/Markdown)", interactive=False)

    gr.Markdown("### Review the result")
    satisfaction = gr.Radio(
        choices=["Yes","No"], value=None,
        label="Are you satisfied with the output?"
    )
    feedback = gr.Textbox(
        label="If 'No', what should we change?",
        lines=4,
        placeholder="e.g., shorter intro, stronger metrics, warmer tone"
    )
    apply_btn = gr.Button("Apply review / Improve")

    state = gr.State(clear_state())

    # No pdf/text toggle; wiring matches new run_flow signature
    run_btn.click(
        fn=run_flow,
        inputs=[cv_pdf, job_url, option, jd_text, state],
        outputs=[output_md, file_out, state, satisfaction, feedback]
    )

    apply_btn.click(
        fn=review_step,
        inputs=[satisfaction, feedback, state],
        outputs=[output_md, file_out, state, satisfaction, feedback]
    )