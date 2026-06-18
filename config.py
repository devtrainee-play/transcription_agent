import os
from google import genai
from dotenv import load_dotenv

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

if not GOOGLE_API_KEY:
    raise ValueError("⚠️ Erro: Chave da API do Google não encontrada no arquivo .env!")

# Inicializa o cliente do Gemini que será reutilizado por outros arquivos
cliente_google = genai.Client(api_key=GOOGLE_API_KEY)