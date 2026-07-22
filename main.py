from datetime import datetime
from threading import Lock
from uuid import uuid4

from fastapi import BackgroundTasks, HTTPException
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


jobs = {}
jobs_lock = Lock()


class ChamadaRequest(BaseModel):
    id_chamada: str
    CodAtendimento: int
    PAS: int
    Atendente: str
    RecordingFile: str


def _agora_iso():
    return datetime.now().isoformat(timespec="seconds")


def _atualizar_job(job_id: str, **dados):
    with jobs_lock:
        job = jobs.get(job_id)
        if not job:
            return

        job.update(dados)
        job["atualizado_em"] = _agora_iso()


def _obter_job(job_id: str):
    with jobs_lock:
        job = jobs.get(job_id)
        if not job:
            return None

        return dict(job)


def _processar_nota_job(job_id: str, request: ChamadaRequest):
    print("\n========== JOB /api/gerar-nota ==========" , flush=True)
    print(f"job_id: {job_id}", flush=True)
    print(f"id_chamada: {request.id_chamada}", flush=True)
    print(f"CodAtendimento: {request.CodAtendimento}", flush=True)
    print(f"PAS: {request.PAS}", flush=True)
    print(f"Atendente: {request.Atendente}", flush=True)
    print(f"RecordingFile recebido: {request.RecordingFile}", flush=True)

    try:
        print("[1/4] Buscando áudio no Asterisk...", flush=True)
        _atualizar_job(job_id, status="processando", etapa="Buscando áudio no Asterisk")
        caminho_audio = services.buscar_audio_no_asterisk(request.RecordingFile)

        print(f"[2/4] Áudio local pronto: {caminho_audio}", flush=True)
        print("[3/4] Gerando nota de atendimento com IA...", flush=True)
        _atualizar_job(job_id, status="processando", etapa="Gerando nota de atendimento com IA")
        transcricao, nota_final = services.gerar_nota_de_atendimento(caminho_audio)

        _atualizar_job(job_id, status="processando", etapa="Salvando resultado")
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

        _atualizar_job(
            job_id,
            status="concluido",
            etapa="Concluído",
            id_chamada=request.id_chamada,
            nota_atendimento=nota_final,
            arquivos_salvos=arquivos_salvos,
        )
    except FileNotFoundError as e:
        print(f"ERRO 404: {e}", flush=True)
        _atualizar_job(job_id, status="erro", etapa="Erro", codigo_http=404, erro=str(e))
    except services.GeminiQuotaExceeded as e:
        print(f"ERRO 429: {e}", flush=True)
        _atualizar_job(job_id, status="erro", etapa="Erro", codigo_http=429, erro=str(e))
    except Exception as e:
        print(f"ERRO 500: {e}", flush=True)
        _atualizar_job(job_id, status="erro", etapa="Erro", codigo_http=500, erro=str(e))


@app.post("/api/gerar-nota", status_code=202)
def api_gerar_nota(request: ChamadaRequest, background_tasks: BackgroundTasks):
    print("\n========== NOVA REQUISIÇÃO /api/gerar-nota ==========" , flush=True)
    print(f"id_chamada: {request.id_chamada}", flush=True)
    print(f"CodAtendimento: {request.CodAtendimento}", flush=True)
    print(f"PAS: {request.PAS}", flush=True)
    print(f"Atendente: {request.Atendente}", flush=True)
    print(f"RecordingFile recebido: {request.RecordingFile}", flush=True)

    job_id = str(uuid4())
    agora = _agora_iso()

    with jobs_lock:
        jobs[job_id] = {
            "job_id": job_id,
            "status": "pendente",
            "etapa": "Aguardando processamento",
            "id_chamada": request.id_chamada,
            "cod_atendimento": request.CodAtendimento,
            "criado_em": agora,
            "atualizado_em": agora,
        }

    background_tasks.add_task(_processar_nota_job, job_id, request)

    return {
        "status": "processando",
        "job_id": job_id,
        "status_url": f"/api/gerar-nota/{job_id}",
    }


@app.get("/api/gerar-nota/{job_id}")
def api_status_gerar_nota(job_id: str):
    job = _obter_job(job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado.")

    return job
