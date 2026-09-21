# -*- coding: utf-8 -*-
"""
danfe.py - Gera o DANFE (Documento Auxiliar da NF-e, modelo 55, retrato, A4)
em PDF a partir do XML da NF-e (arquivo nfeProc ou NFe).

Dependência: reportlab  (pip install reportlab)

Uso:
    from danfe import gerar_danfe, DanfeError
    pdf_bytes, numero = gerar_danfe(xml_bytes)
"""
import io
import re
import xml.etree.ElementTree as ET
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from reportlab.graphics.barcode import code128
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas


class DanfeError(ValueError):
    """Erro de negócio (XML inválido, não é NF-e modelo 55, etc.)."""


# ---------------------------------------------------------------------------
# 1. LEITURA E TRATAMENTO DO XML
# ---------------------------------------------------------------------------
def _carregar_xml(xml_bytes):
    # BOM UTF-8 e espaços/quebras antes de "<?xml" derrubam o parser
    if xml_bytes.startswith(b'\xef\xbb\xbf'):
        xml_bytes = xml_bytes[3:]
    xml_bytes = xml_bytes.strip()

    if not xml_bytes:
        raise DanfeError('O arquivo XML está vazio.')
    # Proteção contra "billion laughs" / entidades externas
    if b'<!ENTITY' in xml_bytes or b'<!DOCTYPE' in xml_bytes:
        raise DanfeError('XML com DTD/entidades não é aceito.')

    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as e:
        raise DanfeError(f'O arquivo não é um XML válido: {e}')

    # Remove o namespace (http://www.portalfiscal.inf.br/nfe) de todas as tags
    for el in root.iter():
        if isinstance(el.tag, str) and '}' in el.tag:
            el.tag = el.tag.split('}', 1)[1]
    return root


def _limpar(s):
    """Mantém somente caracteres que a fonte Helvetica (cp1252) consegue desenhar."""
    s = re.sub(r'[\x00-\x08\x0b-\x1f]', '', s)
    return s.encode('cp1252', 'replace').decode('cp1252')


def _txt(no, caminho, padrao=''):
    if no is None:
        return padrao
    el = no.find(caminho)
    if el is None or el.text is None:
        return padrao
    return _limpar(el.text.strip()) or padrao


# ---------------------------------------------------------------------------
# 2. FORMATADORES
# ---------------------------------------------------------------------------
def _dec(v):
    try:
        d = Decimal(str(v).strip())
    except (InvalidOperation, ValueError):
        return None
    return d if d.is_finite() else None


def fmt_num(v, casas=2, vazio=''):
    d = v if isinstance(v, Decimal) else _dec(v)
    if d is None:
        return vazio
    d = d.quantize(Decimal(1).scaleb(-casas), rounding=ROUND_HALF_UP)
    s = format(d, f',.{casas}f')
    return s.replace(',', 'X').replace('.', ',').replace('X', '.')


def fmt_doc(v):
    n = re.sub(r'\D', '', v or '')
    if len(n) == 14:
        return f'{n[:2]}.{n[2:5]}.{n[5:8]}/{n[8:12]}-{n[12:]}'
    if len(n) == 11:
        return f'{n[:3]}.{n[3:6]}.{n[6:9]}-{n[9:]}'
    return v or ''


def fmt_cep(v):
    n = re.sub(r'\D', '', v or '')
    return f'{n[:5]}-{n[5:]}' if len(n) == 8 else (v or '')


def fmt_fone(v):
    n = re.sub(r'\D', '', v or '')
    if len(n) == 11:
        return f'({n[:2]}) {n[2:7]}-{n[7:]}'
    if len(n) == 10:
        return f'({n[:2]}) {n[2:6]}-{n[6:]}'
    return v or ''


def fmt_data(v):
    m = re.match(r'(\d{4})-(\d{2})-(\d{2})', v or '')
    return f'{m[3]}/{m[2]}/{m[1]}' if m else (v or '')


def fmt_hora(v):
    m = re.search(r'T(\d{2}:\d{2}:\d{2})', v or '')
    return m[1] if m else ''


def fmt_chave(ch):
    return ' '.join(ch[i:i + 4] for i in range(0, len(ch), 4))


def fmt_numero_nf(n):
    n = re.sub(r'\D', '', n or '').zfill(9)
    return f'{n[:3]}.{n[3:6]}.{n[6:]}'


# ---------------------------------------------------------------------------
# 3. EXTRAÇÃO DOS DADOS
# ---------------------------------------------------------------------------
def _endereco(end):
    lgr = _txt(end, 'xLgr')
    nro = _txt(end, 'nro')
    cpl = _txt(end, 'xCpl')
    linha = lgr
    if nro:
        linha = f'{linha}, {nro}' if linha else nro
    if cpl:
        linha = f'{linha} - {cpl}' if linha else cpl
    return {
        'logradouro': linha,
        'bairro': _txt(end, 'xBairro'),
        'cep': fmt_cep(_txt(end, 'CEP')),
        'municipio': _txt(end, 'xMun'),
        'uf': _txt(end, 'UF'),
        'fone': fmt_fone(_txt(end, 'fone')),
    }


def _soma(nos, tag):
    total, achou = Decimal(0), False
    for n in nos:
        d = _dec(_txt(n, tag))
        if d is not None:
            total += d
            achou = True
    return total if achou else None


MOD_FRETE = {
    '0': '0-Emitente', '1': '1-Destinatário', '2': '2-Terceiros',
    '3': '3-Próprio Remet.', '4': '4-Próprio Dest.', '9': '9-Sem Frete',
}


def extrair_dados(root):
    inf = root if root.tag == 'infNFe' else root.find('.//infNFe')
    if inf is None:
        raise DanfeError(
            'Este XML não é uma NF-e (elemento <infNFe> não encontrado). '
            'Envie o XML da nota fiscal eletrônica modelo 55.')

    ide = inf.find('ide')
    modelo = _txt(ide, 'mod')
    if modelo and modelo != '55':
        raise DanfeError(
            f'Este XML é de um documento modelo {modelo} (ex.: NFC-e). '
            'Este conversor gera DANFE somente para NF-e modelo 55.')

    prot = root.find('.//protNFe/infProt')
    chave = _txt(prot, 'chNFe') or re.sub(r'\D', '', inf.get('Id', ''))

    # ---- emitente
    emit = inf.find('emit')
    e_end = _endereco(emit.find('enderEmit') if emit is not None else None)
    linhas_end = [l for l in (
        e_end['logradouro'],
        ' - '.join(p for p in (e_end['bairro'], f"CEP {e_end['cep']}" if e_end['cep'] else '') if p),
        ' - '.join(p for p in (e_end['municipio'], e_end['uf']) if p),
        f"Fone: {e_end['fone']}" if e_end['fone'] else '',
    ) if l]
    emitente = {
        'nome': _txt(emit, 'xNome'),
        'doc': fmt_doc(_txt(emit, 'CNPJ') or _txt(emit, 'CPF')),
        'ie': _txt(emit, 'IE'),
        'iest': _txt(emit, 'IEST'),
        'im': _txt(emit, 'IM'),
        'linhas_end': linhas_end,
    }

    # ---- destinatário
    dest = inf.find('dest')
    d_end = _endereco(dest.find('enderDest') if dest is not None else None)
    destinatario = {
        'nome': _txt(dest, 'xNome'),
        'doc': fmt_doc(_txt(dest, 'CNPJ') or _txt(dest, 'CPF') or _txt(dest, 'idEstrangeiro')),
        'ie': _txt(dest, 'IE'),
        **d_end,
    }

    # ---- identificação
    dh_emi = _txt(ide, 'dhEmi') or _txt(ide, 'dEmi')
    dh_sai = _txt(ide, 'dhSaiEnt') or _txt(ide, 'dSaiEnt')
    dh_rec = _txt(prot, 'dhRecbto')
    c_stat = _txt(prot, 'cStat')
    if prot is not None and _txt(prot, 'nProt'):
        prot_txt = f"{_txt(prot, 'nProt')} - {fmt_data(dh_rec)} {fmt_hora(dh_rec)}".strip()
        if c_stat and c_stat not in ('100', '150'):
            prot_txt += f' (cStat {c_stat})'
    else:
        prot_txt = 'SEM PROTOCOLO DE AUTORIZAÇÃO'

    # ---- totais
    t = inf.find('total/ICMSTot')
    def tv(tag, casas=2):
        return fmt_num(_txt(t, tag), casas, '0,00')
    totais = {
        'bc_icms': tv('vBC'), 'v_icms': tv('vICMS'),
        'bc_st': tv('vBCST'), 'v_st': tv('vST'),
        'v_prod': tv('vProd'), 'v_frete': tv('vFrete'), 'v_seg': tv('vSeg'),
        'v_desc': tv('vDesc'), 'v_outro': tv('vOutro'), 'v_ipi': tv('vIPI'),
        'v_nf': tv('vNF'), 'v_tot_trib': _txt(t, 'vTotTrib'),
    }
    iss = inf.find('total/ISSQNtot')
    issqn = None
    if iss is not None:
        issqn = {
            'v_serv': fmt_num(_txt(iss, 'vServ'), 2, '0,00'),
            'bc': fmt_num(_txt(iss, 'vBC'), 2, '0,00'),
            'v_iss': fmt_num(_txt(iss, 'vISS'), 2, '0,00'),
        }

    # ---- transporte
    tr = inf.find('transp')
    transporta = tr.find('transporta') if tr is not None else None
    veic = tr.find('veicTransp') if tr is not None else None
    vols = tr.findall('vol') if tr is not None else []
    q_vol = _soma(vols, 'qVol')
    transporte = {
        'frete': MOD_FRETE.get(_txt(tr, 'modFrete'), _txt(tr, 'modFrete')),
        'nome': _txt(transporta, 'xNome'),
        'doc': fmt_doc(_txt(transporta, 'CNPJ') or _txt(transporta, 'CPF')),
        'endereco': _txt(transporta, 'xEnder'),
        'municipio': _txt(transporta, 'xMun'),
        'uf': _txt(transporta, 'UF'),
        'ie': _txt(transporta, 'IE'),
        'antt': _txt(veic, 'RNTC'),
        'placa': _txt(veic, 'placa'),
        'uf_veic': _txt(veic, 'UF'),
        'qtd': fmt_num(q_vol, 0) if q_vol is not None else '',
        'especie': _txt(vols[0], 'esp') if vols else '',
        'marca': _txt(vols[0], 'marca') if vols else '',
        'numeracao': _txt(vols[0], 'nVol') if vols else '',
        'peso_b': fmt_num(_soma(vols, 'pesoB'), 3) if _soma(vols, 'pesoB') is not None else '',
        'peso_l': fmt_num(_soma(vols, 'pesoL'), 3) if _soma(vols, 'pesoL') is not None else '',
    }

    # ---- duplicatas
    dups = [{
        'num': _txt(d, 'nDup'),
        'venc': fmt_data(_txt(d, 'dVenc')),
        'valor': fmt_num(_txt(d, 'vDup'), 2, '0,00'),
    } for d in inf.findall('cobr/dup')]

    # ---- itens
    itens = []
    for det in inf.findall('det'):
        prod = det.find('prod')
        imp = det.find('imposto')
        grp = imp.find('ICMS') if imp is not None else None
        icms = list(grp)[0] if grp is not None and len(grp) else None
        ipi = imp.find('IPI/IPITrib') if imp is not None else None
        itens.append({
            'codigo': _txt(prod, 'cProd'),
            'descricao': _txt(prod, 'xProd'),
            'inf_ad': _txt(det, 'infAdProd'),
            'ncm': _txt(prod, 'NCM'),
            'ocst': _txt(icms, 'orig') + (_txt(icms, 'CST') or _txt(icms, 'CSOSN')),
            'cfop': _txt(prod, 'CFOP'),
            'un': _txt(prod, 'uCom'),
            'qtd': fmt_num(_txt(prod, 'qCom'), 4),
            'vun': fmt_num(_txt(prod, 'vUnCom'), 4),
            'vtot': fmt_num(_txt(prod, 'vProd'), 2),
            'bc': fmt_num(_txt(icms, 'vBC'), 2, '0,00'),
            'vicms': fmt_num(_txt(icms, 'vICMS'), 2, '0,00'),
            'vipi': fmt_num(_txt(ipi, 'vIPI'), 2, '0,00'),
            'aliq_icms': fmt_num(_txt(icms, 'pICMS'), 2, '0,00'),
            'aliq_ipi': fmt_num(_txt(ipi, 'pIPI'), 2, '0,00'),
        })

    # ---- informações adicionais
    compl = _txt(inf, 'infAdic/infCpl')
    v_trib = _dec(totais['v_tot_trib'])
    if v_trib and v_trib > 0 and 'ributo' not in compl:
        extra = f"Valor aproximado dos tributos: R$ {fmt_num(v_trib)}"
        compl = f'{compl}\n{extra}' if compl else extra

    return {
        'chave': chave,
        'numero': _txt(ide, 'nNF'),
        'serie': _txt(ide, 'serie'),
        'tp_nf': _txt(ide, 'tpNF'),
        'natureza': _txt(ide, 'natOp'),
        'data_emissao': fmt_data(dh_emi),
        'data_saida': fmt_data(dh_sai),
        'hora_saida': fmt_hora(dh_sai),
        'protocolo': prot_txt,
        'homologacao': _txt(ide, 'tpAmb') == '2',
        'emit': emitente,
        'dest': destinatario,
        'totais': totais,
        'issqn': issqn,
        'transp': transporte,
        'dups': dups,
        'itens': itens,
        'compl': compl,
        'fisco': _txt(inf, 'infAdic/infAdFisco'),
    }


# ---------------------------------------------------------------------------
# 4. DESENHO DO PDF
# ---------------------------------------------------------------------------
PAGE_W, PAGE_H = A4
M = 5 * mm
LARG = PAGE_W - 2 * M            # ~200 mm
LIMITE = PAGE_H - M              # limite inferior (coordenada "de cima para baixo")
H_CAB = 32 * mm                  # altura do bloco Emitente / DANFE / Chave
H_CAMPO = 7.5 * mm
H_TH = 6.5 * mm                  # cabeçalho da tabela de itens
LH = 2.6 * mm                    # altura de linha nos itens
FONTE, NEGRITO = 'Helvetica', 'Helvetica-Bold'

COLS_MM = [14, 52, 13, 9, 8, 7, 13, 14, 15, 14, 12, 11, 9, 9]
COLS = [c * mm for c in COLS_MM]
COL_X = [sum(COLS[:i]) for i in range(len(COLS))]
COL_ROT = [('CÓDIGO',), ('DESCRIÇÃO DO PRODUTO / SERVIÇO',), ('NCM/SH',), ('O/CST',),
           ('CFOP',), ('UN',), ('QUANT.',), ('V. UNIT.',), ('V. TOTAL',),
           ('BC ICMS',), ('V. ICMS',), ('V. IPI',), ('ALÍQ.', 'ICMS'), ('ALÍQ.', 'IPI')]
COL_ALIN = ['e', 'e', 'c', 'c', 'c', 'c', 'd', 'd', 'd', 'd', 'd', 'd', 'd', 'd']
COL_CHAVE = ['codigo', None, 'ncm', 'ocst', 'cfop', 'un', 'qtd', 'vun', 'vtot',
             'bc', 'vicms', 'vipi', 'aliq_icms', 'aliq_ipi']

W_COMPL, W_FISCO = 140 * mm, 60 * mm
LH_AD = 2.7 * mm


def _quebrar(txt, fonte, tam, larg):
    """Quebra o texto em linhas que caibam em 'larg' (inclusive palavras gigantes)."""
    linhas = []
    for par in (txt or '').replace('\r', '').split('\n'):
        atual = ''
        for palavra in par.split(' '):
            while stringWidth(palavra, fonte, tam) > larg and len(palavra) > 1:
                n = len(palavra)
                while n > 1 and stringWidth(palavra[:n], fonte, tam) > larg:
                    n -= 1
                if atual:
                    linhas.append(atual)
                    atual = ''
                linhas.append(palavra[:n])
                palavra = palavra[n:]
            teste = f'{atual} {palavra}' if atual else palavra
            if stringWidth(teste, fonte, tam) <= larg:
                atual = teste
            else:
                linhas.append(atual)
                atual = palavra
        linhas.append(atual)
    return linhas


class _Danfe:
    def __init__(self, dados, total_paginas=1):
        self.d = dados
        self.total = total_paginas
        self.pagina = 0
        self.y_corpo = 0
        self.buf = io.BytesIO()
        self.c = canvas.Canvas(self.buf, pagesize=A4)
        self.c.setTitle(f"DANFE - NF-e {dados['numero']}")
        self.c.setSubject('Documento Auxiliar da Nota Fiscal Eletrônica')

    # ---------------- primitivas ----------------
    def _rect(self, x, y, w, h):
        self.c.rect(x, PAGE_H - y - h, w, h)

    def _str(self, x, y, txt, fonte=FONTE, tam=8, alin='e'):
        self.c.setFont(fonte, tam)
        yy = PAGE_H - y
        if alin == 'd':
            self.c.drawRightString(x, yy, txt)
        elif alin == 'c':
            self.c.drawCentredString(x, yy, txt)
        else:
            self.c.drawString(x, yy, txt)

    @staticmethod
    def _ajustar(txt, fonte, tam, larg, minimo=4.5):
        while tam > minimo and stringWidth(txt, fonte, tam) > larg:
            tam -= 0.25
        if stringWidth(txt, fonte, tam) > larg:
            while len(txt) > 1 and stringWidth(txt + '...', fonte, tam) > larg:
                txt = txt[:-1]
            txt += '...'
        return txt, tam

    def _campo(self, x, y, w, h, rotulo, valor, alin='e', tam=8, negrito=False):
        self._rect(x, y, w, h)
        self._str(x + 0.8 * mm, y + 2.1 * mm, rotulo, FONTE, 5.2)
        fonte = NEGRITO if negrito else FONTE
        txt, t = self._ajustar(valor or '', fonte, tam, w - 1.6 * mm)
        base = y + h - 1.3 * mm
        if alin == 'd':
            self._str(x + w - 0.8 * mm, base, txt, fonte, t, 'd')
        elif alin == 'c':
            self._str(x + w / 2, base, txt, fonte, t, 'c')
        else:
            self._str(x + 0.8 * mm, base, txt, fonte, t)

    def _linha(self, y, campos, h=H_CAMPO):
        """campos: (largura_mm, rotulo, valor[, alin[, negrito]])"""
        x = M
        for cp in campos:
            w = cp[0] * mm
            alin = cp[3] if len(cp) > 3 else 'e'
            neg = cp[4] if len(cp) > 4 else False
            self._campo(x, y, w, h, cp[1], cp[2], alin, 8, neg)
            x += w
        return y + h

    def _titulo(self, y, txt):
        self._str(M, y + 2.4 * mm, txt, NEGRITO, 6.5)
        return y + 3 * mm

    # ---------------- página ----------------
    def _nova_pagina(self):
        if self.pagina > 0:
            self.c.showPage()
        self.pagina += 1
        c = self.c
        c.setLineWidth(0.5)
        c.setStrokeColorRGB(0, 0, 0)
        c.setFillColorRGB(0, 0, 0)
        if self.d['homologacao']:
            c.saveState()
            c.setFillColorRGB(0.88, 0.88, 0.88)
            c.setFont(NEGRITO, 46)
            c.translate(PAGE_W / 2, PAGE_H / 2)
            c.rotate(50)
            c.drawCentredString(0, 0, 'SEM VALOR FISCAL')
            c.restoreState()

    def _canhoto(self, y):
        d, e, ds = self.d, self.d['emit'], self.d['dest']
        w_nf = 40 * mm
        w_txt = LARG - w_nf
        h1, h2 = 10 * mm, 10 * mm
        self._rect(M, y, w_txt, h1)
        texto = (f"RECEBEMOS DE {e['nome']} OS PRODUTOS E/OU SERVIÇOS CONSTANTES DA NOTA FISCAL "
                 f"ELETRÔNICA INDICADA ABAIXO. EMISSÃO: {d['data_emissao']}  "
                 f"VALOR TOTAL: R$ {d['totais']['v_nf']}  DESTINATÁRIO: {ds['nome']}")
        for i, ln in enumerate(_quebrar(texto, FONTE, 6.5, w_txt - 2 * mm)[:3]):
            self._str(M + 1 * mm, y + 3 * mm + i * 2.8 * mm, ln, FONTE, 6.5)
        self._campo(M, y + h1, 40 * mm, h2, 'DATA DE RECEBIMENTO', '')
        self._campo(M + 40 * mm, y + h1, w_txt - 40 * mm, h2, 'IDENTIFICAÇÃO E ASSINATURA DO RECEBEDOR', '')
        xn = M + w_txt
        self._rect(xn, y, w_nf, h1 + h2)
        self._str(xn + w_nf / 2, y + 6 * mm, 'NF-e', NEGRITO, 11, 'c')
        self._str(xn + w_nf / 2, y + 11 * mm, f"Nº {fmt_numero_nf(d['numero'])}", NEGRITO, 8.5, 'c')
        self._str(xn + w_nf / 2, y + 15 * mm, f"SÉRIE {d['serie']}", NEGRITO, 8.5, 'c')
        y += h1 + h2 + 1.5 * mm
        self.c.setDash(2, 2)
        self.c.setLineWidth(0.3)
        self.c.line(M, PAGE_H - y, M + LARG, PAGE_H - y)
        self.c.setDash()
        self.c.setLineWidth(0.5)
        return y + 1.5 * mm

    def _cabecalho(self, y):
        d, e = self.d, self.d['emit']
        w1, w2 = 80 * mm, 38 * mm
        w3 = LARG - w1 - w2
        x1, x2, x3 = M, M + w1, M + w1 + w2
        for x, w in ((x1, w1), (x2, w2), (x3, w3)):
            self._rect(x, y, w, H_CAB)

        # --- emitente
        self._str(x1 + 1 * mm, y + 2.2 * mm, 'IDENTIFICAÇÃO DO EMITENTE', FONTE, 5.2)
        ly = y + 7 * mm
        for ln in _quebrar(e['nome'], NEGRITO, 9, w1 - 3 * mm)[:3]:
            self._str(x1 + w1 / 2, ly, ln, NEGRITO, 9, 'c')
            ly += 3.6 * mm
        ly += 0.6 * mm
        for ln in e['linhas_end'][:5]:
            txt, t = self._ajustar(ln, FONTE, 7, w1 - 3 * mm)
            self._str(x1 + w1 / 2, ly, txt, FONTE, t, 'c')
            ly += 3 * mm

        # --- DANFE / número / série / folha
        cx = x2 + w2 / 2
        self._str(cx, y + 7 * mm, 'DANFE', NEGRITO, 13, 'c')
        self._str(cx, y + 10.5 * mm, 'Documento Auxiliar da', FONTE, 6, 'c')
        self._str(cx, y + 13 * mm, 'Nota Fiscal Eletrônica', FONTE, 6, 'c')
        self._str(x2 + 2 * mm, y + 17.5 * mm, '0 - ENTRADA', FONTE, 6.5)
        self._str(x2 + 2 * mm, y + 20.5 * mm, '1 - SAÍDA', FONTE, 6.5)
        self._rect(x2 + w2 - 9 * mm, y + 15.2 * mm, 5.5 * mm, 5.5 * mm)
        self._str(x2 + w2 - 6.25 * mm, y + 19.5 * mm, d['tp_nf'], NEGRITO, 9, 'c')
        self._str(cx, y + 24.5 * mm, f"Nº {fmt_numero_nf(d['numero'])}", NEGRITO, 8, 'c')
        self._str(cx, y + 27.5 * mm, f"SÉRIE {d['serie']}", NEGRITO, 7.5, 'c')
        self._str(cx, y + 30.5 * mm, f"FOLHA {self.pagina}/{self.total}", NEGRITO, 7.5, 'c')

        # --- código de barras + chave
        chave = d['chave']
        if len(chave) == 44 and chave.isdigit():
            alt = 12 * mm
            bw = 0.26 * mm
            bc = code128.Code128(chave, barHeight=alt, barWidth=bw, quiet=False)
            disp = w3 - 4 * mm
            if bc.width > disp:
                bc = code128.Code128(chave, barHeight=alt, barWidth=bw * disp / bc.width, quiet=False)
            bc.drawOn(self.c, x3 + (w3 - bc.width) / 2, PAGE_H - (y + 2.5 * mm + alt))
        self._campo(x3, y + 16 * mm, w3, 8 * mm, 'CHAVE DE ACESSO', fmt_chave(chave), 'c', 8, True)
        self._str(x3 + w3 / 2, y + 27 * mm, 'Consulta de autenticidade no portal nacional da NF-e', FONTE, 6, 'c')
        self._str(x3 + w3 / 2, y + 30 * mm, 'www.nfe.fazenda.gov.br/portal ou no site da Sefaz Autorizadora', FONTE, 6, 'c')
        return y + H_CAB

    def _tabela_cabecalho(self, y):
        y = self._titulo(y, 'DADOS DOS PRODUTOS / SERVIÇOS')
        for i, (w, rot) in enumerate(zip(COLS, COL_ROT)):
            x = M + COL_X[i]
            self._rect(x, y, w, H_TH)
            for k, ln in enumerate(rot):
                base = y + H_TH / 2 + (k - (len(rot) - 1) / 2) * 2.4 * mm + 0.8 * mm
                self._str(x + w / 2, base, ln, NEGRITO, 5, 'c')
        self.y_corpo = y + H_TH
        return y + H_TH

    def _linha_item(self, y, it, linhas, h):
        for k, ln in enumerate(linhas):
            self._str(M + COL_X[1] + 1 * mm, y + 2.2 * mm + k * LH, ln, FONTE, 6)
        for i, chave in enumerate(COL_CHAVE):
            if chave is None or not it[chave]:
                continue
            w, x = COLS[i], M + COL_X[i]
            txt, t = self._ajustar(it[chave], FONTE, 6, w - 1.6 * mm)
            base = y + 2.2 * mm
            if COL_ALIN[i] == 'd':
                self._str(x + w - 0.8 * mm, base, txt, FONTE, t, 'd')
            elif COL_ALIN[i] == 'c':
                self._str(x + w / 2, base, txt, FONTE, t, 'c')
            else:
                self._str(x + 0.8 * mm, base, txt, FONTE, t)
        self.c.setLineWidth(0.25)
        self.c.setStrokeColorRGB(0.6, 0.6, 0.6)
        self.c.line(M, PAGE_H - (y + h), M + LARG, PAGE_H - (y + h))
        self.c.setStrokeColorRGB(0, 0, 0)
        self.c.setLineWidth(0.5)
        return y + h

    def _fechar_tabela(self, fim):
        topo = PAGE_H - self.y_corpo
        base = PAGE_H - fim
        for x in COL_X + [LARG]:
            self.c.line(M + x, topo, M + x, base)
        self.c.line(M, base, M + LARG, base)

    # ---------------- blocos da 1ª página ----------------
    def _blocos_iniciais(self, y):
        d, e, ds, t, tr = self.d, self.d['emit'], self.d['dest'], self.d['totais'], self.d['transp']

        y = self._linha(y, [(110, 'NATUREZA DA OPERAÇÃO', d['natureza']),
                            (90, 'PROTOCOLO DE AUTORIZAÇÃO DE USO', d['protocolo'], 'c')])
        y = self._linha(y, [(67, 'INSCRIÇÃO ESTADUAL', e['ie']),
                            (66, 'INSCRIÇÃO ESTADUAL DO SUBST. TRIBUTÁRIO', e['iest']),
                            (67, 'CNPJ / CPF', e['doc'])])
        y += 1 * mm

        y = self._titulo(y, 'DESTINATÁRIO / REMETENTE')
        y = self._linha(y, [(110, 'NOME / RAZÃO SOCIAL', ds['nome']),
                            (50, 'CNPJ / CPF', ds['doc']),
                            (40, 'DATA DA EMISSÃO', d['data_emissao'], 'c')])
        y = self._linha(y, [(100, 'ENDEREÇO', ds['logradouro']),
                            (45, 'BAIRRO / DISTRITO', ds['bairro']),
                            (25, 'CEP', ds['cep']),
                            (30, 'DATA ENTRADA / SAÍDA', d['data_saida'], 'c')])
        y = self._linha(y, [(80, 'MUNICÍPIO', ds['municipio']),
                            (40, 'FONE / FAX', ds['fone']),
                            (10, 'UF', ds['uf'], 'c'),
                            (40, 'INSCRIÇÃO ESTADUAL', ds['ie']),
                            (30, 'HORA ENTRADA / SAÍDA', d['hora_saida'], 'c')])
        y += 1 * mm

        if d['dups']:
            y = self._titulo(y, 'FATURA / DUPLICATAS')
            dups = d['dups'][:24]
            for i in range(0, len(dups), 4):
                x = M
                for dp in dups[i:i + 4]:
                    self._campo(x, y, 50 * mm, H_CAMPO, f"Nº {dp['num']}  |  VENC. {dp['venc']}",
                                f"R$ {dp['valor']}", 'd')
                    x += 50 * mm
                y += H_CAMPO
            y += 1 * mm

        y = self._titulo(y, 'CÁLCULO DO IMPOSTO')
        y = self._linha(y, [(40, 'BASE DE CÁLCULO DO ICMS', t['bc_icms'], 'd'),
                            (40, 'VALOR DO ICMS', t['v_icms'], 'd'),
                            (40, 'BASE DE CÁLCULO DO ICMS ST', t['bc_st'], 'd'),
                            (40, 'VALOR DO ICMS ST', t['v_st'], 'd'),
                            (40, 'VALOR TOTAL DOS PRODUTOS', t['v_prod'], 'd')])
        y = self._linha(y, [(33, 'VALOR DO FRETE', t['v_frete'], 'd'),
                            (33, 'VALOR DO SEGURO', t['v_seg'], 'd'),
                            (33, 'DESCONTO', t['v_desc'], 'd'),
                            (33, 'OUTRAS DESPESAS ACESSÓRIAS', t['v_outro'], 'd'),
                            (34, 'VALOR TOTAL DO IPI', t['v_ipi'], 'd'),
                            (34, 'VALOR TOTAL DA NOTA', t['v_nf'], 'd', True)])
        y += 1 * mm

        y = self._titulo(y, 'TRANSPORTADOR / VOLUMES TRANSPORTADOS')
        y = self._linha(y, [(70, 'NOME / RAZÃO SOCIAL', tr['nome']),
                            (38, 'FRETE', tr['frete']),
                            (22, 'CÓDIGO ANTT', tr['antt']),
                            (22, 'PLACA DO VEÍCULO', tr['placa']),
                            (8, 'UF', tr['uf_veic'], 'c'),
                            (40, 'CNPJ / CPF', tr['doc'])])
        y = self._linha(y, [(90, 'ENDEREÇO', tr['endereco']),
                            (60, 'MUNICÍPIO', tr['municipio']),
                            (10, 'UF', tr['uf'], 'c'),
                            (40, 'INSCRIÇÃO ESTADUAL', tr['ie'])])
        y = self._linha(y, [(30, 'QUANTIDADE', tr['qtd'], 'd'),
                            (40, 'ESPÉCIE', tr['especie']),
                            (40, 'MARCA', tr['marca']),
                            (40, 'NUMERAÇÃO', tr['numeracao']),
                            (25, 'PESO BRUTO', tr['peso_b'], 'd'),
                            (25, 'PESO LÍQUIDO', tr['peso_l'], 'd')])
        y += 1 * mm

        if d['issqn']:
            y = self._titulo(y, 'CÁLCULO DO ISSQN')
            y = self._linha(y, [(50, 'INSCRIÇÃO MUNICIPAL', e['im']),
                                (50, 'VALOR TOTAL DOS SERVIÇOS', d['issqn']['v_serv'], 'd'),
                                (50, 'BASE DE CÁLCULO DO ISSQN', d['issqn']['bc'], 'd'),
                                (50, 'VALOR TOTAL DO ISSQN', d['issqn']['v_iss'], 'd')])
            y += 1 * mm
        return y

    # ---------------- dados adicionais ----------------
    def _prep_adicionais(self):
        # h_box máximo: cabe numa página com o cabeçalho
        h_max = LIMITE - (M + H_CAB + 10 * mm)
        l_compl = _quebrar(self.d['compl'], FONTE, 6.5, W_COMPL - 2 * mm)
        l_fisco = _quebrar(self.d['fisco'], FONTE, 6.5, W_FISCO - 2 * mm)
        n = max(len(l_compl), len(l_fisco), 1)
        h_box = max(28 * mm, 5 * mm + n * LH_AD)
        h_box = min(h_box, h_max)
        max_lin = int((h_box - 5 * mm) / LH_AD)
        return l_compl[:max_lin], l_fisco[:max_lin], h_box

    def _desenhar_adicionais(self, y_box, l_compl, l_fisco, h_box):
        self._str(M, y_box - 0.8 * mm, 'DADOS ADICIONAIS', NEGRITO, 6.5)
        self._rect(M, y_box, W_COMPL, h_box)
        self._rect(M + W_COMPL, y_box, W_FISCO, h_box)
        self._str(M + 0.8 * mm, y_box + 2.1 * mm, 'INFORMAÇÕES COMPLEMENTARES', FONTE, 5.2)
        self._str(M + W_COMPL + 0.8 * mm, y_box + 2.1 * mm, 'RESERVADO AO FISCO', FONTE, 5.2)
        for i, ln in enumerate(l_compl):
            self._str(M + 1 * mm, y_box + 5.3 * mm + i * LH_AD, ln, FONTE, 6.5)
        for i, ln in enumerate(l_fisco):
            self._str(M + W_COMPL + 1 * mm, y_box + 5.3 * mm + i * LH_AD, ln, FONTE, 6.5)

    # ---------------- montagem ----------------
    def gerar(self):
        d = self.d
        itens = d['itens']
        l_compl, l_fisco, h_ad = self._prep_adicionais()
        reserva_ad = 3 * mm + h_ad + 1 * mm

        # 1ª página
        self._nova_pagina()
        y = self._canhoto(M)
        y = self._cabecalho(y)
        y = self._blocos_iniciais(y)
        y = self._tabela_cabecalho(y)
        y_tab1 = y
        y_tabn = M + H_CAB + 1 * mm + 3 * mm + H_TH     # início do corpo nas demais páginas

        # quebra dos itens em páginas
        larg_desc = COLS[1] - 2 * mm
        linhas, alturas = [], []
        for it in itens:
            txt = it['descricao'] + ('\n' + it['inf_ad'] if it['inf_ad'] else '')
            ls = _quebrar(txt, FONTE, 6, larg_desc)
            max_lin = int((LIMITE - y_tabn - 2 * mm) / LH)
            ls = ls[:max_lin]
            linhas.append(ls)
            alturas.append(len(ls) * LH + 1.8 * mm)

        paginas, usado, disp = [[]], 0, LIMITE - y_tab1
        for i, h in enumerate(alturas):
            if usado + h > disp and paginas[-1]:
                paginas.append([])
                usado, disp = 0, LIMITE - y_tabn
            paginas[-1].append(i)
            usado += h
        ad_cabe = usado + reserva_ad <= disp

        # desenho
        for n, idxs in enumerate(paginas):
            if n > 0:
                self._nova_pagina()
                y = self._cabecalho(M)
                y = self._tabela_cabecalho(y + 1 * mm)
            for i in idxs:
                y = self._linha_item(y, itens[i], linhas[i], alturas[i])
            ultima = n == len(paginas) - 1
            if ultima and ad_cabe:
                y_box = LIMITE - h_ad
                self._fechar_tabela(y_box - 4 * mm)
                self._desenhar_adicionais(y_box, l_compl, l_fisco, h_ad)
            else:
                self._fechar_tabela(LIMITE)

        if not ad_cabe:
            self._nova_pagina()
            y = self._cabecalho(M)
            self._desenhar_adicionais(y + 5 * mm, l_compl, l_fisco, h_ad)

        self.c.save()
        return self.buf.getvalue(), self.pagina


def gerar_danfe(xml_bytes):
    """Recebe os bytes do XML da NF-e e devolve (pdf_bytes, numero_da_nota)."""
    dados = extrair_dados(_carregar_xml(xml_bytes))
    pdf, paginas = _Danfe(dados, 1).gerar()
    if paginas != 1:                      # 2ª passada para imprimir "FOLHA x/total" correto
        pdf, _ = _Danfe(dados, paginas).gerar()
    return pdf, (dados['numero'] or 'sem_numero')
