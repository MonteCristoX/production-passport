import os, json, requests
import re
import subprocess
import tempfile
from datetime import datetime, timezone
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
    """Call Gemini API with the given prompt."""
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
    
    # Extract location (coordinates or place name)
    location = None
    location_type = "unknown"
    
    # Check for Google Maps coordinates (lat, lng)
    coord_match = re.search(r'(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)', message)
    if coord_match:
        lat = float(coord_match.group(1))
        lng = float(coord_match.group(2))
        location = {"lat": lat, "lng": lng, "name": f"Coordinates: {lat}, {lng}"}
        location_type = "coordinates"
    
    # Check for Google Maps URL
    maps_url_match = re.search(r'(https?://(?:www\.)?google\.com/maps/[^\s]+)', message)
    if maps_url_match:
        location = {"url": maps_url_match.group(1), "name": "Google Maps Location"}
        location_type = "maps_url"
    
    # Check for "near [place]" or "in [place]"
    if not location:
        near_match = re.search(r'(?:near|in|at|around)\s+([A-Z][a-z]+(?:\s[A-Z][a-z]+)*)', message)
        if near_match:
            location = {"name": near_match.group(1)}
            location_type = "place_name"
    
    # Countries - FILM-INDUSTRY STANDARD COUNTRIES
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
    for key, val in film_countries.items():
        if key in msg_lower:
            if val not in countries:
                countries.append(val)
    
    # If no country specified, ask user
    if not countries:
        return {"error": True, "message": "Please specify a destination country for filming. Examples: Mexico, Colombia, Spain, Japan, USA, etc."}
    
    # Scene type / location type
    location_scene_type = "urban"
    if any(w in msg_lower for w in ["colonial", "historic", "old town", "centro Historico"]):
        location_scene_type = "heritage"
    elif any(w in msg_lower for w in ["mountain", "beach", "forest", "desert", "nature", "outdoor"]):
        location_scene_type = "natural"
    elif any(w in msg_lower for w in ["studio", "indoor", "interior", "soundstage"]):
        location_scene_type = "studio"
    elif any(w in msg_lower for w in ["aerial", "drone", "fly", "aerial shot"]):
        location_scene_type = "aerial"
    elif any(w in msg_lower for w in ["water", "lake", "river", "sea", "ocean", "underwater"]):
        location_scene_type = "water"
    
    # Extras
    extras = 0
    extras_match = re.search(r'(\d+)\s*extras?\b', msg_lower)
    if extras_match:
        extras = int(extras_match.group(1))
    
    # Crew size
    crew_size = 0
    crew_match = re.search(r'(\d+)\s*(?:crew|people|person|staff|team)', msg_lower)
    if crew_match:
        crew_size = int(crew_match.group(1))
    else:
        crew_size = 10  # default estimate
    
    # Drones
    drones = any(w in msg_lower for w in ["drone", "drones", "uav", "aerial", "quadcopter", "fpv"])
    
    # Pyrotechnics
    pyrotechnics = any(w in msg_lower for w in ["pyro", "pyrotechnics", "fireworks", "explosion", "fire", "burn"])
    
    # Night shoot
    night_shoot = any(w in msg_lower for w in ["night", "evening", "dusk", "dark", "after dark"])
    
    # Water related
    water_related = any(w in msg_lower for w in ["water", "lake", "river", "sea", "ocean", "pool", "boat", "ship"])
    
    # Budget
    budget_usd = 0
    budget_patterns = [
        r'(?:budget|cost|spend|invest\s+of)\s*\$?(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*(k|thousand|million|m|usd)?',
        r'\$(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*(k|thousand|million|m)',
        r'(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*(?:million|m)\s*(?:budget|project|film|cost)',
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
        "location": location,
        "location_type": location_type,
        "scene_type": location_scene_type,
        "extras": extras,
        "crew_size": crew_size,
        "drones": drones,
        "pyrotechnics": pyrotechnics,
        "night_shoot": night_shoot,
        "water_related": water_related,
        "budget_usd": budget_usd,
        "error": False
    }


def get_country_info(country):
    """Get country-specific film production info."""
    info = {
        "Mexico": {
            "risk": "HIGH",
            "permit_cost": "$500 – $5,000/day",
            "processing_time": "10 – 15 business days",
            "restrictions": "• No foreign drone operators allowed\n• AFAC commercial permit mandatory\n• Extras need individual work permits",
            "showstoppers": "• Drone ban for foreigners\n• Extra work permits required\n• Heritage site restrictions",
            "insurance": "• Mexican insurers: AXA Mexico, GNP Seguros\n• Foreign equipment: Allianz Global, Hiscox\n• Worker comp: IMSS (mandatory for local hires)",
            "medical": "• Public: IMSS, ISSSTE, INSABI\n• Private: Hospital Angeles, Hospital ABC, Médica Sur\n• Travel insurance required for foreign crew"
        },
        "Colombia": {
            "risk": "MEDIUM",
            "permit_cost": "$300 – $3,000/day",
            "processing_time": "5 – 10 business days",
            "restrictions": "• Film commission approval required\n• Drone permits via Aerocivil\n• Extras need temporary work visas",
            "showstoppers": "• Visa requirements for crew\n• Customs delays for gear\n• Language barriers",
            "insurance": "• Colombian insurers: SURA, Mapfre, Bolívar\n• Foreign equipment: Lloyd's of London, AIG\n• Worker comp: ARL (mandatory)",
            "medical": "• Public: EPS system\n• Private: Hospital Universitario San Ignacio, Clínica del Country\n• Travel insurance required"
        },
        "Spain": {
            "risk": "MEDIUM",
            "permit_cost": "$200 – $4,000/day",
            "processing_time": "10 – 20 business days",
            "restrictions": "• Autonomous region approvals\n• Heritage site restrictions\n• EU regulations for drone",
            "showstoppers": "• Autonomy region bureaucracy\n• Spanish bureaucracy\n• Heritage site permits",
            "insurance": "• Spanish insurers: Mapfre, Allianz Spain, AXA Spain\n• EU equipment: covered under EU regulations\n• Worker comp: Mutualidad (mandatory)",
            "medical": "• Public: SNS (Spanish Health System)\• Private: Hospital Quirón, Hospital Clínic\n• EU crew: EHIC card accepted"
        },
        "Japan": {
            "risk": "HIGH",
            "permit_cost": "$1,000 – $10,000/day",
            "processing_time": "14 – 30 days",
            "restrictions": "• Foreign crew limitations\n• Strict drone regulations\n• Location permits complex",
            "showstoppers": "• Strict foreign crew rules\n• Complex bureaucracy\n• High permit costs",
            "insurance": "• Japanese insurers: Tokio Marine, Sompo Japan\n• Foreign equipment: requires local insurance\n• Worker comp: Workers' Accident Compensation",
            "medical": "• Public: NHI (National Health Insurance)\• Private: St. Luke's International, Tokyo Medical University\n• Travel insurance required"
        },
        "United States": {
            "risk": "LOW-MEDIUM",
            "permit_cost": "$100 – $2,000/day",
            "processing_time": "5 – 14 business days",
            "restrictions": "• State-specific permits\n• Location releases needed\n• Union regulations",
            "showstoppers": "• Union pickup fees\n• Insurance requirements\n• Location release laws",
            "insurance": "• US insurers: Film Emissary, AIG Entertainment, Nationwide\n• Equipment: inland marine policy\n• Worker comp: state-mandated",
            "medical": "• Private: Mayo Clinic, Cedars-Sinai, NYU Langone\n• Insurance: employer-provided or ACA\n• Travel insurance recommended"
        }
    }
    # Default fallback
    if country not in info:
        return {
            "risk": "MEDIUM",
            "permit_cost": "$200 – $4,000/day",
            "processing_time": "7 – 21 business days",
            "restrictions": "• Local film commission approval needed\n• Check specific location rules\n• Verify drone regulations",
            "showstoppers": "• Unknown local regulations\n• Permit processing delays\n• Language barriers",
            "insurance": "• Local insurance required\n• Foreign equipment: international policy\n• Worker comp: check local laws",
            "medical": "• Local hospitals: verify coverage\n• Travel insurance required\n• Emergency services: check availability"
        }
    return info[country]


def generate_location_context(data):
    """Generate context about the specific filming location."""
    location = data.get("location")
    if not location:
        return ""
    
    context = "\n\nFILAMINATION LOCATION:\n"
    
    if data["location_type"] == "coordinates":
        context += f"- Coordinates: {location['lat']}, {location['lng']}\n"
        context += f"- Google Maps: https://www.google.com/maps?q={location['lat']},{location['lng']}\n"
    elif data["location_type"] == "maps_url":
        context += f"- Google Maps URL: {location['url']}\n"
    elif data["location_type"] == "place_name":
        context += f"- Place: {location['name']}\n"
    
    context += f"- Scene type: {data['scene_type']}\n"
    context += f"- Crew size: {data['crew_size']}\n"
    
    return context


def generate_insurance_section(data):
    """Generate insurance requirements section."""
    countries_str = ", ".join(data["countries"])
    has_equipment = data.get("drones", False) or data.get("pyrotechnics", False)
    
    section = f"""
### 7. INSURANCE REQUIREMENTS

#### Medical Insurance (Crew: {data['crew_size']} people)
  • Travel medical insurance for foreign crew (min $100K coverage)
  • Emergency evacuation coverage
  • Repatriation coverage
  • Pre-existing condition coverage for seniors

#### Equipment Insurance - Brought to Location
  • All-risk equipment coverage (theft, damage, loss)
  • Transit insurance (door-to-door)
  • Replacement value coverage
  • Deductible: typically 1-2% of equipment value

#### Equipment Insurance - Rented Locally
  • Damage waiver (CDW) from rental house
  • Liability for damage beyond normal wear
  • Theft protection
  • Verify rental house insurance vs own coverage

#### Liability Insurance
  • General liability: $1M-$5M per occurrence
  • Third-party injury coverage
  • Property damage coverage
  • Required by most locations

Recommended Insurance Providers:
  • Film Emissary (US)
  • AIG Entertainment (Global)
  • Hiscox (International)
  • Allianz Global (International)
  • Lloyd's of London (High-value)
"""
    
    # Country-specific insurance
    for c in data["countries"]:
        info = get_country_info(c)
        section += f"\n{c} Specific:\n{info['insurance']}\n"
    
    return section


def generate_logistics_section(data):
    """Generate logistics section with hotels, food, hospitals."""
    countries_str = ", ".join(data["countries"])
    crew_size = data.get("crew_size", 10)
    
    section = f"""
### 8. LOGISTICS & AMENITIES

#### Hotels (Crew: {crew_size} people)
  • Production-friendly hotels with:
    - Early breakfast (5-6 AM)
    - Late return accommodation
    - Equipment storage
    - Group booking discounts
  • Recommended: contact local production services for preferred hotels

#### Food & Catering
  • On-set catering requirements
    - 12-16 hour shooting days = 3 meals + snacks
    - Dietary restrictions (vegan, gluten-free, allergies)
    - Hot meals minimum every 6 hours
  • Local restaurants within 30 min of location
  • Craft services (snacks/drinks on set)

#### Nearby Hospitals
  • Verify nearest hospital with ER/urgent care
  • Trauma center for stunts/pyrotechnics
  • Hospital with foreign language support
  • Emergency contact numbers

#### Transportation
  • Production vehicle rental
    - Cube trucks for equipment
    - Passenger vans for cast/crew
    - Generator trucks
    - Makeup/wardrobe trailers
"""
    
    # Country-specific medical
    for c in data["countries"]:
        info = get_country_info(c)
        section += f"\n{c} Medical System:\n{info['medical']}\n"
    
    return section


def generate_demo_report(data):
    """Generate a comprehensive text-based demo report."""
    if data.get("error"):
        return f"**{data['message']}**"
    
    countries_str = ", ".join(data["countries"])
    extras_str = f"{data['extras']} extras" if data['extras'] > 0 else "no extras"
    crew_str = f"{data['crew_size']} crew" if data['crew_size'] > 0 else "standard crew"
    drones_str = "with drones" if data['drones'] else "no drones"
    pyrotechnics_str = "with pyrotechnics" if data['pyrotechnics'] else "no pyrotechnics"
    night_str = "night shooting" if data['night_shoot'] else "day shooting"
    budget_str = f"${data['budget_usd']:,}" if data['budget_usd'] > 0 else "not specified"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    location_context = generate_location_context(data)
    
    report = f"""## Film Production Report
Generated: {timestamp}

Demo mode — connect Parallel API + Gemini API keys for live research

### 1. Executive Summary
Production for {countries_str} ({data['scene_type']} location) with {extras_str}, {crew_str}, {drones_str}, {pyrotechnics_str}, {night_str}. Budget: {budget_str}. Key challenges: permits, crew, compliance.{location_context}

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
    
    report += """
### 3. Bring vs Hire: Cost Analysis

Gear Rental (Daily Rates - Estimated):
  • Camera package (ARRI Alexa Mini / RED): $400 – $800/day
  • Lens set (cine primes): $200 – $400/day
  • Lighting package (HMI/LED): $300 – $600/day
  • Grip equipment: $150 – $300/day

Crew Day Rates (Local Hire - Estimated):
  • Director of Photography: $600 – $1,200/day
  • Gaffer / Key Grip: $350 – $600/day
  • Camera Assistant (1st/2nd AC): $250 – $450/day
  • Production Manager: $400 – $800/day
  • Location Manager: $300 – $500/day
  • Sound Mixer: $350 – $600/day
  • Extras (50 people): $75 – $150/person/day = $3,750 – $7,500/day

Estimated Daily Total (local hire): $6,000 – $12,000/day
Estimated Daily Total (bring crew): $10,000 – $20,000/day (incl. travel, per diem, insurance)

RECOMMENDATION: HIRE LOCALLY — saves 40–50% and avoids visa/logistics complexity.

Local Vendors (Mexico):
  • Story (story.mx) — Full service production
  • We Produce (weproduce.mx) — Equipment & crew
  • 80 Days Films (80daysfilms.com) — International co-productions
"""
    
    if data['drones']:
        report += """
### 4. Drone Rules (Mexico)
  • AFAC permit required for ALL commercial operations (no exceptions)
  • Foreign operators must partner with Mexican certified operator
  • Max altitude: 400 ft (120 m); VLOS mandatory
  • No-fly zones: airports, military, government buildings, crowds
  • Processing: 15–30 days; cost ~$2,000–$5,000 USD
  • Insurance: $1M+ liability required
"""
    
    report += """
### 5. Actionable Checklist

Mexico:
  ☐ Hire Mexican production service company (fixer) — Week 1
  ☐ Submit film permit application to Mexico City Film Commission — Week 1–2
  ☐ Apply for AFAC commercial drone permit (via local partner) — Week 1
  ☐ Secure work permits for 50 extras via local casting agency — Week 2–3
  ☐ Confirm insurance coverage ($1M+ liability, workers' comp) — Week 2
  ☐ Book production-friendly hotels with early breakfast
  ☐ Arrange on-set catering (3 meals + snacks)
  ☐ Verify nearest hospital with ER and foreign language support
  ☐ Rent production vehicles (cube truck, passenger van, trailer)
"""
    
    report += """
### 6. Final Recommendation

PROCEED WITH MEXICO CITY — strong infrastructure, experienced crews, competitive costs. Partner with a local production service (Story, We Produce, or 80 Days Films) to handle permits, hiring, and drone compliance. Budget **$9,500–$20,500/day** all-in. Start permit process **minimum 4 weeks before shoot**.
"""
    
    # Add new sections
    report += generate_insurance_section(data)
    report += generate_logistics_section(data)
    
    return report


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
            
            # Insurance searches
            futures[executor.submit(ps, f"{c} film production insurance equipment rental")] = (c, "equipment_insurance")
            futures[executor.submit(ps, f"{c} medical insurance film crew actors extras")] = (c, "medical_insurance")
            
            # Logistics searches
            if data.get("location"):
                location_name = data["location"].get("name", c)
                futures[executor.submit(ps, f"hotels near {location_name} film production crew")] = (c, "hotels")
                futures[executor.submit(ps, f"hospitals near {location_name} emergency trauma")] = (c, "hospitals")
                futures[executor.submit(ps, f"restaurants near {location_name} catering group bookings")] = (c, "restaurants")
        
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
    location_context = generate_location_context(data)
    
    prompt = f"""Film production analysis for {countries_str}.
PRODUCTION DETAILS:
- Countries: {countries_str}
- Location type: {data['scene_type']}
- Extras: {data['extras']}
- Crew size: {data['crew_size']}
- Drones: {data['drones']}
- Pyrotechnics: {data['pyrotechnics']}
- Night shoot: {data['night_shoot']}
- Budget: ${data['budget_usd']:,} (if specified)
{location_context}

CRITICAL SEARCH RESULTS:
"""
    for c, info in research.items():
        prompt += f"\n{c}:\n"
        for src in info["sources"][:1]:
            if src.get("url"):
                prompt += f"- {src.get('title', '')}: {src.get('url', '')}\n"
    
    prompt += """
WRITE A COMPREHENSIVE FILM PRODUCTION REPORT.

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
3. Bring vs Hire: cost analysis with bullet points
4. Drone Rules (if applicable) with showstoppers
5. Visa/Citizenship Requirements for crew
6. Actionable Checklist with deadlines
7. Final Recommendation with budget
8. Insurance Requirements:
   - Medical insurance for crew (min $100K coverage)
   - Equipment insurance (brought to location)
   - Equipment insurance (rented locally)
   - Liability insurance ($1M-$5M)
   - Recommended providers
9. Logistics & Amenities:
   - Hotels (production-friendly, early breakfast)
   - Food & Catering (3 meals + snacks, dietary restrictions)
   - Nearby hospitals (ER, trauma, foreign language)
   - Transportation (cube truck, passenger van, trailer)

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

    @app.route("/api/save-to-drive", methods=["POST"])
    def save_to_drive():
        data = request.json or {}
        report_text = data.get("report", "")
        if not report_text:
            return jsonify({"success": False, "error": "No report"}), 400
        try:
            uploaded = upload_report_to_drive(report_text)
            return jsonify({"success": True, "file": uploaded})
        except Exception as e:
            app.logger.exception("Google Drive upload failed")
            return jsonify({"success": False, "error": str(e)}), 502
    
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
    import tempfile
    
    doc = Document()
    
    # Title
    title = doc.add_heading("Production Passport Report", level=0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    # Process text line by line
    lines = text.split('\n')
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # Headers
        if line.startswith('## '):
            doc.add_heading(line[3:].strip(), level=2)
        elif line.startswith('### '):
            doc.add_heading(line[4:].strip(), level=3)
        # Checklists with ☐
        elif '☐' in line:
            clean = line.replace('☐', '').strip().lstrip('•').strip()
            if clean:
                doc.add_paragraph(clean).style = 'List Bullet'
        # Bullet points
        elif '•' in line:
            clean = line.lstrip('•').strip()
            if clean:
                doc.add_paragraph(clean).style = 'List Bullet'
        # Country info with tree structure
        elif any(x in line for x in ['├──', '└──', '│', '[HIGH]', '[MEDIUM]', '[LOW]']):
            clean = line.replace('├── ', '').replace('└── ', '').replace('│', '').strip()
            if clean:
                doc.add_paragraph(clean)
        # Regular paragraphs
        elif line and not line.startswith('[') and '|' not in line:
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


def build_report_filename(text):
    title = "production-passport-report"
    for line in text.splitlines():
        clean = line.strip().lstrip("#").strip()
        if clean:
            clean = re.sub(r"^Film Production Report:\s*", "", clean, flags=re.IGNORECASE)
            clean = re.sub(r"[^A-Za-z0-9]+", "-", clean).strip("-").lower()
            if clean:
                title = clean[:70]
            break
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return f"{title}-{timestamp}.docx"


def upload_report_to_drive(report_text):
    docx_bytes = generate_docx(report_text)
    file_name = build_report_filename(report_text)
    helper_path = os.path.join(os.path.dirname(__file__), "google_drive_upload.js")
    temp_path = None

    try:
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as temp_file:
            temp_file.write(docx_bytes)
            temp_path = temp_file.name

        result = subprocess.run(
            ["node", helper_path, temp_path, file_name],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        if result.returncode != 0:
            error = result.stderr.strip() or "Google Drive upload failed"
            raise RuntimeError(error)
        return json.loads(result.stdout)
    finally:
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=8080, debug=False)