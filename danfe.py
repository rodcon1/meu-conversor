# -*- coding: utf-8 -*-
"""
danfe.py - Gera o DANFE (Documento Auxiliar da NF-e, modelo 55) em PDF A4
a partir do XML da NF-e (arquivo nfeProc ou NFe).

Módulo autônomo: NÃO importa nfce.py (e vice-versa), para que um problema
em uma ferramenta nunca afete a outra.

Uso:
    from danfe import gerar_danfe, DanfeError
    pdf_bytes, numero = gerar_danfe(xml_bytes)
"""
import io
import xml.etree.ElementTree as ET
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from reportlab.graphics.barcode import code128
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas


class DanfeError(Exception):
    """Erro de negócio do DANFE (XML inválido, modelo errado etc.)."""


FONTE = 'Helvetica'
NEGRITO = 'Helvetica-Bold'

MOD_FRETE = {'0': '0-Emitente', '1': '1-Destinatário', '2': '2-Terceiros',
             '3': '3-Próprio rem.', '4': '4-Próprio dest.', '9': '9-Sem frete'}
TPAG = {
    '01': 'Dinheiro', '02': 'Cheque', '03': 'Cartão de Crédito',
    '04': 'Cartão de Débito', '05': 'Crédito Loja', '10': 'Vale Alimentação',
    '11': 'Vale Refeição', '12': 'Vale Presente', '13': 'Vale Combustível',
    '15': 'Boleto Bancário', '16': 'Depósito Bancário', '17': 'PIX',
    '18': 'Transferência bancária', '19': 'Programa de fidelidade',
    '90': 'Sem Pagamento', '99': 'Outros',
}


# ---------------------------------------------------------------------------
# LEITURA DO XML
# ---------------------------------------------------------------------------
def _carregar_xml(xml_bytes):
    if not xml_bytes or not xml_bytes.strip():
        raise DanfeError('O arquivo XML está vazio.')
    # NF-e não usa DOCTYPE/ENTITY; recusar evita ataques de expansão de entidades.
    if b'<!DOCTYPE' in xml_bytes[:4096].upper() or b'<!ENTITY' in xml_bytes.upper():
        raise DanfeError('XML recusado: declarações DOCTYPE/ENTITY não são permitidas.')
    try:
        root = ET.fromstring(xml_bytes)
        for elem in root.iter():
            if isinstance(elem.tag, str) and '}' in elem.tag:
                elem.tag = elem.tag.split('}', 1)[1]
        return root
    except ET.ParseError as e:
        raise DanfeError(f'XML inválido ou malformado: {e}') from e


def _txt(node, tag):
    if node is None:
        return ''
    return (node.findtext(tag) or '').strip()


# ---------------------------------------------------------------------------
# FORMATADORES (padrão brasileiro)
# ---------------------------------------------------------------------------
def _dec(val):
    if val is None or str(val).strip() == '':
        return None
    try:
        return Decimal(str(val).strip().replace(',', '.'))
    except InvalidOperation:
        return None


def fmt_num(val, casas=2, minimo=None):
    """1234.5 -> '1.234,50'. Com minimo < casas remove zeros finais ('2.0000' -> '2')."""
    d = _dec(val)
    if d is None:
        d = Decimal(0)
    minimo = casas if minimo is None else minimo
    try:
        d = d.quantize(Decimal(1).scaleb(-casas), rounding=ROUND_HALF_UP)
    except InvalidOperation:
        return str(val)
    texto = f"{d:,.{casas}f}"
    if minimo < casas:
        inteiro, _, frac = texto.partition('.')
        frac = frac.rstrip('0').ljust(minimo, '0')
        texto = inteiro + ('.' + frac if frac else '')
    return texto.replace(',', '#').replace('.', ',').replace('#', '.')


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
    if not dh or len(dh) < 10:
        return ''
    return f"{dh[8:10]}/{dh[5:7]}/{dh[:4]}"


def fmt_hora(dh):
    return dh[11:19] if dh and len(dh) >= 19 else ''


def fmt_chave(chave):
    return ' '.join(chave[i:i + 4] for i in range(0, len(chave), 4))


def _fatiar_palavra(palavra, fonte, tam, larg):
    """Divide uma palavra maior que a linha. Custo linear, sem laço infinito."""
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
    """Quebra o texto em linhas que cabem em `larg` (pontos), medindo com a fonte real."""
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


def _cortar(txt, fonte, tam, larg):
    """Corta o texto (sem quebrar linha) para caber na largura. Sempre termina."""
    txt = str(txt or '')[:300]
    while len(txt) > 1 and stringWidth(txt, fonte, tam) > larg:
        txt = txt[:-1]
    return txt


# ---------------------------------------------------------------------------
# EXTRAÇÃO DOS DADOS
# ---------------------------------------------------------------------------
def _endereco(node):
    return ', '.join(p for p in (_txt(node, 'xLgr'), _txt(node, 'nro'), _txt(node, 'xCpl')) if p)


def extrair_dados_danfe(root):
    inf = root if root.tag == 'infNFe' else root.find('.//infNFe')
    if inf is None:
        raise DanfeError('Este XML não é uma NF-e (elemento <infNFe> não encontrado).')

    ide = inf.find('ide')
    modelo = _txt(ide, 'mod')
    if modelo == '65':
        raise DanfeError('Este XML é de uma NFC-e (modelo 65). Use a ferramenta "Gerar Cupom Fiscal (NFC-e)".')
    if modelo and modelo != '55':
        raise DanfeError(f'Este XML é de um documento modelo {modelo}. O DANFE só se aplica à NF-e modelo 55.')

    prot = root.find('.//protNFe/infProt')
    chave = _txt(prot, 'chNFe') or _so_digitos(inf.get('Id'))

    emit = inf.find('emit')
    e_end = emit.find('enderEmit') if emit is not None else None
    dest = inf.find('dest')
    d_end = dest.find('enderDest') if dest is not None else None
    transp = inf.find('transp')
    tr = transp.find('transporta') if transp is not None else None
    veic = transp.find('veicTransp') if transp is not None else None
    vol = transp.find('vol') if transp is not None else None
    tot = inf.find('total/ICMSTot')

    if prot is not None and _txt(prot, 'nProt'):
        dh = _txt(prot, 'dhRecbto')
        protocolo = f"{_txt(prot, 'nProt')} - {fmt_data(dh)} {fmt_hora(dh)}".strip()
    else:
        protocolo = 'NF-e SEM PROTOCOLO DE AUTORIZAÇÃO'

    itens = []
    for det in inf.findall('det'):
        prod = det.find('prod')
        imp = det.find('imposto')
        grp = imp.find('ICMS') if imp is not None else None
        icms = list(grp)[0] if grp is not None and len(grp) else None
        cst = (_txt(icms, 'orig') + (_txt(icms, 'CST') or _txt(icms, 'CSOSN'))) if icms is not None else ''
        itens.append({
            'codigo': _txt(prod, 'cProd'),
            'descricao': _txt(prod, 'xProd'),
            'ncm': _txt(prod, 'NCM'),
            'cst': cst,
            'cfop': _txt(prod, 'CFOP'),
            'un': _txt(prod, 'uCom'),
            'qtd': fmt_num(_txt(prod, 'qCom'), 4, 0),
            'vun': fmt_num(_txt(prod, 'vUnCom'), 4, 2),
            'vtot': fmt_num(_txt(prod, 'vProd'), 2),
            'bc': fmt_num(_txt(icms, 'vBC'), 2) if _txt(icms, 'vBC') else '',
            'vicms': fmt_num(_txt(icms, 'vICMS'), 2) if _txt(icms, 'vICMS') else '',
            'aliq': fmt_num(_txt(icms, 'pICMS'), 2) if _txt(icms, 'pICMS') else '',
        })

    pags = []
    for p in inf.findall('pag/detPag'):
        t = _txt(p, 'tPag')
        pags.append(f"{TPAG.get(t, t)}: R$ {fmt_num(_txt(p, 'vPag'), 2)}")

    cpl = _txt(inf, 'infAdic/infCpl')
    fisco = _txt(inf, 'infAdic/infAdFisco')
    adicionais = '\n'.join(x for x in (cpl, fisco) if x)
    if pags:
        adicionais = ('Pagamento - ' + ' | '.join(pags) + ('\n' + adicionais if adicionais else ''))

    dh_emi = _txt(ide, 'dhEmi') or _txt(ide, 'dEmi')
    dh_sai = _txt(ide, 'dhSaiEnt') or _txt(ide, 'dSaiEnt')

    return {
        'chave': chave,
        'numero': _txt(ide, 'nNF'),
        'serie': _txt(ide, 'serie'),
        'natureza': _txt(ide, 'natOp'),
        'tp_nf': _txt(ide, 'tpNF') or '1',
        'homologacao': _txt(ide, 'tpAmb') == '2',
        'protocolo': protocolo,
        'emit': {
            'nome': _txt(emit, 'xNome'),
            'fantasia': _txt(emit, 'xFant'),
            'doc': fmt_doc(_txt(emit, 'CNPJ') or _txt(emit, 'CPF')),
            'ie': _txt(emit, 'IE'),
            'ie_st': _txt(emit, 'IEST'),
            'endereco': _endereco(e_end),
            'bairro': _txt(e_end, 'xBairro'),
            'mun_uf': ' - '.join(p for p in (_txt(e_end, 'xMun'), _txt(e_end, 'UF')) if p),
            'cep': fmt_cep(_txt(e_end, 'CEP')),
            'fone': fmt_fone(_txt(e_end, 'fone')),
        },
        'dest': {
            'nome': _txt(dest, 'xNome'),
            'doc': fmt_doc(_txt(dest, 'CNPJ') or _txt(dest, 'CPF') or _txt(dest, 'idEstrangeiro')),
            'ie': _txt(dest, 'IE'),
            'endereco': _endereco(d_end),
            'bairro': _txt(d_end, 'xBairro'),
            'cep': fmt_cep(_txt(d_end, 'CEP')),
            'mun': _txt(d_end, 'xMun'),
            'uf': _txt(d_end, 'UF'),
            'fone': fmt_fone(_txt(d_end, 'fone')),
            'dt_emissao': fmt_data(dh_emi),
            'dt_saida': fmt_data(dh_sai),
            'hr_saida': fmt_hora(dh_sai),
        },
        'itens': itens,
        'tot': {
            'bc_icms': fmt_num(_txt(tot, 'vBC'), 2), 'v_icms': fmt_num(_txt(tot, 'vICMS'), 2),
            'bc_st': fmt_num(_txt(tot, 'vBCST'), 2), 'v_st': fmt_num(_txt(tot, 'vST'), 2),
            'v_prod': fmt_num(_txt(tot, 'vProd'), 2), 'v_frete': fmt_num(_txt(tot, 'vFrete'), 2),
            'v_seg': fmt_num(_txt(tot, 'vSeg'), 2), 'v_desc': fmt_num(_txt(tot, 'vDesc'), 2),
            'v_outro': fmt_num(_txt(tot, 'vOutro'), 2), 'v_ipi': fmt_num(_txt(tot, 'vIPI'), 2),
            'v_nf': fmt_num(_txt(tot, 'vNF'), 2),
        },
        'transp': {
            'nome': _txt(tr, 'xNome'),
            'doc': fmt_doc(_txt(tr, 'CNPJ') or _txt(tr, 'CPF')),
            'ie': _txt(tr, 'IE'),
            'endereco': _txt(tr, 'xEnder'),
            'mun': _txt(tr, 'xMun'),
            'uf': _txt(tr, 'UF'),
            'frete': MOD_FRETE.get(_txt(transp, 'modFrete'), _txt(transp, 'modFrete')),
            'placa': _txt(veic, 'placa'),
            'uf_placa': _txt(veic, 'UF'),
            'qvol': _txt(vol, 'qVol'),
            'esp': _txt(vol, 'esp'),
            'peso_b': fmt_num(_txt(vol, 'pesoB'), 3) if _txt(vol, 'pesoB') else '',
            'peso_l': fmt_num(_txt(vol, 'pesoL'), 3) if _txt(vol, 'pesoL') else '',
        },
        'adicionais': adicionais,
    }


# ---------------------------------------------------------------------------
# DESENHO (A4 retrato). y é medido a partir do TOPO da folha.
# ---------------------------------------------------------------------------
LARG_PAG, ALT_PAG = A4
M = 7 * mm
LARG = LARG_PAG - 2 * M

# colunas da tabela de produtos (mm) - soma = 196 mm
COLS = [('CÓDIGO', 18), ('DESCRIÇÃO DO PRODUTO/SERVIÇO', 46), ('NCM', 16), ('CST', 9),
        ('CFOP', 10), ('UN', 8), ('QUANT.', 16), ('V. UNIT.', 17), ('V. TOTAL', 18),
        ('BC ICMS', 16), ('V. ICMS', 14), ('ALÍQ.', 8)]


class _Danfe:
    def __init__(self, dados, total_paginas=1):
        self.d = dados
        self.total = total_paginas
        self.pagina = 1
        self.buf = io.BytesIO()
        self.c = canvas.Canvas(self.buf, pagesize=A4)
        self.c.setTitle(f"DANFE NF-e {dados['numero']}")
        self.y = M

    # -- primitivas --
    def _cv(self, y):
        return ALT_PAG - y

    def _box(self, x, y, w, h):
        self.c.setLineWidth(0.5)
        self.c.rect(x, self._cv(y + h), w, h)

    def _txt(self, x, y, txt, fonte=FONTE, tam=8, alin='e'):
        self.c.setFont(fonte, tam)
        yy = self._cv(y)
        txt = '' if txt is None else str(txt)
        if alin == 'c':
            self.c.drawCentredString(x, yy, txt)
        elif alin == 'd':
            self.c.drawRightString(x, yy, txt)
        else:
            self.c.drawString(x, yy, txt)

    def _campo(self, x, y, w, h, rotulo, valor, alin='e', tam=8, fonte=FONTE):
        self._box(x, y, w, h)
        self._txt(x + 1 * mm, y + 2.4 * mm, rotulo, FONTE, 5)
        v = _cortar(valor, fonte, tam, w - 2 * mm)
        base = y + h - 1.6 * mm
        if alin == 'd':
            self._txt(x + w - 1 * mm, base, v, fonte, tam, 'd')
        elif alin == 'c':
            self._txt(x + w / 2, base, v, fonte, tam, 'c')
        else:
            self._txt(x + 1 * mm, base, v, fonte, tam)

    def _titulo(self, texto):
        self._txt(M, self.y + 2.6 * mm, texto, NEGRITO, 6.5)
        self.y += 3.4 * mm

    def _linha(self, campos, h=8 * mm):
        """campos: lista de (largura_mm|None, rotulo, valor[, alin]). None = largura restante."""
        fixo = sum(c[0] for c in campos if c[0] is not None) * mm
        livres = [c for c in campos if c[0] is None]
        x = M
        for c in campos:
            w = (c[0] * mm) if c[0] is not None else (LARG - fixo) / max(len(livres), 1)
            self._campo(x, self.y, w, h, c[1], c[2], c[3] if len(c) > 3 else 'e')
            x += w
        self.y += h

    # -- blocos --
    def _cabecalho(self):
        d, e = self.d, self.d['emit']
        y0, h = self.y, 28 * mm
        w_emit, w_id = 84 * mm, 35 * mm
        w_chave = LARG - w_emit - w_id
        x_id, x_ch = M + w_emit, M + w_emit + w_id

        # Emitente
        self._box(M, y0, w_emit, h)
        self._txt(M + w_emit / 2, y0 + 3 * mm, 'IDENTIFICAÇÃO DO EMITENTE', FONTE, 5, 'c')
        yy = y0 + 7.5 * mm
        for ln in _quebrar(e['nome'], NEGRITO, 9, w_emit - 4 * mm)[:3]:
            self._txt(M + w_emit / 2, yy, ln, NEGRITO, 9, 'c')
            yy += 3.6 * mm
        for texto in (f"{e['endereco']} - {e['bairro']}".strip(' -'),
                      ' - '.join(p for p in (e['mun_uf'], e['cep']) if p),
                      f"Fone: {e['fone']}" if e['fone'] else ''):
            for ln in _quebrar(texto, FONTE, 6.5, w_emit - 4 * mm)[:2]:
                if yy < y0 + h - 1 * mm:
                    self._txt(M + w_emit / 2, yy, ln, FONTE, 6.5, 'c')
                    yy += 2.9 * mm

        # DANFE
        self._box(x_id, y0, w_id, h)
        self._txt(x_id + w_id / 2, y0 + 5 * mm, 'DANFE', NEGRITO, 12, 'c')
        self._txt(x_id + w_id / 2, y0 + 8.6 * mm, 'Documento Auxiliar da', FONTE, 5.5, 'c')
        self._txt(x_id + w_id / 2, y0 + 11 * mm, 'Nota Fiscal Eletrônica', FONTE, 5.5, 'c')
        self._txt(x_id + 3 * mm, y0 + 15.5 * mm, '0 - ENTRADA', FONTE, 5.5)
        self._txt(x_id + 3 * mm, y0 + 18 * mm, '1 - SAÍDA', FONTE, 5.5)
        self._box(x_id + w_id - 9 * mm, y0 + 13.5 * mm, 6 * mm, 6 * mm)
        self._txt(x_id + w_id - 6 * mm, y0 + 18 * mm, d['tp_nf'], NEGRITO, 9, 'c')
        self._txt(x_id + w_id / 2, y0 + 22.2 * mm, f"Nº {d['numero']}  Série {d['serie']}", NEGRITO, 7, 'c')
        self._txt(x_id + w_id / 2, y0 + 25.6 * mm, f"Folha {self.pagina}/{self.total}", FONTE, 6.5, 'c')

        # Chave de acesso + código de barras
        self._box(x_ch, y0, w_chave, h)
        chave = d['chave']
        if len(chave) == 44 and chave.isdigit():
            try:
                bc = code128.Code128(chave, barWidth=0.23 * mm, barHeight=10 * mm, quiet=False)
                bc.drawOn(self.c, x_ch + (w_chave - bc.width) / 2, self._cv(y0 + 13 * mm))
            except Exception:
                pass
        self._txt(x_ch + 1 * mm, y0 + 2.4 * mm, 'CHAVE DE ACESSO', FONTE, 5)
        if chave:
            self._txt(x_ch + w_chave / 2, y0 + 17.5 * mm, fmt_chave(chave), NEGRITO, 6.3, 'c')
        self._txt(x_ch + w_chave / 2, y0 + 21.5 * mm, 'Consulta de autenticidade no portal nacional da NF-e', FONTE, 5, 'c')
        self._txt(x_ch + w_chave / 2, y0 + 24 * mm, 'www.nfe.fazenda.gov.br/portal ou no site da Sefaz', FONTE, 5, 'c')
        self.y = y0 + h

        self._linha([(None, 'NATUREZA DA OPERAÇÃO', d['natureza']),
                     (70, 'PROTOCOLO DE AUTORIZAÇÃO DE USO', d['protocolo'])])
        self._linha([(None, 'INSCRIÇÃO ESTADUAL', e['ie']),
                     (None, 'INSC. ESTADUAL DO SUBST. TRIB.', e['ie_st']),
                     (None, 'CNPJ / CPF', e['doc'])])
        if d['homologacao']:
            self._txt(LARG_PAG / 2, self.y + 3.2 * mm, 'EMITIDA EM AMBIENTE DE HOMOLOGAÇÃO - SEM VALOR FISCAL', NEGRITO, 7, 'c')
            self.y += 4 * mm

    def _blocos_primeira_pagina(self):
        d, t, tr, de = self.d, self.d['tot'], self.d['transp'], self.d['dest']
        self.y += 1.5 * mm
        self._titulo('DESTINATÁRIO / REMETENTE')
        self._linha([(None, 'NOME / RAZÃO SOCIAL', de['nome']), (42, 'CNPJ / CPF', de['doc']),
                     (26, 'DATA DA EMISSÃO', de['dt_emissao'], 'c')])
        self._linha([(None, 'ENDEREÇO', de['endereco']), (42, 'BAIRRO / DISTRITO', de['bairro']),
                     (22, 'CEP', de['cep'], 'c'), (26, 'DATA SAÍDA/ENTR.', de['dt_saida'], 'c')])
        self._linha([(None, 'MUNICÍPIO', de['mun']), (10, 'UF', de['uf'], 'c'),
                     (32, 'FONE / FAX', de['fone']), (42, 'INSCRIÇÃO ESTADUAL', de['ie']),
                     (26, 'HORA SAÍDA', de['hr_saida'], 'c')])

        self.y += 1.5 * mm
        self._titulo('CÁLCULO DO IMPOSTO')
        self._linha([(None, 'BASE DE CÁLC. DO ICMS', t['bc_icms'], 'd'), (None, 'VALOR DO ICMS', t['v_icms'], 'd'),
                     (None, 'BASE CÁLC. ICMS ST', t['bc_st'], 'd'), (None, 'VALOR DO ICMS ST', t['v_st'], 'd'),
                     (None, 'VALOR TOTAL PRODUTOS', t['v_prod'], 'd')])
        self._linha([(None, 'VALOR DO FRETE', t['v_frete'], 'd'), (None, 'VALOR DO SEGURO', t['v_seg'], 'd'),
                     (None, 'DESCONTO', t['v_desc'], 'd'), (None, 'OUTRAS DESP.', t['v_outro'], 'd'),
                     (None, 'VALOR DO IPI', t['v_ipi'], 'd'), (None, 'VALOR TOTAL DA NOTA', t['v_nf'], 'd')])

        self.y += 1.5 * mm
        self._titulo('TRANSPORTADOR / VOLUMES TRANSPORTADOS')
        self._linha([(None, 'NOME / RAZÃO SOCIAL', tr['nome']), (30, 'FRETE POR CONTA', tr['frete']),
                     (22, 'PLACA', tr['placa'], 'c'), (8, 'UF', tr['uf_placa'], 'c'), (38, 'CNPJ / CPF', tr['doc'])])
        self._linha([(None, 'ENDEREÇO', tr['endereco']), (40, 'MUNICÍPIO', tr['mun']), (8, 'UF', tr['uf'], 'c'),
                     (16, 'QUANT.', tr['qvol'], 'd'), (22, 'ESPÉCIE', tr['esp']),
                     (22, 'PESO BRUTO', tr['peso_b'], 'd'), (22, 'PESO LÍQ.', tr['peso_l'], 'd')])

    def _cabecalho_tabela(self):
        self._titulo('DADOS DOS PRODUTOS / SERVIÇOS')
        h = 5.5 * mm
        x = M
        for nome, w in COLS:
            self._box(x, self.y, w * mm, h)
            self._txt(x + w * mm / 2, self.y + 3.6 * mm, nome, NEGRITO, 4.8, 'c')
            x += w * mm
        self.y += h

    def _linha_item(self, it):
        larg_desc = COLS[1][1] * mm - 2 * mm
        linhas = _quebrar(it['descricao'], FONTE, 6.3, larg_desc) or ['']
        h = max(5 * mm, len(linhas) * 2.7 * mm + 1.8 * mm)
        if self.y + h > ALT_PAG - M:
            self._nova_pagina()
        valores = [it['codigo'], None, it['ncm'], it['cst'], it['cfop'], it['un'],
                   it['qtd'], it['vun'], it['vtot'], it['bc'], it['vicms'], it['aliq']]
        alinh = ['e', 'e', 'c', 'c', 'c', 'c', 'd', 'd', 'd', 'd', 'd', 'd']
        x = M
        for (nome, w), val, al in zip(COLS, valores, alinh):
            wpt = w * mm
            self.c.setLineWidth(0.3)
            self.c.rect(x, self._cv(self.y + h), wpt, h)
            base = self.y + 3.1 * mm
            if val is None:
                for i, ln in enumerate(linhas):
                    self._txt(x + 1 * mm, base + i * 2.7 * mm, ln, FONTE, 6.3)
            else:
                v = _cortar(val, FONTE, 6.3, wpt - 1.6 * mm)
                if al == 'd':
                    self._txt(x + wpt - 0.8 * mm, base, v, FONTE, 6.3, 'd')
                elif al == 'c':
                    self._txt(x + wpt / 2, base, v, FONTE, 6.3, 'c')
                else:
                    self._txt(x + 0.8 * mm, base, v, FONTE, 6.3)
            x += wpt
        self.y += h

    def _adicionais(self):
        texto = self.d['adicionais']
        linhas = _quebrar(texto, FONTE, 6.3, LARG - 2 * mm)
        self.y += 1.5 * mm
        if self.y + 3.4 * mm + 14 * mm > ALT_PAG - M:
            self._nova_pagina(com_tabela=False)
        self._titulo('DADOS ADICIONAIS')
        idx = 0
        while True:
            livre = ALT_PAG - M - self.y
            cab = max(int((livre - 3 * mm) / (2.8 * mm)), 1)
            pedaco = linhas[idx: idx + cab]
            idx += len(pedaco)
            h = max(len(pedaco) * 2.8 * mm + 3 * mm, 14 * mm)
            self._box(M, self.y, LARG, h)
            self._txt(M + 1 * mm, self.y + 2.4 * mm, 'INFORMAÇÕES COMPLEMENTARES', FONTE, 5)
            for i, ln in enumerate(pedaco):
                self._txt(M + 1 * mm, self.y + 5.4 * mm + i * 2.8 * mm, ln, FONTE, 6.3)
            self.y += h
            if idx >= len(linhas):
                break
            self._nova_pagina(com_tabela=False)  # texto muito longo: continua na próxima folha

    def _nova_pagina(self, com_tabela=True):
        self.c.showPage()
        self.pagina += 1
        self.y = M
        self._cabecalho()
        self.y += 1.5 * mm
        if com_tabela:
            self._cabecalho_tabela()

    def gerar(self):
        self._cabecalho()
        self._blocos_primeira_pagina()
        self.y += 1.5 * mm
        self._cabecalho_tabela()
        for it in self.d['itens']:
            self._linha_item(it)
        self._adicionais()
        self.c.showPage()
        self.c.save()
        return self.buf.getvalue(), self.pagina


def gerar_danfe(xml_bytes):
    """Recebe os bytes do XML da NF-e e devolve (pdf_bytes, numero_da_nota)."""
    try:
        root = _carregar_xml(xml_bytes)
    except DanfeError:
        raise
    except Exception as e:
        raise DanfeError(f'Não foi possível ler o XML: {e}') from e
    dados = extrair_dados_danfe(root)

    # 1ª passada só conta as páginas; 2ª passada desenha "Folha x/y" correto.
    _, total = _Danfe(dados).gerar()
    pdf, _ = _Danfe(dados, total_paginas=total).gerar()
    return pdf, (dados['numero'] or 'sem_numero')
