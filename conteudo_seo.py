# -*- coding: utf-8 -*-
"""Conteúdo de SEO do Meu Conversor: textos por ferramenta e artigos do blog.

Para editar um texto, altere aqui: o app.py e os templates só leem este arquivo.
Cada ferramenta vira uma página própria (rota, <title>, descrição, canonical,
<h1>, conteúdo, FAQ e dados estruturados JSON-LD).
"""

PRIVACIDADE = (
    "Os arquivos são processados no servidor apenas durante a conversão e apagados "
    "em seguida. Não é preciso cadastro nem instalar nada."
)

# ---------------------------------------------------------------------------
# FERRAMENTAS  (a chave é o id do card no index.html)
# ---------------------------------------------------------------------------
FERRAMENTAS = {
    "imagem-pdf": {
        "rota": "/imagem-para-pdf-online",
        "nome": "Imagem para PDF",
        "titulo": "Imagem para PDF Online Grátis (JPG, PNG) | Meu Conversor",
        "descricao": "Converta uma ou várias imagens JPG, PNG, WEBP ou HEIC em um único PDF, grátis, sem cadastro e sem instalar nada.",
        "h1": "Converter imagem para PDF online",
        "lead": "Transforme fotos e imagens em um único arquivo PDF, uma imagem por página, na ordem em que você selecionar. Serve para enviar comprovantes, documentos fotografados e anexos que exigem PDF.",
        "passos": [
            "Clique na área de envio ou arraste suas imagens (JPG, PNG, WEBP, BMP ou HEIC).",
            "Selecione várias imagens de uma vez se quiser reuni-las em um só PDF.",
            "Clique em Converter Agora e o PDF é baixado automaticamente.",
        ],
        "usos": [
            "Enviar fotos de documentos (RG, CNH, comprovante de residência) em PDF único.",
            "Reunir comprovantes e recibos fotografados no celular em um só arquivo.",
            "Anexar imagens em sistemas e portais que só aceitam PDF.",
        ],
        "dicas": "Fotos tiradas em pé no celular costumam ter a rotação gravada nos metadados da imagem. O conversor lê essa informação e corrige a orientação, então a página não sai deitada. PNGs com fundo transparente ficam com fundo branco, em vez de preto.",
        "faq": [
            ("Posso juntar várias imagens em um PDF só?", "Sim. Selecione todas de uma vez: cada imagem vira uma página, na ordem de seleção."),
            ("Quais formatos de imagem são aceitos?", "JPG, JPEG, PNG, WEBP, BMP e HEIC (formato de fotos do iPhone)."),
            ("Há limite de tamanho?", "O limite é de 100 MB por envio, somando todos os arquivos."),
        ],
        "relacionadas": ["comprimir-pdf", "unir-pdf", "comprimir-imagem"],
        "keywords": "converter imagem em pdf, jpg para pdf, png para pdf, foto para pdf, imagem para pdf online",
    },
    "unir-pdf": {
        "rota": "/unir-pdf-online",
        "nome": "Unir PDFs",
        "titulo": "Unir PDF Online Grátis: Juntar PDFs em Um | Meu Conversor",
        "descricao": "Junte vários arquivos PDF em um único documento, grátis e sem cadastro. Ideal para contratos, notas fiscais e comprovantes.",
        "h1": "Unir PDF online: junte vários arquivos em um",
        "lead": "Combine dois ou mais PDFs em um único documento, mantendo o conteúdo original de cada página. Útil para montar processos, reunir comprovantes ou enviar tudo em um anexo só.",
        "passos": [
            "Clique na área de envio e selecione todos os PDFs que deseja juntar.",
            "Os arquivos são unidos na ordem em que foram selecionados.",
            "Clique em Unir PDFs e baixe o documento final.",
        ],
        "usos": [
            "Juntar várias notas fiscais ou boletos em um só arquivo para a contabilidade.",
            "Montar documentação para financiamento, cadastro ou licitação.",
            "Reunir contrato, anexos e comprovantes antes de enviar por e-mail.",
        ],
        "dicas": "A ordem final segue a ordem de seleção dos arquivos. Se precisar de outra sequência, renomeie os arquivos com números (01, 02, 03) e selecione-os em ordem. Depois de unir, use Comprimir PDF se o arquivo ficar grande demais para e-mail.",
        "faq": [
            ("Perde qualidade ao unir PDFs?", "Não. As páginas são copiadas como estão para o novo documento, sem reconversão."),
            ("Quantos PDFs posso unir?", "Não há limite de quantidade, apenas de tamanho: 100 MB por envio, somando todos os arquivos."),
            ("Consigo unir PDFs protegidos por senha?", "Não. Remova a senha antes de enviar."),
        ],
        "relacionadas": ["dividir-pdf", "comprimir-pdf", "imagem-pdf"],
        "keywords": "unir pdf, juntar pdf, juntar pdfs online, combinar pdf, unir arquivos pdf",
    },
    "dividir-pdf": {
        "rota": "/dividir-pdf-online",
        "nome": "Dividir PDF",
        "titulo": "Dividir PDF Online Grátis: Separar Páginas | Meu Conversor",
        "descricao": "Separe um PDF em um arquivo por página e baixe tudo em ZIP. Grátis, sem cadastro e sem instalar programas.",
        "h1": "Dividir PDF online: uma página por arquivo",
        "lead": "Separe um PDF de várias páginas em documentos individuais. Cada página vira um PDF próprio e tudo é entregue em um único arquivo ZIP.",
        "passos": [
            "Envie o PDF que deseja dividir.",
            "Clique em Dividir PDF.",
            "Baixe o ZIP: dentro dele estão pagina_1.pdf, pagina_2.pdf e assim por diante.",
        ],
        "usos": [
            "Separar um lote de notas, holerites ou boletos digitalizados em um único PDF.",
            "Enviar apenas uma página específica de um documento longo.",
            "Organizar arquivos escaneados em páginas independentes.",
        ],
        "dicas": "Esta ferramenta gera sempre um arquivo por página. Se você precisa de apenas algumas páginas, divida o PDF, pegue as que interessam no ZIP e use Unir PDFs para reuni-las na ordem desejada.",
        "faq": [
            ("Posso escolher quais páginas extrair?", "Hoje a divisão é de uma página por arquivo. Para pegar só algumas, divida e depois una as páginas desejadas."),
            ("Como recebo os arquivos?", "Em um ZIP, com um PDF para cada página do original."),
            ("O PDF original é alterado?", "Não. Você recebe arquivos novos e o original permanece como estava."),
        ],
        "relacionadas": ["unir-pdf", "comprimir-pdf", "pdf-imagem"],
        "keywords": "dividir pdf, separar pdf, separar páginas pdf, extrair páginas pdf, dividir pdf online",
    },
    "comprimir-pdf": {
        "rota": "/comprimir-pdf-online",
        "nome": "Comprimir PDF",
        "titulo": "Comprimir PDF Online Grátis: Diminuir PDF | Meu Conversor",
        "descricao": "Reduza o tamanho de arquivos PDF para enviar por e-mail ou WhatsApp. Grátis, sem cadastro e sem marca d'água.",
        "h1": "Comprimir PDF online: diminua o tamanho do arquivo",
        "lead": "Otimize a estrutura do seu PDF para ele ocupar menos espaço, sem alterar o texto nem o layout. Ajuda quando o arquivo é grande demais para anexar em e-mails ou portais.",
        "passos": [
            "Envie o PDF pesado.",
            "Clique em Comprimir PDF.",
            "Baixe o arquivo otimizado, que sai com o nome comprimido_ seguido do nome original.",
        ],
        "usos": [
            "Enviar documentos por e-mail com limite de anexo.",
            "Cumprir o limite de tamanho de portais e sistemas de cadastro.",
            "Economizar espaço ao arquivar documentos.",
        ],
        "dicas": "A compressão remove dados duplicados e não utilizados e compacta a estrutura do arquivo. O resultado depende do PDF: arquivos com muita redundância encolhem bastante, enquanto PDFs de imagens escaneadas ou já otimizados podem encolher pouco, porque as imagens em si não são reamostradas. Nesse caso, uma alternativa é gerar o PDF de novo a partir de imagens reduzidas, usando Reduzir Imagem e depois Imagem para PDF.",
        "faq": [
            ("O texto do PDF perde qualidade?", "Não. O conteúdo e o layout permanecem iguais; a otimização atua na estrutura do arquivo."),
            ("Quanto o arquivo vai diminuir?", "Depende do PDF. Alguns reduzem muito, outros pouco, principalmente os que já estão otimizados ou são feitos de imagens escaneadas."),
            ("Há marca d'água no arquivo final?", "Não."),
        ],
        "relacionadas": ["unir-pdf", "comprimir-imagem", "imagem-pdf"],
        "keywords": "comprimir pdf, diminuir pdf, reduzir tamanho pdf, compactar pdf, comprimir pdf online grátis",
    },
    "pdf-imagem": {
        "rota": "/pdf-para-imagem-online",
        "nome": "PDF para Imagens",
        "titulo": "PDF para Imagem Online Grátis (PNG) | Meu Conversor",
        "descricao": "Converta cada página de um PDF em imagem PNG e baixe tudo em ZIP. Grátis, sem cadastro e sem instalar programas.",
        "h1": "PDF para imagem online: converta páginas em PNG",
        "lead": "Transforme cada página de um PDF em uma imagem PNG, reunidas em um arquivo ZIP. Útil para publicar páginas na web, inserir em apresentações ou compartilhar como imagem.",
        "passos": [
            "Envie o arquivo PDF.",
            "Clique em Extrair Imagens.",
            "Baixe o ZIP com uma imagem PNG por página (pagina_1.png, pagina_2.png…).",
        ],
        "usos": [
            "Usar uma página de PDF em slides, posts ou documentos.",
            "Compartilhar uma página como imagem em aplicativos de mensagem.",
            "Gerar miniaturas ou prévias de documentos.",
        ],
        "dicas": "As páginas são renderizadas em 150 DPI, uma boa resolução para tela e leitura. Isso significa que a página inteira vira imagem: o texto deixa de ser selecionável.",
        "faq": [
            ("Em que formato saem as imagens?", "PNG, com uma imagem para cada página do PDF, dentro de um ZIP."),
            ("Qual é a resolução?", "150 DPI."),
            ("Preciso instalar algum programa?", "Não, tudo é feito online."),
        ],
        "relacionadas": ["dividir-pdf", "imagem-pdf", "comprimir-pdf"],
        "keywords": "pdf para imagem, pdf para png, converter pdf em imagem, extrair imagens de pdf",
    },
    "xml-pdf": {
        "rota": "/xml-para-pdf-online",
        "nome": "XML para PDF (DANFE)",
        "titulo": "XML para PDF: Gerar DANFE da NF-e Grátis | Meu Conversor",
        "descricao": "Gere o DANFE em PDF a partir do XML da NF-e (modelo 55) para visualizar, imprimir e arquivar. Grátis e sem cadastro.",
        "h1": "XML para PDF: gerar o DANFE da NF-e",
        "lead": "Envie o XML da Nota Fiscal Eletrônica (modelo 55) e receba o DANFE em PDF, pronto para visualizar, imprimir ou arquivar. Evita depender de programas instalados para abrir o XML.",
        "passos": [
            "Envie o arquivo XML da NF-e (o mesmo que o fornecedor ou o seu sistema emitiu).",
            "Clique em Converter para PDF.",
            "Baixe o DANFE, nomeado com o número da nota.",
        ],
        "usos": [
            "Visualizar rapidamente uma nota recebida apenas em XML.",
            "Imprimir o DANFE para acompanhar a mercadoria ou para arquivo.",
            "Conferir itens, valores e impostos sem abrir o XML cru.",
        ],
        "dicas": "O XML é o documento fiscal com validade jurídica; o DANFE é a representação gráfica dele, feita para leitura e impressão. Por isso, guarde sempre o XML original (a legislação exige a guarda por prazo mínimo, em geral cinco anos; confirme com seu contador). A autenticidade da nota pode ser conferida pela chave de acesso de 44 dígitos no Portal Nacional da NF-e.",
        "faq": [
            ("O DANFE gerado substitui o XML?", "Não. O XML continua sendo o documento fiscal; o PDF serve para visualização, impressão e arquivo."),
            ("Funciona para qualquer NF-e?", "Foi feito para o XML da NF-e modelo 55. Para cupom fiscal de consumidor (NFC-e), use a ferramenta de cupom fiscal."),
            ("Meu XML fica salvo no site?", "Não. O arquivo é processado e descartado logo após a conversão."),
        ],
        "relacionadas": ["nfce-pdf", "xml-excel", "unir-pdf"],
        "keywords": "xml para pdf, xml nfe para pdf, gerar danfe pelo xml, converter xml nota fiscal em pdf, danfe online",
    },
    "nfce-pdf": {
        "rota": "/xml-para-nfce-online",
        "nome": "XML para Cupom Fiscal (NFC-e)",
        "titulo": "XML NFC-e para PDF: Cupom Fiscal Grátis | Meu Conversor",
        "descricao": "Transforme o XML da NFC-e em um cupom fiscal em PDF no formato de bobina. Grátis, sem cadastro e sem instalar programas.",
        "h1": "XML NFC-e para PDF: gerar o cupom fiscal",
        "lead": "Converta o XML de uma Nota Fiscal de Consumidor Eletrônica (NFC-e) em um cupom fiscal em PDF, no formato de bobina. Útil para consultar, reimprimir ou arquivar uma venda a partir do arquivo XML.",
        "passos": [
            "Envie o arquivo XML da NFC-e.",
            "Clique em Gerar Cupom em PDF.",
            "Baixe o cupom em PDF, nomeado com o número da nota.",
        ],
        "usos": [
            "Reimprimir um cupom quando só o XML está disponível.",
            "Enviar ao cliente uma cópia do cupom em PDF.",
            "Arquivar vendas em formato de leitura fácil.",
        ],
        "dicas": "A NFC-e é a nota fiscal de varejo (venda ao consumidor final), diferente da NF-e modelo 55 usada entre empresas. Se o seu arquivo é uma NF-e, use a ferramenta XML para PDF (DANFE). Guarde sempre o XML original, que é o documento com validade fiscal.",
        "faq": [
            ("Qual a diferença entre NFC-e e NF-e?", "A NFC-e documenta vendas ao consumidor final no varejo; a NF-e modelo 55 é usada principalmente em operações entre empresas."),
            ("O PDF substitui o XML da nota?", "Não. O XML é o documento fiscal; o PDF é apenas uma representação para leitura e impressão."),
            ("Posso enviar o XML de qualquer estado?", "A NFC-e segue um padrão nacional, mas cada estado tem pequenas particularidades. Se o seu arquivo não converter, entre em contato informando o estado."),
        ],
        "relacionadas": ["xml-pdf", "xml-excel", "unir-pdf"],
        "keywords": "xml nfce para pdf, cupom fiscal xml, imprimir nfc-e, nfc-e pdf",
    },
    "xml-excel": {
        "rota": "/xml-para-excel-online",
        "nome": "XML para Excel",
        "titulo": "XML para Excel Online Grátis (XLSX) | Meu Conversor",
        "descricao": "Converta arquivos XML com listas de registros em planilhas Excel (XLSX), uma coluna por campo. Grátis e sem cadastro.",
        "h1": "XML para Excel online: converta XML em planilha XLSX",
        "lead": "Transforme um arquivo XML que contém uma lista de registros (produtos, clientes, lançamentos, exportações de sistemas) em uma planilha XLSX, com cada campo em sua própria coluna.",
        "passos": [
            "Envie o arquivo XML.",
            "Clique em Converter para Excel.",
            "Abra a planilha .xlsx gerada no Excel, no LibreOffice ou no Google Planilhas.",
        ],
        "usos": [
            "Analisar em planilha uma exportação de sistema feita em XML.",
            "Conferir listas de produtos, clientes ou lançamentos.",
            "Preparar dados para filtros, tabelas dinâmicas e relatórios.",
        ],
        "dicas": "A conversão funciona melhor com XML em formato de lista: um elemento principal que contém vários registros repetidos, cada um com campos simples. XMLs fiscais muito aninhados, como a NF-e completa, têm estrutura em vários níveis e podem não gerar uma planilha útil. Para ler uma NF-e, gere o DANFE em PDF.",
        "faq": [
            ("Funciona com o XML da nota fiscal (NF-e)?", "A NF-e tem muitos níveis aninhados e não é o formato ideal para esta conversão. Para visualizar a nota, use a ferramenta XML para PDF (DANFE)."),
            ("Qual formato de planilha é gerado?", "XLSX, compatível com Excel, LibreOffice e Google Planilhas."),
            ("Meu arquivo fica armazenado?", "Não. Ele é apagado logo após a conversão."),
        ],
        "relacionadas": ["xml-pdf", "nfce-pdf", "unir-pdf"],
        "keywords": "xml para excel, converter xml em xlsx, xml para planilha, xml para xlsx online",
    },
    "comprimir-imagem": {
        "rota": "/reduzir-imagem-online",
        "nome": "Reduzir Imagem",
        "titulo": "Reduzir Tamanho de Imagem Online Grátis | Meu Conversor",
        "descricao": "Diminua o peso de fotos e imagens para enviar por e-mail ou subir em sistemas com limite de tamanho. Grátis e sem cadastro.",
        "h1": "Reduzir tamanho de imagem online",
        "lead": "Diminua o peso de fotos e imagens para enviar mais rápido por e-mail e aplicativos ou para cumprir limites de upload. Você pode enviar várias imagens de uma vez.",
        "passos": [
            "Envie uma ou várias imagens.",
            "Clique em Reduzir Tamanho.",
            "Com uma imagem, o download é um JPG reduzido; com várias, um ZIP com todas.",
        ],
        "usos": [
            "Anexar fotos em e-mails e formulários com limite de tamanho.",
            "Subir imagens em cadastros e sistemas que recusam arquivos grandes.",
            "Reduzir o peso de imagens para uso em sites.",
        ],
        "dicas": "As imagens são salvas como JPG com compressão média, o que reduz bastante o peso mantendo boa leitura visual. Como o resultado é JPG, PNGs transparentes ficam com fundo branco. A rotação das fotos de celular é corrigida automaticamente.",
        "faq": [
            ("Em que formato sai a imagem?", "JPG. Com várias imagens, elas vêm em um ZIP."),
            ("Perde qualidade?", "Há perda leve, típica da compressão JPG, mas a imagem continua adequada para visualização e envio."),
            ("Posso reduzir várias imagens de uma vez?", "Sim, e você recebe tudo em um ZIP."),
        ],
        "relacionadas": ["imagem-pdf", "comprimir-pdf", "pdf-imagem"],
        "keywords": "reduzir tamanho de imagem, diminuir foto, comprimir imagem online, reduzir jpg",
    },
    "word-pdf": {
        "rota": "/word-para-pdf-online",
        "nome": "Word para PDF",
        "titulo": "Word para PDF Online Grátis (DOCX) | Meu Conversor",
        "descricao": "Converta o texto de documentos Word (.docx) em PDF online, grátis e sem cadastro. Indicado para documentos simples, sem tabelas nem imagens.",
        "h1": "Word para PDF online: converta DOCX em PDF",
        "lead": "Gere um PDF a partir do texto de um documento Word (.docx). Indicado para documentos de texto simples, como cartas, declarações e relatórios sem elementos gráficos.",
        "passos": [
            "Envie o arquivo .docx.",
            "Clique em Converter para PDF.",
            "Baixe o PDF com o mesmo nome do documento.",
        ],
        "usos": [
            "Converter declarações, cartas e textos corridos em PDF.",
            "Enviar um documento sem risco de alteração acidental do texto.",
            "Gerar rapidamente uma versão em PDF sem abrir o Word.",
        ],
        "dicas": "Esta ferramenta extrai o texto do documento e o monta em um PDF novo, com quebra de linha e de página automáticas. Tabelas, imagens, cabeçalhos e formatações como negrito, fontes e cores não são reproduzidos. Para documentos com layout elaborado, prefira exportar como PDF diretamente pelo Word (Arquivo > Salvar como > PDF).",
        "faq": [
            ("A formatação do Word é mantida?", "Não. Apenas o texto é convertido; tabelas, imagens e estilos de fonte não são reproduzidos."),
            ("Aceita .doc antigo?", "Apenas arquivos .docx."),
            ("Quando devo usar outra opção?", "Se o documento tem tabelas, imagens ou layout importante, exporte para PDF pelo próprio Word."),
        ],
        "relacionadas": ["imagem-pdf", "unir-pdf", "comprimir-pdf"],
        "keywords": "word para pdf, docx para pdf, converter word em pdf, doc para pdf online",
    },
}

# ---------------------------------------------------------------------------
# ARTIGOS DE BLOG (rota: /blog/<slug>.html)
# ---------------------------------------------------------------------------
ARTIGOS = {
    "xml-nfe-para-pdf-danfe": {
        "titulo": "Como converter o XML da NF-e em PDF (DANFE) | Meu Conversor",
        "descricao": "Passo a passo para transformar o XML da nota fiscal eletrônica em DANFE em PDF, e entenda a diferença entre XML e DANFE.",
        "h1": "Como converter o XML da NF-e em PDF (DANFE)",
        "resumo": "O que é o DANFE, por que o XML não é legível e como gerar o PDF em poucos cliques.",
        "ferramenta": "xml-pdf",
        "secoes": [
            ("O que é o XML da NF-e e o que é o DANFE", [
                "Quando uma empresa emite uma Nota Fiscal Eletrônica (NF-e, modelo 55), o documento fiscal em si é um arquivo XML. É ele que tem validade jurídica e que é autorizado pela SEFAZ.",
                "O DANFE (Documento Auxiliar da Nota Fiscal Eletrônica) é a representação gráfica desse XML, organizada para leitura e impressão. Ele acompanha a mercadoria e facilita a conferência, mas não substitui o XML.",
            ]),
            ("Como gerar o DANFE a partir do XML", [
                "Se você recebeu a nota só em XML e precisa ler ou imprimir, o caminho é gerar o DANFE em PDF:",
                ["Acesse a ferramenta XML para PDF do Meu Conversor.", "Envie o arquivo XML da NF-e.", "Clique em Converter para PDF e baixe o DANFE."],
            ]),
            ("Como conferir se a nota é autêntica", [
                "Toda NF-e tem uma chave de acesso de 44 dígitos. Com ela, você consulta a situação da nota no Portal Nacional da NF-e (nfe.fazenda.gov.br) e confirma se foi autorizada. Faça essa consulta quando for dar entrada em mercadoria ou escriturar a nota.",
            ]),
            ("Por quanto tempo guardar o XML", [
                "A legislação tributária exige a guarda do XML por prazo mínimo, em geral de cinco anos. Guarde sempre o arquivo original, e não apenas o PDF. Para detalhes do seu caso, confirme com seu contador.",
            ]),
        ],
        "faq": [
            ("DANFE e XML são a mesma coisa?", "Não. O XML é o documento fiscal; o DANFE é a representação gráfica para leitura e impressão."),
            ("Posso apagar o XML depois de ter o PDF?", "Não é recomendado. O XML precisa ser guardado pelo prazo legal."),
        ],
    },
    "como-abrir-xml-nota-fiscal": {
        "titulo": "Como abrir um arquivo XML de nota fiscal | Meu Conversor",
        "descricao": "Veja como abrir e ler um XML de nota fiscal sem programas especiais, e quando converter para PDF ou planilha.",
        "h1": "Como abrir um arquivo XML de nota fiscal",
        "resumo": "Três formas de abrir o XML e quando converter para PDF.",
        "ferramenta": "xml-pdf",
        "secoes": [
            ("Por que o XML parece ilegível", [
                "O XML é um formato feito para sistemas trocarem dados. Aberto em um editor de texto, ele aparece como uma sequência de campos entre sinais de menor e maior, sem layout de nota.",
            ]),
            ("Formas de abrir o XML", [
                ["Navegador: arraste o arquivo para uma aba do Chrome, Edge ou Firefox para ver a estrutura organizada.", "Bloco de Notas: clique com o botão direito e escolha Abrir com. Serve para conferir valores, mas é difícil de ler.", "Conversão para PDF: gera o DANFE, com o layout de nota que as pessoas esperam ler."],
            ]),
            ("Quando converter para PDF ou para planilha", [
                "Para ler, conferir e imprimir uma nota, converta o XML em DANFE (PDF). Se o arquivo for de NFC-e (cupom de varejo), use a ferramenta de cupom fiscal. A conversão para Excel funciona melhor com XML em formato de lista de registros, e não com a NF-e completa.",
            ]),
            ("Cuidados ao receber XML por e-mail", [
                "Confirme o remetente antes de abrir qualquer anexo e confira a chave de acesso da nota no portal da SEFAZ. Não renomeie nem edite o XML original: qualquer alteração invalida a assinatura digital.",
            ]),
        ],
        "faq": [
            ("Preciso instalar algum programa para abrir XML?", "Não. O navegador abre o arquivo, e a conversão para PDF é feita online."),
            ("Editar o XML invalida a nota?", "Sim. Alterações quebram a assinatura digital do documento."),
        ],
    },
    "xml-nfce-para-pdf": {
        "titulo": "Como gerar PDF do cupom fiscal NFC-e pelo XML | Meu Conversor",
        "descricao": "Aprenda a transformar o XML da NFC-e em cupom fiscal em PDF e a diferença entre NFC-e e NF-e.",
        "h1": "Como gerar o PDF do cupom fiscal (NFC-e) a partir do XML",
        "resumo": "Reimprima ou arquive um cupom fiscal a partir do XML da NFC-e.",
        "ferramenta": "nfce-pdf",
        "secoes": [
            ("NFC-e: o que é", [
                "A Nota Fiscal de Consumidor Eletrônica (NFC-e) é o cupom fiscal eletrônico usado em vendas ao consumidor final no varejo, como lojas, restaurantes e supermercados. Assim como a NF-e, o documento fiscal é o arquivo XML.",
            ]),
            ("Quando precisa do PDF", [
                ["Reimprimir um cupom que o cliente perdeu.", "Enviar uma cópia digital da venda ao cliente.", "Arquivar vendas em um formato fácil de consultar."],
            ]),
            ("Como gerar o cupom em PDF", [
                ["Acesse a ferramenta de Cupom Fiscal (NFC-e) do Meu Conversor.", "Envie o XML da NFC-e.", "Clique em Gerar Cupom em PDF e baixe o arquivo."],
            ]),
            ("NFC-e ou NF-e: qual ferramenta usar", [
                "Se o XML é de venda ao consumidor (NFC-e), use a ferramenta de cupom. Se é de uma NF-e (modelo 55), usada em operações entre empresas, use a ferramenta XML para PDF, que gera o DANFE.",
            ]),
        ],
        "faq": [
            ("O PDF do cupom tem validade fiscal?", "O documento fiscal é o XML. O PDF é uma representação para leitura, impressão e arquivo."),
            ("Posso converter vários cupons de uma vez?", "Hoje a conversão é de um arquivo por vez."),
        ],
    },
}
