from fastapi import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from agno.os import AgentOS
from agents import agente_suporte
import services

# 1. Usamos a aplicação nativa do Agno como o "motor" principal
agent_os = AgentOS(agents=[agente_suporte])
app = agent_os.get_app()

# 2. Mantemos a liberação de segurança (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 3. Modelo de dados esperado do Monitor Plantão
class ChamadaRequest(BaseModel):
    id_chamada: str

# 4. Nosso ENDPOINT PÚBLICO para os outros sistemas
@app.post("/api/gerar-nota")
def api_gerar_nota(request: ChamadaRequest):
    try:
        caminho_audio = services.buscar_audio_no_asterisk(request.id_chamada)
        nota_final = services.gerar_nota_de_atendimento(caminho_audio)
        
        return {
            "status": "sucesso",
            "id_chamada": request.id_chamada,
            "nota_atendimento": nota_final
        }
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))