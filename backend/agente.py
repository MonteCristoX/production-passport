import os, json, requests
import re
import tempfile
from datetime import datetime
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import io

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

def generate_report(message):
    """Generate a complete production report from a single user message."""
    msg_lower = message.lower()
    
    # 1. Detect location
    countries = []
    location = None
    found_state = None
    
    # Check coordinates
    coord_match = re.search(r'(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)', message)
    if coord_match:
        lat, lng = float(coord_match.group(1)), float(coord_match.group(2))
        location = {"lat": lat, "lng": lng}
        geo = reverse_geocode(lat, lng)
        if geo["city"]:
            location.update(geo)
            if "united states" in geo.get("country", "").lower():
                countries.append("United States")
                found_state = geo.get("state")
            elif geo.get("country"):
                countries.append(geo["country"])
    
    # Check country keywords
    country_keywords = {"united states": "United States", "usa": "United States", "mexico": "Mexico", 
                       "colombia": "Colombia", "spain": "Spain", "japan": "Japan", "uk": "United Kingdom",
                       "france": "France", "germany": "Germany", "brazil": "Brazil", "canada": "Canada", "costa rica": "Costa Rica"}
    for kw, country in country_keywords.items():
        if kw in msg_lower and country not in countries:
            countries.append(country)
    
    if not countries:
        return "Please specify a destination country or US state. Examples: California, New York, Mexico, Spain, Japan, etc."
    
    # 2. Extract numbers (crew, extras, budget)
    all_nums = [int(n.replace(',', '')) for n in re.findall(r'\b(\d{1,3}(?:,\d{3})*)\b', msg_lower)]
    
    crew_size = extras = budget = 0
    
    # Find keywords with positions
    for num in all_nums:
        num_pos = msg_lower.find(str(num))
        context = msg_lower[max(0, num_pos-20):num_pos+20]
        
        if 'crew' in context and crew_size == 0:
            crew_size = num
        elif 'extr' in context or 'actor' in context:
            extras = num
        elif any(w in context for w in ['budget', 'cost', 'dollar', 'usd', 'spend', 'invest']) and budget == 0:
            budget = num
    
    # Fallback: if no keywords matched but we have numbers
    if crew_size == 0 and len(all_nums) >= 2:
        crew_size = all_nums[0]
        if len(all_nums) >= 3 and budget == 0:
            budget = all_nums[2]
    elif crew_size == 0 and len(all_nums) == 1:
        crew_size = all_nums[0]
    
    # 3. Detect features
    drones = any(w in msg_lower for w in ["drone", "drones", "uav", "quadcopter"])
    pyrotechnics = any(w in msg_lower for w in ["pyro", "pyrotechnics", "fireworks", "explosion"])
    night_shoot = any(w in msg_lower for w in ["night", "evening", "dusk", "dark"])
    water = any(w in msg_lower for w in ["water", "lake", "river", "sea", "ocean", "boat"])
    
    scene_type = "urban"
    if drones: scene_type = "aerial"
    elif water: scene_type = "water"
    elif any(w in msg_lower for w in ["mountain", "beach", "forest", "desert"]): scene_type = "natural"
    
    # 4. Generate report
    cs = ", ".join(countries)
    st = found_state or ""
    loc_str = f" ({st})" if st else ""
    
    loc_info = ""
    if location and location.get("city"):
        loc_info = f"\n\n📍 **Filming Location:** {location['city']}, {location.get('state', '')}"
        loc_info += f"\n   📍 Coordinates: {location['lat']}, {location['lng']}"
        loc_info += f"\n   🗺️ Google Maps: https://www.google.com/maps?q={location['lat']},{location['lng']}"
    
    return f"""## Film Production Report
Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

### 1. Executive Summary
Production for **{cs}**{loc_str} ({scene_type} location) with **{extras}** extras, **{crew_size}** crew.
Budget: **${budget:,}**. Key challenges: permits, crew, compliance, insurance.{loc_info}

### 2. Country Analysis
**{cs}**
- **Risk Level:** MEDIUM
- **Permit Cost:** $200 - $4,000/day
- **Processing Time:** 7-21 business days
- **Key Restrictions:** Local film commission approval required
- **Show Stoppers:** Permit processing delays, local regulations vary

### 3. Bring vs Hire: Cost Analysis

**Gear Rental (Daily Rates - Estimated):**
- Camera package (ARRI Alexa Mini / RED): $400 – $800/day
- Lens set (cine primes): $200 – $400/day
- Lighting package (HMI/LED): $300 – $600/day
- Grip equipment: $150 – $300/day

**Crew Day Rates (Local Hire - Estimated):**
- Director of Photography: $600 – $1,200/day
- Gaffer / Key Grip: $350 – $600/day
- Camera Assistant (1st/2nd AC): $250 – $450/day
- Production Manager: $400 – $800/day
- Location Manager: $300 – $500/day
- Sound Mixer: $350 – $600/day
- **Extras ({extras} people):** $75 – $150/person/day = ${extras*75} – ${extras*150}/day

**Estimated Daily Total (local hire):** $6,000 – $12,000/day

### 4. Insurance Requirements

**Medical Insurance ({crew_size + extras} crew):**
- Travel medical insurance for foreign crew (min $100K coverage)
- Emergency evacuation coverage
- Repatriation coverage

**Equipment Insurance - Brought to Location:**
- All-risk equipment coverage (theft, damage, loss)
- Transit insurance (door-to-door)
- Replacement value coverage

**Liability Insurance:**
- General liability: $1M-$5M per occurrence
- Third-party injury coverage
- Property damage coverage

### 5. Actionable Checklist

**Pre-Production:**
- [ ] Contact local film commission for permit requirements
- [ ] Secure insurance quotes from recommended providers
- [ ] Verify property permissions (written authorization)
- [ ] File permit application (3-5 business days)

**Logistics:**
- [ ] Book production-friendly hotels with early breakfast
- [ ] Arrange on-set catering (3 meals + snacks)
- [ ] Rent production vehicles (cube truck, passenger van, trailer)
- [ ] Verify nearest hospital with ER and foreign language support

### 6. Final Recommendation
Proceed with **{cs}** — contact local production services for permits, hiring, and compliance. Budget **$6,000 – $12,000/day** all-in. Start permit process **minimum 4 weeks before shoot**.

---
*Demo mode — connect APIs for live research and real-time data.*
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
        elif line.startswith('•') or line.startswith('-'):
            doc.add_paragraph(line[1:].strip()).style = 'List Bullet'
        elif line.startswith('['):
            doc.add_paragraph(line).style = 'List Bullet'
        elif line and not line.startswith('['):
            doc.add_paragraph(line.replace('**', ''))
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
        
        if not msg: return jsonify({"success": False, "error": "Empty message"}), 400
        
        try:
            report = generate_report(msg)
            return jsonify({"success": True, "response": report})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500
    
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
