import os
import io
from flask import Flask, request, render_template_string, send_file
from PIL import Image
import xml.etree.ElementTree as ET
import pandas as pd
from pdf2docx import Converter

app = Flask(__name__)

UPLOADS_DIR = 'uploads'
os.makedirs(UPLOADS_DIR, exist_ok=True)

HTML_PAGE = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Central de Conversões Pro</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        :root {
            --bg-color: #f8fafc;
            --card-bg: #ffffff;
            --primary: #4f46e5;
            --primary-hover: #4338ca;
            --success: #10b981;
            --success-hover: #059669;
            --purple: #8b5cf6;
            --purple-hover: #7c3aed;
            --text-main: #0f172a;
            --text-muted: #64748b;
            --border: #e2e8f0;
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            font-family: 'Inter', sans-serif;
        }

        body {
            background-color: var(--bg-color);
            color: var(--text-main);
            min-height: 100vh;
            padding: 40px 20px;
        }

        .header {
            text-align: center;
            max-width: 600px;
            margin: 0 auto 40px auto;
        }

        .header h1 {
            font-size: 2.2rem;
            font-weight: 700;
            color: var(--text-main);
            margin-bottom: 8px;
        }

        .header p {
            color: var(--text-muted);
            font-size: 1rem;
        }

        .grid-container {
            max-width: 1100px;
            margin: 0 auto;
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
            gap: 24px;
        }

        .card {
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 28px;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
            transition: transform 0.2s ease, box-shadow 0.2s ease;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
        }

        .card:hover {
            transform: translateY(-4px);
            box-shadow: 0 12px 20px -5px rgba(0, 0, 0, 0.08);
        }

        .card-header {
            display: flex;
            align-items: center;
            gap: 14px;
            margin-bottom: 20px;
        }

        .icon-box {
            width: 48px;
            height: 48px;
            border-radius: 12px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.4rem;
        }

        .icon-green { background-color: #d1fae5; color: #047857; }
        .icon-blue { background-color: #e0e7ff; color: #3730a3; }
        .icon-purple { background-color: #f3e8ff; color: #6b21a8; }

        .card-title h3 {
            font-size: 1.15rem;
            font-weight: 600;
        }

        .card-title p {
            font-size: 0.85rem;
            color: var(--text-muted);
            margin-top: 2px;
        }

        .upload-area {
            border: 2px dashed var(--border);
            border-radius: 10px;
            padding: 16px;
            text-align: center;
            margin-bottom: 20px;
            background-color: #fafafa;
            transition: border-color 0.2s ease;
        }

        .upload-area:hover {
            border-color: var(--primary);
        }

        input[type="file"] {
            width: 100%;
            font-size: 0.85rem;
            color: var(--text-muted);
            cursor: pointer;
        }

        input[type="file"]::file-selector-button {
            background: #e2e8f0;
            border: none;
            padding: 6px 12px;
            border-radius: 6px;
            color: var(--text-main);
            font-weight: 500;
            cursor: pointer;
            margin-right: 10px;
            transition: background 0.2s ease;
        }

        input[type="file"]::file-selector-button:hover {
            background: #cbd5e1;
        }

        .btn {
            width: 100%;
            padding: 12px;
            border: none;
            border-radius: 8px;
            font-size: 0.95rem;
            font-weight: 600;
            color: white;
            cursor: pointer;
            transition: background-color 0.2s ease, opacity 0.2s ease;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
        }

        .btn-green { background-color: var(--success); }
        .btn-green:hover { background-color: var(--success-hover); }

        .btn-blue { background-color: var(--primary); }
        .btn-blue:hover { background-color: var(--primary-hover); }

        .btn-purple { background-color: var(--purple); }
        .btn-purple:hover { background-color: var(--purple-hover); }

        footer {
            text-align: center;
            margin-top: 50px;
            color: var(--text-muted);
            font-size: 0.85rem;
        }
    </style>
</head>
<body>

    <div class="header">
        <h1>Central de Ferramentas</h1>
        <p>Convolua, junte e converta seus documentos em segundos com segurança total.</p>
    </div>

    <div class="grid-container">

        <!-- FERRAMENTA 1: IMAGENS PARA PDF -->
        <div class="card">
            <div>
                <div class="card-header">
                    <div class="icon-box icon-green">
                        <i class="fa-solid fa-file-pdf"></i>
                    </div>
                    <div class="card-title">
                        <h3>Imagens para PDF</h3>
                        <p>Junte múltiplas fotos num único PDF</p>
                    </div>
                </div>
                <form action="/converter-imagem" method="POST" enctype="multipart/form-data">
                    <div class="upload-area">
                        <input type="file" name="imagens" accept="image/*" multiple required>
                    </div>
            </div>
            <button type="submit" class="btn btn-green">
                <i class="fa-solid fa-gear"></i> Gerar PDF
            </button>
            </form>
        </div>

        <!-- FERRAMENTA 2: XML PARA EXCEL -->
        <div class="card">
            <div>
                <div class="card-header">
                    <div class="icon-box icon-blue">
                        <i class="fa-solid fa-file-excel"></i>
                    </div>
                    <div class="card-title">
                        <h3>XML para Excel</h3>
                        <p>Extraia dados de NF-e para planilhas</p>
                    </div>
                </div>
                <form action="/converter-xml" method="POST" enctype="multipart/form-data">
                    <div class="upload-area">
                        <input type="file" name="xmls" accept=".xml" multiple required>
                    </div>
            </div>
            <button type="submit" class="btn btn-blue">
                <i class="fa-solid fa-table"></i> Gerar Excel
            </button>
            </form>
        </div>

        <!-- FERRAMENTA 3: PDF PARA WORD -->
        <div class="card">
            <div>
                <div class="card-header">
                    <div class="icon-box icon-purple">
                        <i class="fa-solid fa-file-word"></i>
                    </div>
                    <div class="card-title">
                        <h3>PDF para Word</h3>
                        <p>Transforme documentos em .docx editáveis</p>
                    </div>
                </div>
                <form action="/pdf-para-word" method="POST" enctype="multipart/form-data">
                    <div class="upload-area">
                        <input type="file" name="arquivo" accept=".pdf" required>
                    </div>
            </div>
            <button type="submit" class="btn btn-purple">
                <i class="fa-solid fa-file-export"></i> Converter para Word
            </button>
            </form>
        </div>

    </div>

    <footer>
        <p>Sistema Interno de Processamento de Arquivos • Python & Flask</p>
    </footer>

    <script>
        document.querySelectorAll('form').forEach(form => {
            form.addEventListener('submit', function() {
                const btn = this.querySelector('button[type="submit"]');
                if (btn) {
                    const originalContent = btn.innerHTML;
                    btn.style.pointerEvents = 'none';
                    btn.style.opacity = '0.75';
                    btn.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> Processando...';

                    // Restaura o botão após 6 segundos caso o arquivo já tenha sido baixado
                    setTimeout(() => {
                        btn.style.pointerEvents = 'auto';
                        btn.style.opacity = '1';
                        btn.innerHTML = originalContent;
                    }, 6000);
                }
            });
        });
    </script>

</body>
</html>
"""

@app.route('/')
def home():
    return render_template_string(HTML_PAGE)

@app.route('/converter-imagem', methods=['POST'])
def converter_imagem():
    arquivos = request.files.getlist('imagens')
    if not arquivos or arquivos[0].filename == '':
        return "Nenhuma imagem selecionada!", 400

    lista_imagens = []
    for arq in arquivos:
        img = Image.open(arq.stream)
        if img.mode != 'RGB':
            img = img.convert('RGB')
        lista_imagens.append(img)
    
    pdf_em_memoria = io.BytesIO()
    lista_imagens[0].save(pdf_em_memoria, format='PDF', save_all=True, append_images=lista_imagens[1:])
    pdf_em_memoria.seek(0)
    
    return send_file(pdf_em_memoria, mimetype='application/pdf', as_attachment=True, download_name="imagens_unificadas.pdf")

@app.route('/converter-xml', methods=['POST'])
def converter_xml():
    arquivos = request.files.getlist('xmls')
    if not arquivos or arquivos[0].filename == '':
        return "Nenhum arquivo XML selecionado!", 400

    dados_notas = []
    ns = {'nfe': 'http://www.portalfiscal.inf.br/nfe'}

    for arq in arquivos:
        try:
            tree = ET.parse(arq.stream)
            root = tree.getroot()

            def buscar_texto(caminho):
                elem = root.find(f'.//{caminho}', ns)
                if elem is None:
                    elem = root.find(f'.//{caminho}')
                return elem.text if elem is not None else "N/A"

            num_nota = buscar_texto('nNF')
            emitente = buscar_texto('xNome')
            destinatario = buscar_texto('dest/nfe:xNome') if root.find('.//dest/nfe:xNome', ns) is not None else buscar_texto('dest/xNome')
            valor_total = buscar_texto('vNF')
            data_emissao = buscar_texto('dhEmi')

            dados_notas.append({
                'Número da Nota': num_nota,
                'Data de Emissão': data_emissao,
                'Emitente': emitente,
                'Destinatário': destinatario,
                'Valor Total (R$)': valor_total
            })
        except Exception:
            continue

    if not dados_notas:
        return "Não foi possível ler os dados dos arquivos XML enviados.", 400

    df = pd.DataFrame(dados_notas)
    excel_em_memoria = io.BytesIO()
    
    with pd.ExcelWriter(excel_em_memoria, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Notas Fiscais')
    
    excel_em_memoria.seek(0)

    return send_file(
        excel_em_memoria,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name="relatorio_notas_fiscais.xlsx"
    )

@app.route('/pdf-para-word', methods=['POST'])
def pdf_para_word():
    if 'arquivo' not in request.files:
        return "Nenhum arquivo enviado", 400
        
    arquivo = request.files['arquivo']
    if arq_nome := arquivo.filename:
        if arq_nome.endswith('.pdf'):
            pdf_path = os.path.join(UPLOADS_DIR, arq_nome)
            docx_name = arq_nome.rsplit('.', 1)[0] + '.docx'
            docx_path = os.path.join(UPLOADS_DIR, docx_name)

            arquivo.save(pdf_path)

            try:
                cv = Converter(pdf_path)
                cv.convert(docx_path, start=0, end=None)
                cv.close()

                return send_file(docx_path, as_attachment=True, download_name=docx_name)
            except Exception as e:
                return f"Erro ao converter PDF para Word: {str(e)}", 500

    return "Formato inválido. Envie um arquivo PDF.", 400

if __name__ == '__main__':
    print("Servidor rodando em http://127.0.0.1:5000")
    app.run(debug=True, port=5000)