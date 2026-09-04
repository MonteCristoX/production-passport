# Production Passport - Agentic Cinema Hackathon Submission

## Project Overview

Production Passport es un agente de IA que toma descripciones de producciones de filmación y genera automáticamente informes completos con requisitos de permisos, costos estimados, contactos de vendor, reglas de drones, y estimaciones de presupuesto para filmaciones internacionales.

## Features

- **Geocoding inverso automático**: Detecta la ubicación exacta (ciudad, estado, país) a partir de coordenadas o descripciones de texto
- **Búsqueda en tiempo real**: Usa Parallel Search API para encontrar requisitos de permisos actualizados, costos de crew, e información de vendor
- **Comparación de ubicaciones**: Compara múltiples ubicaciones al mismo tiempo (ej: California vs New York) con datos específicos por estado
- **Extracción de contactos**: Encuentra emails, teléfonos, y sitios web de film commissions y production services
- **Generación de reportes**: HTML informativos y DOCX descargables con toda la información
- **Modo demo**: Funciona sin API keys para demostraciones rápidas

## Tech Stack

- **Backend**: Flask + Python
- **Search**: Parallel AI Search API (v1/search)
- **AI**: Google Gemini via google-generativeai SDK
- **Export**: python-docx para archivos Word
- **Geocoding**: BigDataCloud API (gratuito, sin clave)

## Data Sources

- Parallel Search API: información de permisos, costos, vendors
- BigDataCloud: geocoding inverso por coordenadas
- Film commission websites: contactos y requisitos

## How It Works

1. El usuario ingresa una descripción de producción (ubicación, crew, extras, budget, drones)
2. El sistema detecta automáticamente la ubicación mediante geocoding
3. Parallel Search API busca información actualizada de permisos, costos, vendors
4. Google Gemini genera un reporte completo basado en los datos encontrados
5. El usuario puede descargar el reporte en formato DOCX

## Installation

```bash
cd backend
pip install -r requirements.txt
python agente.py
```

Luego abre http://localhost:8080 en tu navegador.

## Environment Variables

- `PARALLEL_API_KEY`: Parallel AI API key (para búsqueda en tiempo real)
- `GEMINI_API_KEY`: Google Gemini API key (para generación de reportes)

## Links

- **Project URL**: https://replit.com/@MonteCristoX/production-passport
- **Code Repository**: https://github.com/MonteCristoX/production-passport
- **Demo Video**: [Pending - to be uploaded]

## Learnings

- Integrar múltiples APIs (Parallel, Gemini, BigDataCloud) en un flujo de trabajo cohesivo requiere manejo cuidadoso de errores y timeouts
- Los datos en tiempo real de Parallel mejoran significativamente la utilidad del reporte vs datos pre-cargados
- El manejo de fallos con fallback a Demo mode asegura que la demo siempre funcione, incluso sin APIs configuradas
- La comparación entre múltiples ubicaciones necesita búsqueda paralela para cada estado/país
