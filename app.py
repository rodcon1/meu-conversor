import os
import uuid
from flask import Flask, render_template, request, send_file, after_this_request, flash, redirect, url_for
from PIL import Image

app = Flask(__name__)
app.config['SECRET_KEY'] = 'chave-secreta-conversor-2026'

# Garante que a pasta de uploads exista na inicialização
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Extensões de imagem suportadas
ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'bmp', 'heic'}

def arquivo_permitido(filename, extensoes_permitidas):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in extensoes_permitidas

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/converter-imagem-pdf', methods=['POST'])
def converter_imagem_pdf():
    # 1. Verifica se o arquivo foi enviado na requisição
    if 'file' not in request.files:
        flash('Nenhum arquivo enviado.')
        return redirect(url_for('index'))

    file = request.files['file']

    if file.filename == '':
        flash('Nenhum arquivo selecionado.')
        return redirect(url_for('index'))

    # 2. Processa o arquivo se for uma extensão válida
    if file and arquivo_permitido(file.filename, ALLOWED_IMAGE_EXTENSIONS):
        # Gera IDs únicos para evitar conflitos entre acessos simultâneos
        id_unico = str(uuid.uuid4())
        extensao = file.filename.rsplit('.', 1)[1].lower()
        
        caminho_entrada = os.path.join(UPLOAD_FOLDER, f"input_{id_unico}.{extensao}")
        caminho_saida = os.path.join(UPLOAD_FOLDER, f"output_{id_unico}.pdf")

        try:
            # Salva o arquivo enviado temporariamente
            file.save(caminho_entrada)

            # Converte a Imagem para PDF usando o Pillow
            imagem = Image.open(caminho_entrada)
            imagem_rgb = imagem.convert('RGB')
            imagem_rgb.save(caminho_saida)

        finally:
            # EXCLUSÃO IMEDIATA 1: Apaga a imagem recebida logo após gerar o PDF
            if os.path.exists(caminho_entrada):
                try:
                    os.remove(caminho_entrada)
                except Exception as e:
                    app.logger.error(f"Erro ao deletar imagem de entrada: {e}")

        # EXCLUSÃO IMEDIATA 2: Apaga o PDF gerado assim que o download terminar
        @after_this_request
        def apagar_pdf_gerado(response):
            try:
                if os.path.exists(caminho_saida):
                    os.remove(caminho_saida)
            except Exception as e:
                app.logger.error(f"Erro ao deletar PDF de saída: {e}")
            return response

        # Define o nome original do arquivo com final .pdf para o usuário baixar
        nome_download = f"{os.path.splitext(file.filename)[0]}.pdf"

        # Envia o arquivo final para download
        return send_file(
            caminho_saida,
            as_attachment=True,
            download_name=nome_download
        )

    flash('Formato de arquivo não suportado.')
    return redirect(url_for('index'))

if __name__ == '__main__':
    # Configuração de porta para execução local e no Render
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)