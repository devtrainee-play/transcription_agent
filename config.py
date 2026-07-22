import os
from google import genai
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
GEMINI_BACKEND = os.getenv("GEMINI_BACKEND", "api_key").strip().lower()
GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID")
GCP_LOCATION = os.getenv("GCP_LOCATION", "us-central1")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GOOGLE_APPLICATION_CREDENTIALS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

if GOOGLE_APPLICATION_CREDENTIALS and not os.path.isabs(GOOGLE_APPLICATION_CREDENTIALS):
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.path.join(BASE_DIR, GOOGLE_APPLICATION_CREDENTIALS)

if GEMINI_BACKEND == "vertex":
    if not GCP_PROJECT_ID:
        raise ValueError("⚠️ Erro: GCP_PROJECT_ID não encontrado no arquivo .env!")

    cliente_google = genai.Client(
        vertexai=True,
        project=GCP_PROJECT_ID,
        location=GCP_LOCATION,
    )
elif GEMINI_BACKEND == "api_key":
    if not GOOGLE_API_KEY:
        raise ValueError("⚠️ Erro: Chave da API do Google não encontrada no arquivo .env!")

    cliente_google = genai.Client(api_key=GOOGLE_API_KEY)
else:
    raise ValueError(f"⚠️ Erro: GEMINI_BACKEND inválido: {GEMINI_BACKEND}")
