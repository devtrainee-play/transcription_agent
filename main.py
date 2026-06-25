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
    Atendente: str
    RecordingFile: str


@app.post("/api/gerar-nota")
def api_gerar_nota(request: ChamadaRequest):
    print("\n========== NOVA REQUISIÇÃO /api/gerar-nota ==========", flush=True)
    print(f"id_chamada: {request.id_chamada}", flush=True)
    print(f"CodAtendimento: {request.CodAtendimento}", flush=True)
    print(f"PAS: {request.PAS}", flush=True)
    print(f"Atendente: {request.Atendente}", flush=True)
    print(f"RecordingFile recebido: {request.RecordingFile}", flush=True)

    try:
        print("[1/4] Buscando áudio no Asterisk...", flush=True)
        caminho_audio = services.buscar_audio_no_asterisk(request.RecordingFile)

        print(f"[2/4] Áudio local pronto: {caminho_audio}", flush=True)
        print("[3/4] Gerando nota de atendimento com IA...", flush=True)
        transcricao, nota_final = services.gerar_nota_de_atendimento(caminho_audio)
        arquivos_salvos = services.salvar_resultado_atendimento(
            atendente=request.Atendente,
            pas=request.PAS,
            cod_atendimento=request.CodAtendimento,
            transcricao=transcricao,
            nota=nota_final,
        )

        print("[4/4] Nota gerada com sucesso.", flush=True)
        print("========== NOTA DE ATENDIMENTO ==========" , flush=True)
        print(nota_final, flush=True)
        print("=========================================\n", flush=True)
        
        return {
            "status": "sucesso",
            "id_chamada": request.id_chamada,
            "nota_atendimento": nota_final,
            "arquivos_salvos": arquivos_salvos
        }
    except FileNotFoundError as e:
        print(f"ERRO 404: {e}", flush=True)
        raise HTTPException(status_code=404, detail=str(e))
    except services.GeminiQuotaExceeded as e:
        print(f"ERRO 429: {e}", flush=True)
        raise HTTPException(status_code=429, detail=str(e))
    except Exception as e:
        print(f"ERRO 500: {e}", flush=True)
        raise HTTPException(status_code=500, detail=str(e))
