import os, json, requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

def get_key(name):
    return os.environ.get(name, "")

def ps(q):
    k = get_key("PARALLEL_API_KEY")
    if not k: return {"results": []}
    try:
        r = requests.post("https://api.parallel.ai/v1/search",
            headers={"Content-Type": "application/json", "x-api-key": k},
            json={"objective": q, "search_queries": [q], "mode": "fast"}, timeout=10)
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
            json={"urls": [url], "objective": obj or "Extract"}, timeout=10)
        r.raise_for_status()
        d = r.json()
        ex = d.get("results", [{}])[0].get("excerpts", [""])
        return ex[0][:1500] if ex else ""
    except Exception as e:
        print(f"Parallel extract error: {e}")
        return ""

def gm(prompt, retries=2):
    """Try Vertex AI first, then AI Studio, then demo mode"""
    k = get_key("GEMINI_API_KEY")
    if not k:
        return "Error: GEMINI_API_KEY not configured"
    
    # Check if it's a Replit Vertex AI key (starts with AQ or similar)
    is_vertex_key = k.startswith("AQ.") or not k.startswith("AIza")
    
    if is_vertex_key:
        # Try Vertex AI via SDK
        try:
            from gemini_vertex import init_vertex_ai, gm_vertex
            if init_vertex_ai():
                return gm_vertex(prompt)
        except Exception as e:
            print(f"Vertex AI init error: {e}")
        
        # Fallback to API endpoint
        models_to_try = [
            "gemini-1.5-flash",
            "gemini-1.5-flash-latest", 
            "gemini-1.5-pro",
            "gemini-1.5-pro-latest",
            "gemini-2.0-flash-exp",
        ]
    else:
        # AI Studio key
        models_to_try = [
            "gemini-1.5-flash",
            "gemini-1.5-flash-latest",
            "gemini-1.5-pro",
        ]
    
    for model in models_to_try:
        for attempt in range(retries):
            try:
                base_url = "https://generativelanguage.googleapis.com/v1beta/models"
                r = requests.post(f"{base_url}/{model}:generateContent",
                    json={"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0.7, "maxOutputTokens": 8192}},
                    params={"key": k}, timeout=60)
                if r.status_code == 200:
                    return r.json()["candidates"][0]["content"]["parts"][0]["text"]
                elif r.status_code == 404:
                    break
                elif r.status_code == 429:
                    import time
                    wait = 15 * (attempt + 1)
                    print(f"Rate limited ({model}), waiting {wait}s...")
                    time.sleep(wait)
                    continue
                else:
                    print(f"Gemini HTTP error ({model}): {r.status_code}")
                    break
            except Exception as e:
                print(f"Gemini error ({model}): {e}")
                break
    
    return "Error: No working Gemini model found."

def generate_demo_report(message):
    """Generate a demo report with fancy HTML template."""
    data = extract_production_info(message)
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Generate risk badges
    def risk_badge(level):
        colors = {"HIGH": "badge-high", "MEDIUM": "badge-medium", "LOW": "badge-low"}
        return f'<span class="badge {colors.get(level, "badge-medium")}">{level}</span>'
    
    # Build restricted list
    def make_list(items):
        return "\n".join(f"            {item}" for item in items)
    
    report_parts = []
    
    # Executive Summary
    report_parts.append(f"""
        <div class="section executive-summary">
            <h2>🎯 Executive Summary</h2>
            <p>Production planned for <strong>{', '.join(data['countries'])}</strong> ({data['location_type']} location) with {data['extras']} extras and {'drones' if data['drones'] else 'no drones'}. Budget: ${data['budget_usd']:,} if specified, otherwise not specified. Key challenges include permits, crew hiring, and compliance. Local hiring is recommended.</p>
        </div>
""")
    
    # Permits
    for c in data["countries"]:
        if c == "Mexico":
            restrictions = ["No foreign drone operators", "AFAC commercial permit mandatory", "50 extras need permits"]
            risk = "HIGH"
            cost = "$500 – $5,000 per day"
            time_proc = "10 – 15 business days"
        elif c == "Colombia":
            restrictions = ["Film commission approval required", "Drone permits via Aerocivil", "Extras need visas"]
            risk = "MEDIUM"
            cost = "$300 – $3,000 per day"
            time_proc = "5 – 10 business days"
        else:
            restrictions = ["Local regulations vary", "Check film commission"]
            risk = "MEDIUM"
            cost = "$200 – $4,000 per day"
            time_proc = "5 – 20 business days"
        
        report_parts.append(f"""        <div class="section country-card">
            <h3>{c} {risk_badge(risk)}</h3>
            <div class="cost-grid">
                <div class="cost-item">
                    <div class="label">Permit Cost</div>
                    <div class="value">{cost}</div>
                </div>
                <div class="cost-item">
                    <div class="label">Processing Time</div>
                    <div class="value">{time_proc}</div>
                </div>
            </div>
            <ul class="restriction-list">
{make_list([f"<li>{r}</li>" for r in restrictions])}
            </ul>
        </div>
""")
    
    # Cost Analysis
    report_parts.append("""
        <div class="section cost-analysis">
            <h2>💰 Bring vs Hire: Cost Analysis</h2>
            <div class="cost-grid">
                <div class="cost-item">
                    <div class="label">Camera Package</div>
                    <div class="value">$400 – $800/day</div>
                </div>
                <div class="cost-item">
                    <div class="label">Crew (DP, Gaffer, AC)</div>
                    <div class="value">$600 – $1,200/day</div>
                </div>
                <div class="cost-item">
                    <div class="label">Extras (100)</div>
                    <div class="value">$7,500 – $15,000</div>
                </div>
                <div class="cost-item">
                    <div class="label">Daily Total</div>
                    <div class="value">$6K – $12K</div>
                </div>
            </div>
            <p><strong>Recommendation:</strong> HIRE LOCALLY — saves 40–50%</p>
        </div>
""")
    
    # Vendors
    report_parts.append("""
        <div class="section">
            <h2>🏢 Local Vendors (Mexico)</h2>
            <div class="vendor-grid">
                <div class="vendor-card">
                    <h4>Story</h4>
                    <div class="url">story.mx</div>
                </div>
                <div class="vendor-card">
                    <h4>We Produce</h4>
                    <div class="url">weproduce.mx</div>
                </div>
                <div class="vendor-card">
                    <h4>80 Days Films</h4>
                    <div class="url">80daysfilms.com</div>
                </div>
            </div>
        </div>
""")
    
    # Drone Rules
    if data['drones']:
        drone_items = [
            "AFAC permit required for ALL commercial operations",
            "Foreign operators must partner with Mexican certified operator",
            "Max altitude: 400 ft (120 m); VLOS mandatory",
            "No-fly zones: airports, military, government buildings",
            "Processing: 15–30 days; cost ~$2,000–$5,000 USD"
        ]
        report_parts.append(f"""
        <div class="section drone-rules">
            <h2>🚁 Drone Rules</h2>
            <ul class="drone-list">
{chr(10).join(f'                <li>{item}</li>' for item in drone_items)}
            </ul>
        </div>
""")
    
    # Checklist
    report_parts.append("""
        <div class="section checklist-section">
            <h2>📋 Actionable Checklist</h2>
            <ul class="checklist">
                <li><input type="checkbox"> Hire Mexican production service company — Week 1</li>
                <li><input type="checkbox"> Submit film permit application — Week 1–2</li>
                <li><input type="checkbox"> Apply for AFAC drone permit — Week 1</li>
                <li><input type="checkbox"> Secure work permits for extras — Week 2–3</li>
                <li><input type="checkbox"> Confirm insurance coverage — Week 2</li>
            </ul>
        </div>
""")
    
    # Final Recommendation
    report_parts.append("""
        <div class="section recommendation">
            <h2>✅ Final Recommendation</h2>
            <p><strong>Proceed with Mexico City</strong> — strong infrastructure, experienced crews, competitive costs. Partner with Story, We Produce, or 80 Days Films for permits, hiring, and drone compliance. Budget <strong>$9,500–$20,500/day</strong> all-in. Start permit process <strong>minimum 4 weeks before shoot</strong>.</p>
        </div>
""")
    
    # Read template and inject content
    template_path = os.path.join(os.path.dirname(__file__), 'template.html')
    try:
        with open(template_path, 'r') as f:
            template = f.read()
    except:
        # Fallback to inline template
        with open(__file__, 'r') as f:
            template = f.read()
    
    # Simple template injection
    content = ''.join(report_parts)
    
    # Return as HTML string
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Production Passport Report</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: #e4e4e4;
            min-height: 100vh;
            padding: 40px 20px;
        }}
        .container {{ max-width: 900px; margin: 0 auto; }}
        .header {{
            text-align: center;
            padding: 30px;
            background: linear-gradient(90deg, #0f3460, #1a1a2e);
            border-radius: 16px;
            margin-bottom: 25px;
        }}
        .header h1 {{
            font-size: 2em;
            background: linear-gradient(90deg, #e94560, #0f3460);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 10px;
        }}
        .header .timestamp {{ color: #888; font-size: 0.9em; }}
        .section {{
            background: rgba(255,255,255,0.05);
            border-radius: 12px;
            padding: 25px;
            margin-bottom: 20px;
            border: 1px solid rgba(255,255,255,0.1);
        }}
        .section h2 {{
            font-size: 1.4em;
            color: #e94560;
            margin-bottom: 20px;
            border-bottom: 2px solid #e94560;
            padding-bottom: 10px;
        }}
        .country-card {{
            background: rgba(15,52,96,0.4);
            border-radius: 10px;
            padding: 20px;
            margin: 15px 0;
            border-left: 4px solid #e94560;
        }}
        .country-card h3 {{ color: #e94560; margin-bottom: 15px; }}
        .cost-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 15px;
            margin: 15px 0;
        }}
        .cost-item {{
            background: rgba(0,0,0,0.3);
            padding: 15px;
            border-radius: 8px;
        }}
        .cost-item .label {{ font-size: 0.8em; color: #888; text-transform: uppercase; }}
        .cost-item .value {{ font-size: 1.2em; font-weight: bold; color: #00d9ff; margin-top: 5px; }}
        .badge {{ display: inline-block; padding: 4px 12px; border-radius: 20px; font-size: 0.85em; font-weight: bold; margin-left: 10px; }}
        .badge-high {{ background: rgba(233,69,96,0.2); color: #e94560; }}
        .badge-medium {{ background: rgba(255,200,0,0.2); color: #f7c948; }}
        .badge-low {{ background: rgba(0,200,83,0.2); color: #00c853; }}
        .recommendation {{ background: linear-gradient(135deg, #0f3460, #1a1a2e); border: 2px solid #e94560; }}
        .recommendation h2 {{ color: #e94560; }}
        .vendor-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 15px; }}
        .vendor-card {{ background: rgba(233,69,96,0.15); border-radius: 8px; padding: 15px; border: 1px solid rgba(233,69,96,0.3); }}
        .vendor-card h4 {{ color: #e94560; margin-bottom: 5px; }}
        .vendor-card .url {{ font-size: 0.85em; color: #00d9ff; }}
        .checklist input {{ margin-right: 10px; width: 18px; height: 18px; cursor: pointer; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎬 Production Passport Report</h1>
            <div class="timestamp">Generated: {timestamp}</div>
        </div>
        <p><em>Demo mode — connect Parallel API + Gemini API keys for live research</em></p>
        
{content}
    </div>
</body>
</html>"""
    
    return html


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
    from flask import Flask, request, jsonify, send_file
    from flask_cors import CORS
    import io
    
    app = Flask(__name__, static_folder=os.path.join(os.path.dirname(__file__), '..', 'frontend'), static_url_path='')
    CORS(app)
    
    @app.route("/")
    def index(): return send_file(app.static_folder + '/index.html')
    
    @app.route("/api/chat", methods=["POST"])
    def chat():
        data = request.json
        msg = data.get("message", "")
        if not msg: return jsonify({"success": False, "error": "Empty"}), 400
        try: 
            result = process_query(msg)
            return jsonify({"success": True, "response": result})
        except Exception as e: 
            import traceback
            print(traceback.format_exc())
            result = generate_demo_report(msg)
            return jsonify({"success": True, "response": f"Error using live API, showing demo:\n\n{result[:1000]}"})
    
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
        except Exception as e: 
            import traceback
            print(traceback.format_exc())
            return jsonify({"success": False, "error": str(e)}), 500
    
    @app.route("/api/health", methods=["GET"])
    def health(): return jsonify({"status": "ok", "timestamp": datetime.now().isoformat(), "mode": "demo"})
    return app


def generate_docx(text):
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    import tempfile
    
    doc = Document()
    title = doc.add_heading("Production Passport Report", level=0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    # Convert HTML/markdown to docx lines
    lines = text.replace('<br>', '\n').split('\n')
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.startswith('##'):
            doc.add_heading(line.replace('#', '').strip(), level=2)
        elif line.startswith('###'):
            doc.add_heading(line.replace('#', '').strip(), level=3)
        elif '•' in line:
            # Extract bullet items
            clean = line.replace('•', '').strip()
            if clean:
                doc.add_paragraph(clean, style='List Bullet')
        elif line.startswith('[') and ']' in line:
            # Markdown link
            import re
            match = re.match(r'\[([^\]]+)\]\(([^)]+)\)', line)
            if match:
                p = doc.add_paragraph(match.group(1), style='List Bullet')
                p.add_run(" (").add_run(match.group(2), style='Intense Italic').add_run(")")
        elif line and ('</' in line or '<' in line):
            # HTML tag - skip or handle
            if '<h' in line:
                clean = line.split('>', 1)[-1].split('<', 1)[0] if '>' in line else line
                if clean and not any(x in clean for x in ['<', '>', 'class=', 'style=']):
                    doc.add_paragraph(clean)
            # Skip other HTML
            continue
        elif line.startswith('|') and not line.startswith('|-'):
            # Table row
            cells = [c.strip() for c in line.split('|')[1:-1]]
            if len(cells) > 0 and not all(set(c) <= set('-:') for c in cells):
                if len(doc.tables) == 0 or doc.tables[-1].rows[-1].cells[-1].text:
                    table = doc.add_table(rows=1, cols=len(cells))
                    table.style = 'Table Grid'
                    for i, cell in enumerate(cells):
                        table.rows[0].cells[i].text = cell
                else:
                    row = table.add_row()
                    for i, cell in enumerate(cells):
                        row.cells[i].text = cell
        elif line:
            # Regular text
            clean = line.replace('**', '').replace('▶', '').strip()
            if clean and not clean.startswith('<'):
                doc.add_paragraph(clean)
    
    with tempfile.NamedTemporaryFile(suffix='.docx', delete=False) as tmp:
        doc.save(tmp.name)
        with open(tmp.name, 'rb') as f:
            data = f.read()
        import os as o
        o.unlink(tmp.name)
    return data


def process_query(message):
    # Check if we should use demo mode (no API keys)
    use_demo = not get_key("PARALLEL_API_KEY") or not get_key("GEMINI_API_KEY")
    
    if use_demo:
        return generate_demo_report(message)
    
    # Extract with regex fallback (no API call needed)
    data = extract_production_info(message)
    
    # Research - PARALLELIZED
    research = {}
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {}
        
        for c in data["countries"]:
            research[c] = []
            futures[executor.submit(ps, f"{c} film commission permit requirements costs 2025")] = (c, "permit")
            if data["drones"]:
                futures[executor.submit(ps, f"{c} drone laws filming foreigners")] = (c, "drone")
            futures[executor.submit(ps, f"{c} film production crew hire rental")] = (c, "crew")
        
        search_results = {}
        for future in as_completed(futures, timeout=30):
            c, stype = futures[future]
            try:
                search_results.setdefault(c, {})[stype] = future.result()
            except Exception as e:
                print(f"Search error for {c} {stype}: {e}")
                search_results.setdefault(c, {})[stype] = {"results": []}
        
        extract_futures = {}
        for c in data["countries"]:
            sr = search_results.get(c, {})
            
            for r in sr.get("permit", {}).get("results", [])[:1]:
                if r.get("url"):
                    extract_futures[executor.submit(pe, r["url"], "film permits")] = (c, r["title"], r["url"])
            
            if data["drones"]:
                for r in sr.get("drone", {}).get("results", [])[:1]:
                    if r.get("url"):
                        extract_futures[executor.submit(pe, r["url"], "drone laws")] = (c, "DRONES " + r["title"], r["url"])
            
            for r in sr.get("crew", {}).get("results", [])[:1]:
                if r.get("url"):
                    extract_futures[executor.submit(pe, r["url"], "crew hire")] = (c, "CREW " + r["title"], r["url"])
        
        for future in as_completed(extract_futures, timeout=30):
            c, title, url = extract_futures[future]
            try:
                extract = future.result()
                if extract:
                    research.setdefault(c, []).append(f"[{title}]({url}): {extract[:800]}")
            except Exception as e:
                print(f"Extract error for {url}: {e}")

    # Report
    prompt = f"""Film production report for: "{message}"
Details: {data['countries']}, {data['location_type']}, {data['extras']} extras, drones={'yes' if data['drones'] else 'no'}, ${data['budget_usd']}

Research:
"""
    for c, items in research.items():
        prompt += f"\n{c}:\n" + "\n".join(items) + "\n"

    prompt += """
Write a COMPLETE, DETAILED report (use full 8000 tokens). Structure:

1. **Executive Summary** (3-4 sentences with specific numbers)
2. **Permits & Costs** — for each country use this format:
┌─────────────────────────────────────────────────────────────────┐
│ COUNTRY NAME                                                    │
├─────────────────────┬────────────────────────────────────────────┤
│ Permit Cost         │ $X – $Y per day                            │
│ Processing Time     │ N – M business days                        │
│ Key Restrictions    │ • Bullet 1                                 │
│                     │ • Bullet 2                                 │
│ Risk Level          │ HIGH/MEDIUM/LOW                            │
└─────────────────────┴────────────────────────────────────────────┘
3. **Bring vs Hire**: Gear rental daily rates, crew day rates, extras cost. Calculate totals. List vendor names. Use bullet points with •
4. **Drone Rules** (if applicable) — bullet points with •
5. **Actionable Checklist** (5-7 items per country with timelines) — checkboxes with ☐
6. **Final Recommendation** with specific budget range

Be specific. No "data unavailable". Use estimates marked as (estimate). Include source URLs as markdown links. NO markdown tables — use the box format above. DO NOT truncate - write the full report."""
    
    result = gm(prompt)
    # Fallback to demo if API failed
    if result.startswith("Error:") or "No working Gemini" in result:
        print(f"API failed, using demo: {result}")
        return generate_demo_report(message)
    return result


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=8080, debug=False)