import os
import posixpath

import paramiko

from config import cliente_google
from agents import agente_suporte

try:
    from ftp_asterisk import HOST as DEFAULT_ASTERISK_HOST
    from ftp_asterisk import PASSWORD as DEFAULT_ASTERISK_PASSWORD
    from ftp_asterisk import PORT as DEFAULT_ASTERISK_PORT
    from ftp_asterisk import USER as DEFAULT_ASTERISK_USER
except ImportError:
    DEFAULT_ASTERISK_HOST = "192.168.0.2"
    DEFAULT_ASTERISK_PORT = 22
    DEFAULT_ASTERISK_USER = "root"
    DEFAULT_ASTERISK_PASSWORD = None

LOCAL_DIR = "./downloads"
ASTERISK_HOST = os.getenv("ASTERISK_HOST", DEFAULT_ASTERISK_HOST)
ASTERISK_PORT = int(os.getenv("ASTERISK_PORT", str(DEFAULT_ASTERISK_PORT)))
ASTERISK_USER = os.getenv("ASTERISK_USER", DEFAULT_ASTERISK_USER)
ASTERISK_PASSWORD = os.getenv("ASTERISK_PASSWORD", DEFAULT_ASTERISK_PASSWORD)


def buscar_audio_no_asterisk(recording_file: str) -> str:
    if not recording_file or not recording_file.strip():
        raise FileNotFoundError("O caminho da gravação não foi informado.")

    if not ASTERISK_PASSWORD:
        raise Exception("Senha do Asterisk não configurada. Defina ASTERISK_PASSWORD no arquivo .env.")

    remote_path = recording_file.strip().replace("\\", "/")
    filename = posixpath.basename(remote_path)

    if not filename:
        raise FileNotFoundError(f"Caminho de gravação inválido: {recording_file}")

    os.makedirs(LOCAL_DIR, exist_ok=True)
    local_path = os.path.join(LOCAL_DIR, filename)

    if os.path.exists(local_path):
        print(f"Áudio já baixado: {local_path}")
        return local_path

    print(f"Localizando áudio no Asterisk: {remote_path}")

    transport = None
    sftp = None

    try:
        transport = paramiko.Transport((ASTERISK_HOST, ASTERISK_PORT))
        transport.connect(username=ASTERISK_USER, password=ASTERISK_PASSWORD)
        sftp = paramiko.SFTPClient.from_transport(transport)

        sftp.stat(remote_path)
        sftp.get(remote_path, local_path)

        print(f"Áudio baixado para: {local_path}")
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


def gerar_nota_de_atendimento(caminho_do_audio: str) -> str:
   
    print("🎙️ [Serviço] Enviando áudio para o pipeline do Google Gemini...")
    try:
        arquivo_audio = cliente_google.files.upload(file=caminho_do_audio)
        resposta_transcricao = cliente_google.models.generate_content(
            model="gemini-2.5-flash",
            contents=[arquivo_audio, "Transcreva exatamente o que está sendo dito neste áudio."]
        )
        texto_bruto = resposta_transcricao.text
    except Exception as e:
        raise Exception(f"Falha na comunicação com o provedor de IA: {e}")

    print("✅ [Serviço] Transcrição concluída com sucesso! Estruturando nota técnica...")
    resposta = agente_suporte.run(f"Por favor, crie a nota de atendimento com base nesta transcrição: {texto_bruto}")
    
    return resposta.content
