import zipfile
import io
import fitz  # Esta é a biblioteca PyMuPDF
import os
import uuid
import xml.etree.ElementTree as ET
import pandas as pd
import jinja2
from flask import Flask, render_template, request, send_file, after_this_request, flash, redirect, url_for, send_from_directory
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

# Rota para carregar a imagem do QR Code do Pix
@app.route('/pix-qr.png')
def serve_pix_qr():
    return send_from_directory(diretorio_atual, 'pix-qr.png')

# ---------------------------------------------------------
# 1. ROTA: IMAGENS PARA PDF
# ---------------------------------------------------------
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

# ---------------------------------------------------------
# 2. ROTA: PDF PARA WORD (.docx)
# ---------------------------------------------------------
@app.route('/pdf-para-word', methods=['POST'])
@app.route('/converter-pdf-word', methods=['POST'])
def converter_pdf_word():
    file = request.files.get('file')
    if not file or file.filename == '':
        flash('Nenhum arquivo PDF selecionado.')
        return redirect(url_for('index'))

    if not arquivo_permitido(file.filename, {'pdf'}):
        flash('Por favor, envie um arquivo .pdf válido.')
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
        return f"Erro no processamento do PDF: {e}", 500

    finally:
        if os.path.exists(caminho_entrada):
            try:
                os.remove(caminho_entrada)
            except Exception as e:
                app.logger.error(f"Erro ao apagar PDF temporário: {e}")

    @after_this_request
    def apagar_docx_gerado(response):
        try:
            if os.path.exists(caminho_saida):
                os.remove(caminho_saida)
        except Exception as e:
            app.logger.error(f"Erro ao apagar Word de saída: {e}")
        return response

    nome_download = f"{os.path.splitext(file.filename)[0]}.docx"
    return send_file(
        caminho_saida,
        as_attachment=True,
        download_name=nome_download
    )

# ---------------------------------------------------------
# 3. ROTA: XML PARA EXCEL (.xlsx)
# ---------------------------------------------------------
@app.route('/xml-para-excel', methods=['POST'])
@app.route('/converter-xml-xlsx', methods=['POST'])
def converter_xml_xlsx():
    file = request.files.get('file')
    if not file or file.filename == '':
        flash('Nenhum arquivo XML selecionado.')
        return redirect(url_for('index'))

    if not arquivo_permitido(file.filename, {'xml'}):
        flash('Por favor, envie um arquivo .xml válido.')
        return redirect(url_for('index'))

    id_unico = str(uuid.uuid4())
    caminho_entrada = os.path.join(UPLOAD_FOLDER, f"input_{id_unico}.xml")
    caminho_saida = os.path.join(UPLOAD_FOLDER, f"output_{id_unico}.xlsx")

    try:
        file.save(caminho_entrada)
        
        tree = ET.parse(caminho_entrada)
        root = tree.getroot()

        dados = []
        for elem in root:
            row = {}
            for child in elem:
                tag_limpa = child.tag.split('}')[-1] if '}' in child.tag else child.tag
                row[tag_limpa] = child.text
            if row:
                dados.append(row)

        if dados:
            df = pd.DataFrame(dados)
        else:
            df = pd.read_xml(caminho_entrada)

        df.to_excel(caminho_saida, index=False)

    except Exception as e:
        app.logger.error(f"Erro ao converter XML para Excel: {e}")
        return f"Erro no processamento do XML: {e}", 500

    finally:
        if os.path.exists(caminho_entrada):
            try:
                os.remove(caminho_entrada)
            except Exception as e:
                app.logger.error(f"Erro ao apagar XML temporário: {e}")

    @after_this_request
    def apagar_excel_gerado(response):
        try:
            if os.path.exists(caminho_saida):
                os.remove(caminho_saida)
        except Exception as e:
            app.logger.error(f"Erro ao apagar Excel de saída: {e}")
        return response

    nome_download = f"{os.path.splitext(file.filename)[0]}.xlsx"
    return send_file(
        caminho_saida,
        as_attachment=True,
        download_name=nome_download
    )
@app.route('/pdf-para-imagem', methods=['POST'])
def pdf_para_imagem():
    if 'file' not in request.files:
        return 'Nenhum arquivo enviado', 400
    
    file = request.files['file']
    if file.filename == '':
        return 'Nenhum arquivo selecionado', 400

    if file and file.filename.lower().endswith('.pdf'):
        try:
            pdf_document = fitz.open(stream=file.read(), filetype="pdf")
            memory_zip = io.BytesIO()
            
            with zipfile.ZipFile(memory_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
                for page_num in range(len(pdf_document)):
                    page = pdf_document.load_page(page_num)
                    pix = page.get_pixmap(dpi=150) # Qualidade 150 DPI
                    image_bytes = pix.tobytes("png")
                    zf.writestr(f"pagina_{page_num + 1}.png", image_bytes)
            
            memory_zip.seek(0)
            
            return send_file(
                memory_zip,
                mimetype='application/zip',
                as_attachment=True,
                download_name='imagens_extraidas.zip'
            )
        except Exception as e:
            print(f"Erro na conversão: {e}")
            return 'Erro ao processar o PDF.', 500
            
    return 'Formato inválido.', 400
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
