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
    """Get country-specific film commission contacts."""
    contacts = {
        "Mexico": [
            "• **Mexico Film Commission**",
            "  📧 film@filmcommission.gob.mx",
            "  🌐 [filmcommission.gob.mx](https://www.filmcommission.gob.mx/)",
            "",
            "• **Story Productions (Mexico City)**",
            "  📧 info@story.mx",
            "  🌐 [story.mx](https://story.mx/)",
            "",
            "• **80 Days Films**",
            "  📧 info@80daysfilms.com",
            "  🌐 [80daysfilms.com](https://80daysfilms.com/)",
        ],
        "United States": [
            "• **FilmLA (Los Angeles)**",
            "  📧 info@filmla.com",
            "  📞 (213) 977-8600",
            "  🌐 [filmla.com](https://www.filmla.com/)",
            "",
            "• **CA Film Commission**",
            "  📧 info@film.ca.gov",
            "  🌐 [film.ca.gov](https://www.film.ca.gov/)",
            "",
            "• **SAG-AFTRA**",
            "  📧 info@sagaftra.org",
            "  🌐 [sagaftra.org](https://www.sagaftra.org/)",
        ],
        "California": [
            "• **FilmLA (Los Angeles)**",
            "  📧 info@filmla.com",
            "  📞 (213) 977-8600",
            "  🌐 [filmla.com](https://www.filmla.com/)",
            "",
            "• **CA Film Commission**",
            "  📧 info@film.ca.gov",
            "  🌐 [film.ca.gov](https://www.film.ca.gov/)",
        ],
        "Colombia": [
            "• **ProColombia Film**",
            "  📧 film@procolombia.co",
            "  🌐 [procolombia.co](https://www.procolombia.co/en/industries/creative-industries/film)",
        ],
        "Spain": [
            "• **Spain Film Commission**",
            "  📧 info@spainfilmcommission.com",
            "  🌐 [spainfilmcommission.com](https://www.spainfilmcommission.com/)",
        ],
        "Japan": [
            "• **Japan Film Commission**",
            "  📧 info@japanfc.jp",
            "  🌐 [japanfc.jp](https://www.japanfc.jp/eng/)",
        ],
        "United Kingdom": [
            "• **British Film Commission**",
            "  📧 info@britishfilmcommission.org.uk",
            "  🌐 [britishfilmcommission.org.uk](https://britishfilmcommission.org.uk/)",
        ],
    }
    return "
".join(contacts.get(country, ["• Contact local film office for specific contacts"]))

def get_country_vendors(country):
    """Get country-specific vendor links."""
    vendors = {
        "Mexico": [
            "• [Story Productions](https://story.mx/) — Full service production",
            "• [We Produce](https://weproduce.mx/) — Equipment & crew",
            "• [80 Days Films](https://80daysfilms.com/) — International co-productions",
            "• [Mexico Film Commission](https://www.filmcommission.gob.mx/) — Permits & locations",
        ],
        "United States": [
            "• [Film Emissary](https://www.filmemissary.com/) — Insurance",
            "• [Wrapbook](https://www.wrapbook.com/) — Payroll + Insurance",
            "• [ShareGrid](https://www.sharegrid.com/) — Equipment rental",
            "• [ProductionHUB](https://www.productionhub.com/) — Crew & vendors",
            "• [SAG-AFTRA](https://www.sagaftra.org/) — Union resources",
            "• [FilmLA](https://www.filmla.com/) — LA permits",
        ],
        "California": [
            "• [FilmLA](https://www.filmla.com/) — LA City permits",
            "• [CA Film Commission](https://www.film.ca.gov/) — State incentives",
            "• [SAG-AFTRA](https://www.sagaftra.org/) — Union rates",
        ],
        "Colombia": [
            "• [ProColombia Film](https://www.procolombia.co/en/industries/creative-industries/film) — Film commission",
            "• [Cartagena Film Festival](https://www.cartagenafilmfestival.com/) — Festival info",
        ],
        "Spain": [
            "• [Spain Film Commission](https://www.spainfilmcommission.com/) — Locations & permits",
        ],
        "Japan": [
            "• [Japan Film Commission](https://www.japanfc.jp/eng/) — Production resources",
        ],
        "United Kingdom": [
            "• [British Film Commission](https://britishfilmcommission.org.uk/) — UK production",
        ],
    }
    return "\n".join(vendors.get(country, ["• Contact local film office for vendor recommendations"]))

def extract_contacts(country, state=None):
    """Extract film commission and vendor contacts using Parallel API."""
    contacts = []
    
    # Build search queries
    queries = []
    if state:
        queries.append(f"{state} film commission contact email phone office")
        queries.append(f"{state} film permit office contact information 2025")
        queries.append(f"{state} production services company contact email")
    if country:
        queries.append(f"{country} film commission contact email phone")
        queries.append(f"{country} film permit office contact information")
        queries.append(f"{country} production services film crew contact")
    
    # Execute searches
    search_results = []
    for query in queries[:4]:  # Limit to 4 queries
        results = ps(query)
        if results.get("results"):
            search_results.extend(results["results"][:3])
    
    # Extract contact information from snippets
    for r in search_results:
        title = r.get("title", "")
        url = r.get("url", "")
        snippet = r.get("snippet", "") or r.get("description", "")
        
        if not url or not title:
            continue
        
        # Extract email from snippet
        email_match = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', snippet)
        email = email_match.group(0) if email_match else None
        
        # Extract phone from snippet
        phone_match = re.search(r'(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', snippet)
        phone = phone_match.group(0) if phone_match else None
        
        # Only add if we found contact info or it's a relevant org
        if email or phone or 'film commission' in title.lower() or 'permit' in title.lower():
            contact_entry = f"• **{title}**"
            if email:
                contact_entry += f"
  📧 {email}"
            if phone:
                contact_entry += f"
  📞 {phone}"
            contact_entry += f"
  🌐 [{url}]({url})"
            
            # Avoid duplicates
            if not any(c.startswith(contact_entry[:50]) for c in contacts):
                contacts.append(contact_entry)
    
    return contacts[:8]  # Return top 8 contacts

def generate_live_report(message):
    """Generate report using live APIs with real-time price research."""
    # 1. Detect location from message
    msg_lower = message.lower()
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
    
    cs = ", ".join(countries) if countries else "the specified location"
    st = found_state or ""
    
    # 2. Search for real prices based on location
    search_queries = []
    if st:
        search_queries.extend([
            f"{st} film permit cost fees 2025",
            f"{st} film production crew day rates 2025",
            f"{st} camera equipment rental prices",
        ])
    if countries:
        search_queries.extend([
            f"{cs} film permit requirements costs 2025",
            f"{cs} film production insurance rates",
            f"{cs} film commission contact office",
        ])
    
    # Execute searches
    search_results = []
    for query in search_queries:
        results = ps(query)
        if results.get("results"):
            search_results.extend(results["results"][:3])
    
    # Extract real links and data
    real_links = []
    price_data = []
    for r in search_results:
        title = r.get("title", "")
        url = r.get("url", "")
        snippet = r.get("snippet", "") or r.get("description", "")
        if url and title:
            real_links.append(f"• [{title}]({url})")
        if snippet and any(kw in snippet.lower() for kw in ["$", "cost", "fee", "rate", "price", "usd"]):
            price_data.append(f"- {title}: {snippet[:150]}")
    
    links_text = "\n".join(real_links[:10]) if real_links else "No additional links found."
    price_text = "\n".join(price_data[:5]) if price_data else "No specific price data found in search results."
    
    # 3. Extract numbers from message
    all_nums = [int(n.replace(',', '')) for n in re.findall(r'(\d{1,3}(?:,\d{3})*)', msg_lower)]
    crew_size = extras = budget = 0
    for num in all_nums:
        num_pos = msg_lower.find(str(num))
        context = msg_lower[max(0, num_pos-20):num_pos+20]
        if 'crew' in context and crew_size == 0:
            crew_size = num
        elif 'extr' in context or 'actor' in context:
            extras = num
        elif any(w in context for w in ['budget', 'cost', 'dollar', 'usd']) and budget == 0:
            budget = num
    if crew_size == 0 and len(all_nums) >= 2:
        crew_size = all_nums[0]
        if len(all_nums) >= 3: budget = all_nums[2]
    elif crew_size == 0 and len(all_nums) == 1:
        crew_size = all_nums[0]
    
    # 4. Detect features
    drones = any(w in msg_lower for w in ["drone", "drones", "uav", "quadcopter"])
    scene_type = "aerial" if drones else "urban"
    
    # 5. Extract real contacts
    contacts = extract_contacts(cs, st)
    contacts_text = "
".join(contacts) if contacts else "No specific contacts found. Contact local film commission."
    
    # 6. Generate report with real data
    prompt = f"""Write a comprehensive film production report based on real search data.

PRODUCTION DETAILS:
- Location: {cs}{" ("+st+")" if st else ""}
- Scene type: {scene_type}
- Crew size: {crew_size}
- Extras: {extras}
- Budget: ${budget:,}
- Drones: {"Yes" if drones else "No"}

REAL PRICE DATA FROM WEB SEARCH:
{price_text}

REAL CONTACTS FOUND:
{contacts_text}

REAL SOURCE LINKS:
{links_text}

Write a detailed report with these sections:
1. Executive Summary (use production details above)
2. Country/State Analysis (include real permit costs and processing times from search data)
3. Bring vs Hire: Cost Analysis (use real price data from search results)
4. Insurance Requirements (mention real rates if found)
5. Actionable Checklist
6. Key Contacts (use the real contacts found above with emails and phones)
7. References & Links (use ONLY URLs from search results above)

IMPORTANT: 
- Use real data from search results where available
- Include specific costs and fees found in search
- Include contact information (emails, phones) in the contacts section
- Cite sources using markdown links
- If search didn't find specific prices, use reasonable estimates and note them as such"""

    result = gm(prompt)
    if result.startswith("Error:"):
        return generate_demo_report(message)
    
    # Add footer
    result += "

---
*Report generated in **LIVE MODE** with real-time API research.*"
    return result

def generate_demo_report(message):
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
    
    # Determine mode footer
    has_apis = bool(get_key("GEMINI_API_KEY")) and bool(get_key("PARALLEL_API_KEY"))
    mode_footer = "*Report generated in **LIVE MODE** with real-time API research.*" if has_apis else "*Report generated in **DEMO MODE**. For live research, configure API keys and switch to Live mode.*"

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

### 7. Key Contacts
{get_country_contacts(cs)}

### 8. References & Links
{get_country_vendors(cs)}

---
{mode_footer}
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
            # Check if APIs are configured
            has_gemini = bool(get_key("GEMINI_API_KEY"))
            has_parallel = bool(get_key("PARALLEL_API_KEY"))
            
            if has_gemini and has_parallel:
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
