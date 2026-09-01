# Production Passport 🎬

**Agente inteligente para investigación de producción cinematográfica internacional**

## Descripción

Production Passport es un agente de IA que investiga automáticamente requisitos de producción cinematográfica (permisos, incentivos fiscales, costos, restricciones) por país y genera un reporte comparativo accionable en minutos en lugar de semanas.

Construido para el [Agentic Cinema: The Blockbuster Hackathon](https://agentic-cinema.devpost.com/) - Track: **Parallel Web Systems**

## Demo

[URL del demo aquí]

## Cómo Funciona

1. **Input:** El usuario ingresa el desglose de producción (locación, equipo especial, extras, etc.)
2. **Investigación:** El agente usa Parallel Search API para buscar información en film commissions y fuentes oficiales
3. **Extracción:** Parallel Extract API extrae los detalles específicos de cada fuente
4. **Síntesis:** Gemini Enterprise razona sobre la información y genera un reporte comparativo
5. **Output:** Reporte con costos, tiempos, requisitos, riesgos y checklist accionable por país

## Stack Tecnológico

- **Google Cloud Gemini Enterprise** - Modelo de lenguaje (requerido por el hackathon)
- **Parallel Web Systems** - Search, Extract y Monitor APIs (partner track)
- **ADK (Agent Development Kit)** - Framework para construir el agente
- **Flask** - Backend API
- **Next.js + TailwindCSS** - Frontend (o HTML vanilla para versión mínima)

## Instalación

```bash
# Clonar repositorio
git clone https://github.com/tu-usuario/production-passport.git
cd production-passport

# Backend
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configurar variables de entorno
cp ../.env.example .env
# Editar .env con tus API keys

# Ejecutar
python agente.py
```

## Variables de Entorno

| Variable | Descripción |
|----------|-------------|
| `PARALLEL_API_KEY` | API key de Parallel Web Systems |
| `GEMINI_API_KEY` | API key de Google Cloud (Gemini) |

## Uso

1. Abrir http://localhost:8080
2. Llenar el formulario con el desglose de producción
3. Seleccionar países a comparar
4. Clic en "Investigar"
5. Esperar 30-60 segundos para el reporte

## API Endpoints

- `POST /api/investigar` - Genera reporte comparativo
- `GET /api/health` - Health check

## Contribuir

Este proyecto es parte de un hackathon. Para contribuir:

1. Fork el repositorio
2. Crea una rama (`git checkout -b feature/nueva-funcionalidad`)
3. Commit tus cambios (`git commit -m 'Agrega nueva funcionalidad'`)
4. Push a la rama (`git push origin feature/nueva-funcionalidad`)
5. Abre un Pull Request

## Licencia

MIT License - ver [LICENSE](LICENSE) para detalles

## Autor

**Johnny Aguirre (Ekrome)** - [LinkedIn](https://linkedin.com/in/tu-perfil)

## Agradecimientos

- Google Cloud por Gemini Enterprise
- Parallel Web Systems por las APIs de búsqueda
- Devpost por organizar el hackathon
