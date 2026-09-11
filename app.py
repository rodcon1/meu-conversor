import os
import uuid
import jinja2
from flask import Flask, render_template, request, send_file, after_this_request, flash, redirect, url_for
from PIL import Image

app = Flask(__name__)
app.config['SECRET_KEY'] = 'chave-secreta-conversor-2026'

# Configura o Flask para buscar páginas na raiz ou na pasta 'templates'
diretorio_atual = os.path.dirname(os.path.abspath(__file__))
app.jinja_loader = jinja2.ChoiceLoader([
    app.jinja_loader,
    jinja2.FileSystemLoader(diretorio_atual),
    jinja2.FileSystemLoader(os.path.join(diretorio_atual, 'templates')),
])

# Pasta temporária para uploads
UPLOAD_FOLDER = os.path.join(diretorio_atual, 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'bmp', 'heic'}

def arquivo_permitido(filename, extensoes_permitidas):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in extensoes_permitidas

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/politica')
def politica():
    return render_template('politica.html')

@app.route('/termos')
def termos():
    return render_template('termos.html')

@app.route('/converter', methods=['POST'])
@app.route('/converter-imagem-pdf', methods=['POST'])
def converter_imagem_pdf():
    if 'files' not in request.files and 'file' not in request.files:
        flash('Nenhum arquivo enviado.')
        return redirect(url_for('index'))

    files = request.files.getlist('files') or [request.files.get('file')]

    if not files or files[0].filename == '':
        flash('Nenhum arquivo selecionado.')
        return redirect(url_for('index'))

    id_unico = str(uuid.uuid4())
    caminho_saida = os.path.join(UPLOAD_FOLDER, f"output_{id_unico}.pdf")
    arquivos_temporarios = []

    try:
        imagens_pil = []
        for file in files:
            if file and arquivo_permitido(file.filename, ALLOWED_IMAGE_EXTENSIONS):
                extensao = file.filename.rsplit('.', 1)[1].lower()
                caminho_temp = os.path.join(UPLOAD_FOLDER, f"input_{uuid.uuid4()}.{extensao}")
                file.save(caminho_temp)
                arquivos_temporarios.append(caminho_temp)

                img = Image.open(caminho_temp)
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                imagens_pil.append(img)

        if not imagens_pil:
            flash('Nenhum arquivo de imagem válido foi enviado.')
            return redirect(url_for('index'))

        imagens_pil[0].save(caminho_saida, save_all=True, append_images=imagens_pil[1:])
        
        for img in imagens_pil:
            img.close()

    except Exception as e:
        app.logger.error(f"Erro na conversão: {e}")
        return f"Erro no processamento da imagem: {e}", 500

    finally:
        for caminho in arquivos_temporarios:
            if os.path.exists(caminho):
                try:
                    os.remove(caminho)
                except Exception as e:
                    app.logger.error(f"Erro ao deletar imagem temporária: {e}")

    @after_this_request
    def apagar_pdf_gerado(response):
        try:
            if os.path.exists(caminho_saida):
                os.remove(caminho_saida)
        except Exception as e:
            app.logger.error(f"Erro ao deletar PDF de saída: {e}")
        return response

    return send_file(
        caminho_saida,
        as_attachment=True,
        download_name="imagens_convertidas.pdf"
    )

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
