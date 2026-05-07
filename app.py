import os
from google import genai
from agno.agent import Agent
from agno.models.google import Gemini
from dotenv import load_dotenv

load_dotenv()

chave_google = os.getenv("GOOGLE_API_KEY")

if not chave_google:
    print("⚠️ Erro: Chave da API do Google não encontrada no arquivo .env!")
    exit()

cliente_google = genai.Client(api_key=chave_google)

def processar_ligacao(caminho_do_audio):
    print("🎙️ Enviando e transcrevendo o áudio no Google Gemini...")
    
    try:
        arquivo_audio = cliente_google.files.upload(file=caminho_do_audio)
        
        resposta_transcricao = cliente_google.models.generate_content(
            model="gemini-2.5-flash",
            contents=[arquivo_audio, "Transcreva exatamente o que está sendo dito neste áudio."]
        )
        texto_bruto = resposta_transcricao.text
        print("✅ Transcrição concluída! Iniciando o Agente para formatar a nota...\n")
    except Exception as e:
        print(f"Erro ao processar o áudio no Google: {e}")
        return

    agente_suporte = Agent(
        model=Gemini(id="gemini-2.5-flash"),
        description="Você é um especialista técnico em suporte a sistemas corporativos e comunicação.",
        instructions=[
            "Você receberá a transcrição bruta de uma ligação telefônica com um cliente.",
            "Sua tarefa é limpar os vícios de linguagem, organizar as ideias e gerar uma Nota de Atendimento.",
            "Formate a saída rigorosamente com os seguintes tópicos:",
            "1. **Motivo do Contato:** Qual foi o problema ou dúvida relatada?",
            "2. **Sistema Afetado:** Identifique se o problema ocorreu no MAKER, Commercial, Smart Manager, Logger ou outro software.",
            "3. **Diagnóstico / Ações Realizadas:** O que foi conversado, analisado ou configurado durante a ligação.",
            "4. **Próximos Passos:** O que ficou combinado de ser feito."
        ],
        markdown=True
    )

    resposta = agente_suporte.run(f"Por favor, crie a nota de atendimento com base nesta transcrição: {texto_bruto}")
    
    print("================ NOTA DE ATENDIMENTO ================\n")
    print(resposta.content)
    print("\n=====================================================")

if __name__ == "__main__":
    nome_do_arquivo = "audio.wav" 
    
    if os.path.exists(nome_do_arquivo):
        processar_ligacao(nome_do_arquivo)
    else:
        print(f"⚠️ Arquivo '{nome_do_arquivo}' não encontrado. Por favor, coloque um áudio na pasta do projeto.")