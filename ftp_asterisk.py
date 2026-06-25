import os
import paramiko


HOST = "192.168.0.2"
PORT = 22

USER = "root"
PASSWORD = "#y2#QqiyjG9zjjA"

REMOTE_DIR = "/var/spool/asterisk/monitor/"
LOCAL_DIR = "./downloads"  # pasta local para salvar os arquivos baixados

#q-202-5531997336921-20260514-144153-1778780475.370050.wav

def main():
    os.makedirs(LOCAL_DIR, exist_ok=True)

    transport = None
    sftp = None

    try:
        print("Conectando via SFTP...")

        transport = paramiko.Transport((HOST, PORT))
        transport.connect(username=USER, password=PASSWORD)

        sftp = paramiko.SFTPClient.from_transport(transport)

        print("Conectado com sucesso.")
        print(f"Lendo diretório remoto: {REMOTE_DIR}")

        files = sftp.listdir(REMOTE_DIR)

        if not files:
            print("Nenhum arquivo encontrado.")
            return

        for filename in files:
            remote_path = f"{REMOTE_DIR}/{filename}"
            local_path = os.path.join(LOCAL_DIR, filename)

            print(f"Encontrado: {filename}")

            if filename.lower().endswith((".wav", ".mp3", ".gsm", ".ogg")):
                print(f"Baixando {filename}...")
                sftp.get(remote_path, local_path)
                print(f"Baixado para: {local_path}")

    except PermissionError:
        print("Erro de permissão. O usuário SSH não tem acesso à pasta do Asterisk.")

    except FileNotFoundError:
        print(f"Diretório não encontrado no servidor: {REMOTE_DIR}")

    except Exception as e:
        print("Erro geral:", e)

    finally:
        if sftp:
            sftp.close()

        if transport:
            transport.close()

        print("Conexão encerrada.")


if __name__ == "__main__":
    main()