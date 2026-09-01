"""
Production Passport - Backend Agente
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


def parallel_search(query: str, max_results: int = 5) -> dict:
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
    
    # Google AI Studio usa v1beta con modelo gemini-2.0-flash
    url = f"{GEMINI_BASE_URL}/models/gemini-2.5-flash:generateContent"
    
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 2048
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
SYSTEM_PROMPT = """Eres un experto en producción cinematográfica internacional. 
Tu trabajo es investigar y comparar requisitos de producción (permisos, costos, incentivos fiscales, restricciones) 
para diferentes países.

Cuando recibas un desglose de producción, debes:
1. Identificar los requisitos específicos según el tipo de producción
2. Investigar por cada país solicitado
3. Generar un reporte comparativo claro y accionable

Siempre incluye:
- Costos estimados de permisos
- Tiempos de aprobación
- Requisitos específicos (drones, pirotecnia, menores, etc.)
- Links a fuentes oficiales cuando estén disponibles
- Un checklist accionable por país

Si no tienes información específica, indícalo claramente y sugiere alternativas."""


def investigar_pais(pais: str, desglose: dict) -> dict:
    """Investiga requisitos de producción para un país específico."""
    # Construir query de búsqueda
    elementos = []
    if desglose.get("drones"):
        elementos.append("permisos de drones")
    if desglose.get("pirotecnia"):
        elementos.append("permisos de pirotecnia")
    if desglose.get("menores"):
        elementos.append("requisitos para menores")
    if desglose.get("agua"):
        elementos.append("filmación en agua")
    if desglose.get("armas"):
        elementos.append("uso de armas")
    
    query_elementos = ", ".join(elementos) if elementos else "filmación general"
    
    query = f"film production permits {pais} {query_elementos} requirements costs 2025"
    
    # Buscar información
    resultados = parallel_search(query)
    
    # Extraer contenido de las primeras URLs
    contenidos = []
    for resultado in resultados.get("results", [])[:3]:
        url = resultado.get("url", "")
        if url:
            extract = parallel_extract(url, query)
            contenidos.append({
                "url": url,
                "titulo": resultado.get("title", ""),
                "contenido": extract.get("results", [{}])[0].get("excerpts", [""])[0][:2000] if extract.get("results") else ""
            })
    
    return {
        "pais": pais,
        "query": query,
        "contenidos": contenidos
    }


def generar_reporte(desglose: dict, paises: list) -> str:
    """Genera el reporte comparativo final."""
    
    # Investigar cada país
    investigaciones = []
    for pais in paises:
        inv = investigar_pais(pais, desglose)
        investigaciones.append(inv)
    
    # Construir prompt para Gemini
    prompt_usuario = f"""Genera un reporte comparativo de producción cinematográfica.

DESGLOSE DE PRODUCCIÓN:
- Locación: {desglose.get('locacion', 'No especificada')}
- Equipo especial: {desglose.get('equipo_especial', 'Ninguno')}
- Número de extras: {desglose.get('extras', 0)}
- Vestuario/arte: {desglose.get('vestuario', 'Normal')}
- Stunts/efectos: {desglose.get('stunts', 'Ninguno')}
- Presupuesto estimado: ${desglose.get('presupuesto', 0):,}

PAÍSES A COMPARAR: {', '.join(paises)}

INFORMACIÓN INVESTIGADA:
"""
    
    for inv in investigaciones:
        prompt_usuario += f"\n--- {inv['pais']} ---\n"
        for contenido in inv.get("contenidos", []):
            prompt_usuario += f"Fuente: {contenido['titulo']}\nURL: {contenido['url']}\n{contenido['contenido'][:500]}\n\n"
    
    prompt_usuario += """
FORMATO DEL REPORTE:
1. Resumen ejecutivo (2-3 líneas)
2. Tabla comparativa con columnas: País | Costo Estimado | Tiempo | Requisitos Clave | Riesgo
3. Detalle por país con checklist accionable
4. Recomendación final

Incluye los URLs de las fuentes cuando estén disponibles.
"""
    
    # Generar reporte con Gemini
    reporte = gemini_generate(prompt_usuario, SYSTEM_PROMPT)
    
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
    
    @app.route("/api/investigar", methods=["POST"])
    def investigar():
        data = request.json
        desglose = data.get("desglose", {})
        paises = data.get("paises", ["Mexico", "Colombia", "Spain"])
        
        try:
            reporte = generar_reporte(desglose, paises)
            return jsonify({"success": True, "reporte": reporte})
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
