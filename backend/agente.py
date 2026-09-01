"""
Production Passport - Conversational Backend
Film production intelligence agent.
Uses Parallel Search API + Gemini to generate comparative reports.
"""

import os
import json
import requests
from typing import Optional

# --- Configuration ---
PARALLEL_API_KEY = os.getenv("PARALLEL_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
PARALLEL_BASE_URL = "https://api.parallel.ai/v1"
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"


def parallel_search(query: str) -> dict:
    """Search using Parallel Search API."""
    if not PARALLEL_API_KEY:
        return {"error": "PARALLEL_API_KEY not configured", "results": []}
    
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


def parallel_extract(url: str, objective: str = "") -> dict:
    """Extract content from URL using Parallel Extract API."""
    if not PARALLEL_API_KEY:
        return {"error": "PARALLEL_API_KEY not configured", "content": ""}
    
    response = requests.post(
        f"{PARALLEL_BASE_URL}/extract",
        headers={
            "Content-Type": "application/json",
            "x-api-key": PARALLEL_API_KEY
        },
        json={
            "urls": [url],
            "objective": objective or "Extract relevant information"
        },
        timeout=30
    )
    response.raise_for_status()
    return response.json()


def gemini_generate(prompt: str, system_prompt: str = "") -> str:
    """Generate text using Gemini API (Google AI Studio)."""
    if not GEMINI_API_KEY:
        return "[GEMINI_API_KEY not configured - simulated result]"
    
    url = f"{GEMINI_BASE_URL}/models/gemini-2.5-flash:generateContent"
    
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 4096
        }
    }
    
    if system_prompt:
        payload["systemInstruction"] = {"parts": [{"text": system_prompt}]}
    
    response = requests.post(
        url,
        json=payload,
        params={"key": GEMINI_API_KEY},
        timeout=60
    )
    response.raise_for_status()
    
    data = response.json()
    try:
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError):
        return json.dumps(data, indent=2)


# --- System Prompt ---
SYSTEM_PROMPT = """You are "Production Passport" — an expert film production intelligence agent.

Your job:
1. Research film production requirements (permits, costs, tax incentives, legal restrictions) across countries
2. Compare whether it's cheaper to BRING gear/crew from abroad vs HIRE locally
3. Provide actionable comparative reports with specific recommendations

When analyzing a production, always include:
- Permit requirements and costs (in USD)
- Processing times
- Key restrictions (drones, pyrotechnics, minors, etc.)
- Local vendor recommendations (camera crews, lighting, grip, extras agencies, etc.)
- Bring vs Hire analysis: what's cheaper to import vs rent/buy locally
- Links to official sources when available
- Actionable checklist per country

If the user doesn't mention countries, suggest 2-3 viable alternatives based on their production type.

Respond in clear, professional English. Use tables for comparisons when helpful."""


def process_query(message: str) -> str:
    """Process user query and generate comparative report."""
    
    # Step 1: Extract production info with Gemini
    extraction_prompt = f"""Extract the following from the user's message:

Message: "{message}"

Respond with ONLY valid JSON (no markdown, no extra text):
{{
  "countries": ["country1", "country2"],
  "location_type": "urban/natural/interior/heritage/aerial",
  "extras": number (0 if not mentioned),
  "drones": true/false,
  "pyrotechnics": true/false,
  "minors": true/false,
  "water": true/false,
  "weapons": true/false,
  "animals": true/false,
  "cranes": true/false,
  "night_shoot": true/false,
  "budget_usd": number (0 if not mentioned),
  "gear_needed": ["camera", "lighting", "grip", "sound", "other"],
  "crew_needed": ["dp", "gaffer", "grip", "sound", "other"]
}}"""

    try:
        extraction_json = gemini_generate(extraction_prompt, "You are an information extractor. Respond ONLY with valid JSON.")
        extraction_json = extraction_json.replace("```json", "").replace("```", "").strip()
        data = json.loads(extraction_json)
    except:
        data = {
            "countries": ["Mexico", "Colombia"],
            "location_type": "urban",
            "extras": 0,
            "drones": False,
            "pyrotechnics": False,
            "minors": False,
            "water": False,
            "weapons": False,
            "animals": False,
            "cranes": False,
            "night_shoot": False,
            "budget_usd": 0,
            "gear_needed": [],
            "crew_needed": []
        }

    if not data.get("countries"):
        data["countries"] = ["Mexico", "Colombia", "Spain"]

    # Step 2: Research each country
    research = []
    for country in data["countries"]:
        elements = []
        if data.get("drones"):
            elements.append("drones")
        if data.get("pyrotechnics"):
            elements.append("pyrotechnics")
        if data.get("minors"):
            elements.append("minors")
        if data.get("water"):
            elements.append("water")
        if data.get("weapons"):
            elements.append("weapons")
        
        elements_str = ", ".join(elements) if elements else "general filming"
        
        # Search for permits
        permit_query = f"film production permits {country} {elements_str} requirements costs 2025"
        
        # Search for local vendors
        vendor_query = f"film production crew hire {country} camera lighting grip rental companies 2025"
        
        contents = []
        try:
            # Permit search
            permit_results = parallel_search(permit_query)
            for result in permit_results.get("results", [])[:2]:
                url = result.get("url", "")
                if url:
                    extract = parallel_extract(url, permit_query)
                    contents.append({
                        "url": url,
                        "title": result.get("title", ""),
                        "content": extract.get("results", [{}])[0].get("excerpts", [""])[0][:1500] if extract.get("results") else ""
                    })
            
            # Vendor search
            vendor_results = parallel_search(vendor_query)
            for result in vendor_results.get("results", [])[:2]:
                url = result.get("url", "")
                if url:
                    extract = parallel_extract(url, vendor_query)
                    contents.append({
                        "url": url,
                        "title": result.get("title", ""),
                        "content": extract.get("results", [{}])[0].get("excerpts", [""])[0][:1500] if extract.get("results") else ""
                    })
        except:
            pass
        
        research.append({
            "country": country,
            "contents": contents
        })

    # Step 3: Generate final report
    report_prompt = f"""Generate a comprehensive film production comparison report.

USER QUERY: "{message}"

EXTRACTED DETAILS:
- Countries: {', '.join(data['countries'])}
- Location: {data['location_type']}
- Extras: {data['extras']}
- Drones: {'Yes' if data['drones'] else 'No'}
- Pyrotechnics: {'Yes' if data['pyrotechnics'] else 'No'}
- Budget: ${data['budget_usd']:,} USD
- Gear needed: {', '.join(data['gear_needed']) if data['gear_needed'] else 'Not specified'}
- Crew needed: {', '.join(data['crew_needed']) if data['crew_needed'] else 'Not specified'}

RESEARCH DATA:
"""

    for r in research:
        report_prompt += f"\n--- {r['country']} ---\n"
        for c in r.get("contents", []):
            report_prompt += f"Source: {c['title']}\nURL: {c['url']}\n{c['content'][:500]}\n\n"

    report_prompt += """
REPORT FORMAT:
1. Executive Summary (2-3 sentences)
2. Comparison Table: Country | Permit Cost | Processing Time | Key Restrictions | Risk Level
3. Bring vs Hire Analysis:
   - What's cheaper to bring from abroad vs hire locally
   - Local vendor recommendations (crews, gear rental, extras agencies)
   - Estimated savings with local hiring
4. Country-specific details with actionable checklist
5. Final recommendation

Be specific with numbers when possible. Include source URLs. If data is limited, say so and recommend contacting local authorities."""

    report = gemini_generate(report_prompt, SYSTEM_PROMPT)
    
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
