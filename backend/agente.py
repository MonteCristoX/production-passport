import os, json, requests

def get_key(name):
    return os.environ.get(name, "")

def ps(q):
    k = get_key("PARALLEL_API_KEY")
    if not k: return {"results": []}
    try:
        r = requests.post("https://api.parallel.ai/v1/search",
            headers={"Content-Type": "application/json", "x-api-key": k},
            json={"objective": q, "search_queries": [q], "mode": "fast"}, timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"Parallel search error: {e}")
        return {"results": []}

def pe(url, obj=""):
    k = get_key("PARALLEL_API_KEY")
    if not k or not url: return ""
    try:
        r = requests.post("https://api.parallel.ai/v1/extract",
            headers={"Content-Type": "application/json", "x-api-key": k},
            json={"urls": [url], "objective": obj or "Extract"}, timeout=15)
        r.raise_for_status()
        d = r.json()
        ex = d.get("results", [{}])[0].get("excerpts", [""])
        return ex[0][:1500] if ex else ""
    except Exception as e:
        print(f"Parallel extract error: {e}")
        return ""

def gm(prompt, retries=3):
    k = get_key("GEMINI_API_KEY")
    if not k:
        return "Error: GEMINI_API_KEY not configured"
    
    for attempt in range(retries):
        try:
            r = requests.post("https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent",
                json={"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0.7, "maxOutputTokens": 4096}},
                params={"key": k}, timeout=60)
            r.raise_for_status()
            return r.json()["candidates"][0]["content"]["parts"][0]["text"]
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                import time
                wait = 30 * (attempt + 1)
                print(f"Rate limited, waiting {wait}s...")
                time.sleep(wait)
                continue
            print(f"Gemini HTTP error: {e}")
            return f"API Error: {e}"
        except Exception as e:
            print(f"Gemini error: {e}")
            return f"Error: {e}"
    return "Error: Rate limit exceeded. Please try again in a moment."

def process_query(message):
    # Extract with regex fallback (no API call needed)
    data = extract_production_info(message)
    
    # Research
    research = {}
    for c in data["countries"]:
        research[c] = []
        for r in ps(f"{c} film commission permit requirements costs 2025").get("results",[])[:2]:
            if r.get("url"):
                research[c].append(f"[{r.get('title','')}]({r.get('url','')}): {pe(r['url'], 'film permits')[:800]}")
        if data["drones"]:
            for r in ps(f"{c} drone laws filming foreigners").get("results",[])[:1]:
                if r.get("url"):
                    research[c].append(f"[DRONES {r.get('title','')}]({r.get('url','')}): {pe(r['url'], 'drone laws')[:800]}")
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


def extract_production_info(message):
    """Extract production info using regex (no API needed)."""
    import re
    msg = message.lower()
    
    # Countries
    country_map = {
        "mexico": "Mexico", "méxico": "Mexico", "mexico city": "Mexico",
        "colombia": "Colombia", "bogota": "Colombia", "bogotá": "Colombia",
        "spain": "Spain", "madrid": "Spain", "barcelona": "Spain",
        "argentina": "Argentina", "buenos aires": "Argentina",
        "brazil": "Brazil", "rio": "Brazil", "sao paulo": "Brazil",
        "chile": "Chile", "santiago": "Chile",
        "peru": "Peru", "lima": "Peru",
        "costa rica": "Costa Rica",
        "japan": "Japan", "tokyo": "Japan",
        "us": "United States", "usa": "United States", "los angeles": "United States", "new york": "United States",
        "uk": "United Kingdom", "london": "United Kingdom",
        "france": "France", "paris": "France",
        "germany": "Germany", "berlin": "Germany",
        "italy": "Italy", "rome": "Italy",
        "australia": "Australia", "sydney": "Australia"
    }
    
    countries = []
    for key, val in country_map.items():
        if key in msg and val not in countries:
            countries.append(val)
    
    if not countries:
        countries = ["Mexico", "Colombia"]
    
    # Location type
    location_type = "urban"
    if any(w in msg for w in ["colonial", "historic", "old town"]):
        location_type = "heritage"
    elif any(w in msg for w in ["mountain", "beach", "forest", "desert", "nature", "outdoor"]):
        location_type = "natural"
    elif any(w in msg for w in ["studio", "indoor", "interior"]):
        location_type = "interior"
    elif any(w in msg for w in ["aerial", "drone", "fly"]):
        location_type = "aerial"
    
    # Extras
    extras = 0
    extras_match = re.search(r'(\d+)\s*extras', msg)
    if extras_match:
        extras = int(extras_match.group(1))
    
    # Drones
    drones = any(w in msg for w in ["drone", "drones", "uav", "aerial"])
    
    # Pyrotechnics
    pyrotechnics = any(w in msg for w in ["pyro", "pyrotechnics", "fireworks", "explosion", "fire"])
    
    # Night shoot
    night_shoot = any(w in msg for w in ["night", "evening", "dusk", "dark"])
    
    # Budget - look for budget-related keywords
    budget_usd = 0
    budget_patterns = [
        r'(?:budget|cost|spend|invest)\s*(?:of\s*)?\$?(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*(k|thousand|million|m|usd)?',
        r'\$(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*(k|thousand|million|m)?',
        r'(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*(k|thousand|million|m)\s*(?:budget|cost|usd|dollars?)',
    ]
    for pattern in budget_patterns:
        budget_match = re.search(pattern, msg)
        if budget_match:
            amount = float(budget_match.group(1).replace(",", ""))
            unit = (budget_match.group(2) or "").lower()
            if unit in ["k", "thousand"]:
                amount *= 1000
            elif unit in ["million", "m"]:
                amount *= 1000000
            budget_usd = int(amount)
            break
    
    return {
        "countries": countries,
        "location_type": location_type,
        "extras": extras,
        "drones": drones,
        "pyrotechnics": pyrotechnics,
        "night_shoot": night_shoot,
        "budget_usd": budget_usd
    }

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
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    import tempfile
    
    doc = Document()
    title = doc.add_heading("Production Passport Report", level=0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    lines = text.split('\n')
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.startswith('####'):
            doc.add_heading(line.replace('#', '').strip(), level=4)
        elif line.startswith('###'):
            doc.add_heading(line.replace('#', '').strip(), level=3)
        elif line.startswith('##'):
            doc.add_heading(line.replace('#', '').strip(), level=2)
        elif line.startswith('#'):
            doc.add_heading(line.replace('#', '').strip(), level=1)
        elif line.startswith('|') and not line.startswith('|-'):
            cells = [c.strip() for c in line.split('|')[1:-1]]
            if len(cells) > 0 and not all(set(c) <= set('-: ') for c in cells):
                if len(doc.tables) == 0 or doc.tables[-1].rows[-1].cells[-1].text:
                    table = doc.add_table(rows=1, cols=len(cells))
                    table.style = 'Table Grid'
                    for i, cell in enumerate(cells):
                        table.rows[0].cells[i].text = cell
                else:
                    row = table.add_row()
                    for i, cell in enumerate(cells):
                        row.cells[i].text = cell
        elif line.startswith('- ') or line.startswith('* '):
            doc.add_paragraph(line[2:], style='List Bullet')
        elif line and line[0].isdigit() and '. ' in line[:4]:
            doc.add_paragraph(line, style='List Number')
        else:
            clean = line.replace('**', '')
            doc.add_paragraph(clean)
    
    with tempfile.NamedTemporaryFile(suffix='.docx', delete=False) as tmp:
        doc.save(tmp.name)
        with open(tmp.name, 'rb') as f:
            data = f.read()
        import os as o
        o.unlink(tmp.name)
    return data

if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=8080, debug=True)
