import os, json, requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import re

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
    """Call Gemini API with the given prompt."""
    k = get_key("GEMINI_API_KEY")
    if not k:
        return "Error: GEMINI_API_KEY not configured"
    
    # Detect key type and choose appropriate models
    is_vertex_key = k.startswith("AQ.") or not k.startswith("AIza")
    
    models_to_try = ["gemini-1.5-flash", "gemini-1.5-pro"]
    
    for model in models_to_try:
        for attempt in range(retries):
            try:
                base_url = "https://generativelanguage.googleapis.com/v1beta/models"
                r = requests.post(f"{base_url}/{model}:generateContent",
                    json={"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0.5, "maxOutputTokens": 8192}},
                    params={"key": k}, timeout=60)
                if r.status_code == 200:
                    return r.json()["candidates"][0]["content"]["parts"][0]["text"]
                elif r.status_code == 404:
                    break
                elif r.status_code == 429:
                    import time
                    wait = 15 * (attempt + 1)
                    time.sleep(wait)
                    continue
            except Exception as e:
                print(f"Gemini error ({model}): {e}")
                break
    
    return "Error: Gemini API failed"


def extract_production_info(message):
    """Extract production info from message - country is required."""
    msg_lower = message.lower()
    
    # Countries - FILM-INDUSTRY STANDARD COUNTRIES (major hubs)
    film_countries = {
        "mexico": "Mexico", "méxico": "Mexico", "mexico city": "Mexico", "ciudad de mexico": "Mexico",
        "colombia": "Colombia", "bogota": "Colombia", "bogotá": "Colombia",
        "spain": "Spain", "madrid": "Spain", "barcelona": "Spain",
        "argentina": "Argentina", "buenos aires": "Argentina",
        "brazil": "Brazil", "rio": "Brazil", "sao paulo": "Brazil", "são paulo": "Brazil",
        "chile": "Chile", "santiago": "Chile",
        "peru": "Peru", "lima": "Peru",
        "costa rica": "Costa Rica",
        "japan": "Japan", "tokyo": "Japan", "osaka": "Japan",
        "uk": "United Kingdom", "london": "United Kingdom",
        "france": "France", "paris": "France",
        "germany": "Germany", "berlin": "Germany",
        "italy": "Italy", "rome": "Rome", "milan": "Italy",
        "india": "India", "mumbai": "India", "delhi": "India",
        "south korea": "South Korea", "seoul": "South Korea", "korea": "South Korea",
        "new zealand": "New Zealand", "australia": "Australia", "sydney": "Australia", "melbourne": "Australia",
        "canada": "Canada", "vancouver": "Canada", "toronto": "Canada",
        "usa": "United States", "us": "United States", "california": "United States", 
        "los angeles": "United States", "la": "United States", "new york": "United States",
        "czech republic": "Czech Republic", "prague": "Czech Republic",
        "hungary": "Hungary", "budapest": "Hungary",
        "romania": "Romania", "bucharest": "Romania",
        "malaysia": "Malaysia", "kuala lumpur": "Malaysia",
        "dubai": "United Arab Emirates", "uae": "United Arab Emirates",
        "thailand": "Thailand", "bangkok": "Thailand",
        "czech": "Czech Republic",
    }
    
    countries = []
    found_country = False
    for key, val in film_countries.items():
        if key in msg_lower:
            if val not in countries:
                countries.append(val)
            found_country = True
    
    # If no country specified, ask user
    if not countries:
        return {"error": True, "message": "Please specify a destination country for filming. Examples: Mexico, Colombia, Spain, Japan, USA, etc."}
    
    # Location type
    location_type = "urban"
    if any(w in msg_lower for w in ["colonial", "historic", "old town", "centro Historico", "ciudad antigua"]):
        location_type = "heritage"
    elif any(w in msg_lower for w in ["mountain", "beach", "forest", "desert", "nature", "outdoor", "nature reserve", "ecological"]):
        location_type = "natural"
    elif any(w in msg_lower for w in ["studio", "indoor", "interior", "soundstage", "backlot"]):
        location_type = "studio"
    elif any(w in msg_lower for w in ["aerial", "drone", "fly", "aerial shot", "aerial footage"]):
        location_type = "aerial"
    
    # Extras
    extras = 0
    extras_match = re.search(r'(\d+)\s*extras?\b', msg_lower)
    if extras_match:
        extras = int(extras_match.group(1))
    
    # Drones
    drones = any(w in msg_lower for w in ["drone", "drones", "uav", "aerial", "quadcopter", "fpv"])
    
    # Pyrotechnics
    pyrotechnics = any(w in msg_lower for w in ["pyro", "pyrotechnics", "fireworks", "explosion", "fire", "burn", "car explosion", "exploding car"])
    
    # Night shoot
    night_shoot = any(w in msg_lower for w in ["night", "evening", "dusk", "dark", "after dark", "night scene"])
    
    # Water related
    water_related = any(w in msg_lower for w in ["water", "lake", "river", "sea", "ocean", "pool", "boat", "ship", "vessel", "marine"])
    
    # Budget - multiple patterns
    budget_usd = 0
    budget_patterns = [
        r'(?:budget|cost|spend|invest\s+of)\s*\$?(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*(k|thousand|million|m|usd)?',
        r'\$(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*(k|thousand|million|m)',
        r'(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*(?:million|m)\s*(?:budget|project|film|cost)',
        r'(?:budget\s+of\s+)?\$?(\d{1,3})\s*(?:to\s+)?\d{1,3}(?:,\d{3})*\s*(?:k|thousand)?',
    ]
    for pattern in budget_patterns:
        budget_match = re.search(pattern, msg_lower)
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
        "water_related": water_related,
        "budget_usd": budget_usd,
        "error": False
    }


def generate_demo_report(data):
    """Generate a text-based demo report."""
    if data.get("error"):
        return f"**{data['message']}**"
    
    countries_str = ", ".join(data["countries"])
    extras_str = f"{data['extras']} extras" if data['extras'] > 0 else "no extras"
    drones_str = "with drones" if data['drones'] else "no drones"
    pyrotechnics_str = "with pyrotechnics" if data['pyrotechnics'] else "no pyrotechnics"
    night_str = "night shooting" if data['night_shoot'] else "day shooting"
    budget_str = f"${data['budget_usd']:,}" if data['budget_usd'] > 0 else "not specified"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    report = f"""## Film Production Report
Generated: {timestamp}

Demo mode — connect Parallel API + Gemini API keys for live research

### 1. Executive Summary
Production for {countries_str} ({data['location_type']} location) with {extras_str}, {drones_str}, {pyrotechnics_str}, {night_str}. Budget: {budget_str}. Key challenges: permits, crew, compliance.

### 2. Country Analysis
"""
    
    for c in data["countries"]:
        info = get_country_info(c)
        report += f"""
{c.upper()} [{info['risk']}]
├── Permit Cost: {info['permit_cost']}
├── Processing Time: {info['processing_time']}
├── Key Restrictions:
{info['restrictions']}
└── Show Stoppers:
{info['showstoppers']}
"""
    
    return report


def get_country_info(country):
    """Get country-specific film production info."""
    info = {
        "Mexico": {
            "risk": "HIGH",
            "permit_cost": "$500 – $5,000/day",
            "processing_time": "10 – 15 business days",
            "restrictions": "• No foreign drone operators allowed\n• AFAC commercial permit mandatory\n• 50 extras need individual work permits",
            "showstoppers": "• Drone ban for foreigners\n• Extra work permits required\n• Heritage site restrictions"
        },
        "Colombia": {
            "risk": "MEDIUM",
            "permit_cost": "$300 – $3,000/day",
            "processing_time": "5 – 10 business days",
            "restrictions": "• Film commission approval required\n• Drone permits via Aerocivil\n• Extras need temporary work visas",
            "showstoppers": "• Visa requirements for crew\n• Customs delays for gear\n• Language barriers"
        },
        "Spain": {
            "risk": "MEDIUM",
            "permit_cost": "$200 – $4,000/day",
            "processing_time": "10 – 20 business days",
            "restrictions": "• Autonomous region approvals\n• Heritage site restrictions\n• EU regulations for drone",
            "showstoppers": "• Autonomy region bureaucracy\n• Spanish bureaucracy\n• Heritage site permits"
        },
        "Japan": {
            "risk": "HIGH",
            "permit_cost": "$1,000 – $10,000/day",
            "processing_time": "14 – 30 days",
            "restrictions": "• Foreign crew limitations\n• Strict drone regulations\n• Location permits complex",
            "showstoppers": "• Strict foreign crew rules\n• Complex bureaucracy\n• High permit costs"
        },
        "United States": {
            "risk": "LOW-MEDIUM",
            "permit_cost": "$100 – $2,000/day",
            "processing_time": "5 – 14 business days",
            "restrictions": "• State-specific permits\n• Location releases needed\n• Union regulations",
            "showstoppers": "• Union pickup fees\n• Insurance requirements\n• Location release laws"
        }
    }
    # Default fallback
    if country not in info:
        return {
            "risk": "MEDIUM",
            "permit_cost": "$200 – $4,000/day",
            "processing_time": "7 – 21 business days",
            "restrictions": "• Local film commission approval needed\n• Check specific location rules\n• Verify drone regulations",
            "showstoppers": "• Unknown local regulations\n• Permit processing delays\n• Language barriers"
        }
    return info[country]


def process_query(message):
    """Main query processor with live research."""
    # Extract info first
    data = extract_production_info(message)
    
    if data.get("error"):
        return generate_demo_report(data)
    
    # Check if we should use demo mode
    use_demo = not get_key("PARALLEL_API_KEY") or not get_key("GEMINI_API_KEY")
    
    if use_demo:
        return generate_demo_report(data)
    
    # Live research mode
    research = {}
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {}
        
        for c in data["countries"]:
            research[c] = {"info": get_country_info(c), "sources": []}
            
            # Critical searches for showstoppers
            futures[executor.submit(ps, f"{c} film permit requirements showstoppers 2025 2026")] = (c, "critical_permits")
            futures[executor.submit(ps, f"{c} drone restrictions foreign filmmakers aerial filming")] = (c, "drone_restrictions")
            futures[executor.submit(ps, f"{c} film crew visa requirements work permit extras actors")] = (c, "visa_work_permits")
            
            if data["drones"]:
                futures[executor.submit(ps, f"{c} commercial drone permit AFAC regulation")] = (c, "drone_permits")
            
            if data['pyrotechnics']:
                futures[executor.submit(ps, f"{c} pyrotechnics filming permit special effects")] = (c, "pyro")
        
        # Collect all search results
        for future in as_completed(futures, timeout=60):
            c, dtype = futures[future]
            try:
                result = future.result()
                if result.get("results"):
                    research[c]["sources"].extend(result["results"][:2])
            except Exception as e:
                print(f"Search error for {c} {dtype}: {e}")
    
    # Build prompt for Gemini
    prompt = f"""Film production analysis for {countries_str}.

PRODUCTION DETAILS:
- Countries: {countries_str}
- Location type: {data['location_type']}
- Extras: {data['extras']}
- Drones: {data['drones']}
- Pyrotechnics: {data['pyrotechnics']}
- Night shoot: {data['night_shoot']}
- Budget: ${data['budget_usd']:,} (if specified)

CRITICAL SEARCH RESULTS:
"""
    for c, info in research.items():
        prompt += f"\n{c}:\n"
        for src in info["sources"][:1]:
            if src.get("url"):
                prompt += f"- {src.get('title', '')}: {src.get('url', '')}\n"
    
    prompt += """
WRITE A DETAILED REPORT WITH SHOWSTOPPERS SECTION.

Structure:
1. Executive Summary
2. Country Analysis Table
   Format:
Country Name [RISK]
├── Permit Cost: $X
├── Processing Time: N days
├── Key Restrictions:
    • Item 1
    • Item 2
├── Show Stoppers:
    ⚠️ CRITICAL ISSUES (referrals, drone bans, visa requirements)
    • Issue 1
    • Issue 2
3. Cost Analysis
4. Drone Rules (if applicable) with showstoppers
5. Visa/Citizenship Requirements for crew
6. Actionable Checklist with deadlines
7. Final Recommendation with budget

Be extremely specific about what could STOP production. List actual legal barriers."""
    
    result = gm(prompt)
    
    if result.startswith("Error:") or "No working Gemini" in result:
        return generate_demo_report(data)
    
    return result


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
        if not msg: return jsonify({"success": False, "error": "Empty message"}), 400
        try: 
            result = process_query(msg)
            return jsonify({"success": True, "response": result})
        except Exception as e: 
            import traceback
            print(traceback.format_exc())
            data = extract_production_info(msg)
            result = generate_demo_report(data)
            return jsonify({"success": True, "response": result + "\n\n--- Error using live API, showing demo ---"})
    
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
    def health(): 
        return jsonify({
            "status": "ok", 
            "timestamp": datetime.now().isoformat(),
            "mode": "live" if get_key("GEMINI_API_KEY") and get_key("PARALLEL_API_KEY") else "demo",
            "has_gemini": bool(get_key("GEMINI_API_KEY")),
            "has_parallel": bool(get_key("PARALLEL_API_KEY"))
        })
    return app


def generate_docx(text):
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Pt
    import tempfile
    
    doc = Document()
    
    # Title
    title = doc.add_heading("Production Passport Report", level=0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    # Process text line by line
    lines = text.split('\n')
    current_list = None
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # Headers
        if line.startswith('## '):
            doc.add_heading(line[3:].strip(), level=2)
            current_list = None
        elif line.startswith('### '):
            doc.add_heading(line[4:].strip(), level=3)
            current_list = None
        # Checklists with ☐
        elif '☐' in line:
            clean = line.replace('☐', '').strip().lstrip('•').strip()
            if clean:
                doc.add_paragraph(clean).style = 'List Bullet'
                current_list = 'checklist'
        # Bullet points
        elif '•' in line:
            clean = line.lstrip('•').strip()
            if clean:
                doc.add_paragraph(clean).style = 'List Bullet'
                current_list = 'list'
        # Country info with tree structure
        elif any(x in line for x in ['├──', '└──', '│', '[HIGH]', '[MEDIUM]', '[LOW]']):
            # Tree structure line
            clean = line.replace('├── ', '').replace('└── ', '').replace('│', '').strip()
            if clean:
                doc.add_paragraph(clean)
        # Regular paragraphs
        elif line and not line.startswith('[') and '|' not in line:
            # Clean up formatting
            clean = line.replace('**', '').strip()
            if clean and len(clean) > 2:
                doc.add_paragraph(clean)
    
    # Save to temp file and return bytes
    with tempfile.NamedTemporaryFile(suffix='.docx', delete=False) as tmp:
        doc.save(tmp.name)
        with open(tmp.name, 'rb') as f:
            data = f.read()
        import os as o
        o.unlink(tmp.name)
    return data


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=8080, debug=False)