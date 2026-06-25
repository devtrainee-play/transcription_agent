from fastapi import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from agno.os import AgentOS
from agents import agente_suporte
import services

agent_os = AgentOS(agents=[agente_suporte])
app = agent_os.get_app()


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChamadaRequest(BaseModel):
    id_chamada: str
    CodAtendimento: int
    PAS: int
    RecordingFile: str


@app.post("/api/gerar-nota")
def api_gerar_nota(request: ChamadaRequest):
    try:
        caminho_audio = services.buscar_audio_no_asterisk(request.RecordingFile)
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
