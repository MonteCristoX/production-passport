import os, json, requests
import re
import tempfile
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import io

sessions = {}

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
    except: return {"results": []}

def gm(prompt, retries=2):
    k = get_key("GEMINI_API_KEY")
    if not k: return "Error: GEMINI_API_KEY not configured"
    for model in ["gemini-1.5-flash", "gemini-1.5-pro"]:
        for attempt in range(retries):
            try:
                r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                    json={"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0.5, "maxOutputTokens": 8192}},
                    params={"key": k}, timeout=60)
                if r.status_code == 200: return r.json()["candidates"][0]["content"]["parts"][0]["text"]
                elif r.status_code == 404: break
                elif r.status_code == 429: import time; time.sleep(15 * (attempt + 1)); continue
            except: break
    return "Error: Gemini API failed"

def reverse_geocode(lat, lng):
    try:
        r = requests.get(f"https://api.bigdatacloud.net/data/reverse-geocode-client?latitude={lat}&longitude={lng}&localityLanguage=en", timeout=5)
        if r.status_code == 200:
            d = r.json()
            return {"city": d.get("city") or "", "neighborhood": d.get("locality") or "", 
                    "state": d.get("principalSubdivision") or "", "country": d.get("countryName") or "",
                    "full": f"{d.get('locality', '')}, {d.get('city', '')}, {d.get('principalSubdivision', '')}"}
    except: pass
    return {"city": "", "neighborhood": "", "state": "", "country": "", "full": f"{lat}, {lng}"}

def extract_production_info(msg):
    """Extract production info from message - simple and robust."""
    msg_lower = msg.lower()
    location = None
    location_type = "unknown"
    found_state = None
    countries = []
    
    # 1. Detect coordinates
    coord_match = re.search(r'(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)', msg)
    if coord_match:
        lat, lng = float(coord_match.group(1)), float(coord_match.group(2))
        location = {"lat": lat, "lng": lng, "name": f"{lat}, {lng}"}
        location_type = "coordinates"
        geo = reverse_geocode(lat, lng)
        if geo["city"]:
            location.update(geo)
            if "united states" in geo.get("country", "").lower():
                if "United States" not in countries: countries.append("United States")
                if geo.get("state"): found_state = geo["state"]
            elif geo.get("country"):
                countries.append(geo["country"])
    
    # 2. Detect countries
    country_keywords = {"united states": "United States", "usa": "United States", "mexico": "Mexico", 
                       "colombia": "Colombia", "spain": "Spain", "japan": "Japan", "uk": "United Kingdom",
                       "france": "France", "germany": "Germany", "italy": "Italy", "brazil": "Brazil",
                       "canada": "Canada", "costa rica": "Costa Rica"}
    for kw, country in country_keywords.items():
        if kw in msg_lower and country not in countries:
            countries.append(country)
    
    # 3. Detect US states (only if USA detected)
    if "United States" in countries:
        state_keywords = {"california": "California", "new york": "New York", "georgia": "Georgia",
                         "louisiana": "Louisiana", "texas": "Texas", "florida": "Florida"}
        for kw, state in state_keywords.items():
            if kw in msg_lower:
                found_state = state
                break
    
    # 4. Extract numbers and assign by keyword proximity
    all_nums = [int(n.replace(',', '')) for n in re.findall(r'\b\d{1,3}(?:,\d{3})*\b', msg_lower)]
    
    # Find keywords with positions
    kw_positions = []
    for match in re.finditer(r'(crew|extras|actors|principals|talent|people|staff|team)', msg_lower):
        kw_positions.append((match.start(), match.group(1)))
    
    # Assign numbers to closest keyword
    crew_size = extras = principals = 0
    budget_usd = 0
    
    used_indices = set()
    for num in all_nums:
        num_pos = msg_lower.find(str(num).replace(',', ''))
        best_kw = None
        best_dist = float('inf')
        
        for kw_pos, kw in kw_positions:
            dist = abs(num_pos - kw_pos)
            if dist < best_dist and dist < 30:  # Max 30 chars apart
                best_dist = dist
                best_kw = kw
        
        if best_kw == 'crew': crew_size = num
        elif best_kw in ['extras', 'actors']: extras = num
        elif best_kw in ['principals', 'talent']: principals = num
        elif best_kw in ['people', 'staff', 'team'] and crew_size == 0: crew_size = num
    
    # Fallback: if crew and extras still 0 but we have 2+ numbers
    if crew_size == 0 and extras == 0 and len(all_nums) >= 2:
        crew_size = all_nums[0]
        extras = all_nums[1]
    elif crew_size == 0 and len(all_nums) == 1:
        crew_size = all_nums[0]
    
    # 5. Detect budget (only with money keywords)
    if any(kw in msg_lower for kw in ['budget', 'cost', 'dollars', 'usd', 'thousand', 'million', 'spend', 'invest']):
        for num in sorted(all_nums, reverse=True):
            if num > 100:  # Ignore small numbers
                budget_usd = num
                break
    
    # 6. Detect features
    drones = any(w in msg_lower for w in ["drone", "drones", "uav", "quadcopter", "fpv"])
    pyrotechnics = any(w in msg_lower for w in ["pyro", "pyrotechnics", "fireworks", "explosion"])
    night_shoot = any(w in msg_lower for w in ["night", "evening", "dusk", "dark"])
    water_related = any(w in msg_lower for w in ["water", "lake", "river", "sea", "ocean", "boat", "ship"])
    
    scene_type = "urban"
    if drones: scene_type = "aerial"
    elif water_related: scene_type = "water"
    elif any(w in msg_lower for w in ["mountain", "beach", "forest", "desert"]): scene_type = "natural"
    elif any(w in msg_lower for w in ["colonial", "historic"]): scene_type = "heritage"
    
    return {
        "countries": countries, "location": location, "location_type": location_type,
        "scene_type": scene_type, "extras": extras, "principals": principals,
        "crew_size": crew_size, "drones": drones, "pyrotechnics": pyrotechnics,
        "night_shoot": night_shoot, "water_related": water_related,
        "budget_usd": budget_usd, "state": found_state, "error": False
    }

def generate_demo_report(data):
    """Generate a demo report."""
    if not data.get("countries"):
        return "Please specify a destination country or US state."
    
    cs = ", ".join(data.get("countries", []))
    st = data.get("state", "")
    loc_str = f" ({st})" if st else ""
    crew = data.get("crew_size", 10)
    extras = data.get("extras", 0)
    budget = data.get("budget_usd", 0)
    drones = "with drones" if data.get("drones") else "no drones"
    
    loc_info = ""
    if data.get("location") and data["location"].get("city"):
        loc_info = f"\n📍 Location: {data['location']['city']}, {data['location'].get('state', '')}"
        loc_info += f"\n   Google Maps: https://www.google.com/maps?q={data['location']['lat']},{data['location']['lng']}"
    
    return f"""## Film Production Report
Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

### 1. Executive Summary
Production for {cs}{loc_str} ({data.get('scene_type', 'urban')} location) with {extras} extras, {crew} crew, {drones}.
Budget: ${budget:,}. Key challenges: permits, crew, compliance, insurance.{loc_info}

### 2. Country Analysis
**{cs}** - Risk: MEDIUM
- Permit Cost: $200-$4,000/day
- Processing Time: 7-21 days
- Contact local film commission for specific requirements

### 3. Next Steps
1. Contact local film office for permits
2. Secure insurance quotes
3. Verify property permissions
4. File permit application (3-5 business days)
5. Coordinate SAG-AFTRA casting if using union actors

### 4. References
• Contact local film commission for specific links
"""

def generate_docx(text):
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    doc = Document()
    title = doc.add_heading("Production Passport Report", level=0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for line in text.split('\n'):
        line = line.strip()
        if not line: continue
        if line.startswith('## '): doc.add_heading(line[3:], level=2)
        elif line.startswith('### '): doc.add_heading(line[4:], level=3)
        elif line.startswith('•'): doc.add_paragraph(line[1:].strip()).style = 'List Bullet'
        elif line and not line.startswith('['): doc.add_paragraph(line.replace('**', ''))
    with tempfile.NamedTemporaryFile(suffix='.docx', delete=False) as tmp:
        doc.save(tmp.name)
        with open(tmp.name, 'rb') as f: data = f.read()
        os.unlink(tmp.name)
    return data

def create_app():
    app = Flask(__name__, static_folder=os.path.join(os.path.dirname(__file__), '..', 'frontend'), static_url_path='')
    CORS(app)
    
    @app.route("/")
    def index(): return send_file(app.static_folder + '/index.html')
    
    @app.route("/api/chat", methods=["POST"])
    def chat():
        data = request.json
        msg = data.get("message", "").strip()
        demo = data.get("demo_mode", False)
        session_id = data.get("session_id", "default")
        
        if not msg: return jsonify({"success": False, "error": "Empty"}), 400
        
        if session_id not in sessions:
            sessions[session_id] = {"data": {}, "stage": "gathering"}
        
        session = sessions[session_id]
        
        # Check for final trigger
        final_triggers = ["no", "listo", "así está", "generar", "proceed", "ready", "done", "perfect"]
        if any(t in msg.lower() for t in final_triggers) and session["data"].get("countries"):
            merged = session["data"]
            merged.setdefault("crew_size", 10)
            merged.setdefault("extras", 0)
            merged.setdefault("budget_usd", 0)
            report = generate_demo_report(merged)
            session["stage"] = "complete"
            return jsonify({"success": True, "response": report, "stage": "complete"})
        
        # Extract info from message
        new_data = extract_production_info(msg)
        
        # Merge with existing data
        for key, val in new_data.items():
            if val and val not in [0, False, "", []]:
                session["data"][key] = val
        
        # Check what's missing
        missing = []
        if not session["data"].get("countries"): missing.append("destination country")
        if not session["data"].get("crew_size"): missing.append("crew size")
        if session["data"].get("extras", 0) == 0: missing.append("extras")
        if session["data"].get("budget_usd", 0) == 0: missing.append("budget")
        
        if missing:
            response = f"So far I have:\n"
            if session["data"].get("countries"): response += f"  • 📍 {', '.join(session['data']['countries'])}\n"
            if session["data"].get("crew_size"): response += f"  • 👥 {session['data']['crew_size']} crew\n"
            if session["data"].get("extras"): response += f"  • 🎭 {session['data']['extras']} extras\n"
            if session["data"].get("budget_usd"): response += f"  • 💰 ${session['data']['budget_usd']:,}\n"
            response += f"\nWhat's your {missing[0]}?"
            return jsonify({"success": True, "response": response, "stage": "gathering"})
        else:
            merged = session["data"]
            merged.setdefault("crew_size", 10)
            merged.setdefault("extras", 0)
            merged.setdefault("budget_usd", 0)
            report = generate_demo_report(merged)
            session["stage"] = "complete"
            return jsonify({"success": True, "response": report, "stage": "complete"})
    
    @app.route("/api/export-docx", methods=["POST"])
    def export_docx():
        data = request.json
        report_text = data.get("report", "")
        if not report_text: return jsonify({"success": False, "error": "No report"}), 400
        try:
            docx_bytes = generate_docx(report_text)
            return send_file(io.BytesIO(docx_bytes), mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            as_attachment=True, download_name="production-passport-report.docx")
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500
    
    @app.route("/api/health", methods=["GET"])
    def health():
        return jsonify({"status": "ok", "mode": "live" if get_key("GEMINI_API_KEY") else "demo"})
    return app

if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=8080, debug=False)
