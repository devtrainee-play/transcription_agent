import os
from config import cliente_google
from agents import agente_suporte

def buscar_audio_no_asterisk(id_chamada: str) -> str:
    """
    Regra de negócio para localizar o arquivo físico gerado pela telefonia.
    Posteriormente, você integrará a busca real ao Asterisk aqui.
    """
    print(f"🔍 [Serviço] Localizando áudio da chamada {id_chamada}...")
    
    caminho_arquivo = "audio.mp3"  # Simulação local temporária
    
    if not os.path.exists(caminho_arquivo):
        raise FileNotFoundError(f"O arquivo de áudio para a chamada {id_chamada} não foi encontrado no servidor.")
        
    return caminho_arquivo


def gerar_nota_de_atendimento(caminho_do_audio: str) -> str:
    """
    Faz o upload do áudio para a infraestrutura do Google, aguarda a transcrição
    e aciona o Agente para estruturar as informações coletadas.
    """
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