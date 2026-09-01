import os, json, requests

P_KEY = os.getenv("PARALLEL_API_KEY", "")
G_KEY = os.getenv("GEMINI_API_KEY", "")

def ps(q):
    if not P_KEY: return {"results": []}
    try:
        r = requests.post("https://api.parallel.ai/v1/search",
            headers={"Content-Type": "application/json", "x-api-key": P_KEY},
            json={"objective": q, "search_queries": [q], "mode": "fast"}, timeout=15)
        return r.json()
    except: return {"results": []}

def pe(url, obj=""):
    if not P_KEY or not url: return ""
    try:
        r = requests.post("https://api.parallel.ai/v1/extract",
            headers={"Content-Type": "application/json", "x-api-key": P_KEY},
            json={"urls": [url], "objective": obj or "Extract"}, timeout=15)
        d = r.json()
        ex = d.get("results", [{}])[0].get("excerpts", [""])
        return ex[0][:1500] if ex else ""
    except: return ""

def gm(prompt):
    if not G_KEY: return ""
    try:
        r = requests.post("https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent",
            json={"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0.7, "maxOutputTokens": 4096}},
            params={"key": G_KEY}, timeout=60)
        return r.json()["candidates"][0]["content"]["parts"][0]["text"]
    except: return ""

def process_query(message):
    # Extract
    data = {"countries":["Mexico","Colombia"],"location_type":"urban","extras":0,"drones":False,"budget_usd":0}
    try:
        j = gm(f'Extract from: "{message}"\nJSON: {{"countries":["c1"],"location_type":"urban","extras":0,"drones":false,"budget_usd":0}}')
        j = j.replace("```json","").replace("```","").strip()
        data.update(json.loads(j))
    except: pass
    data["extras"] = int(data.get("extras") or 0)
    data["budget_usd"] = int(data.get("budget_usd") or 0)
    if not data["countries"]: data["countries"] = ["Mexico","Colombia"]

    # Research (máximo 3 búsquedas por país para rapidez)
    research = {}
    for c in data["countries"]:
        research[c] = []
        # Permisos
        for r in ps(f"{c} film commission permit requirements costs 2025").get("results",[])[:2]:
            if r.get("url"):
                research[c].append(f"[{r.get('title','')}]({r.get('url','')}): {pe(r['url'], 'film permits')[:800]}")
        # Drones
        if data["drones"]:
            for r in ps(f"{c} drone laws filming foreigners").get("results",[])[:1]:
                if r.get("url"):
                    research[c].append(f"[DRONES {r.get('title','')}]({r.get('url','')}): {pe(r['url'], 'drone laws')[:800]}")
        # Crew local
        for r in ps(f"{c} film production crew hire rental").get("results",[])[:1]:
            if r.get("url"):
                research[c].append(f"[CREW {r.get('title','')}]({r.get('url','')}): {pe(r['url'], 'crew hire')[:800]}")

    # Report
    prompt = f"""Film production report for: "{message}"
Details: {data['countries']}, {data['location_type']}, {data['extras']} extras, drones={'yes' if data['drones'] else 'no'}, ${data['budget_usd']}

Research:
"""
    for c, items in research.items():
        prompt += f"\n{c}:\n" + "\n".join(items) + "\n"

    prompt += """
Write a comprehensive but concise report (max 2500 chars). Structure:

1. **Executive Summary** (2-3 sentences)
2. **Permits & Costs Table**: Country | Permit Cost | Processing Time | Key Restrictions | Risk
3. **Bring vs Hire**: Gear rental daily rates, crew day rates, extras cost. Calculate totals. List vendor names.
4. **Drone Rules** (if applicable)
5. **Actionable Checklist** (3-5 items per country)
6. **Final Recommendation**

Be specific. No "data unavailable". Use estimates marked as (estimate). Include source URLs as markdown links."""
    
    return gm(prompt)

def create_app():
    from flask import Flask, request, jsonify, send_from_directory, send_file
    from flask_cors import CORS
    import io
    
    app = Flask(__name__, static_folder=os.path.join(os.path.dirname(__file__), '..', 'frontend'), static_url_path='')
    CORS(app)
    
    @app.route("/")
    def index(): return send_from_directory(app.static_folder, 'index.html')
    
    @app.route("/api/chat", methods=["POST"])
    def chat():
        data = request.json
        msg = data.get("message", "")
        if not msg: return jsonify({"success": False, "error": "Empty"}), 400
        try: return jsonify({"success": True, "response": process_query(msg)})
        except Exception as e: return jsonify({"success": False, "error": str(e)}), 500
    
    @app.route("/api/export-docx", methods=["POST"])
    def export_docx():
        data = request.json
        report_text = data.get("report", "")
        if not report_text: return jsonify({"success": False, "error": "No report"}), 400
        try:
            docx_bytes = generate_docx(report_text)
            return send_file(
                io.BytesIO(docx_bytes),
                mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                as_attachment=True,
                download_name="production-passport-report.docx"
            )
        except Exception as e: return jsonify({"success": False, "error": str(e)}), 500
    
    @app.route("/api/health", methods=["GET"])
    def health(): return jsonify({"status": "ok"})
    return app


def generate_docx(text):
    """Generate a DOCX file from report text."""
    from docx import Document
    from docx.shared import Pt, Inches
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    
    doc = Document()
    
    # Title
    title = doc.add_heading("Production Passport Report", level=0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    # Parse markdown-style text
    lines = text.split('\n')
    for line in lines:
        line = line.strip()
        if not line:
            continue
        # Headings
        if line.startswith('####'):
            doc.add_heading(line.replace('#', '').strip(), level=4)
        elif line.startswith('###'):
            doc.add_heading(line.replace('#', '').strip(), level=3)
        elif line.startswith('##'):
            doc.add_heading(line.replace('#', '').strip(), level=2)
        elif line.startswith('#'):
            doc.add_heading(line.replace('#', '').strip(), level=1)
        # Table rows
        elif line.startswith('|') and not line.startswith('|-'):
            cells = [c.strip() for c in line.split('|')[1:-1]]
            if len(cells) > 0 and not all(set(c) <= set('-: ') for c in cells):
                # Find or create table
                if len(doc.tables) == 0 or doc.tables[-1].rows[-1].cells[-1].text:
                    table = doc.add_table(rows=1, cols=len(cells))
                    table.style = 'Table Grid'
                    for i, cell in enumerate(cells):
                        table.rows[0].cells[i].text = cell
                else:
                    row = table.add_row()
                    for i, cell in enumerate(cells):
                        row.cells[i].text = cell
        # Bullet points
        elif line.startswith('- ') or line.startswith('* '):
            doc.add_paragraph(line[2:], style='List Bullet')
        # Numbered lists
        elif line and line[0].isdigit() and '. ' in line[:4]:
            doc.add_paragraph(line, style='List Number')
        # Regular paragraph
        else:
            # Remove markdown bold
            clean = line.replace('**', '')
            doc.add_paragraph(clean)
    
    # Save to bytes
    from io import BytesIO
    buffer = BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer.read()

if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=8080, debug=True)
