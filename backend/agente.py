import os, json, requests
import re
import tempfile
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

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
    k = get_key("GEMINI_API_KEY")
    if not k:
        return "Error: GEMINI_API_KEY not configured"
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
                    time.sleep(15 * (attempt + 1))
                    continue
            except Exception as e:
                print(f"Gemini error ({model}): {e}")
                break
    return "Error: Gemini API failed"

def extract_production_info(message):
    msg_lower = message.lower()
    location = None
    location_type = "unknown"
    
    coord_match = re.search(r'(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)', message)
    if coord_match:
        lat, lng = float(coord_match.group(1)), float(coord_match.group(2))
        location = {"lat": lat, "lng": lng, "name": f"{lat}, {lng}"}
        location_type = "coordinates"
    
    maps_match = re.search(r'(https?://(?:www\.)?google\.com/maps/[^\s]+)', message)
    if maps_match:
        location = {"url": maps_match.group(1), "name": "Google Maps Location"}
        location_type = "maps_url"
    
    if not location:
        near_match = re.search(r'(?:near|in|at|around)\s+([A-Z][a-z]+(?:\s[A-Z][a-z]+)*)', message)
        if near_match:
            location = {"name": near_match.group(1)}
            location_type = "place_name"
    
    film_countries = {
        "mexico": "Mexico", "colombia": "Colombia", "spain": "Spain",
        "argentina": "Argentina", "brazil": "Brazil", "chile": "Chile",
        "peru": "Peru", "costa rica": "Costa Rica", "japan": "Japan",
        "uk": "United Kingdom", "france": "France", "germany": "Germany",
        "italy": "Italy", "india": "India", "south korea": "South Korea",
        "australia": "Australia", "canada": "Canada", "usa": "United States",
        "czech republic": "Czech Republic", "hungary": "Hungary",
        "thailand": "Thailand", "uae": "United Arab Emirates",
    }
    
    usa_states = {
        "california": "California", "ca": "California", "los angeles": "California",
        "hollywood": "California", "san francisco": "California", "san diego": "California",
        "new york": "New York", "ny": "New York", "nyc": "New York",
        "brooklyn": "New York", "manhattan": "New York",
        "georgia": "Georgia", "ga": "Georgia", "atlanta": "Georgia", "savannah": "Georgia",
        "louisiana": "Louisiana", "new orleans": "Louisiana",
        "new mexico": "New Mexico", "nm": "New Mexico", "albuquerque": "New Mexico",
        "texas": "Texas", "tx": "Texas", "austin": "Texas", "houston": "Texas", "dallas": "Texas",
        "illinois": "Illinois", "il": "Illinois", "chicago": "Illinois",
        "florida": "Florida", "fl": "Florida", "miami": "Florida", "orlando": "Florida",
        "colorado": "Colorado", "co": "Colorado", "denver": "Colorado",
        "washington": "Washington", "wa": "Washington", "seattle": "Washington",
        "oregon": "Oregon", "or": "Oregon", "portland": "Oregon",
        "tennessee": "Tennessee", "tn": "Tennessee", "nashville": "Tennessee",
        "arizona": "Arizona", "az": "Arizona", "phoenix": "Arizona",
        "utah": "Utah", "ut": "Utah", "salt lake city": "Utah",
        "nevada": "Nevada", "nv": "Nevada", "las vegas": "Nevada",
        "massachusetts": "Massachusetts", "ma": "Massachusetts", "boston": "Massachusetts",
        "pennsylvania": "Pennsylvania", "pa": "Pennsylvania", "philadelphia": "Pennsylvania",
        "north carolina": "North Carolina", "nc": "North Carolina",
        "south carolina": "South Carolina", "sc": "South Carolina",
        "michigan": "Michigan", "mi": "Michigan", "detroit": "Michigan",
        "ohio": "Ohio", "oh": "Ohio", "cleveland": "Ohio", "columbus": "Ohio",
        "virginia": "Virginia", "va": "Virginia",
        "maryland": "Maryland", "md": "Maryland", "baltimore": "Maryland",
        "new jersey": "New Jersey", "nj": "New Jersey",
        "connecticut": "Connecticut", "ct": "Connecticut",
        "alabama": "Alabama", "al": "Alabama",
        "kentucky": "Kentucky", "ky": "Kentucky",
        "minnesota": "Minnesota", "mn": "Minnesota", "minneapolis": "Minnesota",
        "wisconsin": "Wisconsin", "wi": "Wisconsin",
        "indiana": "Indiana", "in": "Indiana",
        "missouri": "Missouri", "mo": "Missouri", "kansas city": "Missouri",
        "hawaii": "Hawaii", "hi": "Hawaii", "honolulu": "Hawaii",
        "alaska": "Alaska", "ak": "Alaska",
    }
    
    found_state = None
    countries = []
    for key, val in usa_states.items():
        if key in msg_lower:
            found_state = val
            countries = ["United States"]
            break
    
    if not found_state:
        for key, val in film_countries.items():
            if key in msg_lower and val not in countries:
                countries.append(val)
    
    if not countries:
        return {"error": True, "message": "Please specify a destination country or US state. Examples: California, New York, Mexico, Spain, Japan, etc."}
    
    scene_type = "urban"
    if any(w in msg_lower for w in ["colonial", "historic", "old town"]):
        scene_type = "heritage"
    elif any(w in msg_lower for w in ["mountain", "beach", "forest", "desert", "nature"]):
        scene_type = "natural"
    elif any(w in msg_lower for w in ["studio", "indoor", "interior", "soundstage"]):
        scene_type = "studio"
    elif any(w in msg_lower for w in ["aerial", "drone", "fly"]):
        scene_type = "aerial"
    elif any(w in msg_lower for w in ["water", "lake", "river", "sea", "ocean", "underwater"]):
        scene_type = "water"
    
    extras = 0
    m = re.search(r'(\d+)\s*extras?\b', msg_lower)
    if m:
        extras = int(m.group(1))
    
    crew_size = 10
    m = re.search(r'(\d+)\s*(?:crew|people|person|staff|team)', msg_lower)
    if m:
        crew_size = int(m.group(1))
    
    drones = any(w in msg_lower for w in ["drone", "drones", "uav", "quadcopter", "fpv"])
    pyrotechnics = any(w in msg_lower for w in ["pyro", "pyrotechnics", "fireworks", "explosion", "fire", "burn"])
    night_shoot = any(w in msg_lower for w in ["night", "evening", "dusk", "dark"])
    water_related = any(w in msg_lower for w in ["water", "lake", "river", "sea", "ocean", "boat", "ship"])
    
    budget_usd = 0
    budget_patterns = [
        r'(?:budget|cost|spend|invest\s+of)\s*\$?(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*(k|thousand|million|m|usd)?',
        r'\$(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*(k|thousand|million|m)',
        r'(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*(?:million|m)\s*(?:budget|project|film|cost)',
    ]
    for pat in budget_patterns:
        m = re.search(pat, msg_lower)
        if m:
            amount = float(m.group(1).replace(",", ""))
            unit = (m.group(2) or "").lower()
            if unit in ["k", "thousand"]:
                amount *= 1000
            elif unit in ["million", "m"]:
                amount *= 1000000
            budget_usd = int(amount)
            break
    
    return {
        "countries": countries,
        "location": location,
        "location_type": location_type,
        "scene_type": scene_type,
        "extras": extras,
        "crew_size": crew_size,
        "drones": drones,
        "pyrotechnics": pyrotechnics,
        "night_shoot": night_shoot,
        "water_related": water_related,
        "budget_usd": budget_usd,
        "state": found_state,
        "error": False
    }

def get_usa_state_info(state):
    states = {
        "California": {
            "film_office": "California Film Commission",
            "incentives": "20-25% tax credit (Film & TV Tax Credit 4.0)",
            "locations": "Hollywood, LA, SF, SD, Santa Barbara",
            "permits": "FilmLA (LA city) + State permits",
            "unions": "SAG-AFTRA, IATSE, Teamsters 399",
            "showstoppers": "FilmLA permits required; High union costs; Parking restrictions",
            "hotels": "The Garland, Magic Castle Hotel, Taglyan Complex",
            "hospitals": "Cedars-Sinai (LA), UCSF (SF), UCSD (SD)",
        },
        "New York": {
            "film_office": "Governor's Office for Motion Picture & TV",
            "incentives": "25-30% tax credit (NY State Film Tax Credit)",
            "locations": "Manhattan, Brooklyn, Queens, Hudson Valley",
            "permits": "MOME (Mayor's Office of Media & Entertainment)",
            "unions": "SAG-AFTRA, IATSE 52, Teamsters 817",
            "showstoppers": "MOME permits required; Congestion pricing; Noise ordinances",
            "hotels": "The Pod Hotel, The Local NYC, The William Vale",
            "hospitals": "NYU Langone, Mount Sinai, Bellevue",
        },
        "Georgia": {
            "film_office": "Georgia Film Office",
            "incentives": "20-30% tax credit (GA Entertainment Industry Act)",
            "locations": "Atlanta, Savannah, Senoia, Crawfordville",
            "permits": "Local city/county + GA Film Office",
            "unions": "SAG-AFTRA, IATSE (lower presence)",
            "showstoppers": "Less infrastructure than CA/NY; Weather delays",
            "hotels": "The Whitley, Embassy Suites Atlanta, The Gastonian",
            "hospitals": "Emory Healthcare (ATL), Memorial Health, Candler (Sav)",
        },
        "Louisiana": {
            "film_office": "Louisiana Entertainment",
            "incentives": "25-40% tax credit (LA Motion Picture Tax Credit)",
            "locations": "New Orleans, Baton Rouge, Shreveport",
            "permits": "LA Film Office + local",
            "unions": "SAG-AFTRA, IATSE (moderate)",
            "showstoppers": "Hurricane season (June-Nov); Humidity affects gear",
            "hotels": "The Roosevelt Windsor Court, Omni Royal Orleans",
            "hospitals": "Ochsner Medical Center, Tulane Medical Center",
        },
        "New Mexico": {
            "film_office": "New Mexico Film Office",
            "incentives": "25-35% tax credit (NM Film Tax Credit)",
            "locations": "Albuquerque, Santa Fe, Las Cruces",
            "permits": "NM Film Office + local",
            "unions": "SAG-AFTRA, IATSE (smaller market)",
            "showstoppers": "High altitude affects gear; Limited crew pool",
            "hotels": "Hotel Parq Central, El Rey Inn, Isleta Resort",
            "hospitals": "UNM Hospital (ABQ), Christus St. Vincent (SF)",
        },
    }
    return states.get(state, {
        "film_office": f"{state} Film Commission/Office",
        "incentives": "Check state film office for current incentives",
        "locations": "Contact state film office",
        "permits": "State + local film permits required",
        "unions": "SAG-AFTRA, IATSE may apply",
        "showstoppers": "Check with state film office",
        "hotels": "Contact local production services",
        "hospitals": "Verify nearest trauma center",
    })

def get_country_info(country):
    info = {
        "Mexico": {"risk": "HIGH", "permit_cost": "$500-$5,000/day", "processing_time": "10-15 days",
                   "restrictions": "No foreign drone ops; AFAC permit mandatory; Extras need permits",
                   "showstoppers": "Drone ban for foreigners; Extra work permits; Heritage restrictions",
                   "insurance": "AXA Mexico, GNP Seguros; Allianz Global for foreign equip; IMSS for locals",
                   "medical": "IMSS/ISSSTE (public); Hospital Angeles, ABC (private)"},
        "Colombia": {"risk": "MEDIUM", "permit_cost": "$300-$3,000/day", "processing_time": "5-10 days",
                     "restrictions": "Film commission approval; Aerocivil drone permits; Extras need visas",
                     "showstoppers": "Visa requirements; Customs delays; Language barriers",
                     "insurance": "SURA, Mapfre; Lloyd's for foreign equip; ARL (mandatory)",
                     "medical": "EPS (public); Hospital Universitario San Ignacio (private)"},
        "Spain": {"risk": "MEDIUM", "permit_cost": "$200-$4,000/day", "processing_time": "10-20 days",
                  "restrictions": "Autonomous region approvals; Heritage restrictions; EU drone regs",
                  "showstoppers": "Autonomy bureaucracy; Spanish bureaucracy; Heritage permits",
                  "insurance": "Mapfre, Allianz Spain; EU equip covered; Mutualidad (mandatory)",
                  "medical": "SNS (public); Hospital Quirón (private); EHIC for EU crew"},
        "Japan": {"risk": "HIGH", "permit_cost": "$1,000-$10,000/day", "processing_time": "14-30 days",
                  "restrictions": "Foreign crew limits; Strict drone regs; Complex location permits",
                  "showstoppers": "Strict foreign crew rules; Complex bureaucracy; High costs",
                  "insurance": "Tokio Marine, Sompo Japan; Local insurance required for foreign equip",
                  "medical": "NHI (public); St. Luke's International (private)"},
        "United States": {"risk": "LOW-MEDIUM", "permit_cost": "$100-$2,000/day", "processing_time": "5-14 days",
                          "restrictions": "State-specific permits; Location releases; Union regs",
                          "showstoppers": "Union pickup fees; Insurance requirements; Location release laws",
                          "insurance": "Film Emissary, AIG Entertainment; Inland marine for equip",
                          "medical": "Mayo Clinic, Cedars-Sinai, NYU Langone"},
    }
    return info.get(country, {"risk": "MEDIUM", "permit_cost": "$200-$4,000/day", "processing_time": "7-21 days",
                               "restrictions": "Local film commission approval needed",
                               "showstoppers": "Unknown local regulations; Permit delays",
                               "insurance": "Local insurance required",
                               "medical": "Verify nearest hospital"})

def generate_demo_report(data):
    if data.get("error"):
        return f"**{data['message']}**"
    
    cs = ", ".join(data["countries"])
    st = data.get("state", "")
    loc_str = f" ({st})" if st else ""
    
    report = f"""## Film Production Report
Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

Demo mode — connect APIs for live research

### 1. Executive Summary
Production for {cs}{loc_str} ({data['scene_type']} location) with {data['extras']} extras, {data['crew_size']} crew.
Budget: ${data['budget_usd']:,}. Key challenges: permits, crew, compliance, insurance.

### 2. Country Analysis
"""
    for c in data["countries"]:
        info = get_country_info(c)
        report += f"""
{c.upper()} [{info['risk']}]
├── Permit Cost: {info['permit_cost']}
├── Processing Time: {info['processing_time']}
├── Key Restrictions:
    • {info['restrictions']}
└── Show Stoppers:
    ⚠️ {info['showstoppers']}
"""
    
    if st:
        si = get_usa_state_info(st)
        report += f"""
### 2b. {st} State Details
├── Film Office: {si['film_office']}
├── Incentives: {si['incentives']}
├── Key Locations: {si['locations']}
├── Permits: {si['permits']}
├── Unions: {si['unions']}
├── Show Stoppers: {si['showstoppers']}
├── Hotels: {si['hotels']}
└── Hospitals: {si['hospitals']}
"""
    
    report += f"""
### 3. Bring vs Hire: Cost Analysis
Gear Rental: Camera $400-800/day, Lens $200-400, Lighting $300-600, Grip $150-300
Crew (local hire): DP $600-1200, Gaffer $350-600, AC $250-450, PM $400-800
Extras ({data['extras']} people): $75-150/person/day = ${data['extras']*75}-${data['extras']*150}/day

Estimated Daily Total (local hire): $6,000-$12,000
Estimated Daily Total (bring crew): $10,000-$20,000

RECOMMENDATION: HIRE LOCALLY — saves 40-50%
"""
    
    report += f"""
### 7. INSURANCE REQUIREMENTS
Medical ({data['crew_size']} crew): Travel medical ($100K+), Evacuation, Repatriation
Equipment (brought): All-risk, Transit, Replacement value (1-2% deductible)
Equipment (rented locally): Damage waiver, Theft protection
Liability: $1M-$5M per occurrence, Third-party injury
Providers: Film Emissary, AIG Entertainment, Hiscox, Allianz Global
"""
    
    report += f"""
### 8. LOGISTICS
Hotels ({data['crew_size']} crew): Production-friendly, Early breakfast, Equipment storage
Food: 3 meals + snacks, Dietary restrictions, Craft services
Hospitals: Nearest ER + trauma center, Foreign language support
Transport: Cube truck, Passenger van, Generator truck, Makeup/wardrobe trailer
"""
    
    return report

def process_query(message, demo_mode=False):
    data = extract_production_info(message)
    if data.get("error"):
        return generate_demo_report(data)
    
    use_demo = demo_mode or not get_key("GEMINI_API_KEY")
    if use_demo:
        return generate_demo_report(data)
    
    # Live research
    cs = ", ".join(data["countries"])
    st = data.get("state", "")
    prompt = f"""Film production analysis for {cs}{' ('+st+' state)' if st else ''}.
PRODUCTION: {data['scene_type']} location, {data['extras']} extras, {data['crew_size']} crew, ${data['budget_usd']:,} budget
DRONES: {data['displays'] if False else data['drones']}, PYRO: {data['pyrotechnics']}, NIGHT: {data['night_shoot']}

WRITE A DETAILED REPORT:
1. Executive Summary
2. Country/State Analysis Table:
Country [RISK]
├── Permit Cost, Processing Time
├── Key Restrictions
└── Show Stoppers: (drone bans, visa requirements, legal barriers)
3. Bring vs Hire cost analysis
4. Drone Rules (if applicable)
5. Visa/Work Permit requirements
6. Insurance: medical, equipment (brought/rented), liability
7. Logistics: hotels, food, hospitals, transport
8. Actionable Checklist with deadlines
9. Final Recommendation

Be specific about showstoppers - what could STOP production."""
    
    result = gm(prompt)
    if result.startswith("Error:"):
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
        demo = data.get("demo_mode", False)
        if not msg: return jsonify({"success": False, "error": "Empty"}), 400
        try:
            result = process_query(msg, demo_mode=demo)
            return jsonify({"success": True, "response": result})
        except Exception as e:
            print(f"Chat error: {e}")
            data = extract_production_info(msg)
            return jsonify({"success": True, "response": generate_demo_report(data)})
    
    @app.route("/api/export-docx", methods=["POST"])
    def export_docx():
        data = request.json
        report_text = data.get("report", "")
        if not report_text: return jsonify({"success": False, "error": "No report"}), 400
        try:
            docx_bytes = generate_docx(report_text)
            return send_file(io.BytesIO(docx_bytes),
                mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                as_attachment=True, download_name="production-passport-report.docx")
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500
    
    @app.route("/api/health", methods=["GET"])
    def health():
        return jsonify({"status": "ok", "mode": "live" if get_key("GEMINI_API_KEY") else "demo"})
    return app

def generate_docx(text):
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    
    doc = Document()
    title = doc.add_heading("Production Passport Report", level=0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    for line in text.split('\n'):
        line = line.strip()
        if not line:
            continue
        if line.startswith('## '):
            doc.add_heading(line[3:], level=2)
        elif line.startswith('### '):
            doc.add_heading(line[4:], level=3)
        elif '☐' in line:
            doc.add_paragraph(line.replace('☐', '').strip()).style = 'List Bullet'
        elif '•' in line:
            doc.add_paragraph(line.lstrip('•').strip()).style = 'List Bullet'
        elif any(x in line for x in ['├──', '└──', '│', '[HIGH]', '[MEDIUM]', '[LOW]']):
            doc.add_paragraph(line.replace('├── ', '').replace('└── ', '').replace('│', '').strip())
        elif line and not line.startswith('['):
            doc.add_paragraph(line.replace('**', ''))
    
    with tempfile.NamedTemporaryFile(suffix='.docx', delete=False) as tmp:
        doc.save(tmp.name)
        with open(tmp.name, 'rb') as f:
            data = f.read()
        os.unlink(tmp.name)
    return data

if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=8080, debug=False)
