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
from urllib.parse import urlsplit

from flask import Flask, abort, redirect, render_template, request, send_file, send_from_directory
from PIL import Image, ImageOps
from werkzeug.exceptions import HTTPException

from conteudo_seo import ARTIGOS, FERRAMENTAS, PRIVACIDADE

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

# URL oficial do site (usada em canonical, sitemap e dados estruturados).
# Pode ser trocada pela variável de ambiente BASE_URL.
BASE_URL = os.environ.get('BASE_URL', 'https://meuconversorpdf.com.br').rstrip('/')
BASE_HOST = urlsplit(BASE_URL).netloc
# E-mail exibido na página /contato (defina CONTATO_EMAIL no servidor).
CONTATO_EMAIL = os.environ.get('CONTATO_EMAIL', '').strip()


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
    return render_template('index.html', ld=_ld_home())


@app.route('/politica')
def politica():
    return render_template('politica.html')


@app.route('/termos')
def termos():
    return render_template('termos.html')


@app.route('/pix-qr.png')
def serve_pix_qr():
    return send_from_directory(diretorio_atual, 'pix-qr.png')


@app.route('/manifest.json')
def serve_manifest():
    return send_from_directory(diretorio_atual, 'manifest.json')

@app.route('/sw.js')
def serve_sw():
    return send_from_directory(diretorio_atual, 'sw.js', mimetype='application/javascript')


# ---------------------------------------------------------
# SEO: CONTEXTO COMPARTILHADO, REDIRECT WWW E DADOS ESTRUTURADOS
# ---------------------------------------------------------
@app.before_request
def redirecionar_www():
    """www.dominio -> dominio (301), para o Google não indexar o site duplicado."""
    host = request.host.split(':')[0].lower()
    if host == 'www.' + BASE_HOST and request.method in ('GET', 'HEAD'):
        return redirect(BASE_URL + request.full_path.rstrip('?'), 301)


@app.context_processor
def contexto_global():
    return {
        'base_url': BASE_URL,
        'ferramentas': FERRAMENTAS,
        'artigos': ARTIGOS,
        'privacidade': PRIVACIDADE,
        'contato_email': CONTATO_EMAIL,
    }


def _ld_ferramenta(chave, p):
    url = BASE_URL + p['rota']
    itens = [
        {
            "@context": "https://schema.org",
            "@type": "WebApplication",
            "name": p['nome'],
            "url": url,
            "description": p['descricao'],
            "applicationCategory": "UtilitiesApplication",
            "operatingSystem": "Any",
            "inLanguage": "pt-BR",
            "browserRequirements": "Requer um navegador com JavaScript",
            "offers": {"@type": "Offer", "price": "0", "priceCurrency": "BRL"},
        },
        {
            "@context": "https://schema.org",
            "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "Início", "item": BASE_URL + "/"},
                {"@type": "ListItem", "position": 2, "name": p['nome'], "item": url},
            ],
        },
    ]
    if p.get('faq'):
        itens.append({
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": [
                {"@type": "Question", "name": q,
                 "acceptedAnswer": {"@type": "Answer", "text": a}}
                for q, a in p['faq']
            ],
        })
    return itens


def _ld_home():
    return [{
        "@context": "https://schema.org",
        "@type": "WebSite",
        "name": "Meu Conversor",
        "url": BASE_URL + "/",
        "inLanguage": "pt-BR",
        "description": "Ferramentas online gratuitas para PDF, XML de nota fiscal e imagens.",
    }]


# ---------------------------------------------------------
# ROTAS DE PÁGINAS DEDICADAS (SEO HÍBRIDO)
# Uma rota por ferramenta, gerada a partir de conteudo_seo.FERRAMENTAS.
# ---------------------------------------------------------
def _criar_pagina_ferramenta(chave):
    def view():
        p = FERRAMENTAS[chave]
        return render_template('index.html', ferramenta_ativa=chave, pagina=p,
                               ld=_ld_ferramenta(chave, p))
    view.__name__ = 'pagina_' + chave.replace('-', '_')
    return view


for _chave, _p in FERRAMENTAS.items():
    app.add_url_rule(_p['rota'], endpoint='pagina_' + _chave.replace('-', '_'),
                     view_func=_criar_pagina_ferramenta(_chave), methods=['GET'])


@app.route('/contato')
def contato():
    return render_template('contato.html')


@app.route('/blog/<slug>.html')
def artigo(slug):
    a = ARTIGOS.get(slug)
    if not a:
        abort(404)
    url = f"{BASE_URL}/blog/{slug}.html"
    ld = [{
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": a['h1'],
        "description": a['descricao'],
        "inLanguage": "pt-BR",
        "mainEntityOfPage": url,
        "author": {"@type": "Organization", "name": "Meu Conversor"},
        "publisher": {"@type": "Organization", "name": "Meu Conversor"},
    }]
    return render_template('artigo.html', a=a, slug=slug, canonical=url, ld=ld,
                           ferramenta=FERRAMENTAS[a['ferramenta']])


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
# 2. FERRAMENTA NOVA: DIVIDIR PDF
# ---------------------------------------------------------
@app.route('/dividir-pdf', methods=['POST'])
def dividir_pdf():
    file = request.files.get('file')
    if not file or file.filename == '':
        return _erro('Nenhum arquivo selecionado.', 400)

    if not file.filename.lower().endswith('.pdf'):
        return _erro('Formato inválido. Envie um arquivo PDF.', 400)

    doc = None
    try:
        doc = pymupdf.open(stream=file.read(), filetype="pdf")
        memory_zip = io.BytesIO()

        with zipfile.ZipFile(memory_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
            for page_num in range(len(doc)):
                # Cria um novo documento PDF apenas com a página atual
                pagina_doc = pymupdf.open()
                pagina_doc.insert_pdf(doc, from_page=page_num, to_page=page_num)
                
                # Converte para bytes e salva no ZIP
                pdf_bytes = pagina_doc.tobytes(deflate=True, garbage=3)
                zf.writestr(f"pagina_{page_num + 1}.pdf", pdf_bytes)
                pagina_doc.close()

        memory_zip.seek(0)
        nome_zip = f"dividido_{_nome_base(file.filename)}.zip"
        return send_file(memory_zip, mimetype='application/zip', as_attachment=True, download_name=nome_zip)
    
    except Exception as e:
        log.exception("Erro ao dividir PDF")
        return _erro(f'Erro ao dividir o PDF: {e}', 500)
    finally:
        if doc is not None:
            doc.close()


# ---------------------------------------------------------
# 3. IMAGENS PARA PDF
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
# 4. PDF PARA WORD (.docx)
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
# 5. XML PARA EXCEL (.xlsx)
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
# 6. PDF PARA IMAGEM (.zip)
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
# 7. COMPRIMIR PDF
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
# 8. XML PARA PDF (DANFE OFICIAL MODELO 55)
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
# 9. XML PARA CUPOM FISCAL (NFC-e)
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
# 10. DIMINUIR IMAGEM
# ---------------------------------------------------------
@app.route('/comprimir-imagem', methods=['POST'])
def comprimir_imagem():
    uploaded_files = [f for f in request.files.getlist("files") if f and f.filename]
    if not uploaded_files:
        return _erro("Nenhuma imagem enviada.", 400)

    def _reduzir(arquivo):
        # _preparar_imagem corrige rotação EXIF e põe fundo branco em PNG transparente
        img = _preparar_imagem(arquivo.read())
        try:
            saida = io.BytesIO()
            img.save(saida, format='JPEG', quality=50, optimize=True)
            return saida.getvalue()
        finally:
            img.close()

    try:
        if len(uploaded_files) == 1:
            file = uploaded_files[0]
            dados = _reduzir(file)
            return send_file(io.BytesIO(dados), mimetype='image/jpeg', as_attachment=True,
                             download_name=f"reduzida_{_nome_base(file.filename)}.jpg")

        memory_zip = io.BytesIO()
        usados = set()
        with zipfile.ZipFile(memory_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
            for file in uploaded_files:
                nome = f"reduzida_{_nome_base(file.filename)}"
                final, n = nome, 1
                while final in usados:  # evita sobrescrever nomes repetidos no ZIP
                    n += 1
                    final = f"{nome}_{n}"
                usados.add(final)
                zf.writestr(f"{final}.jpg", _reduzir(file))

        memory_zip.seek(0)
        return send_file(memory_zip, mimetype='application/zip', as_attachment=True,
                         download_name='imagens_reduzidas.zip')
    except Exception as e:
        log.exception("Erro na redução de imagem")
        return _erro(f"Erro ao processar as imagens: {e}", 500)


# ---------------------------------------------------------
# 11. NOVA FERRAMENTA: WORD PARA PDF
# ---------------------------------------------------------
@app.route('/word-para-pdf', methods=['POST'])
def word_para_pdf():
    file = request.files.get('file')
    if not file or file.filename == '':
        return _erro('Nenhum arquivo selecionado.', 400)

    if not file.filename.lower().endswith('.docx'):
        return _erro('Formato inválido. Envie um arquivo .docx.', 400)

    pdf_doc = None
    try:
        # Importação local para não pesar a inicialização global do app
        import docx

        # python-docx lê direto da memória: não precisa de arquivo temporário
        doc_docx = docx.Document(io.BytesIO(file.read()))

        pdf_doc = pymupdf.open()
        page = pdf_doc.new_page()

        margin_x, margin_top, margin_bottom = 50, 50, 50
        fontsize = 11
        line_h = fontsize * 1.4
        max_width = page.rect.width - (2 * margin_x)
        limite_y = page.rect.height - margin_bottom
        cursor_y = margin_top

        def quebrar_linhas(texto):
            """Quebra o parágrafo em linhas que cabem na largura da página."""
            linhas, atual = [], ""
            for palavra in texto.split():
                teste = f"{atual} {palavra}".strip()
                if pymupdf.get_text_length(teste, fontname="helv", fontsize=fontsize) <= max_width:
                    atual = teste
                else:
                    if atual:
                        linhas.append(atual)
                    atual = palavra
            if atual:
                linhas.append(atual)
            return linhas

        for para in doc_docx.paragraphs:
            texto = para.text
            if texto.strip() == "":
                cursor_y += line_h
                continue

            for linha in quebrar_linhas(texto):
                # Nova página quando a próxima linha não cabe mais
                if cursor_y + line_h > limite_y:
                    page = pdf_doc.new_page()
                    cursor_y = margin_top
                page.insert_text((margin_x, cursor_y + fontsize), linha,
                                 fontsize=fontsize, fontname="helv", color=(0, 0, 0))
                cursor_y += line_h
            cursor_y += line_h * 0.4  # espaço entre parágrafos

        memory_pdf = io.BytesIO()
        pdf_doc.save(memory_pdf, deflate=True, garbage=4, clean=True)
        memory_pdf.seek(0)

        nome_saida = f"{_nome_base(file.filename)}.pdf"
        return send_file(memory_pdf, mimetype='application/pdf', as_attachment=True, download_name=nome_saida)

    except Exception as e:
        log.exception("Erro ao converter Word para PDF")
        return _erro(f'Erro ao processar o arquivo Word: {e}', 500)
    finally:
        if pdf_doc is not None:
            pdf_doc.close()

# ---------------------------------------------------------
# ROTAS DE SEO (Sitemap e Robots.txt)
# ---------------------------------------------------------
@app.route('/sitemap.xml')
def sitemap():
    # Gerado a partir do conteudo_seo.py: toda ferramenta/artigo novo entra sozinho.
    caminhos = ['/']
    caminhos += [p['rota'] for p in FERRAMENTAS.values()]
    caminhos += [f'/blog/{slug}.html' for slug in ARTIGOS]
    caminhos += ['/blog/comprimir-pdf.html', '/blog/juntar-pdf.html',
                 '/guia-fechamento-contabil', '/otimizacao-notas',
                 '/gestao-documentos', '/contato']
    linhas = ''.join(f'    <url><loc>{BASE_URL}{c}</loc></url>\n' for c in caminhos)
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
           f'{linhas}</urlset>')
    return xml, 200, {'Content-Type': 'application/xml; charset=utf-8'}

@app.route('/robots.txt')
def robots():
    txt = f"User-agent: *\nAllow: /\nSitemap: {BASE_URL}/sitemap.xml\n"
    return txt, 200, {'Content-Type': 'text/plain'}

# ---------------------------------------------------------
# ROTAS DO BLOG E GUIAS (ARTIGOS)
# ---------------------------------------------------------
@app.route('/blog/comprimir-pdf.html')
def blog_comprimir_pdf():
    return render_template('blog/comprimir-pdf.html')

@app.route('/blog/juntar-pdf.html')
def blog_juntar_pdf():
    return render_template('blog/juntar-pdf.html')

@app.route('/guia-fechamento-contabil')
def guia_fechamento():
    return render_template('fechamento.html')

@app.route('/otimizacao-notas')
def otimizacao_notas():
    return render_template('otimizacao-notas.html')

@app.route('/gestao-documentos')
def gestao_documentos():
    return render_template('gestao-documentos.html')
    
# ---------------------------------------------------------
# INICIALIZAÇÃO DO SERVIDOR
# ---------------------------------------------------------
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
