import io
import os
import time
import uuid
import logging
import tempfile
import zipfile
import xml.etree.ElementTree as ET

import jinja2
import pandas as pd
import pymupdf  # PyMuPDF (manipulação e compressão de PDFs)
from flask import Flask, render_template, request, send_file, send_from_directory
from PIL import Image, ImageOps
from werkzeug.exceptions import HTTPException

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("conversor")

# ---------------------------------------------------------
# 1. MOTORES DE NOTA FISCAL (isolados: se um falhar, o site continua de pé)
# ---------------------------------------------------------
# IMPORTANTE: usamos "except Exception" (e não só ImportError) porque um erro
# de sintaxe ou de execução dentro de danfe.py / nfce.py derrubaria o app
# inteiro na inicialização. Aqui o erro é registrado no log e só a ferramenta
# afetada fica indisponível.
try:
    from danfe import gerar_danfe, DanfeError
    DANFE_ERRO_IMPORT = None
except Exception as _e:
    gerar_danfe = None
    DANFE_ERRO_IMPORT = _e
    log.exception("Falha ao carregar o motor DANFE (danfe.py)")

    class DanfeError(Exception):
        pass

try:
    from nfce import gerar_nfce, NfceError
    NFCE_ERRO_IMPORT = None
except Exception as _e:
    gerar_nfce = None
    NFCE_ERRO_IMPORT = _e
    log.exception("Falha ao carregar o motor NFC-e (nfce.py)")

    class NfceError(Exception):
        pass

# Suporte a HEIC (a extensão é aceita no upload, mas o Pillow sozinho não abre)
try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
except Exception:
    log.warning("pillow-heif não instalado: arquivos .heic não serão convertidos.")

# ---------------------------------------------------------
# 2. INICIALIZAÇÃO DO APLICATIVO FLASK
# ---------------------------------------------------------
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'chave-secreta-conversor-2026')
# Limite de upload: evita que arquivos gigantes travem/derrubem o worker
app.config['MAX_CONTENT_LENGTH'] = int(os.environ.get('MAX_UPLOAD_MB', '100')) * 1024 * 1024

diretorio_atual = os.path.dirname(os.path.abspath(__file__))
app.jinja_loader = jinja2.ChoiceLoader([
    app.jinja_loader,
    jinja2.FileSystemLoader(diretorio_atual),
    jinja2.FileSystemLoader(os.path.join(diretorio_atual, 'templates')),
])

# Pasta temporária para uploads (com fallback caso a pasta do app não seja gravável)
UPLOAD_FOLDER = os.path.join(diretorio_atual, 'uploads')
try:
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
except OSError:
    UPLOAD_FOLDER = os.path.join(tempfile.gettempdir(), 'conversor_uploads')
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'bmp', 'heic'}

MIME_DOCX = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
MIME_XLSX = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'


# ---------------------------------------------------------
# FUNÇÕES AUXILIARES
# ---------------------------------------------------------
def arquivo_permitido(filename, extensoes_permitidas):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in extensoes_permitidas


def _erro(mensagem, status):
    """Resposta de erro SEMPRE em texto simples e com status HTTP correto.
    Evita redirect+flash (que devolvia a página inicial com status 200 e deixava
    o front-end esperando um arquivo que nunca chegava)."""
    return mensagem, status, {'Content-Type': 'text/plain; charset=utf-8'}


def _remover(caminho):
    try:
        if caminho and os.path.exists(caminho):
            os.remove(caminho)
    except Exception as e:
        log.error("Erro ao apagar arquivo temporário %s: %s", caminho, e)


def _nome_base(filename):
    return os.path.splitext(os.path.basename(filename or ''))[0] or 'arquivo'


def _enviar_e_apagar(caminho, nome_download, mimetype):
    """Lê o arquivo gerado para a memória, apaga do disco e devolve o download.
    Mais simples e seguro que after_this_request (funciona também no Windows)."""
    try:
        with open(caminho, 'rb') as f:
            dados = io.BytesIO(f.read())
    finally:
        _remover(caminho)
    dados.seek(0)
    return send_file(dados, mimetype=mimetype, as_attachment=True, download_name=nome_download)


def limpar_arquivos_antigos(max_idade_segundos=3600):
    """Remove sobras de uploads antigos (ex.: de requisições que foram interrompidas)."""
    agora = time.time()
    try:
        for nome in os.listdir(UPLOAD_FOLDER):
            caminho = os.path.join(UPLOAD_FOLDER, nome)
            try:
                if os.path.isfile(caminho) and agora - os.path.getmtime(caminho) > max_idade_segundos:
                    os.remove(caminho)
            except OSError:
                pass
    except OSError:
        pass


limpar_arquivos_antigos()


# ---------------------------------------------------------
# TRATAMENTO GLOBAL DE ERROS (o front-end nunca fica sem resposta)
# ---------------------------------------------------------
@app.errorhandler(413)
def arquivo_muito_grande(e):
    limite = app.config['MAX_CONTENT_LENGTH'] // (1024 * 1024)
    return _erro(f'Arquivo muito grande. O limite é de {limite} MB.', 413)


@app.errorhandler(Exception)
def erro_inesperado(e):
    if isinstance(e, HTTPException):
        return e  # 404, 405 etc. mantêm o comportamento padrão
    log.exception("Erro não tratado")
    return _erro(f'Erro interno do servidor: {e}', 500)


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


@app.route('/xml-para-nfce-online', methods=['GET'])
def pagina_xml_nfce():
    return render_template('index.html', ferramenta_ativa='nfce-pdf')


# ---------------------------------------------------------
# 1. UNIR PDFs
# ---------------------------------------------------------
@app.route('/unir-pdf', methods=['POST'])
def unir_pdf():
    arquivos = request.files.getlist("files") or request.files.getlist("file")
    arquivos = [f for f in arquivos if f and f.filename.lower().endswith('.pdf')]
    if not arquivos:
        return _erro('Nenhum arquivo PDF válido foi enviado.', 400)

    unido = pymupdf.open()
    try:
        for arq in arquivos:
            doc = pymupdf.open(stream=arq.read(), filetype="pdf")
            try:
                unido.insert_pdf(doc)
            finally:
                doc.close()
        # Em memória: não deixa mais arquivos "unido_*.pdf" acumulando em /tmp
        saida = io.BytesIO(unido.tobytes(deflate=True, garbage=3))
    except Exception as e:
        log.exception("Erro ao unir PDFs")
        return _erro(f'Erro ao unir os PDFs: {e}', 500)
    finally:
        unido.close()

    saida.seek(0)
    return send_file(saida, mimetype='application/pdf', as_attachment=True,
                     download_name="documentos_unidos.pdf")


# ---------------------------------------------------------
# 2. IMAGENS PARA PDF
# ---------------------------------------------------------
def _preparar_imagem(dados_bytes):
    """Abre a imagem, corrige a rotação (EXIF de celular) e converte para RGB.
    Transparência vira fundo branco (em vez de preto)."""
    img = Image.open(io.BytesIO(dados_bytes))
    img = ImageOps.exif_transpose(img)
    if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
        img = img.convert('RGBA')
        fundo = Image.new('RGB', img.size, (255, 255, 255))
        fundo.paste(img, mask=img.split()[-1])
        return fundo
    return img.convert('RGB')


@app.route('/converter', methods=['POST'])
@app.route('/converter-imagem-pdf', methods=['POST'])
def converter_imagem_pdf():
    files = request.files.getlist('files') or request.files.getlist('file')
    files = [f for f in files if f and f.filename]
    if not files:
        return _erro('Nenhum arquivo selecionado.', 400)

    imagens = []
    try:
        for file in files:
            if arquivo_permitido(file.filename, ALLOWED_IMAGE_EXTENSIONS):
                imagens.append(_preparar_imagem(file.read()))

        if not imagens:
            return _erro('Nenhum arquivo de imagem válido foi enviado.', 400)

        saida = io.BytesIO()
        imagens[0].save(saida, format='PDF', save_all=True, append_images=imagens[1:])
        saida.seek(0)
    except Exception as e:
        log.exception("Erro na conversão de imagem para PDF")
        return _erro(f'Erro no processamento da imagem: {e}', 500)
    finally:
        for img in imagens:
            img.close()

    return send_file(saida, mimetype='application/pdf', as_attachment=True,
                     download_name="imagens_convertidas.pdf")


# ---------------------------------------------------------
# 3. PDF PARA WORD (.docx)
# ---------------------------------------------------------
@app.route('/pdf-para-word', methods=['POST'])
@app.route('/converter-pdf-word', methods=['POST'])
def converter_pdf_word():
    file = request.files.get('file')
    if not file or file.filename == '':
        return _erro('Nenhum arquivo PDF selecionado.', 400)

    if not arquivo_permitido(file.filename, {'pdf'}):
        return _erro('Por favor, envie um arquivo .pdf válido.', 400)

    id_unico = str(uuid.uuid4())
    caminho_entrada = os.path.join(UPLOAD_FOLDER, f"input_{id_unico}.pdf")
    caminho_saida = os.path.join(UPLOAD_FOLDER, f"output_{id_unico}.docx")

    try:
        file.save(caminho_entrada)
        from pdf2docx import Converter  # import pesado: só quando a ferramenta é usada
        cv = Converter(caminho_entrada)
        try:
            cv.convert(caminho_saida, start=0, end=None)
        finally:
            cv.close()  # sempre fecha, mesmo se a conversão falhar
    except Exception as e:
        log.exception("Erro ao converter PDF para Word")
        _remover(caminho_saida)
        return _erro(f'Erro no processamento do PDF: {e}', 500)
    finally:
        _remover(caminho_entrada)

    return _enviar_e_apagar(caminho_saida, f"{_nome_base(file.filename)}.docx", MIME_DOCX)


# ---------------------------------------------------------
# 4. XML PARA EXCEL (.xlsx)
# ---------------------------------------------------------
@app.route('/xml-para-excel', methods=['POST'])
@app.route('/converter-xml-xlsx', methods=['POST'])
def converter_xml_xlsx():
    file = request.files.get('file')
    if not file or file.filename == '':
        return _erro('Nenhum arquivo XML selecionado.', 400)

    if not arquivo_permitido(file.filename, {'xml'}):
        return _erro('Por favor, envie um arquivo .xml válido.', 400)

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
        log.exception("Erro ao converter XML para Excel")
        _remover(caminho_saida)
        return _erro(f'Erro no processamento do XML: {e}', 500)
    finally:
        _remover(caminho_entrada)

    return _enviar_e_apagar(caminho_saida, f"{_nome_base(file.filename)}.xlsx", MIME_XLSX)


# ---------------------------------------------------------
# 5. PDF PARA IMAGEM (.zip)
# ---------------------------------------------------------
@app.route('/pdf-para-imagem', methods=['POST'])
def pdf_para_imagem():
    file = request.files.get('file')
    if not file or file.filename == '':
        return _erro('Nenhum arquivo selecionado.', 400)

    if not file.filename.lower().endswith('.pdf'):
        return _erro('Formato inválido. Envie um arquivo PDF.', 400)

    pdf_document = None
    try:
        pdf_document = pymupdf.open(stream=file.read(), filetype="pdf")
        memory_zip = io.BytesIO()

        with zipfile.ZipFile(memory_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
            for page_num in range(len(pdf_document)):
                page = pdf_document.load_page(page_num)
                pix = page.get_pixmap(dpi=150)
                zf.writestr(f"pagina_{page_num + 1}.png", pix.tobytes("png"))
                pix = None  # libera a memória de cada página antes da próxima

        memory_zip.seek(0)
        return send_file(memory_zip, mimetype='application/zip', as_attachment=True,
                         download_name='imagens_extraidas.zip')
    except Exception as e:
        log.exception("Erro ao converter PDF para imagem")
        return _erro(f'Erro ao processar o PDF: {e}', 500)
    finally:
        if pdf_document is not None:
            pdf_document.close()


# ---------------------------------------------------------
# 6. COMPRIMIR PDF
# ---------------------------------------------------------
@app.route('/comprimir-pdf', methods=['POST'])
def comprimir_pdf():
    file = request.files.get('file')
    if not file or file.filename == '':
        return _erro('Nenhum arquivo selecionado.', 400)

    if not file.filename.lower().endswith('.pdf'):
        return _erro('Formato inválido. Envie um arquivo PDF.', 400)

    doc = None
    try:
        doc = pymupdf.open(stream=file.read(), filetype="pdf")
        memory_pdf = io.BytesIO()
        doc.save(memory_pdf, deflate=True, garbage=4, clean=True)
        memory_pdf.seek(0)

        nome_saida = f"comprimido_{_nome_base(file.filename)}.pdf"
        return send_file(memory_pdf, mimetype='application/pdf', as_attachment=True,
                         download_name=nome_saida)
    except Exception as e:
        log.exception("Erro ao comprimir PDF")
        return _erro(f'Erro ao comprimir o PDF: {e}', 500)
    finally:
        if doc is not None:
            doc.close()


# ---------------------------------------------------------
# 7. XML PARA PDF (DANFE OFICIAL MODELO 55)
# ---------------------------------------------------------
@app.route('/xml-para-pdf', methods=['POST'])
def xml_para_pdf():
    file = request.files.get('file')
    if not file or file.filename == '':
        return _erro('Nenhum arquivo selecionado.', 400)

    if not file.filename.lower().endswith('.xml'):
        return _erro('Formato inválido. Envie um arquivo XML.', 400)

    if gerar_danfe is None:
        log.error("Motor DANFE indisponível: %s", DANFE_ERRO_IMPORT)
        return _erro('A ferramenta de DANFE está temporariamente indisponível.', 503)

    try:
        pdf_bytes, numero_nf = gerar_danfe(file.read())
        memory_pdf = io.BytesIO(pdf_bytes)
        return send_file(memory_pdf, mimetype='application/pdf', as_attachment=True,
                         download_name=f"DANFE_NFe_{numero_nf}.pdf")
    except DanfeError as de:
        return _erro(f"Erro ao processar a Nota Fiscal: {de}", 400)
    except Exception as e:
        log.exception("Erro ao gerar DANFE")
        return _erro(f"Erro interno ao gerar o DANFE: {e}", 500)


# ---------------------------------------------------------
# 8. XML PARA CUPOM FISCAL (NFC-e)
# ---------------------------------------------------------
@app.route('/converter-xml-nfce', methods=['POST'])
def converter_xml_nfce():
    file = request.files.get('file') or request.files.get('arquivo')
    if not file or file.filename == '':
        return _erro('Nenhum arquivo selecionado.', 400)

    if not file.filename.lower().endswith('.xml'):
        return _erro('Formato inválido. Envie um arquivo XML.', 400)

    if gerar_nfce is None:
        log.error("Motor NFC-e indisponível: %s", NFCE_ERRO_IMPORT)
        return _erro('A ferramenta de NFC-e está temporariamente indisponível.', 503)

    try:
        resultado = gerar_nfce(file.read())

        if isinstance(resultado, tuple):
            pdf_bytes, numero = resultado
        else:
            pdf_bytes = resultado
            numero = uuid.uuid4().hex[:6]

        if not isinstance(pdf_bytes, (bytes, bytearray)):
            raise TypeError("o motor de NFC-e não retornou os bytes do PDF")

        memory_pdf = io.BytesIO(pdf_bytes)
        return send_file(memory_pdf, mimetype='application/pdf', as_attachment=True,
                         download_name=f"NFCe_{numero}.pdf")
    except NfceError as ne:
        return _erro(f"Erro ao processar a NFC-e: {ne}", 400)
    except Exception as e:
        log.exception("Erro ao gerar NFC-e")
        return _erro(f"Erro ao processar o arquivo NFC-e: {e}", 500)


# ---------------------------------------------------------
# ROTAS DE SEO (Sitemap e Robots.txt)
# ---------------------------------------------------------
@app.route('/sitemap.xml')
def sitemap():
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <url><loc>https://meuconversorpdf.com.br/</loc><changefreq>weekly</changefreq><priority>1.0</priority></url>
    <url><loc>https://meuconversorpdf.com.br/xml-para-excel-online</loc><changefreq>weekly</changefreq><priority>0.9</priority></url>
    <url><loc>https://meuconversorpdf.com.br/unir-pdf-online</loc><changefreq>weekly</changefreq><priority>0.9</priority></url>
    <url><loc>https://meuconversorpdf.com.br/imagem-para-pdf-online</loc><changefreq>weekly</changefreq><priority>0.8</priority></url>
    <url><loc>https://meuconversorpdf.com.br/pdf-para-imagem-online</loc><changefreq>weekly</changefreq><priority>0.8</priority></url>
    <url><loc>https://meuconversorpdf.com.br/comprimir-pdf-online</loc><changefreq>weekly</changefreq><priority>0.9</priority></url>
    <url><loc>https://meuconversorpdf.com.br/xml-para-pdf-online</loc><changefreq>weekly</changefreq><priority>0.8</priority></url>
    <url><loc>https://meuconversorpdf.com.br/xml-para-nfce-online</loc><changefreq>weekly</changefreq><priority>0.8</priority></url>
    <url><loc>https://meuconversorpdf.com.br/blog/comprimir-pdf.html</loc><changefreq>weekly</changefreq><priority>0.8</priority></url>
    <url><loc>https://meuconversorpdf.com.br/blog/juntar-pdf.html</loc><changefreq>weekly</changefreq><priority>0.8</priority></url>
</urlset>"""
    return xml, 200, {'Content-Type': 'application/xml'}


@app.route('/robots.txt')
def robots():
    txt = "User-agent: *\nAllow: /\nSitemap: https://meuconversorpdf.com.br/sitemap.xml"
    return txt, 200, {'Content-Type': 'text/plain'}


@app.route('/blog/comprimir-pdf.html')
def blog_comprimir_pdf():
    return render_template('blog/comprimir-pdf.html')


@app.route('/blog/juntar-pdf.html')
def blog_juntar_pdf():
    return render_template('blog/juntar-pdf.html')


# ---------------------------------------------------------
# INICIALIZAÇÃO DO SERVIDOR (uso local; em produção o gunicorn importa "app")
# ---------------------------------------------------------
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
