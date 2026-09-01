"""
Production Passport - Backend Agente Conversacional
Investiga requisitos de producción cinematográfica por país.
Usa Parallel Search API + Gemini para generar reportes comparativos.
"""

import os
import json
import requests
from typing import Optional

# --- Configuración ---
PARALLEL_API_KEY = os.getenv("PARALLEL_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
PARALLEL_BASE_URL = "https://api.parallel.ai/v1"
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"


def parallel_search(query: str) -> dict:
    """Busca información usando Parallel Search API."""
    if not PARALLEL_API_KEY:
        return {"error": "PARALLEL_API_KEY no configurada", "results": []}
    
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
    """Extrae contenido de una URL usando Parallel Extract API."""
    if not PARALLEL_API_KEY:
        return {"error": "PARALLEL_API_KEY no configurada", "content": ""}
    
    response = requests.post(
        f"{PARALLEL_BASE_URL}/extract",
        headers={
            "Content-Type": "application/json",
            "x-api-key": PARALLEL_API_KEY
        },
        json={
            "urls": [url],
            "objective": objective or "Extraer información relevante"
        },
        timeout=30
    )
    response.raise_for_status()
    return response.json()


def gemini_generate(prompt: str, system_prompt: str = "") -> str:
    """Genera texto usando Gemini API (Google AI Studio)."""
    if not GEMINI_API_KEY:
        return "[GEMINI_API_KEY no configurada - resultado simulado]"
    
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


# --- System Prompt del Agente ---
SYSTEM_PROMPT = """Eres un experto en producción cinematográfica internacional llamado "Production Passport".
Tu trabajo es investigar y comparar requisitos de producción (permisos, costos, incentivos fiscales, restricciones) 
para diferentes países.

Cuando recibas una consulta del usuario, debes:
1. Identificar los requisitos específicos según el tipo de producción mencionado
2. Investigar por cada país mencionado o sugerir alternativas
3. Generar un reporte comparativo claro y accionable

Siempre incluye:
- Costos estimados de permisos (en USD)
- Tiempos de aprobación
- Requisitos específicos (drones, pirotecnia, menores, etc.)
- Links a fuentes oficiales cuando estén disponibles
- Un checklist accionable por país

Si no tienes información específica, indícalo claramente y sugiere alternativas.
Si el usuario no menciona países, sugiere 2-3 opciones viables según el tipo de producción.

Responde en español por defecto, a menos que el usuario escriba en otro idioma."""


def procesar_consulta(mensaje: str) -> str:
    """Procesa una consulta conversacional del usuario y genera un reporte."""
    
    # Paso 1: Extraer información del mensaje con Gemini
    prompt_extraccion = f"""Extrae la siguiente información del mensaje del usuario:

Mensaje: "{mensaje}"

Formato de respuesta (solo JSON, sin texto adicional):
{{
  "paises": ["pais1", "pais2"],
  "locacion": "tipo de locación (urbana, natural, interior, patrimonio, aérea)",
  "extras": número de extras (0 si no se menciona),
  "drones": true/false,
  "pirotecnia": true/false,
  "menores": true/false,
  "agua": true/false,
  "armas": true/false,
  "animales": true/false,
  "gruas": true/false,
  "nocturno": true/false,
  "presupuesto": presupuesto en USD (0 si no se menciona)
}}"""

    try:
        extraccion_json = gemini_generate(prompt_extraccion, "Eres un extractor de información. Responde solo con JSON válido.")
        # Limpiar el JSON si viene con markdown
        extraccion_json = extraccion_json.replace("```json", "").replace("```", "").strip()
        desglose = json.loads(extraccion_json)
    except:
        # Fallback: usar valores por defecto
        desglose = {
            "paises": ["Mexico", "Colombia"],
            "locacion": "urbana",
            "extras": 0,
            "drones": False,
            "pirotecnia": False,
            "menores": False,
            "agua": False,
            "armas": False,
            "animales": False,
            "gruas": False,
            "nocturno": False,
            "presupuesto": 0
        }

    # Asegurar que haya países
    if not desglose.get("paises"):
        desglose["paises"] = ["Mexico", "Colombia", "Spain"]

    # Paso 2: Investigar cada país
    investigaciones = []
    for pais in desglose["paises"]:
        elementos = []
        if desglose.get("drones"):
            elementos.append("drones")
        if desglose.get("pirotecnia"):
            elementos.append("pirotecnia")
        if desglose.get("menores"):
            elementos.append("menores")
        if desglose.get("agua"):
            elementos.append("agua")
        if desglose.get("armas"):
            elementos.append("armas")
        
        query_elementos = ", ".join(elementos) if elementos else "filmación general"
        query = f"film production permits {pais} {query_elementos} requirements costs 2025"
        
        try:
            resultados = parallel_search(query)
            contenidos = []
            for resultado in resultados.get("results", [])[:3]:
                url = resultado.get("url", "")
                if url:
                    extract = parallel_extract(url, query)
                    contenidos.append({
                        "url": url,
                        "titulo": resultado.get("title", ""),
                        "contenido": extract.get("results", [{}])[0].get("excerpts", [""])[0][:1500] if extract.get("results") else ""
                    })
            investigaciones.append({
                "pais": pais,
                "contenidos": contenidos
            })
        except:
            investigaciones.append({
                "pais": pais,
                "contenidos": []
            })

    # Paso 3: Generar reporte final con Gemini
    prompt_reporte = f"""Genera un reporte comparativo de producción cinematográfica.

CONSULTA ORIGINAL DEL USUARIO: "{mensaje}"

DESGLOSE DETECTADO:
- Países: {', '.join(desglose['paises'])}
- Locación: {desglose['locacion']}
- Extras: {desglose['extras']}
- Drones: {'Sí' if desglose['drones'] else 'No'}
- Pirotecnia: {'Sí' if desglose['pirotecnia'] else 'No'}
- Presupuesto: ${desglose['presupuesto']:,} USD

INFORMACIÓN INVESTIGADA:
"""

    for inv in investigaciones:
        prompt_reporte += f"\n--- {inv['pais']} ---\n"
        for contenido in inv.get("contenidos", []):
            prompt_reporte += f"Fuente: {contenido['titulo']}\nURL: {contenido['url']}\n{contenido['contenido'][:500]}\n\n"

    prompt_reporte += """
FORMATO DEL REPORTE:
1. Resumen ejecutivo (2-3 líneas)
2. Tabla comparativa con columnas: País | Costo Estimado | Tiempo | Requisitos Clave | Riesgo
3. Detalle por país con checklist accionable
4. Recomendación final

Sé conciso pero completo. Incluye los URLs de las fuentes cuando estén disponibles.
Si la información es limitada, indícalo y sugiere contactar autoridades locales."""

    reporte = gemini_generate(prompt_reporte, SYSTEM_PROMPT)
    
    return reporte


# --- API simple con Flask ---
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
        mensaje = data.get("message", "")
        
        if not mensaje:
            return jsonify({"success": False, "error": "Mensaje vacío"}), 400
        
        try:
            respuesta = procesar_consulta(mensaje)
            return jsonify({"success": True, "response": respuesta})
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
