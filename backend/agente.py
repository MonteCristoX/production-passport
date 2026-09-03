import os, json, requests
import re
import tempfile
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
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

def reverse_geocode(lat, lng):
    try:
        r = requests.get(f"https://api.bigdatacloud.net/data/reverse-geocode-client?latitude={lat}&longitude={lng}&localityLanguage=en", timeout=5)
        if r.status_code == 200:
            data = r.json()
            return {"city": data.get("city") or "", "neighborhood": data.get("locality") or "", 
                    "state": data.get("principalSubdivision") or "", "country": data.get("countryName") or "",
                    "full": f"{data.get('locality', '')}, {data.get('city', '')}, {data.get('principalSubdivision', '')}"}
    except:
        pass
    return {"city": "", "neighborhood": "", "state": "", "country": "", "full": f"{lat}, {lng}"}

def get_sag_aftra_rates():
    return {"background_actor_daily": 231, "background_actor_hourly": 29, "principal_actor_daily": 1246,
            "principal_actor_weekly": 4357, "pension_health_pct": 20.5, "meal_penalty_first": 25,
            "meal_penalty_second": 35, "meal_penalty_subsequent": 50, "meal_break_hours": 6,
            "minimum_background_la": 57, "overtime_hourly_multiplier": 1.5, "golden_time_threshold_hours": 12,
            "golden_time_multiplier": 2.0, "rest_period_hours": 12, "travel_day_rate": 300,
            "wardrobe_allowance": 44, "stunt_base_daily": 2608}

def get_insurance_breakdown(crew_size, equipment_value, days):
    rates = {"general_liability_daily": 150, "workers_comp_pct": 0.025, "equipment_daily_pct": 0.001,
             "cast_insurance_daily": 200, "errors_omissions_daily": 100, "auto_liability_daily": 75, "umbrella_policy_daily": 250}
    estimated_payroll = crew_size * 400 * days
    breakdown = {"general_liability": rates["general_liability_daily"] * days, "workers_comp": int(estimated_payroll * rates["workers_comp_pct"]),
                 "equipment": int(equipment_value * rates["equipment_daily_pct"] * days) if equipment_value > 0 else 0,
                 "cast_insurance": rates["cast_insurance_daily"] * days, "errors_omissions": rates["errors_omissions_daily"] * days,
                 "auto_liability": rates["auto_liability_daily"] * days, "umbrella": rates["umbrella_policy_daily"] * days, "total": 0}
    breakdown["total"] = sum(v for k, v in breakdown.items() if k != "total")
    return breakdown

def get_parking_requirements(crew_size, extras):
    total_people = crew_size + extras
    personal_vehicles = total_people // 2
    production_vehicles = 2 if crew_size <= 10 else 4
    if crew_size > 20: production_vehicles += 2
    return {"personal_vehicles": personal_vehicles, "production_vehicles": production_vehicles, "total_vehicles": personal_vehicles + production_vehicles,
            "parking_cost_daily": (personal_vehicles + production_vehicles) * 25, "truck_cost_daily": production_vehicles * 150,
            "basecamp_needed": crew_size > 15, "basecamp_cost_daily": 500 if crew_size > 15 else 0}

def get_catering_requirements(crew_size, extras, shooting_hours=12):
    total_people = crew_size + extras
    meals_per_day = 2 if shooting_hours >= 10 else 1
    return {"total_people": total_people, "meals_per_day": meals_per_day, "snack_cost_daily": total_people * 35,
            "meal_cost_daily": total_people * 45 * meals_per_day, "total_daily_catering": (total_people * 45 * meals_per_day) + (total_people * 35),
            "meal_penalty_first_30min": 25, "meal_penalty_second_30min": 35, "meal_penalty_subsequent": 50, "turnaround_hours": 6, "golden_time_threshold": 12}

def get_budget_estimate(crew_size, extras, shooting_days=1):
    sag = get_sag_aftra_rates()
    principals = min(5, max(1, extras // 5))
    principals_total = principals * sag["principal_actor_daily"] * shooting_days
    extras_total = extras * sag["background_actor_daily"] * shooting_days
    crew_total = crew_size * 500 * shooting_days
    sag_contribution = int((extras_total + principals_total) * (sag["pension_health_pct"] / 100))
    permit = 1620 if (crew_size + extras) > 30 else 0
    insurance = 1500 * shooting_days
    parking = get_parking_requirements(crew_size, extras)
    parking_total = (parking["parking_cost_daily"] + parking["truck_cost_daily"] + parking["basecamp_cost_daily"]) * shooting_days
    catering = get_catering_requirements(crew_size, extras)
    catering_total = catering["total_daily_catering"] * shooting_days
    equipment_total = (2000 if crew_size <= 10 else 3500) * shooting_days
    total = extras_total + principals_total + crew_total + sag_contribution + permit + insurance + parking_total + catering_total + equipment_total
    return {"shooting_days": shooting_days, "principals": principals, "principals_daily": principals * sag["principal_actor_daily"], "principals_total": principals_total,
            "extras": extras, "extras_daily": extras * sag["background_actor_daily"], "extras_total": extras_total, "crew_daily": crew_size * 500, "crew_total": crew_total,
            "sag_contribution": sag_contribution, "permit": permit, "insurance": insurance, "parking_total": parking_total,
            "catering_total": catering_total, "equipment_total": equipment_total, "total": total, "contingency": int(total * 0.1), "grand_total": int(total * 1.1)}

def extract_production_info(message):
    msg_lower = message.lower()
    location = None
    location_type = "unknown"
    found_state = None
    countries = []
    
    coord_match = re.search(r'(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)', message)
    if coord_match:
        lat, lng = float(coord_match.group(1)), float(coord_match.group(2))
        location = {"lat": lat, "lng": lng, "name": f"{lat}, {lng}"}
        location_type = "coordinates"
        geo = reverse_geocode(lat, lng)
        if geo["city"]:
            location.update({"city": geo["city"], "state": geo["state"], "neighborhood": geo["neighborhood"], "full_address": geo["full"]})
            if "united states" in geo.get("country", "").lower():
                countries.append("United States")
                if geo.get("state"): found_state = geo["state"]
    
    maps_match = re.search(r'(https?://(?:www\.)?google\.com/maps/[^\s]+)', message)
    if maps_match:
        location = {"url": maps_match.group(1), "name": "Google Maps Location"}
        location_type = "maps_url"
    
    if not location:
        near_match = re.search(r'(?:near|in|at|around)\s+([A-Z][a-z]+(?:\s[A-Z][a-z]+)*)', message)
        if near_match:
            location = {"name": near_match.group(1)}
            location_type = "place_name"
    
    film_countries = {"mexico": "Mexico", "colombia": "Colombia", "spain": "Spain", "argentina": "Argentina", "brazil": "Brazil",
                      "chile": "Chile", "peru": "Peru", "costa rica": "Costa Rica", "japan": "Japan", "uk": "United Kingdom",
                      "france": "France", "germany": "Germany", "italy": "Italy", "india": "India", "south korea": "South Korea",
                      "australia": "Australia", "canada": "Canada", "usa": "United States", "czech republic": "Czech Republic",
                      "hungary": "Hungary", "thailand": "Thailand", "uae": "United Arab Emirates"}
    
    usa_states = {"california": "California", "los angeles": "California", "hollywood": "California", "san francisco": "California",
                  "san diego": "California", "new york": "New York", "brooklyn": "New York", "manhattan": "New York",
                  "georgia": "Georgia", "atlanta": "Georgia", "savannah": "Georgia", "louisiana": "Louisiana", "new orleans": "Louisiana",
                  "new mexico": "New Mexico", "albuquerque": "New Mexico", "texas": "Texas", "austin": "Texas", "houston": "Texas",
                  "dallas": "Texas", "illinois": "Illinois", "chicago": "Illinois", "florida": "Florida", "miami": "Florida",
                  "orlando": "Florida", "colorado": "Colorado", "denver": "Colorado", "washington": "Washington", "seattle": "Washington",
                  "oregon": "Oregon", "portland": "Oregon", "tennessee": "Tennessee", "nashville": "Tennessee", "arizona": "Arizona",
                  "phoenix": "Arizona", "utah": "Utah", "salt lake city": "Utah", "nevada": "Nevada", "las vegas": "Nevada",
                  "massachusetts": "Massachusetts", "boston": "Massachusetts", "pennsylvania": "Pennsylvania", "philadelphia": "Pennsylvania",
                  "north carolina": "North Carolina", "south carolina": "South Carolina", "michigan": "Michigan", "detroit": "Michigan",
                  "ohio": "Ohio", "cleveland": "Ohio", "columbus": "Ohio", "virginia": "Virginia", "maryland": "Maryland", "baltimore": "Maryland",
                  "new jersey": "New Jersey", "connecticut": "Connecticut", "alabama": "Alabama", "kentucky": "Kentucky",
                  "minnesota": "Minnesota", "minneapolis": "Minnesota", "wisconsin": "Wisconsin", "indiana": "Indiana",
                  "missouri": "Missouri", "kansas city": "Missouri", "hawaii": "Hawaii", "honolulu": "Hawaii", "alaska": "Alaska"}
    
    for key, val in film_countries.items():
        if key in msg_lower and val not in countries:
            countries.append(val)
    
    if not found_state:
        for key, val in usa_states.items():
            if len(key) >= 4 and key in msg_lower:
                found_state = val
                if "United States" not in countries: countries.append("United States")
                break
    
    if not countries:
        return {"error": True, "message": "Please specify a destination country or US state. Examples: California, New York, Mexico, Spain, Japan, etc."}
    
    scene_type = "urban"
    if any(w in msg_lower for w in ["colonial", "historic", "old town"]): scene_type = "heritage"
    elif any(w in msg_lower for w in ["mountain", "beach", "forest", "desert", "nature"]): scene_type = "natural"
    elif any(w in msg_lower for w in ["studio", "indoor", "interior", "soundstage"]): scene_type = "studio"
    elif any(w in msg_lower for w in ["aerial", "drone", "fly"]): scene_type = "aerial"
    elif any(w in msg_lower for w in ["water", "lake", "river", "sea", "ocean", "underwater"]): scene_type = "water"
    
    extras = 0
    m = re.search(r'(\d+)\s*extras?\b', msg_lower)
    if m: extras = int(m.group(1))
    
    principals = 0
    m = re.search(r'(\d+)\s*(?:actors?|principals?|talent)', msg_lower)
    if m: principals = int(m.group(1))
    
    crew_size = 10
    m = re.search(r'(\d+)\s*(?:crew|people|person|staff|team)', msg_lower)
    if m: crew_size = int(m.group(1))
    else: crew_size = max(10, extras // 2)
    
    drones = any(w in msg_lower for w in ["drone", "drones", "uav", "quadcopter", "fpv"])
    pyrotechnics = any(w in msg_lower for w in ["pyro", "pyrotechnics", "fireworks", "explosion", "fire", "burn"])
    night_shoot = any(w in msg_lower for w in ["night", "evening", "dusk", "dark"])
    water_related = any(w in msg_lower for w in ["water", "lake", "river", "sea", "ocean", "boat", "ship"])
    
    budget_usd = 0
    for pat in [r'(?:budget|cost|spend|invest\s+of)\s*\$?(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*(k|thousand|million|m|usd)?',
                r'\$(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*(k|thousand|million|m)',
                r'(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*(?:million|m)\s*(?:budget|project|film|cost)']:
        m = re.search(pat, msg_lower)
        if m:
            amount = float(m.group(1).replace(",", ""))
            unit = (m.group(2) or "").lower()
            if unit in ["k", "thousand"]: amount *= 1000
            elif unit in ["million", "m"]: amount *= 1000000
            budget_usd = int(amount)
            break
    
    return {"countries": countries, "location": location, "location_type": location_type, "scene_type": scene_type,
            "extras": extras, "principals": principals, "crew_size": crew_size, "drones": drones,
            "pyrotechnics": pyrotechnics, "night_shoot": night_shoot, "water_related": water_related,
            "budget_usd": budget_usd, "state": found_state, "error": False}

def get_usa_state_info(state):
    states = {"California": {"film_office": "California Film Commission", "incentives": "20-25% tax credit (Film & TV Tax Credit 4.0)",
                            "locations": "Hollywood, LA, SF, SD, Santa Barbara", "permits": "FilmLA (LA city) + State permits",
                            "unions": "SAG-AFTRA, IATSE, Teamsters 399", "showstoppers": "FilmLA permits required; High union costs; Parking restrictions",
                            "hotels": "The Garland, Magic Castle Hotel, Taglyan Complex", "hospitals": "Cedars-Sinai (LA), UCSF (SF), UCSD (SD)"},
              "New York": {"film_office": "Governor's Office for Motion Picture & TV", "incentives": "25-30% tax credit",
                           "locations": "Manhattan, Brooklyn, Queens, Hudson Valley", "permits": "MOME", "unions": "SAG-AFTRA, IATSE 52",
                           "showstoppers": "MOME permits required; Congestion pricing", "hotels": "The Pod Hotel, The Local NYC",
                           "hospitals": "NYU Langone, Mount Sinai, Bellevue"}}
    return states.get(state, {"film_office": f"{state} Film Commission", "incentives": "Check state office",
                               "locations": "Contact state office", "permits": "State + local required",
                               "unions": "SAG-AFTRA may apply", "showstoppers": "Check with state",
                               "hotels": "Contact local services", "hospitals": "Verify nearest hospital"})

def get_country_info(country):
    info = {"Mexico": {"risk": "HIGH", "permit_cost": "$500-$5,000/day", "processing_time": "10-15 days",
                       "restrictions": "No foreign drone ops; AFAC permit mandatory; Extras need permits",
                       "showstoppers": "Drone ban for foreigners; Extra work permits; Heritage restrictions",
                       "insurance": "AXA Mexico, GNP Seguros; Allianz Global for foreign equip",
                       "medical": "IMSS/ISSSTE (public); Hospital Angeles, ABC (private)"},
            "United States": {"risk": "LOW-MEDIUM", "permit_cost": "$100-$2,000/day", "processing_time": "5-14 days",
                              "restrictions": "State-specific permits; Location releases; Union regs",
                              "showstoppers": "Union pickup fees; Insurance requirements; Location release laws",
                              "insurance": "Film Emissary, AIG Entertainment; Inland marine for equip",
                              "medical": "Mayo Clinic, Cedars-Sinai, NYU Langone"}}
    return info.get(country, {"risk": "MEDIUM", "permit_cost": "$200-$4,000/day", "processing_time": "7-21 days",
                               "restrictions": "Local film commission approval needed", "showstoppers": "Unknown regulations",
                               "insurance": "Local insurance required", "medical": "Verify nearest hospital"})

def get_country_vendors(country):
    vendors = {"Mexico": ["• [Story Productions](https://story.mx/) — Full service",
                          "• [We Produce](https://weproduce.mx/) — Equipment & crew",
                          "• [80 Days Films](https://80daysfilms.com/) — International co-productions",
                          "• [Mexico Film Commission](https://www.filmcommission.gob.mx/) — Permits"],
               "United States": ["• [Film Emissary](https://www.filmemissary.com/) — Insurance",
                                 "• [Wrapbook](https://www.wrapbook.com/) — Payroll + Insurance",
                                 "• [ShareGrid](https://www.sharegrid.com/) — Equipment rental",
                                 "• [ProductionHUB](https://www.productionhub.com/) — Crew & vendors",
                                 "• [SAG-AFTRA](https://www.sagaftra.org/) — Union resources",
                                 "• [FilmLA](https://www.filmla.com/) — LA permits"],
               "California": ["• [FilmLA](https://www.filmla.com/) — LA City permits",
                              "• [CA Film Commission](https://www.film.ca.gov/) — State incentives",
                              "• [SAG-AFTRA](https://www.sagaftra.org/) — Union rates"]}
    return "\n".join(vendors.get(country, ["• Contact local film office for vendor recommendations"]))

def generate_demo_report(data):
    if data.get("error"): return f"**{data['message']}**"
    cs = ", ".join(data["countries"])
    st = data.get("state", "")
    loc_str = f" ({st})" if st else ""
    
    location_info = ""
    if data.get("location") and data["location"].get("city"):
        location_info = f"\n\n📍 FILMING LOCATION: {data['location'].get('neighborhood', '')}, {data['location']['city']}, {data['location'].get('state', '')}"
        location_info += f"\n   Coordinates: {data['location']['lat']}, {data['location']['lng']}"
        location_info += f"\n   Google Maps: https://www.google.com/maps?q={data['location']['lat']},{data['location']['lng']}"
    
    report = f"""## Film Production Report
Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

### 1. Executive Summary
Production for {cs}{loc_str} ({data['scene_type']} location) with {data['extras']} extras, {data['principals']} principals, {data['crew_size']} crew.
Budget: ${data['budget_usd']:,}. Key challenges: permits, crew, compliance, insurance.{location_info}

### 2. Country Analysis
"""
    for c in data["countries"]:
        info = get_country_info(c)
        report += f"""
{c.upper()} [{info['risk']}]
├── Permit Cost: {info['permit_cost']}
├── Processing Time: {info['processing_time']}
├── Key Restrictions: {info['restrictions']}
└── Show Stoppers: ⚠️ {info['showstoppers']}
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
└── Hotels: {si['hotels']} | Hospitals: {si['hospitals']}
"""
    budget = get_budget_estimate(data['crew_size'], data['extras'])
    sag = get_sag_aftra_rates()
    report += f"""
### 3. Detailed Budget Estimate (1 shooting day)
├── Principals ({budget['principals']} actors): ${budget['principals_daily']:,}/day = ${budget['principals_total']:,}
├── Extras ({budget['extras']} people): ${sag['background_actor_daily']}/day = ${budget['extras_total']:,}
├── Crew: ${budget['crew_daily']:,}/day | SAG Pension ({sag['pension_health_pct']}%): ${budget['sag_contribution']:,}
├── Permit: ${budget['permit']:,} | Insurance: ${budget['insurance']:,}
├── Parking: ${budget['parking_total']:,} | Catering: ${budget['catering_total']:,} | Equipment: ${budget['equipment_total']:,}
├── SUBTOTAL: ${budget['total']:,} | Contingency (10%): ${budget['contingency']:,}
└── GRAND TOTAL (1 day): ${budget['grand_total']:,}

### 4. SAG-AFTRA Requirements (2025-2026)
├── Background Actors: ${sag['background_actor_daily']}/day | Principal: ${sag['principal_actor_daily']}/day
├── Pension & Health: {sag['pension_health_pct']}% | Meal Break: Every {sag['meal_break_hours']}h
├── Meal Penalty: ${sag['meal_penalty_first']}/${sag['meal_penalty_second']}/${sag['meal_penalty_subsequent']}
└── Golden Time (>{sag['golden_time_threshold_hours']}h): {sag['golden_time_multiplier']}× hourly

### 5. Insurance Breakdown (1 day)
├── General Liability: ${get_insurance_breakdown(data['crew_size'], 50000, 1)['general_liability']}
├── Workers' Comp: ${get_insurance_breakdown(data['crew_size'], 50000, 1)['workers_comp']}
├── Equipment: ${get_insurance_breakdown(data['crew_size'], 50000, 1)['equipment']}
├── Cast: ${get_insurance_breakdown(data['crew_size'], 50000, 1)['cast_insurance']}
└── TOTAL DAILY: ${get_insurance_breakdown(data['crew_size'], 50000, 1)['total']}

### 6. Parking & Logistics
├── Vehicles: {get_parking_requirements(data['crew_size'], data['extras'])['total_vehicles']} total
├── Parking: ${get_parking_requirements(data['crew_size'], data['extras'])['parking_cost_daily']}/day
├── Trucks: ${get_parking_requirements(data['crew_size'], data['extras'])['truck_cost_daily']}/day
└── TOTAL: ${sum([get_parking_requirements(data['crew_size'], data['extras'])['parking_cost_daily'], get_parking_requirements(data['crew_size'], data['extras'])['truck_cost_daily'], get_parking_requirements(data['crew_size'], data['extras'])['basecamp_cost_daily']])}

### 7. Catering Requirements
├── People: {get_catering_requirements(data['crew_size'], data['extras'])['total_people']}
├── Meals: {get_catering_requirements(data['crew_size'], data['extras'])['meals_per_day']}/day
├── TOTAL: ${get_catering_requirements(data['crew_size'], data['extras'])['total_daily_catering']}/day
└── Meal Penalty: ${get_catering_requirements(data['crew_size'], data['extras'])['meal_penalty_first_30min']}/${get_catering_requirements(data['crew_size'], data['extras'])['meal_penalty_second_30min']}/${get_catering_requirements(data['crew_size'], data['extras'])['meal_penalty_subsequent']}

### 8. Next Steps
1. Contact local film office for permits
2. Secure insurance quotes
3. Verify property permissions (written authorization)
4. File permit application (3-5 business days)
5. Reserve parking/basecamp
6. Coordinate SAG-AFTRA casting
7. Arrange catering (dietary restrictions)
8. Verify nearest hospital with ER

### 9. References & Links
{get_country_vendors(data['countries'][0])}
"""
    if st:
        report += f"\n{get_country_vendors(st)}\n"
    return report

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
        elif '☐' in line: doc.add_paragraph(line.replace('☐', '').strip()).style = 'List Bullet'
        elif '•' in line:
            clean = line.lstrip('•').strip()
            if clean: doc.add_paragraph(clean).style = 'List Bullet'
        elif any(x in line for x in ['├──', '└──', '│', '[HIGH]', '[MEDIUM]', '[LOW]']):
            doc.add_paragraph(line.replace('├── ', '').replace('└── ', '').replace('│', '').strip())
        elif line and not line.startswith('['): doc.add_paragraph(line.replace('**', ''))
    with tempfile.NamedTemporaryFile(suffix='.docx', delete=False) as tmp:
        doc.save(tmp.name)
        with open(tmp.name, 'rb') as f: data = f.read()
        os.unlink(tmp.name)
    return data

def process_query(message, demo_mode=False):
    data = extract_production_info(message)
    if data.get("error"): return generate_demo_report(data)
    use_demo = demo_mode or not get_key("GEMINI_API_KEY")
    if use_demo: return generate_demo_report(data)
    
    # Live research - gather real links from Parallel
    search_results = []
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {}
        for c in data["countries"]:
            futures[executor.submit(ps, f"{c} film production insurance providers 2025")] = f"{c}_insurance"
            futures[executor.submit(ps, f"{c} film commission permit office website")] = f"{c}_film_office"
            futures[executor.submit(ps, f"{c} film equipment rental companies")] = f"{c}_equipment"
        for future in as_completed(futures, timeout=30):
            try:
                result = future.result()
                if result.get("results"): search_results.extend(result["results"][:2])
            except: pass
    
    real_links = [f"• [{r.get('title', '')}]({r.get('url', '')})" for r in search_results if r.get("url") and r.get("title")]
    links_text = "\n".join(real_links[:15]) if real_links else "No specific links found."
    
    cs = ", ".join(data["countries"])
    st = data.get("state", "")
    prompt = f"""Film production analysis for {cs}{' ('+st+' state)' if st else ''}.
PRODUCTION: {data['scene_type']} location, {data['extras']} extras, {data['principals']} principals, {data['crew_size']} crew, ${data['budget_usd']:,} budget
DRONES: {data['drones']}, PYRO: {data['pyrotechnics']}, NIGHT: {data['night_shoot']}

SEARCH RESULTS:
{links_text}

WRITE A DETAILED REPORT:
1. Executive Summary
2. Country/State Analysis Table
3. Detailed Budget Estimate
4. SAG-AFTRA Requirements (2025-2026 rates)
5. Insurance Breakdown
6. Parking & Logistics
7. Catering Requirements
8. Next Steps & Contacts
9. References & Links (ONLY use URLs from search results above)

IMPORTANT: Only include URLs from search results. Do not make up website addresses."""
    
    result = gm(prompt)
    if result.startswith("Error:"): return generate_demo_report(data)
    return result

def create_app():
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
            return send_file(io.BytesIO(docx_bytes), mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            as_attachment=True, download_name="production-passport-report.docx")
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500
    
    @app.route("/api/save-to-drive", methods=["POST"])
    def save_to_drive():
        """Save report to Google Drive using Google Apps Script webhook."""
        data = request.json
        report_text = data.get("report", "")
        if not report_text: return jsonify({"success": False, "error": "No report"}), 400
        
        try:
            # Generate DOCX
            docx_bytes = generate_docx(report_text)
            
            # Google Apps Script webhook URL (user must configure this)
            drive_webhook_url = os.environ.get("GOOGLE_DRIVE_WEBHOOK_URL", "")
            
            if not drive_webhook_url:
                return jsonify({"success": False, "error": "Google Drive not configured. Set GOOGLE_DRIVE_WEBHOOK_URL in Replit Secrets."}), 400
            
            # Send to Google Apps Script
            import base64
            encoded = base64.b64encode(docx_bytes).decode('utf-8')
            
            response = requests.post(drive_webhook_url, json={
                "fileName": f"production-passport-report-{datetime.now().strftime('%Y%m%d-%H%M%S')}.docx",
                "content": encoded,
                "mimeType": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            }, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                return jsonify({"success": True, "file": result.get("file", {})})
            else:
                return jsonify({"success": False, "error": f"Drive upload failed: {response.status_code}"}), 500
                
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500
    
    @app.route("/api/health", methods=["GET"])
    def health():
        return jsonify({"status": "ok", "mode": "live" if get_key("GEMINI_API_KEY") else "demo"})
    return app

if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=8080, debug=False)
