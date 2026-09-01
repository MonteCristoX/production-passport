"""
Production Passport - Backend
Film production intelligence agent with specific, actionable data.
"""

import os
import json
import requests

# --- Configuration ---
PARALLEL_API_KEY = os.getenv("PARALLEL_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
PARALLEL_BASE_URL = "https://api.parallel.ai/v1"
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"


def parallel_search(query: str) -> dict:
    """Search using Parallel Search API."""
    if not PARALLEL_API_KEY:
        return {"results": []}
    
    try:
        response = requests.post(
            f"{PARALLEL_BASE_URL}/search",
            headers={
                "Content-Type": "application/json",
                "x-api-key": PARALLEL_API_KEY
            },
            json={
                "objective": query,
                "search_queries": [query],
                "mode": "fast"
            },
            timeout=30
        )
        response.raise_for_status()
        return response.json()
    except:
        return {"results": []}


def parallel_extract(url: str, objective: str = "") -> str:
    """Extract content from URL using Parallel Extract API."""
    if not PARALLEL_API_KEY:
        return ""
    
    try:
        response = requests.post(
            f"{PARALLEL_BASE_URL}/extract",
            headers={
                "Content-Type": "application/json",
                "x-api-key": PARALLEL_API_KEY
            },
            json={
                "urls": [url],
                "objective": objective or "Extract all relevant information"
            },
            timeout=30
        )
        response.raise_for_status()
        data = response.json()
        excerpts = data.get("results", [{}])[0].get("excerpts", [""])
        return excerpts[0] if excerpts else ""
    except:
        return ""


def gemini_generate(prompt: str) -> str:
    """Generate text using Gemini API."""
    if not GEMINI_API_KEY:
        return ""
    
    url = f"{GEMINI_BASE_URL}/models/gemini-2.5-flash:generateContent"
    
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 4096
        }
    }
    
    try:
        response = requests.post(
            url,
            json=payload,
            params={"key": GEMINI_API_KEY},
            timeout=90
        )
        response.raise_for_status()
        data = response.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except:
        return ""


def search_and_extract(query: str, max_results: int = 3) -> list:
    """Search for a query and extract content from top results."""
    results = parallel_search(query)
    items = []
    for r in results.get("results", [])[:max_results]:
        url = r.get("url", "")
        title = r.get("title", "")
        if url:
            content = parallel_extract(url, query)
            items.append({
                "url": url,
                "title": title,
                "content": content[:2000]
            })
    return items


def process_query(message: str) -> str:
    """Process user query and generate comprehensive report."""
    
    # Step 1: Extract production details
    extraction_prompt = f"""Extract production details from this message: "{message}"

Respond with ONLY valid JSON:
{{
  "countries": ["country1", "country2"],
  "location_type": "urban/rural/studio",
  "extras": number,
  "drones": true/false,
  "pyrotechnics": true/false,
  "night_shoot": true/false,
  "budget_usd": number,
  "gear_to_rent": ["camera", "lighting", "grip", "sound", "drones", "generators"],
  "crew_to_hire": ["dp", "gaffer", "grip", "sound_mixer", "extras_coordinator"]
}}"""

    try:
        extraction_json = gemini_generate(extraction_prompt)
        extraction_json = extraction_json.replace("```json", "").replace("```", "").strip()
        data = json.loads(extraction_json)
    except:
        data = {
            "countries": ["Mexico", "Colombia"],
            "location_type": "urban",
            "extras": 0,
            "drones": False,
            "pyrotechnics": False,
            "night_shoot": False,
            "budget_usd": 0,
            "gear_to_rent": [],
            "crew_to_hire": []
        }

    if not data.get("countries"):
        data["countries"] = ["Mexico", "Colombia"]

    # Step 2: Research each country with specific queries
    research = {}
    for country in data["countries"]:
        research[country] = {
            "permits": [],
            "drone_rules": [],
            "local_crew": [],
            "gear_rental": [],
            "extras_agencies": [],
            "tax_incentives": []
        }

        # Permits and regulations
        research[country]["permits"] = search_and_extract(
            f"{country} film commission permit requirements costs fees 2024 2025"
        )

        # Drone rules
        if data.get("drones"):
            research[country]["drone_rules"] = search_and_extract(
                f"{country} drone laws filming commercial use foreigners restrictions"
            )

        # Local crew and vendors
        research[country]["local_crew"] = search_and_extract(
            f"{country} film production crew hire DP gaffer grip rental companies"
        )

        # Gear rental
        research[country]["gear_rental"] = search_and_extract(
            f"{country} camera lighting grip equipment rental film production"
        )

        # Extras agencies
        if data.get("extras", 0) > 0:
            research[country]["extras_agencies"] = search_and_extract(
                f"{country} extras agency film production casting"
            )

        # Tax incentives
        research[country]["tax_incentives"] = search_and_extract(
            f"{country} film production tax incentives rebate cash back"
        )

    # Step 3: Build comprehensive prompt for final report
    report_prompt = f"""Generate a detailed film production comparison report. Use ONLY the research data provided below. Do NOT say "data not available" - instead provide estimates based on typical industry standards and clearly mark them as estimates.

USER QUERY: "{message}"

PRODUCTION DETAILS:
- Countries: {', '.join(data['countries'])}
- Location: {data['location_type']}
- Extras: {data['extras']}
- Drones: {'Yes' if data['drones'] else 'No'}
- Pyrotechnics: {'Yes' if data['pyrotechnics'] else 'No'}
- Night shoot: {'Yes' if data['night_shoot'] else 'No'}
- Budget: ${data['budget_usd']:,} USD
- Gear to rent: {', '.join(data['gear_to_rent']) if data['gear_to_rent'] else 'General'}
- Crew to hire: {', '.join(data['crew_to_hire']) if data['crew_to_hire'] else 'General'}

RESEARCH DATA:
"""

    for country, data_research in research.items():
        report_prompt += f"\n{'='*50}\n{country.upper()}\n{'='*50}\n"
        
        report_prompt += "\n[PERMITS & REGULATIONS]\n"
        for item in data_research["permits"]:
            report_prompt += f"Source: {item['title']} ({item['url']})\n{item['content']}\n\n"
        
        if data_research["drone_rules"]:
            report_prompt += "\n[DRONE RULES]\n"
            for item in data_research["drone_rules"]:
                report_prompt += f"Source: {item['title']} ({item['url']})\n{item['content']}\n\n"
        
        if data_research["local_crew"]:
            report_prompt += "\n[LOCAL CREW & VENDORS]\n"
            for item in data_research["local_crew"]:
                report_prompt += f"Source: {item['title']} ({item['url']})\n{item['content']}\n\n"
        
        if data_research["gear_rental"]:
            report_prompt += "\n[GEAR RENTAL]\n"
            for item in data_research["gear_rental"]:
                report_prompt += f"Source: {item['title']} ({item['url']})\n{item['content']}\n\n"
        
        if data_research["extras_agencies"]:
            report_prompt += "\n[EXTRAS AGENCIES]\n"
            for item in data_research["extras_agencies"]:
                report_prompt += f"Source: {item['title']} ({item['url']})\n{item['content']}\n\n"
        
        if data_research["tax_incentives"]:
            report_prompt += "\n[TAX INCENTIVES]\n"
            for item in data_research["tax_incentives"]:
                report_prompt += f"Source: {item['title']} ({item['url']})\n{item['content']}\n\n"

    report_prompt += """
REPORT REQUIREMENTS:
1. Executive Summary (2-3 sentences with specific insights)
2. Permits & Costs Table with columns: Country | Permit Cost (USD) | Processing Time | Key Restrictions
3. Bring vs Hire Analysis:
   - Specific gear rental costs (daily/weekly rates if available)
   - Local crew day rates (DP, gaffer, grip, sound)
   - Extras cost per person per day
   - Calculate: Total bring cost vs Total hire local cost
   - Specific local vendor names and websites when available
4. Drone Rules Summary (if applicable) - specific requirements for foreign operators
5. Tax Incentives (if any) - specific percentages or amounts
6. Country-specific checklist with actionable items

IMPORTANT RULES:
- NEVER say "data not available" - provide estimates based on industry standards
- Mark estimates clearly with "(estimate)"
- Include specific costs whenever possible
- List vendor names and URLs
- Give actionable next steps
- Use tables for comparisons
- Be specific, not vague"""

    report = gemini_generate(report_prompt)
    
    return report


# --- Flask API ---
def create_app():
    from flask import Flask, request, jsonify, send_from_directory
    from flask_cors import CORS
    import os
    
    app = Flask(__name__, static_folder=os.path.join(os.path.dirname(__file__), '..', 'frontend'), static_url_path='')
    CORS(app)
    
    @app.route("/")
    def index():
        return send_from_directory(app.static_folder, 'index.html')
    
    @app.route("/api/chat", methods=["POST"])
    def chat():
        data = request.json
        message = data.get("message", "")
        
        if not message:
            return jsonify({"success": False, "error": "Empty message"}), 400
        
        try:
            response = process_query(message)
            return jsonify({"success": True, "response": response})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500
    
    @app.route("/api/health", methods=["GET"])
    def health():
        return jsonify({
            "status": "ok",
            "parallel_configured": bool(PARALLEL_API_KEY),
            "gemini_configured": bool(GEMINI_API_KEY)
        })
    
    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=8080, debug=True)
