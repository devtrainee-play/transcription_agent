import os
import posixpath
import re
import time
from datetime import datetime

import paramiko

from config import cliente_google
from agents import agente_suporte

LOCAL_DIR = "./downloads"
ATENDIMENTOS_DIR = "./atendimentos"
ASTERISK_HOST = os.getenv("ASTERISK_HOST")
ASTERISK_PORT = int(os.getenv("ASTERISK_PORT", "22"))
ASTERISK_USER = os.getenv("ASTERISK_USER")
ASTERISK_PASSWORD = os.getenv("ASTERISK_PASSWORD")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_MAX_TENTATIVAS = int(os.getenv("GEMINI_MAX_TENTATIVAS", "3"))
PROMPT_TRANSCRICAO = """
Você está transcrevendo uma ligação telefônica de suporte técnico em português do Brasil.

Regras obrigatórias:
- Transcreva apenas o que conseguir ouvir com segurança.
- Não invente palavras, nomes, números, senhas, sistemas ou conclusões.
- Quando não entender um trecho, escreva [inaudível].
- Preserve números falados, IDs, senhas, horários, nomes de sistemas e nomes de pessoas.
- Identifique os interlocutores como Atendente e Cliente quando for possível perceber.
- Não resuma. Faça uma transcrição literal.
- Não corrija tecnicamente o que foi dito.
- Mantenha a ordem cronológica da conversa.
""".strip()

class GeminiQuotaExceeded(Exception):
    pass


def _erro_temporario_gemini(erro: Exception) -> bool:
    mensagem = str(erro).lower()
    return "503" in mensagem or "unavailable" in mensagem or "high demand" in mensagem


def _erro_cota_gemini(erro: Exception) -> bool:
    mensagem = str(erro).lower()
    return "429" in mensagem or "resource_exhausted" in mensagem or "quota" in mensagem


def _conteudo_indica_cota_gemini(conteudo: str) -> bool:
    mensagem = (conteudo or "").lower()
    return "429" in mensagem and ("resource_exhausted" in mensagem or "quota" in mensagem)


def _normalizar_nome_pasta(valor: str, padrao: str) -> str:
    valor = (valor or "").strip() or padrao
    valor = re.sub(r'[\\/:*?"<>|]', "-", valor)
    valor = re.sub(r"\s+", " ", valor)
    return valor.strip(" .") or padrao


def buscar_audio_no_asterisk(recording_file: str) -> str:
    print("[SFTP] Validando caminho remoto recebido...", flush=True)

    if not recording_file or not recording_file.strip():
        raise FileNotFoundError("O caminho da gravação não foi informado.")

    if not ASTERISK_HOST or not ASTERISK_USER or not ASTERISK_PASSWORD:
        raise Exception("Configuração do Asterisk incompleta. Defina ASTERISK_HOST, ASTERISK_USER e ASTERISK_PASSWORD no arquivo .env.")

    remote_path = recording_file.strip().replace("\\", "/")
    filename = posixpath.basename(remote_path)

    print(f"[SFTP] Host: {ASTERISK_HOST}:{ASTERISK_PORT}", flush=True)
    print(f"[SFTP] Usuário: {ASTERISK_USER}", flush=True)
    print(f"[SFTP] Caminho remoto: {remote_path}", flush=True)
    print(f"[SFTP] Nome do arquivo: {filename}", flush=True)

    if not filename:
        raise FileNotFoundError(f"Caminho de gravação inválido: {recording_file}")

    os.makedirs(LOCAL_DIR, exist_ok=True)
    local_path = os.path.join(LOCAL_DIR, filename)

    print(f"[SFTP] Pasta local: {os.path.abspath(LOCAL_DIR)}", flush=True)
    print(f"[SFTP] Caminho local: {os.path.abspath(local_path)}", flush=True)

    if os.path.exists(local_path):
        print(f"[SFTP] Áudio já baixado, reutilizando: {local_path}", flush=True)
        return local_path

    print("[SFTP] Conectando ao Asterisk...", flush=True)

    transport = None
    sftp = None

    try:
        transport = paramiko.Transport((ASTERISK_HOST, ASTERISK_PORT))
        transport.connect(username=ASTERISK_USER, password=ASTERISK_PASSWORD)
        sftp = paramiko.SFTPClient.from_transport(transport)

        print("[SFTP] Conectado com sucesso.", flush=True)
        print("[SFTP] Verificando se o arquivo existe no servidor...", flush=True)
        sftp.stat(remote_path)

        print("[SFTP] Baixando arquivo de áudio...", flush=True)
        sftp.get(remote_path, local_path)

        print(f"[SFTP] Áudio baixado para: {local_path}", flush=True)
        return local_path
    except FileNotFoundError:
        raise FileNotFoundError(f"Arquivo de áudio não encontrado no Asterisk: {remote_path}")
    except PermissionError:
        raise PermissionError(f"Sem permissão para acessar o áudio no Asterisk: {remote_path}")
    except Exception as e:
        raise Exception(f"Falha ao baixar áudio do Asterisk via SFTP: {e}")
    finally:
        if sftp:
            sftp.close()
        if transport:
            transport.close()
        print("[SFTP] Conexão encerrada.", flush=True)


def gerar_nota_de_atendimento(caminho_do_audio: str) -> tuple[str, str]:
   
    print(f"[IA] Arquivo que será enviado ao Gemini: {os.path.abspath(caminho_do_audio)}", flush=True)
    print("[IA] Enviando áudio para o Google Gemini...", flush=True)

    texto_bruto = None
    ultimo_erro = None

    for tentativa in range(1, GEMINI_MAX_TENTATIVAS + 1):
        try:
            print(f"[IA] Tentativa {tentativa}/{GEMINI_MAX_TENTATIVAS}: upload do áudio...", flush=True)
            arquivo_audio = cliente_google.files.upload(file=caminho_do_audio)
            print(f"[IA] Tentativa {tentativa}/{GEMINI_MAX_TENTATIVAS}: solicitando transcrição no modelo {GEMINI_MODEL}...", flush=True)

            resposta_transcricao = cliente_google.models.generate_content(
                model=GEMINI_MODEL,
                contents=[arquivo_audio, PROMPT_TRANSCRICAO]
            )
            texto_bruto = resposta_transcricao.text
            print("[IA] Transcrição bruta concluída.", flush=True)
            print("========== TRANSCRIÇÃO BRUTA ==========" , flush=True)
            print(texto_bruto, flush=True)
            print("=======================================", flush=True)
            break
        except Exception as e:
            ultimo_erro = e
            print(f"[IA] Falha na tentativa {tentativa}/{GEMINI_MAX_TENTATIVAS}: {e}", flush=True)

            if _erro_cota_gemini(e):
                raise GeminiQuotaExceeded("Cota diária do Gemini esgotada. Aguarde a liberação da cota ou ajuste o plano/chave da API.")

            if tentativa == GEMINI_MAX_TENTATIVAS or not _erro_temporario_gemini(e):
                break

            segundos = tentativa * 3
            print(f"[IA] Erro temporário no Gemini. Nova tentativa em {segundos} segundos...", flush=True)
            time.sleep(segundos)

    if texto_bruto is None:
        if ultimo_erro and _erro_temporario_gemini(ultimo_erro):
            raise Exception("Gemini temporariamente indisponível por alta demanda. Tente novamente em alguns minutos.")

        if ultimo_erro and _erro_cota_gemini(ultimo_erro):
            raise GeminiQuotaExceeded("Cota diária do Gemini esgotada. Aguarde a liberação da cota ou ajuste o plano/chave da API.")

        raise Exception(f"Falha na comunicação com o provedor de IA: {ultimo_erro}")

    print("[AGENTE] Estruturando nota técnica...", flush=True)
    resposta = None
    ultimo_erro = None

    for tentativa in range(1, GEMINI_MAX_TENTATIVAS + 1):
        try:
            print(f"[AGENTE] Tentativa {tentativa}/{GEMINI_MAX_TENTATIVAS}: gerando nota...", flush=True)
            resposta = agente_suporte.run(
                "Crie a nota de atendimento com base nesta transcrição. "
                "Limpe vícios de linguagem e organize as ideias, mas não invente informações ausentes. "
                f"Transcrição: {texto_bruto}"
            )

            if _conteudo_indica_cota_gemini(resposta.content):
                raise GeminiQuotaExceeded("Cota diária do Gemini esgotada. Aguarde a liberação da cota ou ajuste o plano/chave da API.")

            break
        except Exception as e:
            ultimo_erro = e
            print(f"[AGENTE] Falha na tentativa {tentativa}/{GEMINI_MAX_TENTATIVAS}: {e}", flush=True)

            if _erro_cota_gemini(e):
                raise GeminiQuotaExceeded("Cota diária do Gemini esgotada. Aguarde a liberação da cota ou ajuste o plano/chave da API.")

            if tentativa == GEMINI_MAX_TENTATIVAS or not _erro_temporario_gemini(e):
                break

            segundos = tentativa * 3
            print(f"[AGENTE] Erro temporário no Gemini. Nova tentativa em {segundos} segundos...", flush=True)
            time.sleep(segundos)

    if resposta is None:
        if ultimo_erro and _erro_temporario_gemini(ultimo_erro):
            raise Exception("Gemini temporariamente indisponível por alta demanda. Tente novamente em alguns minutos.")

        if ultimo_erro and _erro_cota_gemini(ultimo_erro):
            raise GeminiQuotaExceeded("Cota diária do Gemini esgotada. Aguarde a liberação da cota ou ajuste o plano/chave da API.")

        raise Exception(f"Falha ao estruturar nota técnica com o agente: {ultimo_erro}")

    print("[AGENTE] Nota técnica estruturada.", flush=True)
    
    return texto_bruto, resposta.content


def salvar_resultado_atendimento(atendente: str, pas: int, cod_atendimento: int, transcricao: str, nota: str) -> dict:
    atendente_pasta = _normalizar_nome_pasta(atendente, "Atendente nao informado")
    dia_pasta = datetime.now().strftime("%Y-%m-%d")
    pas_pasta = _normalizar_nome_pasta(str(pas), "PAS nao informado")

    pasta_destino = os.path.join(ATENDIMENTOS_DIR, atendente_pasta, dia_pasta, pas_pasta)
    os.makedirs(pasta_destino, exist_ok=True)

    arquivo_transcricao = os.path.join(pasta_destino, f"{cod_atendimento}_transcricao.txt")
    arquivo_nota = os.path.join(pasta_destino, f"{cod_atendimento}_nota_atendimento.txt")

    with open(arquivo_transcricao, "w", encoding="utf-8") as arquivo:
        arquivo.write(transcricao or "")

    with open(arquivo_nota, "w", encoding="utf-8") as arquivo:
        arquivo.write(nota or "")

    print(f"[ARQUIVOS] Transcrição salva em: {os.path.abspath(arquivo_transcricao)}", flush=True)
    print(f"[ARQUIVOS] Nota salva em: {os.path.abspath(arquivo_nota)}", flush=True)

    return {
        "pasta": os.path.abspath(pasta_destino),
        "transcricao": os.path.abspath(arquivo_transcricao),
        "nota_atendimento": os.path.abspath(arquivo_nota),
    }
