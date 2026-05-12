"""
Gerador de NF-e fake para testes do SRM Credit Engine.

Uso:
    python scripts/generate_nfe.py --count 5
    python scripts/generate_nfe.py --count 10 --min-value 5000 --max-value 50000
    python scripts/generate_nfe.py --count 3 --installments 3  # 3 duplicatas por nota
    python scripts/generate_nfe.py --count 5 --upload          # faz upload para o R2

Os XMLs são salvos em /tmp/nfe/ e opcionalmente enviados ao R2.
"""

import argparse
import random
import sys
import uuid
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from string import digits
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom.minidom import parseString

sys.path.insert(0, ".")

CEDENTES = [
    {"cnpj": "11222333000181", "razao_social": "INDUSTRIA ALFA LTDA", "ie": "111111111111"},
    {"cnpj": "22333444000190", "razao_social": "COMERCIO BETA S/A", "ie": "222222222222"},
    {"cnpj": "33444555000107", "razao_social": "DISTRIBUIDORA GAMMA EIRELI", "ie": "333333333333"},
]

SACADOS = [
    {"cnpj": "44555666000115", "razao_social": "VAREJISTA DELTA LTDA", "ie": "444444444444"},
    {"cnpj": "55666777000123", "razao_social": "ATACADO EPSILON S/A", "ie": "555555555555"},
    {"cnpj": "66777888000131", "razao_social": "SUPERMERCADOS ZETA LTDA", "ie": "666666666666"},
]

PRODUTOS = [
    {"descricao": "PRODUTO INDUSTRIAL A", "ncm": "84099190", "cfop": "6102"},
    {"descricao": "MERCADORIA B", "ncm": "39173290", "cfop": "6102"},
    {"descricao": "COMPONENTE C", "ncm": "73182900", "cfop": "6102"},
]


def _random_digits(n: int) -> str:
    return "".join(random.choices(digits, k=n))


def _chave_nfe(cnpj: str, aamm: str, serie: str, numero: str) -> str:
    codigo_uf = "35"
    codigo_numerico = _random_digits(8)
    raw = f"{codigo_uf}{aamm}{cnpj}{serie.zfill(3)}{numero.zfill(9)}1{codigo_numerico}"
    # dígito verificador simplificado (módulo 11)
    weights = list(range(2, 10)) * 6
    total = sum(int(d) * w for d, w in zip(reversed(raw), weights))
    remainder = total % 11
    dv = 0 if remainder < 2 else 11 - remainder
    return raw + str(dv)


def _format_cnpj(cnpj: str) -> str:
    return f"{cnpj[:2]}.{cnpj[2:5]}.{cnpj[5:8]}/{cnpj[8:12]}-{cnpj[12:]}"


def generate_nfe(
    cedente: dict,
    sacado: dict,
    valor_total: Decimal,
    numero: str,
    serie: str,
    installments: int,
    emissao: date,
) -> tuple[str, bytes]:
    """Gera um XML NF-e e retorna (chave_acesso, xml_bytes)."""
    aamm = emissao.strftime("%y%m")
    chave = _chave_nfe(cedente["cnpj"], aamm, serie, numero)

    nfe = Element("nfeProc", xmlns="http://www.portalfiscal.inf.br/nfe", versao="4.00")
    nfe_elem = SubElement(nfe, "NFe")
    inf_nfe = SubElement(nfe_elem, "infNFe", Id=f"NFe{chave}", versao="4.00")

    # Identificação
    ide = SubElement(inf_nfe, "ide")
    SubElement(ide, "cUF").text = "35"
    SubElement(ide, "cNF").text = chave[35:43]
    SubElement(ide, "natOp").text = "VENDA DE MERCADORIA"
    SubElement(ide, "mod").text = "55"
    SubElement(ide, "serie").text = serie
    SubElement(ide, "nNF").text = numero
    SubElement(ide, "dhEmi").text = f"{emissao.isoformat()}T09:00:00-03:00"
    SubElement(ide, "dhSaiEnt").text = f"{emissao.isoformat()}T10:00:00-03:00"
    SubElement(ide, "tpNF").text = "1"
    SubElement(ide, "idDest").text = "1"
    SubElement(ide, "cMunFG").text = "3550308"
    SubElement(ide, "tpImp").text = "1"
    SubElement(ide, "tpEmis").text = "1"
    SubElement(ide, "cDV").text = chave[-1]
    SubElement(ide, "tpAmb").text = "2"
    SubElement(ide, "finNFe").text = "1"
    SubElement(ide, "indFinal").text = "0"
    SubElement(ide, "indPres").text = "0"
    SubElement(ide, "procEmi").text = "0"
    SubElement(ide, "verProc").text = "SRM-GEN 1.0"

    # Emitente (cedente)
    emit = SubElement(inf_nfe, "emit")
    SubElement(emit, "CNPJ").text = cedente["cnpj"]
    SubElement(emit, "xNome").text = cedente["razao_social"]
    ender_emit = SubElement(emit, "enderEmit")
    SubElement(ender_emit, "xLgr").text = "RUA DAS INDUSTRIAS"
    SubElement(ender_emit, "nro").text = "100"
    SubElement(ender_emit, "xBairro").text = "INDUSTRIAL"
    SubElement(ender_emit, "cMun").text = "3550308"
    SubElement(ender_emit, "xMun").text = "SAO PAULO"
    SubElement(ender_emit, "UF").text = "SP"
    SubElement(ender_emit, "CEP").text = "01000000"
    SubElement(ender_emit, "cPais").text = "1058"
    SubElement(ender_emit, "xPais").text = "Brasil"
    SubElement(emit, "IE").text = cedente["ie"]
    SubElement(emit, "xFant").text = cedente["razao_social"].split()[0]
    SubElement(emit, "CRT").text = "3"

    # Destinatário (sacado)
    dest = SubElement(inf_nfe, "dest")
    SubElement(dest, "CNPJ").text = sacado["cnpj"]
    SubElement(dest, "xNome").text = sacado["razao_social"]
    ender_dest = SubElement(dest, "enderDest")
    SubElement(ender_dest, "xLgr").text = "AV COMERCIAL"
    SubElement(ender_dest, "nro").text = "200"
    SubElement(ender_dest, "xBairro").text = "CENTRO"
    SubElement(ender_dest, "cMun").text = "3304557"
    SubElement(ender_dest, "xMun").text = "RIO DE JANEIRO"
    SubElement(ender_dest, "UF").text = "RJ"
    SubElement(ender_dest, "CEP").text = "20000000"
    SubElement(ender_dest, "cPais").text = "1058"
    SubElement(ender_dest, "xPais").text = "Brasil"
    SubElement(dest, "IE").text = sacado["ie"]
    SubElement(dest, "indIEDest").text = "1"

    # Produto
    produto = random.choice(PRODUTOS)
    det = SubElement(inf_nfe, "det", nItem="1")
    prod = SubElement(det, "prod")
    SubElement(prod, "cProd").text = _random_digits(6)
    SubElement(prod, "cEAN").text = "SEM GTIN"
    SubElement(prod, "xProd").text = produto["descricao"]
    SubElement(prod, "NCM").text = produto["ncm"]
    SubElement(prod, "CFOP").text = produto["cfop"]
    SubElement(prod, "uCom").text = "UN"
    SubElement(prod, "qCom").text = "100.0000"
    SubElement(prod, "vUnCom").text = str(valor_total / 100)
    SubElement(prod, "vProd").text = str(valor_total)
    SubElement(prod, "cEANTrib").text = "SEM GTIN"
    SubElement(prod, "uTrib").text = "UN"
    SubElement(prod, "qTrib").text = "100.0000"
    SubElement(prod, "vUnTrib").text = str(valor_total / 100)
    SubElement(prod, "indTot").text = "1"

    # Impostos (simplificado — tributação simples nacional / CSOSN 400)
    imposto = SubElement(det, "imposto")
    icms = SubElement(imposto, "ICMS")
    icms_csosn = SubElement(icms, "ICMSSN400")
    SubElement(icms_csosn, "orig").text = "0"
    SubElement(icms_csosn, "CSOSN").text = "400"
    pis = SubElement(imposto, "PIS")
    pis_nt = SubElement(pis, "PISNT")
    SubElement(pis_nt, "CST").text = "07"
    cofins = SubElement(imposto, "COFINS")
    cofins_nt = SubElement(cofins, "COFINSNT")
    SubElement(cofins_nt, "CST").text = "07"

    # Totais
    total = SubElement(inf_nfe, "total")
    icms_tot = SubElement(total, "ICMSTot")
    SubElement(icms_tot, "vBC").text = "0.00"
    SubElement(icms_tot, "vICMS").text = "0.00"
    SubElement(icms_tot, "vICMSDeson").text = "0.00"
    SubElement(icms_tot, "vFCP").text = "0.00"
    SubElement(icms_tot, "vBCST").text = "0.00"
    SubElement(icms_tot, "vST").text = "0.00"
    SubElement(icms_tot, "vFCPST").text = "0.00"
    SubElement(icms_tot, "vFCPSTRet").text = "0.00"
    SubElement(icms_tot, "vProd").text = str(valor_total)
    SubElement(icms_tot, "vFrete").text = "0.00"
    SubElement(icms_tot, "vSeg").text = "0.00"
    SubElement(icms_tot, "vDesc").text = "0.00"
    SubElement(icms_tot, "vII").text = "0.00"
    SubElement(icms_tot, "vIPI").text = "0.00"
    SubElement(icms_tot, "vIPIDevol").text = "0.00"
    SubElement(icms_tot, "vPIS").text = "0.00"
    SubElement(icms_tot, "vCOFINS").text = "0.00"
    SubElement(icms_tot, "vOutro").text = "0.00"
    SubElement(icms_tot, "vNF").text = str(valor_total)

    # Transporte
    transp = SubElement(inf_nfe, "transp")
    SubElement(transp, "modFrete").text = "9"

    # Cobrança — duplicatas
    cobr = SubElement(inf_nfe, "cobr")
    fat = SubElement(cobr, "fat")
    SubElement(fat, "nFat").text = numero
    SubElement(fat, "vOrig").text = str(valor_total)
    SubElement(fat, "vDesc").text = "0.00"
    SubElement(fat, "vLiq").text = str(valor_total)

    valor_dup = (valor_total / installments).quantize(Decimal("0.01"))
    for i in range(1, installments + 1):
        due = emissao + timedelta(days=30 * i)
        dup = SubElement(cobr, "dup")
        SubElement(dup, "nDup").text = str(i).zfill(3)
        SubElement(dup, "dVenc").text = due.isoformat()
        SubElement(dup, "vDup").text = str(valor_dup if i < installments else valor_total - valor_dup * (installments - 1))

    # Pagamento
    pag = SubElement(inf_nfe, "pag")
    det_pag = SubElement(pag, "detPag")
    SubElement(det_pag, "indPag").text = "1"
    SubElement(det_pag, "tPag").text = "01"
    SubElement(det_pag, "vPag").text = str(valor_total)

    xml_bytes = parseString(tostring(nfe, encoding="unicode")).toprettyxml(indent="  ", encoding="utf-8")
    return chave, xml_bytes


def main() -> None:
    parser = argparse.ArgumentParser(description="Gerador de NF-e fake para o SRM Credit Engine")
    parser.add_argument("--count", type=int, default=5, help="Número de NF-es a gerar (default: 5)")
    parser.add_argument("--min-value", type=float, default=10000, help="Valor mínimo da NF (default: 10000)")
    parser.add_argument("--max-value", type=float, default=100000, help="Valor máximo da NF (default: 100000)")
    parser.add_argument("--installments", type=int, default=1, help="Duplicatas por nota (default: 1)")
    parser.add_argument("--output", type=str, default="/tmp/nfe", help="Diretório de saída (default: /tmp/nfe)")
    args = parser.parse_args()

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    for i in range(args.count):
        cedente = random.choice(CEDENTES)
        sacado = random.choice(SACADOS)
        valor = Decimal(str(round(random.uniform(args.min_value, args.max_value), 2)))
        numero = str(random.randint(100000, 999999))
        serie = "1"
        emissao = date.today() - timedelta(days=random.randint(0, 30))

        chave, xml_bytes = generate_nfe(
            cedente=cedente,
            sacado=sacado,
            valor_total=valor,
            numero=numero,
            serie=serie,
            installments=args.installments,
            emissao=emissao,
        )

        filepath = output_dir / f"nfe_{chave}.xml"
        filepath.write_bytes(xml_bytes)

        print(f"  [{i+1}/{args.count}] NF-e {numero} | {cedente['razao_social'][:20]} → {sacado['razao_social'][:20]} | R$ {valor:,.2f} | {args.installments}x")
        print(f"         {filepath}")

    print(f"\n{args.count} NF-e(s) gerada(s) em {output_dir}")


if __name__ == "__main__":
    main()
