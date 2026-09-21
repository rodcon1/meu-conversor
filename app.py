import os
import uuid
import zipfile
import io
import xml.etree.ElementTree as ET
import pandas as pd
import jinja2
import pymupdf  # PyMuPDF
from pdf2docx import Converter 
from flask import Flask, render_template, request, send_file, after_this_request, flash, redirect, url_for, send_from_directory
from PIL import Image

# ---------------------------------------------------------
# 1. INICIALIZAÇÃO DO APLICATIVO FLASK
# ---------------------------------------------------------
app = Flask(__name__)
app.config['SECRET_KEY'] = 'chave-secreta-conversor-2026'

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

# ---------------------------------------------------------
# ROTAS PRINCIPAIS E INSTITUCIONAIS
# ---------------------------------------------------------
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/politica')
def politica():
    return render_template('politica.html')

@app.route('/termos')
def termos():
    return render_template('termos.html')

@app.route('/pix-qr.png')
def serve_pix_qr():
    return send_from_directory(diretorio_atual, 'pix-qr.png')

# ---------------------------------------------------------
# ROTAS DE PÁGINAS DEDICADAS (SEO HÍBRIDO)
# ---------------------------------------------------------
@app.route('/xml-para-excel-online', methods=['GET'])
def pagina_xml_excel():
    return render_template('index.html', ferramenta_ativa='xml-excel')

@app.route('/unir-pdf-online', methods=['GET'])
def pagina_unir_pdf():
    return render_template('index.html', ferramenta_ativa='unir-pdf')

@app.route('/imagem-para-pdf-online', methods=['GET'])
def pagina_imagem_pdf():
    return render_template('index.html', ferramenta_ativa='imagem-pdf')

@app.route('/pdf-para-imagem-online', methods=['GET'])
def pagina_pdf_imagem():
    return render_template('index.html', ferramenta_ativa='pdf-imagem')

@app.route('/comprimir-pdf-online', methods=['GET'])
def pagina_comprimir_pdf():
    return render_template('index.html', ferramenta_ativa='comprimir-pdf')

@app.route('/xml-para-pdf-online', methods=['GET'])
def pagina_xml_pdf():
    return render_template('index.html', ferramenta_ativa='xml-pdf')

# ---------------------------------------------------------
# 1. ROTA DE PROCESSAMENTO: UNIR PDFS
# ---------------------------------------------------------
@app.route('/unir-pdf', methods=['POST'])
def unir_pdf():
    uploaded_files = request.files.getlist("files")
    
    merged_pdf = pymupdf.open()
    
    for file in uploaded_files:
        if file and file.filename.lower().endswith('.pdf'):
            file_bytes = file.read()
            doc = pymupdf.open(stream=file_bytes, filetype="pdf")
            merged_pdf.insert_pdf(doc)
            
    output_filename = f"unido_{uuid.uuid4().hex}.pdf"
    output_path = os.path.join(UPLOAD_FOLDER, output_filename)
    merged_pdf.save(output_path)
    merged_pdf.close()
    
    @after_this_request
    def apagar_pdf_unido(response):
        try:
            if os.path.exists(output_path):
                os.remove(output_path)
        except Exception as e:
            app.logger.error(f"Erro ao deletar PDF unido: {e}")
        return response

    return send_file(output_path, as_attachment=True, download_name="documentos_unidos.pdf")

# ---------------------------------------------------------
# 2. ROTA DE PROCESSAMENTO: IMAGENS PARA PDF
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
# 3. ROTA DE PROCESSAMENTO: PDF PARA WORD (.docx)
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
# 4. ROTA DE PROCESSAMENTO: XML PARA EXCEL (.xlsx)
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

# ---------------------------------------------------------
# 5. ROTA DE PROCESSAMENTO: PDF PARA IMAGEM (.zip)
# ---------------------------------------------------------
@app.route('/pdf-para-imagem', methods=['POST'])
def pdf_para_imagem():
    if 'file' not in request.files:
        return 'Nenhum arquivo enviado', 400
    
    file = request.files['file']
    if file.filename == '':
        return 'Nenhum arquivo selecionado', 400

    if file and file.filename.lower().endswith('.pdf'):
        try:
            pdf_document = pymupdf.open(stream=file.read(), filetype="pdf")
            memory_zip = io.BytesIO()
            
            with zipfile.ZipFile(memory_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
                for page_num in range(len(pdf_document)):
                    page = pdf_document.load_page(page_num)
                    pix = page.get_pixmap(dpi=150)
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
            app.logger.error(f"Erro na conversão: {e}")
            return 'Erro ao processar o PDF.', 500
            
    return 'Formato inválido.', 400

# ---------------------------------------------------------
# 6. ROTA DE PROCESSAMENTO: COMPRIMIR PDF
# ---------------------------------------------------------
@app.route('/comprimir-pdf', methods=['POST'])
def comprimir_pdf():
    file = request.files.get('file')
    if not file or file.filename == '':
        return 'Nenhum arquivo selecionado', 400

    if file and file.filename.lower().endswith('.pdf'):
        try:
            doc = pymupdf.open(stream=file.read(), filetype="pdf")
            memory_pdf = io.BytesIO()
            
            doc.save(memory_pdf, deflate=True, garbage=4, clean=True)
            doc.close()
            memory_pdf.seek(0)

            nome_saida = f"comprimido_{os.path.splitext(file.filename)[0]}.pdf"
            return send_file(
                memory_pdf,
                mimetype='application/pdf',
                as_attachment=True,
                download_name=nome_saida
            )
        except Exception as e:
            app.logger.error(f"Erro ao comprimir PDF: {e}")
            return 'Erro ao comprimir o PDF.', 500

    return 'Formato inválido.', 400

# ---------------------------------------------------------
# 7. ROTA DE PROCESSAMENTO: XML PARA PDF (LAYOUT ESTRUTURADO)
# ---------------------------------------------------------
@app.route('/xml-para-pdf', methods=['POST'])
def xml_para_pdf():
    file = request.files.get('file')
    if not file or file.filename == '':
        return 'Nenhum arquivo selecionado', 400

    if file and file.filename.lower().endswith('.xml'):
        try:
            tree = ET.parse(file)
            root = tree.getroot()

            # Extrai textos ignorando o prefixo do namespace
            def get_text(tag_name):
                for elem in root.iter():
                    if elem.tag.endswith(tag_name):
                        return elem.text
                return "N/A"

            def get_all(tag_name):
                return [elem.text for elem in root.iter() if elem.tag.endswith(tag_name)]

            # Dados básicos
            nnf = get_text('nNF')
            dhemi = get_text('dhEmi')
            natop = get_text('natOp')
            vnf = get_text('vNF')

            # Entidades (Geralmente índice 0 é Emitente e 1 é Destinatário na NFe)
            cnpjs = get_all('CNPJ')
            nomes = get_all('xNome')
            emit_nome = nomes[0] if len(nomes) > 0 else "N/A"
            emit_cnpj = cnpjs[0] if len(cnpjs) > 0 else "N/A"
            dest_nome = nomes[1] if len(nomes) > 1 else "N/A"
            dest_cnpj = cnpjs[1] if len(cnpjs) > 1 else "N/A"

            # Produtos (Buscando pelos nós de detalhes da nota 'det')
            produtos = []
            for det in root.iter():
                if det.tag.endswith('det'):
                    prod = {}
                    for child in det.iter():
                        if child.tag.endswith('xProd'): prod['nome'] = child.text
                        elif child.tag.endswith('qCom'): prod['qtd'] = child.text
                        elif child.tag.endswith('vUnCom'): prod['unid'] = child.text
                        elif child.tag.endswith('vProd'): prod['total'] = child.text
                    if prod:
                        produtos.append(prod)

            # Inicia o desenho do PDF com PyMuPDF
            doc = pymupdf.open()
            page = doc.new_page()
            margin = 40
            y = margin

            # Função auxiliar para desenhar caixas (Boxes) do DANFE
            def draw_box(title, lines, current_y):
                page.insert_text((margin, current_y), title, fontsize=11, fontname="helv-bo")
                current_y += 15
                
                box_height = len(lines) * 15 + 10
                rect = pymupdf.Rect(margin, current_y, 595 - margin, current_y + box_height)
                page.draw_rect(rect, color=(0.7, 0.7, 0.7), width=1)
                
                text_y = current_y + 12
                for line in lines:
                    page.insert_text((margin + 10, text_y), line, fontsize=10, fontname="helv")
                    text_y += 15
                return current_y + box_height + 20

            # Cabeçalho
            page.insert_text((margin, y), "DANFE SIMPLIFICADO", fontsize=16, fontname="helv-bo")
            y += 30

            y = draw_box("DADOS DA NOTA FISCAL", [
                f"Número: {nnf}",
                f"Emissão: {dhemi}",
                f"Natureza: {natop}"
            ], y)

            y = draw_box("EMITENTE", [
                f"Razão Social: {emit_nome}",
                f"CNPJ: {emit_cnpj}"
            ], y)

            y = draw_box("DESTINATÁRIO", [
                f"Razão Social: {dest_nome}",
                f"CNPJ: {dest_cnpj}"
            ], y)

            # Cabeçalho de Produtos
            page.insert_text((margin, y), "PRODUTOS", fontsize=11, fontname="helv-bo")
            y += 15
            page.insert_text((margin, y), "Descrição", fontsize=9, fontname="helv-bo")
            page.insert_text((margin + 300, y), "Qtd", fontsize=9, fontname="helv-bo")
            page.insert_text((margin + 350, y), "V. Unid", fontsize=9, fontname="helv-bo")
            page.insert_text((margin + 450, y), "V. Total", fontsize=9, fontname="helv-bo")
            y += 15

            # Lista de Produtos
            for p in produtos:
                nome_formatado = p.get('nome', '')[:50] # Limita tamanho do nome
                page.insert_text((margin, y), nome_formatado, fontsize=9, fontname="helv")
                page.insert_text((margin + 300, y), p.get('qtd', ''), fontsize=9, fontname="helv")
                page.insert_text((margin + 350, y), f"R$ {p.get('unid', '')}", fontsize=9, fontname="helv")
                page.insert_text((margin + 450, y), f"R$ {p.get('total', '')}", fontsize=9, fontname="helv")
                y += 15
                
                # Quebra de página se a nota tiver muitos itens
                if y > 750:
                    page = doc.new_page()
                    y = margin

            y += 15
            y = draw_box("TOTAIS", [
                f"Valor Total da Nota: R$ {vnf}"
            ], y)

            # Salva o arquivo na memória e envia
            memory_pdf = io.BytesIO()
            doc.save(memory_pdf)
            doc.close()
            memory_pdf.seek(0)

            nome_saida = f"DANFE_Simplificado_{os.path.splitext(file.filename)[0]}.pdf"
            return send_file(
                memory_pdf,
                mimetype='application/pdf',
                as_attachment=True,
                download_name=nome_saida
            )

        except Exception as e:
            app.logger.error(f"Erro ao converter XML para PDF: {e}")
            return 'Erro ao processar a estrutura do XML.', 500

    return 'Formato inválido. Envie um arquivo XML.', 400

# ---------------------------------------------------------
# ROTAS DE SEO
# ---------------------------------------------------------
@app.route('/sitemap.xml')
def sitemap():
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <url>
        <loc>https://meuconversorpdf.com.br/</loc>
        <changefreq>weekly</changefreq>
        <priority>1.0</priority>
    </url>
    <url>
        <loc>https://meuconversorpdf.com.br/xml-para-excel-online</loc>
        <changefreq>weekly</changefreq>
        <priority>0.9</priority>
    </url>
    <url>
        <loc>https://meuconversorpdf.com.br/unir-pdf-online</loc>
        <changefreq>weekly</changefreq>
        <priority>0.9</priority>
    </url>
    <url>
        <loc>https://meuconversorpdf.com.br/imagem-para-pdf-online</loc>
        <changefreq>weekly</changefreq>
        <priority>0.8</priority>
    </url>
    <url>
        <loc>https://meuconversorpdf.com.br/pdf-para-imagem-online</loc>
        <changefreq>weekly</changefreq>
        <priority>0.8</priority>
    </url>
    <url>
        <loc>https://meuconversorpdf.com.br/comprimir-pdf-online</loc>
        <changefreq>weekly</changefreq>
        <priority>0.9</priority>
    </url>
    <url>
        <loc>https://meuconversorpdf.com.br/xml-para-pdf-online</loc>
        <changefreq>weekly</changefreq>
        <priority>0.8</priority>
    </url>
</urlset>"""
    return xml, 200, {'Content-Type': 'application/xml'}

@app.route('/robots.txt')
def robots():
    txt = """User-agent: *
Allow: /

Sitemap: https://meuconversorpdf.com.br/sitemap.xml"""
    return txt, 200, {'Content-Type': 'text/plain'}

# ---------------------------------------------------------
# INICIALIZAÇÃO DO SERVIDOR
# ---------------------------------------------------------
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
