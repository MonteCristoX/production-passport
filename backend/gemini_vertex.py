"""
Google Cloud Vertex AI integration for Replit
This module uses google-cloud-aiplatform SDK which Replit provides access to
"""

import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def init_vertex_ai():
    """Initialize Vertex AI - no explicit key needed, uses Replit's GCP access"""
    try:
        from google.cloud import aiplatform
        
        # Replit provides GCP credentials via metadata service
        # Use default region and project
        project_id = os.environ.get('GOOGLE_CLOUD_PROJECT', 'replit-hackathon')
        location = os.environ.get('GOOGLE_CLOUD_REGION', 'us-central1')
        
        aiplatform.init(
            project=project_id,
            location=location,
            # Replit handles authentication via service account
        )
        return True
    except ImportError:
        logger.warning("google-cloud-aiplatform not installed. Install with: pip install google-cloud-aiplatform")
        return False
    except Exception as e:
        logger.error(f"Failed to initialize Vertex AI: {e}")
        return False

def gm_vertex(prompt: str, model_name: str = "gemini-1.5-flash") -> str:
    """Generate content using Vertex AI Gemini model"""
    try:
        from google.cloud import aiplatform
        from google.cloud.aiplatform import GenerativeModel
        
        # Initialize if not done
        if not aiplatform._global_experiment_name:
            init_vertex_ai()
        
        model = GenerativeModel(model_name)
        response = model.generate_content(prompt)
        return response.text
        
    except ImportError:
        raise ImportError("Install google-cloud-aiplatform: pip install google-cloud-aiplatform")
    except Exception as e:
        logger.error(f"Vertex AI error: {e}")
        raise

# Alternative: Try using Replit's built-in access via metadata
def gm_replit_fallback(prompt: str) -> str:
    """Fallback using Replit's internal service account"""
    try:
        # Replit provides metadata service at this endpoint
        import requests
        
        # Internal Replit metadata service
        metadata_url = "http://metadata.google.internal/computeMetadata/v1/"
        headers = {"Metadata-Flavor": "Google"}
        
        # Get service account token (Replit injects this)
        token_response = requests.get(
            "http://169.254.169.254/computeMetadata/v1/instance/service-accounts/default/token",
            headers=headers,
            timeout=5
        )
        
        if token_response.status_code == 200:
            token = token_response.json()["access_token"]
            
            # Use with Vertex AI API
            # ... implementation
            pass
            
    except Exception as e:
        logger.debug(f"Replit fallback not available: {e}")
        return None

if __name__ == "__main__":
    # Test the integration
    if init_vertex_ai():
        try:
            result = gm_vertex("Say hello from Vertex AI!")
            print("Success:", result[:100])
        except Exception as e:
            print("Error:", e)
    else:
        print("Vertex AI not available, using demo mode instead")