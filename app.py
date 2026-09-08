import os
import uuid
from flask import Flask, render_template, request, send_file, after_this_request, flash, redirect, url_for
from PIL import Image

app = Flask(__name__)
app.config['SECRET_KEY'] = 'chave-secreta-conversor-2026'

# Pasta temporária para arquivos
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'bmp', 'heic'}

def arquivo_permitido(filename, extensoes_permitidas):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in extensoes_permitidas

@app.route('/')
def index():
    try:
        return render_template('index.html')
    except Exception as e:
        return f"Erro ao carregar o template index.html. Verifique se ele esta na pasta 'templates/'. Detalhes: {e}", 500

# Aceita tanto /converter quanto /converter-imagem-pdf para evitar divergência no HTML
@app.route('/converter', methods=['POST'])
@app.route('/converter-imagem-pdf', methods=['POST'])
def converter_imagem_pdf():
    if 'file' not in request.files:
        flash('Nenhum arquivo enviado.')
        return redirect(url_for('index'))

    file = request.files['file']

    if file.filename == '':
        flash('Nenhum arquivo selecionado.')
        return redirect(url_for('index'))

    if file and arquivo_permitido(file.filename, ALLOWED_IMAGE_EXTENSIONS):
        id_unico = str(uuid.uuid4())
        extensao = file.filename.rsplit('.', 1)[1].lower()
        
        caminho_entrada = os.path.join(UPLOAD_FOLDER, f"input_{id_unico}.{extensao}")
        caminho_saida = os.path.join(UPLOAD_FOLDER, f"output_{id_unico}.pdf")

        try:
            file.save(caminho_entrada)

            imagem = Image.open(caminho_entrada)
            imagem_rgb = imagem.convert('RGB')
            imagem_rgb.save(caminho_saida)
            imagem.close()

        except Exception as e:
            app.logger.error(f"Erro na conversão: {e}")
            if os.path.exists(caminho_entrada):
                os.remove(caminho_entrada)
            return f"Erro no processamento da imagem: {e}", 500

        finally:
            # EXCLUSÃO IMEDIATA 1: Apaga a imagem recebida
            if os.path.exists(caminho_entrada):
                try:
                    os.remove(caminho_entrada)
                except Exception as e:
                    app.logger.error(f"Erro ao deletar imagem de entrada: {e}")

        # EXCLUSÃO IMEDIATA 2: Apaga o PDF gerado após o download
        @after_this_request
        def apagar_pdf_gerado(response):
            try:
                if os.path.exists(caminho_saida):
                    os.remove(caminho_saida)
            except Exception as e:
                app.logger.error(f"Erro ao deletar PDF de saída: {e}")
            return response

        nome_download = f"{os.path.splitext(file.filename)[0]}.pdf"

        return send_file(
            caminho_saida,
            as_attachment=True,
            download_name=nome_download
        )

    flash('Formato de arquivo não suportado.')
    return redirect(url_for('index'))

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)