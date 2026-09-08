import os
import uuid
import xml.etree.ElementTree as ET
import pandas as pd
from flask import Flask, render_template, request, send_file, after_this_request, flash, redirect, url_for
from PIL import Image

app = Flask(__name__)
app.config['SECRET_KEY'] = 'chave-secreta-conversor-2026'

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'bmp', 'heic'}

@app.route('/')
def index():
    try:
        return render_template('index.html')
    except Exception:
        caminho_raiz = os.path.join(os.path.dirname(__file__), 'index.html')
        if os.path.exists(caminho_raiz):
            return send_file(caminho_raiz)
        return "Erro: O arquivo index.html não foi encontrado.", 404

# 1. ROTA: IMAGEM PARA PDF
@app.route('/converter', methods=['POST'])
@app.route('/converter-imagem-pdf', methods=['POST'])
def converter_imagem_pdf():
    file = request.files.get('file')
    if not file or file.filename == '':
        return redirect(url_for('index'))

    id_unico = str(uuid.uuid4())
    extensao = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else 'png'
    caminho_entrada = os.path.join(UPLOAD_FOLDER, f"input_{id_unico}.{extensao}")
    caminho_saida = os.path.join(UPLOAD_FOLDER, f"output_{id_unico}.pdf")

    try:
        file.save(caminho_entrada)
        imagem = Image.open(caminho_entrada)
        imagem_rgb = imagem.convert('RGB')
        imagem_rgb.save(caminho_saida)
        imagem.close()
    except Exception as e:
        app.logger.error(f"Erro ao converter Imagem: {e}")
        return f"Erro na conversão da imagem: {e}", 500
    finally:
        if os.path.exists(caminho_entrada):
            os.remove(caminho_entrada)

    @after_this_request
    def apagar_gerado(response):
        if os.path.exists(caminho_saida):
            os.remove(caminho_saida)
        return response

    nome_download = f"{os.path.splitext(file.filename)[0]}.pdf"
    return send_file(caminho_saida, as_attachment=True, download_name=nome_download)

# 2. ROTA: PDF PARA WORD (.docx)
@app.route('/converter-pdf-word', methods=['POST'])
def converter_pdf_word():
    file = request.files.get('file')
    if not file or file.filename == '':
        return redirect(url_for('index'))

    id_unico = str(uuid.uuid4())
    caminho_entrada = os.path.join(UPLOAD_FOLDER, f"input_{id_unico}.pdf")
    caminho_saida = os.path.join(UPLOAD_FOLDER, f"output_{id_unico}.docx")

    try:
        file.save(caminho_entrada)
        from pdf2docx import Converter
        cv = Converter(caminho_entrada)
        cv.convert(caminho_saida, start=0, end=None)
        cv.close()
    except Exception as e:
        app.logger.error(f"Erro ao converter PDF para Word: {e}")
        return f"Erro na conversão do PDF: {e}", 500
    finally:
        if os.path.exists(caminho_entrada):
            os.remove(caminho_entrada)

    @after_this_request
    def apagar_gerado(response):
        if os.path.exists(caminho_saida):
            os.remove(caminho_saida)
        return response

    nome_download = f"{os.path.splitext(file.filename)[0]}.docx"
    return send_file(caminho_saida, as_attachment=True, download_name=nome_download)

# 3. ROTA: XML PARA EXCEL (.xlsx)
@app.route('/converter-xml-xlsx', methods=['POST'])
def converter_xml_xlsx():
    file = request.files.get('file')
    if not file or file.filename == '':
        return redirect(url_for('index'))

    id_unico = str(uuid.uuid4())
    caminho_entrada = os.path.join(UPLOAD_FOLDER, f"input_{id_unico}.xml")
    caminho_saida = os.path.join(UPLOAD_FOLDER, f"output_{id_unico}.xlsx")

    try:
        file.save(caminho_entrada)
        
        # Leitura simples do XML para DataFrame
        tree = ET.parse(caminho_entrada)
        root = tree.getroot()
        
        dados = []
        for elem in root:
            row = {}
            for child in elem:
                row[child.tag] = child.text
            if row:
                dados.append(row)

        df = pd.DataFrame(dados) if dados else pd.read_xml(caminho_entrada)
        df.to_excel(caminho_saida, index=False)

    except Exception as e:
        app.logger.error(f"Erro ao converter XML para Excel: {e}")
        return f"Erro no processamento do XML: {e}", 500
    finally:
        if os.path.exists(caminho_entrada):
            os.remove(caminho_entrada)

    @after_this_request
    def apagar_gerado(response):
        if os.path.exists(caminho_saida):
            os.remove(caminho_saida)
        return response

    nome_download = f"{os.path.splitext(file.filename)[0]}.xlsx"
    return send_file(caminho_saida, as_attachment=True, download_name=nome_download)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
