# -*- coding: utf-8 -*-
"""
nfce.py - Gera o Extrato/DANFE-NFC-e (Cupom Fiscal, modelo 65) em PDF
a partir do XML da NFC-e (arquivo nfeProc ou NFe), no layout estreito
de bobina térmica com QR Code de consulta, conforme Manual de
Orientação do Contribuinte (MOC) do SAT/NFC-e.

Dependência: reportlab (QR Code nativo em reportlab.graphics.barcode.qr)

Uso:
    from nfce import gerar_nfce, NfceError
    pdf_bytes, numero = gerar_nfce(xml_bytes, largura_mm=80)
"""
import io
import xml.etree.ElementTree as ET
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from reportlab.graphics import renderPDF
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas


class NfceError(Exception):
    """Erro de negócio específico da NFC-e (XML inválido, modelo errado etc.)."""


FONTE = 'Helvetica'
NEGRITO = 'Helvetica-Bold'


def _carregar_xml(xml_bytes):
    """
    Faz o parse do XML e remove os namespaces de forma segura.

    O parser recebe os bytes diretamente para respeitar a codificação
    declarada no próprio XML. Erros de sintaxe são convertidos em
    NfceError para que a rota Flask consiga devolvê-los ao usuário.
    """
    if not xml_bytes or not xml_bytes.strip():
        raise NfceError('O arquivo XML está vazio.')
    # NFC-e não usa DOCTYPE/ENTITY; recusar evita ataques de expansão de entidades.
    cabecalho = xml_bytes[:4096].upper()
    if b'<!DOCTYPE' in cabecalho or b'<!ENTITY' in xml_bytes.upper():
        raise NfceError('XML recusado: declarações DOCTYPE/ENTITY não são permitidas.')
    try:
        root = ET.fromstring(xml_bytes)

        # Remove o namespace de cada elemento sem alterar o conteúdo.
        for elem in root.iter():
            if isinstance(elem.tag, str) and '}' in elem.tag:
                elem.tag = elem.tag.split('}', 1)[1]

        return root
    except ET.ParseError as e:
        raise NfceError(f'XML inválido ou malformado: {e}') from e


def _txt(node, tag):
    """Texto de um subelemento; sempre devolve str ('' quando não existe)."""
    if node is None:
        return ''
    return (node.findtext(tag) or '').strip()


# ---------------------------------------------------------------------------
# FORMATADORES (padrão brasileiro)
# ---------------------------------------------------------------------------
def _dec(val):
    """Converte texto do XML em Decimal; devolve None se vazio/inválido."""
    if val is None or str(val).strip() == '':
        return None
    try:
        return Decimal(str(val).strip().replace(',', '.'))
    except InvalidOperation:
        return None


def fmt_num(val, casas=2, minimo=None):
    """1234.5 -> '1.234,50'. Com minimo < casas, remove zeros finais ('2.0000' -> '2')."""
    d = _dec(val)
    if d is None:
        d = Decimal(0)
    minimo = casas if minimo is None else minimo
    try:
        d = d.quantize(Decimal(1).scaleb(-casas), rounding=ROUND_HALF_UP)
    except InvalidOperation:
        return str(val)
    texto = f"{d:,.{casas}f}"                      # 1,234.50
    if minimo < casas:
        inteiro, _, frac = texto.partition('.')
        frac = frac.rstrip('0').ljust(minimo, '0')
        texto = inteiro + ('.' + frac if frac else '')
    return texto.replace(',', '#').replace('.', ',').replace('#', '.')


def _positivo(val, casas=2):
    """Texto formatado se o valor for > 0; senão ''."""
    d = _dec(val)
    return fmt_num(d, casas) if d is not None and d > 0 else ''


def _so_digitos(v):
    return ''.join(ch for ch in (v or '') if ch.isdigit())


def fmt_doc(doc):
    n = _so_digitos(doc)
    if len(n) == 11:
        return f"{n[:3]}.{n[3:6]}.{n[6:9]}-{n[9:]}"
    if len(n) == 14:
        return f"{n[:2]}.{n[2:5]}.{n[5:8]}/{n[8:12]}-{n[12:]}"
    return doc or ''


def fmt_cep(cep):
    n = _so_digitos(cep)
    return f"{n[:5]}-{n[5:]}" if len(n) == 8 else (cep or '')


def fmt_fone(fone):
    n = _so_digitos(fone)
    if len(n) == 10:
        return f"({n[:2]}) {n[2:6]}-{n[6:]}"
    if len(n) == 11:
        return f"({n[:2]}) {n[2:7]}-{n[7:]}"
    return fone or ''


def fmt_data(dh):
    """'2026-06-10T14:35:22-03:00' -> '10/06/2026'."""
    if not dh or len(dh) < 10:
        return ''
    ano, mes, dia = dh[:4], dh[5:7], dh[8:10]
    return f"{dia}/{mes}/{ano}"


def fmt_hora(dh):
    return dh[11:19] if dh and len(dh) >= 19 else ''


def fmt_chave(chave):
    """Agrupa a chave de acesso de 4 em 4 dígitos."""
    return ' '.join(chave[i:i + 4] for i in range(0, len(chave), 4))


def _fatiar_palavra(palavra, fonte, tam, larg):
    """Divide uma palavra maior que a linha em pedaços que cabem. Custo linear."""
    partes, atual, w = [], '', 0.0
    for ch in palavra:
        wc = stringWidth(ch, fonte, tam)
        if atual and w + wc > larg:
            partes.append(atual)
            atual, w = '', 0.0
        atual += ch
        w += wc
    if atual:
        partes.append(atual)
    return partes


def _quebrar(txt, fonte, tam, larg):
    """
    Quebra o texto em linhas que cabem em `larg` (pontos), medindo com a fonte real.
    Palavras maiores que a linha são fatiadas. Cada caractere é processado uma única
    vez por etapa, portanto não há laço infinito nem custo quadrático.
    """
    if not txt:
        return []
    saida = []
    for paragrafo in str(txt).replace('\r', '').split('\n'):
        atual = ''
        for palavra in paragrafo.split():
            candidato = f"{atual} {palavra}" if atual else palavra
            if stringWidth(candidato, fonte, tam) <= larg:
                atual = candidato
                continue
            if atual:
                saida.append(atual)
                atual = ''
            if stringWidth(palavra, fonte, tam) > larg:
                partes = _fatiar_palavra(palavra, fonte, tam, larg)
                saida.extend(partes[:-1])
                palavra = partes[-1]
            atual = palavra
        if atual:
            saida.append(atual)
    return saida


UF_AMBIENTE = {'1': 'PRODUÇÃO', '2': 'HOMOLOGAÇÃO'}
IND_PAG = {'0': 'Pagamento à Vista', '1': 'Pagamento a Prazo', '2': 'Outros'}
TPAG = {
    '01': 'Dinheiro', '02': 'Cheque', '03': 'Cartão de Crédito',
    '04': 'Cartão de Débito', '05': 'Crédito Loja', '10': 'Vale Alimentação',
    '11': 'Vale Refeição', '12': 'Vale Presente', '13': 'Vale Combustível',
    '15': 'Boleto Bancário', '16': 'Depósito Bancário', '17': 'PIX',
    '18': 'Transferência bancária', '19': 'Programa de fidelidade',
    '90': 'Sem Pagamento', '99': 'Outros',
}


# ---------------------------------------------------------------------------
# EXTRAÇÃO DOS DADOS DO XML
# ---------------------------------------------------------------------------
def extrair_dados_nfce(root):
    inf = root if root.tag == 'infNFe' else root.find('.//infNFe')
    if inf is None:
        raise NfceError(
            'Este XML não é uma NF-e/NFC-e (elemento <infNFe> não encontrado).')

    ide = inf.find('ide')
    modelo = _txt(ide, 'mod')
    if modelo and modelo != '65':
        raise NfceError(
            f'Este XML é de um documento modelo {modelo}. '
            'Este conversor gera o cupom apenas para NFC-e modelo 65.')

    prot = root.find('.//protNFe/infProt')
    chave = _txt(prot, 'chNFe') or ''.join(ch for ch in (inf.get('Id') or '') if ch.isdigit())

    emit = inf.find('emit')
    e_end = emit.find('enderEmit') if emit is not None else None
    endereco = ', '.join(p for p in (
        _txt(e_end, 'xLgr'),
        _txt(e_end, 'nro'),
        _txt(e_end, 'xCpl'),
    ) if p)
    municipio_uf = ' - '.join(p for p in (_txt(e_end, 'xMun'), _txt(e_end, 'UF')) if p)

    emitente = {
        'nome': _txt(emit, 'xNome'),
        'fantasia': _txt(emit, 'xFant'),
        'doc': fmt_doc(_txt(emit, 'CNPJ') or _txt(emit, 'CPF')),
        'ie': _txt(emit, 'IE'),
        'endereco': endereco,
        'bairro': _txt(e_end, 'xBairro'),
        'municipio_uf': municipio_uf,
        'cep': fmt_cep(_txt(e_end, 'CEP')),
        'fone': fmt_fone(_txt(e_end, 'fone')),
    }

    dest = inf.find('dest')
    consumidor = None
    if dest is not None:
        doc = _txt(dest, 'CNPJ') or _txt(dest, 'CPF')
        nome = _txt(dest, 'xNome')
        if doc or nome:
            consumidor = {'nome': nome or 'CONSUMIDOR NÃO IDENTIFICADO', 'doc': fmt_doc(doc)}

    dh_emi = _txt(ide, 'dhEmi')
    dh_rec = _txt(prot, 'dhRecbto')
    c_stat = _txt(prot, 'cStat')
    if prot is not None and _txt(prot, 'nProt'):
        prot_txt = f"Protocolo de autorização: {_txt(prot, 'nProt')} - {fmt_data(dh_rec)} {fmt_hora(dh_rec)}"
        if c_stat and c_stat not in ('100', '150'):
            prot_txt += f' (cStat {c_stat})'
    else:
        prot_txt = 'NFC-e SEM PROTOCOLO DE AUTORIZAÇÃO'

    itens = []
    for det in inf.findall('det'):
        prod = det.find('prod')
        imp = det.find('imposto')
        grp = imp.find('ICMS') if imp is not None else None
        icms = list(grp)[0] if grp is not None and len(grp) else None
        itens.append({
            'codigo': _txt(prod, 'cProd'),
            'descricao': _txt(prod, 'xProd'),
            'qtd': fmt_num(_txt(prod, 'qCom'), 4, 0),
            'un': _txt(prod, 'uCom'),
            'vun': fmt_num(_txt(prod, 'vUnCom'), 4, 2),
            'vtot': fmt_num(_txt(prod, 'vProd'), 2),
            'vdesc': _positivo(_txt(prod, 'vDesc')),
            'cst': (_txt(icms, 'CST') or _txt(icms, 'CSOSN') or ''),
        })

    pags = []
    for p in inf.findall('pag/detPag'):
        tpag = _txt(p, 'tPag')
        pags.append({
            'tipo': TPAG.get(tpag, tpag),
            'valor': fmt_num(_txt(p, 'vPag'), 2),
        })
    v_troco = _positivo(_txt(inf, 'pag/vTroco'))

    t = inf.find('total/ICMSTot')
    v_trib = _positivo(_txt(t, 'vTotTrib'))
    compl = _txt(inf, 'infAdic/infCpl')

    # Ambiente e URL de consulta (URL do QR Code já traz tudo que a Sefaz exige,
    # e costuma vir pronta no grupo infNFeSupl do XML autorizado)
    qrcode_url = root.findtext('.//infNFeSupl/qrCode') or ''
    qrcode_url = qrcode_url.replace('<![CDATA[', '').replace(']]>', '').strip()
    # infNFeSupl é irmão de infNFe (não filho): precisa ser buscado a partir da raiz
    url_chave = (root.findtext('.//infNFeSupl/urlChave') or '').strip()

    return {
        'chave': chave,
        'numero': _txt(ide, 'nNF'),
        'serie': _txt(ide, 'serie'),
        'natureza': _txt(ide, 'natOp'),
        'data_emissao': fmt_data(dh_emi),
        'hora_emissao': fmt_hora(dh_emi),
        'ambiente': UF_AMBIENTE.get(_txt(ide, 'tpAmb'), ''),
        'homologacao': _txt(ide, 'tpAmb') == '2',
        'protocolo': prot_txt,
        'emit': emitente,
        'consumidor': consumidor,
        'itens': itens,
        'v_prod': fmt_num(_txt(t, 'vProd'), 2),
        'v_desc': fmt_num(_txt(t, 'vDesc'), 2),
        'v_nf': fmt_num(_txt(t, 'vNF'), 2),
        'v_trib': v_trib or None,
        'pags': pags,
        'v_troco': v_troco or None,
        'compl': compl,
        'qrcode_url': qrcode_url,
        'url_chave': url_chave,
    }


# ---------------------------------------------------------------------------
# DESENHO DO CUPOM
# ---------------------------------------------------------------------------
class _Cupom:
    def __init__(self, dados, largura_mm=80, altura_mm=None):
        self.d = dados
        self.W = largura_mm * mm
        self.M = 3 * mm
        self.larg_util = self.W - 2 * self.M
        # Na 1ª passada (altura_mm=None) usa uma folha bem alta só para medir
        # o conteúdo; na 2ª passada desenha de verdade já na altura final.
        self.H = (altura_mm * mm) if altura_mm else 2000 * mm
        self.buf = io.BytesIO()
        self.c = canvas.Canvas(self.buf, pagesize=(self.W, self.H))
        self.y = 8 * mm  # distância do topo (a folha cresce pra baixo visualmente)

    # -- primitivas (origem do y no topo, convertida para coordenada do PDF) --
    def _conv(self, y):
        return self.H - y

    def _str(self, x, y, txt, fonte=FONTE, tam=8, alin='e'):
        txt = '' if txt is None else str(txt)
        self.c.setFont(fonte, tam)
        yy = self._conv(y)
        if alin == 'c':
            self.c.drawCentredString(x, yy, txt)
        elif alin == 'd':
            self.c.drawRightString(x, yy, txt)
        else:
            self.c.drawString(x, yy, txt)

    def _centro(self, txt, fonte=FONTE, tam=8):
        # quebra em várias linhas se não couber na largura da bobina
        for ln in _quebrar(txt, fonte, tam, self.larg_util):
            self._str(self.W / 2, self.y, ln, fonte, tam, 'c')
            self.y += tam * 0.42 * mm + 1.6 * mm

    def _linha_texto(self, txt, fonte=FONTE, tam=7.5, alin='e'):
        larg = self.larg_util
        x = self.M if alin == 'e' else (self.W / 2 if alin == 'c' else self.W - self.M)
        for ln in _quebrar(txt, fonte, tam, larg):
            self._str(x, self.y, ln, fonte, tam, alin)
            self.y += tam * 0.42 * mm + 1.4 * mm

    def _duas_colunas(self, esq, dir_, fonte=FONTE, tam=7.5, negrito_dir=False):
        fonte_dir = NEGRITO if negrito_dir else fonte
        passo = tam * 0.42 * mm + 1.4 * mm
        # reserva espaço para o valor da direita; o texto da esquerda quebra se precisar
        larg_esq = max(self.larg_util - stringWidth(str(dir_), fonte_dir, tam) - 2 * mm, 20 * mm)
        linhas = _quebrar(esq, fonte, tam, larg_esq) or ['']
        for ln in linhas[:-1]:
            self._str(self.M, self.y, ln, fonte, tam, 'e')
            self.y += passo
        self._str(self.M, self.y, linhas[-1], fonte, tam, 'e')
        self._str(self.W - self.M, self.y, dir_, fonte_dir, tam, 'd')
        self.y += passo

    def _separador(self, pontilhado=True):
        self.y += 1.4 * mm
        if pontilhado:
            self.c.setDash(1, 1)
        self.c.setLineWidth(0.4)
        self.c.line(self.M, self._conv(self.y), self.W - self.M, self._conv(self.y))
        self.c.setDash()
        self.y += 3.2 * mm

    def _espaco(self, h=2 * mm):
        self.y += h

    # -- blocos --
    def _cabecalho_emit(self):
        e = self.d['emit']
        self._centro(e['fantasia'] or e['nome'], NEGRITO, 9.5)
        if e['fantasia'] and e['nome'] != e['fantasia']:
            self._centro(e['nome'], FONTE, 6.5)
        self._centro(f"CNPJ/CPF: {e['doc']}" + (f"   IE: {e['ie']}" if e['ie'] else ''), FONTE, 6.5)
        if e['endereco']:
            self._linha_texto(e['endereco'] + (f" - {e['bairro']}" if e['bairro'] else ''), FONTE, 6.5, 'c')
        linha2 = ' - '.join(p for p in (e['municipio_uf'], e['cep']) if p)
        if linha2:
            self._linha_texto(linha2, FONTE, 6.5, 'c')
        if e['fone']:
            self._centro(f"Fone: {e['fone']}", FONTE, 6.5)
        if self.d['homologacao']:
            self._espaco(1 * mm)
            self._centro('EMITIDA EM AMBIENTE DE HOMOLOGAÇÃO', NEGRITO, 7)
            self._centro('SEM VALOR FISCAL', NEGRITO, 7)
        self._separador()

    def _dados_nfce(self):
        d = self.d
        self._centro('DOCUMENTO AUXILIAR DA NOTA FISCAL', NEGRITO, 7)
        self._centro('DE CONSUMIDOR ELETRÔNICA', NEGRITO, 7)
        self._espaco(0.8 * mm)
        if d['natureza']:
            self._centro(d['natureza'], FONTE, 6.5)
        self._separador()

    def _itens(self):
        self._str(self.M, self.y, '#', NEGRITO, 6.3)
        self._str(self.M + 5 * mm, self.y, 'CÓDIGO', NEGRITO, 6.3)
        self._str(self.W - self.M, self.y, 'DESCRIÇÃO DO PRODUTO', NEGRITO, 6.3, 'd')
        self.y += 3.6 * mm
        self._separador(pontilhado=False)

        for i, it in enumerate(self.d['itens'], start=1):
            cab = f"{i:03d} {it['codigo']}"
            self._str(self.M, self.y, cab, FONTE, 6.5)
            self.y += 3.3 * mm
            for ln in _quebrar(it['descricao'], FONTE, 7, self.larg_util):
                self._str(self.M, self.y, ln, FONTE, 7)
                self.y += 3.4 * mm
            qtd_un = f"{it['qtd']} {it['un']} x {it['vun']}"
            self._duas_colunas(qtd_un, f"R$ {it['vtot']}", FONTE, 6.8, negrito_dir=True)
            if it['vdesc']:
                self._duas_colunas('Desconto no item', f"-R$ {it['vdesc']}", FONTE, 6.5)
            self._espaco(0.6 * mm)
        self._separador()

    def _totais(self):
        d = self.d
        self._duas_colunas('QTD. TOTAL DE ITENS', str(len(d['itens'])), FONTE, 7.5)
        self._duas_colunas('VALOR TOTAL R$', d['v_prod'], FONTE, 8)
        if d['v_desc'] and d['v_desc'] != '0,00':
            self._duas_colunas('DESCONTOS R$', f"-{d['v_desc']}", FONTE, 8)
        self._duas_colunas('VALOR A PAGAR R$', d['v_nf'], NEGRITO, 10, negrito_dir=True)
        self._espaco(0.8 * mm)
        for p in d['pags']:
            self._duas_colunas(f"FORMA DE PAGAMENTO: {p['tipo']}", f"R$ {p['valor']}", FONTE, 7)
        if d['v_troco']:
            self._duas_colunas('TROCO R$', d['v_troco'], FONTE, 7)
        if d['v_trib']:
            self._espaco(0.6 * mm)
            self._linha_texto(f"Valor aprox. dos tributos: R$ {d['v_trib']} (Lei 12.741/2012)", FONTE, 6, 'c')
        self._separador()

    def _consumidor(self):
        c = self.d['consumidor']
        if c:
            self._centro('CONSUMIDOR', NEGRITO, 6.8)
            texto = c['nome'] + (f" - {c['doc']}" if c['doc'] else '')
            self._linha_texto(texto, FONTE, 6.8, 'c')
        else:
            self._centro('CONSUMIDOR NÃO IDENTIFICADO', FONTE, 6.8)
        self._separador()

    def _chave_qrcode(self):
        d = self.d
        self._centro(f"NFC-e nº {d['numero']}  Série {d['serie']}", NEGRITO, 7.5)
        self._centro(f"Emissão: {d['data_emissao']} {d['hora_emissao']}", FONTE, 7)
        self._espaco(1 * mm)

        chave = d['chave']
        if len(chave) == 44:
            self._linha_texto(fmt_chave(chave), FONTE, 6.5, 'c')
        self._espaco(1.5 * mm)

        conteudo_qr = d['qrcode_url'] or d['url_chave'] or chave
        if conteudo_qr:
            lado = 32 * mm
            widget = QrCodeWidget(conteudo_qr)
            b = widget.getBounds()
            w_nat, h_nat = b[2] - b[0], b[3] - b[1]
            d_draw = Drawing(lado, lado, transform=[lado / w_nat, 0, 0, lado / h_nat, 0, 0])
            d_draw.add(widget)
            renderPDF.draw(d_draw, self.c, (self.W - lado) / 2, self._conv(self.y) - lado)
            self.y += lado + 2 * mm

        self._centro('Consulte pela Chave de Acesso em', FONTE, 6.5)
        url_base = (d['url_chave'] or 'www.nfe.fazenda.gov.br/portal').strip()
        self._linha_texto(url_base, FONTE, 6.5, 'c')
        self._espaco(1 * mm)
        self._linha_texto(d['protocolo'], FONTE, 6, 'c')

    def _rodape(self):
        if self.d['compl']:
            self._separador()
            self._linha_texto(self.d['compl'], FONTE, 6.3, 'e')
        self._espaco(3 * mm)
        self._centro('Tributos aproximados conforme Lei Federal 12.741/2012', FONTE, 5.8)

    # -- montagem --
    def _desenhar_tudo(self):
        self._cabecalho_emit()
        self._dados_nfce()
        self._itens()
        self._totais()
        self._consumidor()
        self._chave_qrcode()
        self._rodape()

    def medir(self):
        """1ª passada: desenha numa folha alta só para descobrir a altura real."""
        self._desenhar_tudo()
        return self.y + 6 * mm

    def gerar(self):
        """2ª passada: a folha já nasce com a altura final (sem cortes)."""
        self._desenhar_tudo()
        self.c.showPage()
        self.c.save()
        return self.buf.getvalue()


def gerar_nfce(xml_bytes, largura_mm=80):
    """
    Recebe os bytes do XML da NFC-e e devolve (pdf_bytes, numero_da_nota).
    largura_mm: 80 (padrão) ou 58, conforme a bobina da impressora térmica.
    """
    if largura_mm not in (58, 80):
        raise NfceError('Largura de bobina inválida: use 58 ou 80 (mm).')
    try:
        root = _carregar_xml(xml_bytes)
    except NfceError:
        raise
    except Exception as e:
        raise NfceError(f'Não foi possível ler o XML: {e}') from e
    dados = extrair_dados_nfce(root)

    altura_mm = _Cupom(dados, largura_mm).medir() / mm
    pdf = _Cupom(dados, largura_mm, altura_mm=altura_mm).gerar()
    return pdf, (dados['numero'] or 'sem_numero')
