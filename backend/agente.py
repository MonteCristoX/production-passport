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

def get_country_contacts(country):
    contacts = {
        "Mexico": ["• **Mexico Film Commission**", "  📧 film@filmcommission.gob.mx", "  🌐 [filmcommission.gob.mx](https://www.filmcommission.gob.mx/)",
                   "", "• **Story Productions**", "  📧 info@story.mx", "  🌐 [story.mx](https://story.mx/)",
                   "", "• **80 Days Films**", "  📧 info@80daysfilms.com", "  🌐 [80daysfilms.com](https://80daysfilms.com/)"],
        "United States": ["• **FilmLA (Los Angeles)**", "  📧 info@filmla.com", "  📞 (213) 977-8600", "  🌐 [filmla.com](https://www.filmla.com/)",
                          "", "• **CA Film Commission**", "  📧 info@film.ca.gov", "  🌐 [film.ca.gov](https://www.film.ca.gov/)",
                          "", "• **SAG-AFTRA**", "  📧 info@sagaftra.org", "  🌐 [sagaftra.org](https://www.sagaftra.org/)"],
        "California": ["• **FilmLA (Los Angeles)**", "  📧 info@filmla.com", "  📞 (213) 977-8600", "  🌐 [filmla.com](https://www.filmla.com/)",
                       "", "• **CA Film Commission**", "  📧 info@film.ca.gov", "  🌐 [film.ca.gov](https://www.film.ca.gov/)"],
        "New York": ["• **Governor's Office for Motion Picture & TV**", "  📧 film@esd.ny.gov", "  🌐 [esd.ny.gov](https://esd.ny.gov/industries/film-and-television)",
                     "", "• **NYC Mayor's Office (MOME)**", "  📧 mome@nyc.gov", "  🌐 [nyc.gov/mome](https://www.nyc.gov/site/mome/index.page)"],
        "Colombia": ["• **ProColombia Film**", "  📧 film@procolombia.co", "  🌐 [procolombia.co](https://www.procolombia.co/en/industries/creative-industries/film)"],
        "Spain": ["• **Spain Film Commission**", "  📧 info@spainfilmcommission.com", "  🌐 [spainfilmcommission.com](https://www.spainfilmcommission.com/)"],
        "Japan": ["• **Japan Film Commission**", "  📧 info@japanfc.jp", "  🌐 [japanfc.jp](https://www.japanfc.jp/eng/)"],
        "United Kingdom": ["• **British Film Commission**", "  📧 info@britishfilmcommission.org.uk", "  🌐 [britishfilmcommission.org.uk](https://britishfilmcommission.org.uk/)"],
    }
    return "\n".join(contacts.get(country, ["• Contact local film office for specific contacts"]))

def get_country_vendors(country):
    vendors = {
        "Mexico": ["• [Story Productions](https://story.mx/) — Full service", "• [We Produce](https://weproduce.mx/) — Equipment",
                   "• [80 Days Films](https://80daysfilms.com/) — Co-productions", "• [Mexico Film Commission](https://www.filmcommission.gob.mx/) — Permits"],
        "United States": ["• [Film Emissary](https://www.filmemissary.com/) — Insurance", "• [Wrapbook](https://www.wrapbook.com/) — Payroll",
                          "• [ShareGrid](https://www.sharegrid.com/) — Equipment", "• [ProductionHUB](https://www.productionhub.com/) — Crew",
                          "• [SAG-AFTRA](https://www.sagaftra.org/) — Union", "• [FilmLA](https://www.filmla.com/) — LA permits"],
        "California": ["• [FilmLA](https://www.filmla.com/) — LA permits", "• [CA Film Commission](https://www.film.ca.gov/) — Incentives",
                       "• [SAG-AFTRA](https://www.sagaftra.org/) — Union"],
        "New York": ["• [NY Governor's Office](https://esd.ny.gov/industries/film-and-television) — State incentives",
                     "• [MOME](https://www.nyc.gov/site/mome/index.page) — NYC permits"],
        "Colombia": ["• [ProColombia Film](https://www.procolombia.co/en/industries/creative-industries/film) — Film commission"],
        "Spain": ["• [Spain Film Commission](https://www.spainfilmcommission.com/) — Locations"],
        "Japan": ["• [Japan Film Commission](https://www.japanfc.jp/eng/) — Production"],
        "United Kingdom": ["• [British Film Commission](https://britishfilmcommission.org.uk/) — UK production"],
    }
    return "\n".join(vendors.get(country, ["• Contact local film office for vendor recommendations"]))

def extract_contacts(country, state=None):
    contacts = []
    queries = []
    if state: queries.extend([f"{state} film commission contact email phone", f"{state} film permit office contact 2025"])
    if country: queries.extend([f"{country} film commission contact email phone", f"{country} film permit office contact"])
    
    search_results = []
    for query in queries[:4]:
        results = ps(query)
        if results.get("results"): search_results.extend(results["results"][:3])
    
    for r in search_results:
        title = r.get("title", "")
        url = r.get("url", "")
        snippet = r.get("snippet", "") or r.get("description", "")
        if not url or not title: continue
        email_match = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', snippet)
        email = email_match.group(0) if email_match else None
        phone_match = re.search(r'(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', snippet)
        phone = phone_match.group(0) if phone_match else None
        if email or phone or 'film commission' in title.lower():
            entry = f"• **{title}**"
            if email: entry += f"\n  📧 {email}"
            if phone: entry += f"\n  📞 {phone}"
            entry += f"\n  🌐 [{url}]({url})"
            if not any(c.startswith(entry[:50]) for c in contacts): contacts.append(entry)
    return contacts[:8]

def generate_live_report(message):
    msg_lower = message.lower()
    countries = []
    location = None
    found_state = None
    
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
            elif geo.get("country"): countries.append(geo["country"])
    
    country_keywords = {"united states": "United States", "usa": "United States", "mexico": "Mexico", 
                       "colombia": "Colombia", "spain": "Spain", "japan": "Japan", "uk": "United Kingdom",
                       "france": "France", "germany": "Germany", "brazil": "Brazil", "canada": "Canada", "costa rica": "Costa Rica"}
    for kw, country in country_keywords.items():
        if kw in msg_lower and country not in countries: countries.append(country)
    
    state_keywords = {"california": "California", "new york": "New York", "georgia": "Georgia",
                     "louisiana": "Louisiana", "texas": "Texas", "florida": "Florida"}
    found_states = []
    for kw, state in state_keywords.items():
        if kw in msg_lower:
            found_states.append(state)
            if "United States" not in countries: countries.append("United States")
    found_state = ", ".join(found_states) if found_states else None
    
    cs = ", ".join(countries)
    st = found_state or ""
    states_list = [s.strip() for s in found_state.split(", ") if s.strip()] if found_state else []
    
    # Search for EACH state separately
    price_data = []
    real_links = []
    all_contacts = []
    
    for state in states_list if states_list else [cs]:
        queries = [
            f"{state} film permit cost fees 2025",
            f"{state} film crew day rates 2025",
            f"{state} film commission contact email phone",
        ]
        for query in queries:
            results = ps(query)
            if results.get("results"):
                for r in results["results"][:3]:
                    title = r.get("title", "")
                    url = r.get("url", "")
                    snippet = r.get("snippet", "") or r.get("description", "")
                    if url and title: real_links.append(f"• [{title}]({url})")
                    if snippet and any(kw in snippet.lower() for kw in ["$", "cost", "fee", "rate", "price"]):
                        price_data.append(f"- {title}: {snippet[:150]}")
        
        state_contacts = extract_contacts(state)
        all_contacts.extend(state_contacts[:3])
    
    links_text = "\n".join(real_links[:15]) if real_links else "No additional links found."
    price_text = "\n".join(price_data[:8]) if price_data else "No specific price data found."
    contacts_text = "\n".join(all_contacts[:10]) if all_contacts else "Contact local film commission."
    
    all_nums = [int(n.replace(',', '')) for n in re.findall(r'\b(\d{1,3}(?:,\d{3})*)\b', msg_lower)]
    crew_size = extras = budget = 0
    for num in all_nums:
        num_pos = msg_lower.find(str(num))
        context = msg_lower[max(0, num_pos-20):num_pos+20]
        if 'crew' in context and crew_size == 0: crew_size = num
        elif 'extr' in context or 'actor' in context: extras = num
        elif any(w in context for w in ['budget', 'cost', 'dollar', 'usd']) and budget == 0: budget = num
    if crew_size == 0 and len(all_nums) >= 2:
        crew_size = all_nums[0]
        if len(all_nums) >= 3: budget = all_nums[2]
    elif crew_size == 0 and len(all_nums) == 1: crew_size = all_nums[0]
    
    drones = any(w in msg_lower for w in ["drone", "drones", "uav", "quadcopter"])
    scene_type = "aerial" if drones else "urban"
    
    verification_queries = []
    if st: verification_queries.extend([f"{st} drone regulations filming 2025", f"{st} film permit changes 2025"])
    if countries: verification_queries.extend([f"{cs} drone laws filming 2025", f"{cs} film regulations updated"])
    
    verification_results = []
    for query in verification_queries[:4]:
        results = ps(query)
        if results.get("results"):
            for r in results["results"][:2]:
                title = r.get("title", "")
                snippet = r.get("snippet", "") or r.get("description", "")
                url = r.get("url", "")
                if title and snippet: verification_results.append(f"- [{title}]({url}): {snippet[:200]}")
    
    verification_text = "\n".join(verification_results[:6]) if verification_results else "No recent updates found. Verify with local authorities."
    
    # Build per-state data sections
    state_data_sections = ""
    for state in states_list if states_list else [cs]:
        state_prices = [p for p in price_data if state.lower() in p.lower()]
        state_links = [l for l in real_links if state.lower() in l.lower()]
        state_contacts_list = [c for c in all_contacts if state.lower() in c.lower()]
        
        state_data_sections += f"\n\n**{state}:**\n"
        if state_prices:
            state_data_sections += "Prices:\n" + "\n".join(state_prices[:3]) + "\n"
        if state_contacts_list:
            state_data_sections += "Contacts:\n" + "\n".join(state_contacts_list[:2]) + "\n"
        if state_links:
            state_data_sections += "Links:\n" + "\n".join(state_links[:3]) + "\n"
    
    prompt = f"""Write a comprehensive film production report comparing multiple locations. Use REAL data from search results.

PRODUCTION DETAILS:
- Locations: {cs}{" ("+st+")" if st else ""}
- Scene type: {scene_type}
- Crew size: {crew_size}
- Extras: {extras}
- Budget: ${budget:,}
- Drones: {"Yes" if drones else "No"}

PER-STATE DATA FROM WEB SEARCH:
{state_data_sections}

ALL PRICE DATA:
{price_text}

ALL CONTACTS:
{contacts_text}

REQUIREMENTS VERIFICATION:
{verification_text}

ALL SOURCE LINKS:
{links_text}

Write a detailed report with these sections. For EACH location, provide separate data where available:

1. Executive Summary (mention all locations)
2. Location Comparison (separate subsection for EACH state with its own permit costs, incentives, contacts)
3. Bring vs Hire: Cost Analysis (compare costs between locations)
4. Insurance Requirements (note any location-specific requirements)
5. Actionable Checklist (organized by location where relevant)
6. Key Contacts (separate contacts for EACH location)
7. Requirements Verification (note location-specific regulations)
8. References & Links (organize by location)

IMPORTANT: 
- Use real data from search results
- Separate information by location throughout the report
- Include specific costs for each location
- Include contact info for each location
- Cite sources using markdown links"""
    
    result = gm(prompt)
    if result.startswith("Error:"): return generate_demo_report(message)
    result += "\n\n---\n*Report generated in **LIVE MODE** with real-time API research.*"
    return result

def generate_demo_report(message):
    msg_lower = message.lower()
    countries = []
    location = None
    found_state = None
    
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
            elif geo.get("country"): countries.append(geo["country"])
    
    country_keywords = {"united states": "United States", "usa": "United States", "mexico": "Mexico", 
                       "colombia": "Colombia", "spain": "Spain", "japan": "Japan", "uk": "United Kingdom",
                       "france": "France", "germany": "Germany", "brazil": "Brazil", "canada": "Canada", "costa rica": "Costa Rica"}
    for kw, country in country_keywords.items():
        if kw in msg_lower and country not in countries: countries.append(country)
    
    state_keywords = {"california": "California", "new york": "New York", "georgia": "Georgia",
                     "louisiana": "Louisiana", "texas": "Texas", "florida": "Florida"}
    found_states = []
    for kw, state in state_keywords.items():
        if kw in msg_lower:
            found_states.append(state)
            if "United States" not in countries: countries.append("United States")
    found_state = ", ".join(found_states) if found_states else None
    
    if not countries:
        return "Please specify a destination country or US state. Examples: California, New York, Mexico, Spain, Japan, etc."
    
    all_nums = [int(n.replace(',', '')) for n in re.findall(r'\b(\d{1,3}(?:,\d{3})*)\b', msg_lower)]
    crew_size = extras = budget = 0
    for num in all_nums:
        num_pos = msg_lower.find(str(num))
        context = msg_lower[max(0, num_pos-20):num_pos+20]
        if 'crew' in context and crew_size == 0: crew_size = num
        elif 'extr' in context or 'actor' in context: extras = num
        elif any(w in context for w in ['budget', 'cost', 'dollar', 'usd']) and budget == 0: budget = num
    if crew_size == 0 and len(all_nums) >= 2:
        crew_size = all_nums[0]
        if len(all_nums) >= 3: budget = all_nums[2]
    elif crew_size == 0 and len(all_nums) == 1: crew_size = all_nums[0]
    
    drones = any(w in msg_lower for w in ["drone", "drones", "uav", "quadcopter"])
    scene_type = "aerial" if drones else "urban"
    
    cs = ", ".join(countries)
    st = found_state or ""
    loc_str = f" ({st})" if st else ""
    
    loc_info = ""
    if location and location.get("city"):
        loc_info = f"\n\n📍 **Filming Location:** {location['city']}, {location.get('state', '')}"
        loc_info += f"\n   📍 Coordinates: {location['lat']}, {location['lng']}"
        loc_info += f"\n   🗺️ Google Maps: https://www.google.com/maps?q={location['lat']},{location['lng']}"
    
    # Per-state comparison sections
    state_sections = ""
    states_list = [s.strip() for s in found_state.split(", ") if s.strip()] if found_state else []
    if len(states_list) >= 2:
        for state in states_list:
            state_contacts = get_country_contacts(state)
            state_vendors = get_country_vendors(state)
            contact_lines = [l.strip() for l in state_contacts.split('\n') if l.strip()][:3]
            vendor_lines = [l.strip() for l in state_vendors.split('\n') if l.strip()][:2]
            state_sections += f"\n\n### {state}\n**Key Contacts:**\n"
            for cl in contact_lines: state_sections += f"{cl}\n"
            state_sections += f"\n**Vendors:**\n"
            for vl in vendor_lines: state_sections += f"{vl}\n"
    
    return f"""## Film Production Report
Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

### 1. Executive Summary
Production comparison for **{cs}**{loc_str} ({scene_type} locations) with **{extras}** extras, **{crew_size}** crew.
Budget: **${budget:,}**.{state_sections}{loc_info}

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

### 5. Requirements Verification

**⚠️ IMPORTANT:** Regulations change frequently. Always verify directly with local authorities:
- Contact the local film commission for current permit requirements
- Confirm drone regulations with civil aviation authority
- Verify if any new tax incentives or restrictions have been enacted
- Check for any recent changes to labor laws affecting crew

### 6. Actionable Checklist

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

### 7. Final Recommendation
Proceed with **{cs}** — contact local production services for permits, hiring, and compliance. Budget **$6,000 – $12,000/day** all-in. Start permit process **minimum 4 weeks before shoot**.

### 8. Key Contacts
{get_country_contacts(cs)}

### 9. References & Links
{get_country_vendors(cs)}
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
        
        if not msg: return jsonify({"success": False, "error": "Empty message"}), 400
        
        try:
            has_apis = bool(get_key("GEMINI_API_KEY")) and bool(get_key("PARALLEL_API_KEY"))
            if has_apis:
                report = generate_live_report(msg)
            else:
                report = generate_demo_report(msg)
            
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
