from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import defusedxml.ElementTree as ET

NS = "http://www.portalfiscal.inf.br/nfe"


class XMLParseError(Exception):
    pass


@dataclass
class ParsedInstallment:
    invoice_key: str
    invoice_number: str
    series: str
    issued_at: date
    installment_number: str
    due_date: date
    face_value: Decimal
    products_value: Decimal
    discount_value: Decimal
    freight_value: Decimal
    other_value: Decimal
    assignor_cnpj: str
    assignor_social_reason: str
    assignor_fantasy_name: str | None
    drawee_cnpj: str
    drawee_social_reason: str


def _tag(name: str) -> str:
    return f"{{{NS}}}{name}"


def _find(node, path: str):
    parts = [_tag(p) for p in path.split("/")]
    current = node
    for part in parts:
        current = current.find(part)
        if current is None:
            return None
    return current


def _text(node, path: str, required: bool = True) -> str:
    el = _find(node, path)
    if el is None or el.text is None:
        if required:
            raise XMLParseError(f"Campo obrigatório ausente: {path}")
        return ""
    return el.text.strip()


def _decimal(node, path: str, default: str = "0") -> Decimal:
    el = _find(node, path)
    if el is None or el.text is None:
        return Decimal(default)
    return Decimal(el.text.strip())


def parse(xml_bytes: bytes) -> list[ParsedInstallment]:
    """
    Parse NF-e XML bytes and return one ParsedInstallment per duplicata.
    Raises XMLParseError for malformed or missing required fields.
    """
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as e:
        raise XMLParseError(f"XML inválido: {e}") from e

    inf_nfe = _find(root, "NFe/infNFe")
    if inf_nfe is None:
        raise XMLParseError("Elemento infNFe não encontrado")

    chave_id = inf_nfe.get("Id", "")
    if not chave_id.startswith("NFe") or len(chave_id) != 47:
        raise XMLParseError(f"Chave de acesso inválida: {chave_id}")
    invoice_key = chave_id[3:]

    ide = _find(inf_nfe, "ide")
    if ide is None:
        raise XMLParseError("Elemento ide não encontrado")

    invoice_number = _text(ide, "nNF")
    series = _text(ide, "serie")
    issued_at = date.fromisoformat(_text(ide, "dhEmi")[:10])

    emit = _find(inf_nfe, "emit")
    dest = _find(inf_nfe, "dest")
    if emit is None or dest is None:
        raise XMLParseError("Elementos emit/dest não encontrados")

    assignor_cnpj = _text(emit, "CNPJ")
    assignor_social_reason = _text(emit, "xNome")
    assignor_fantasy_name = _text(emit, "xFant", required=False) or None
    drawee_cnpj = _text(dest, "CNPJ")
    drawee_social_reason = _text(dest, "xNome")

    if assignor_cnpj == drawee_cnpj:
        raise XMLParseError("Cedente e sacado não podem ser o mesmo CNPJ")

    total = _find(inf_nfe, "total/ICMSTot")
    if total is None:
        raise XMLParseError("Elemento total/ICMSTot não encontrado")

    products_value = _decimal(total, "vProd")
    discount_value = _decimal(total, "vDesc")
    freight_value = _decimal(total, "vFrete")
    other_value = _decimal(total, "vOutro")

    cobr = _find(inf_nfe, "cobr")
    if cobr is None:
        raise XMLParseError("Elemento cobr não encontrado — NF-e sem cobrança")

    dups = cobr.findall(_tag("dup"))
    if not dups:
        raise XMLParseError("Nenhuma duplicata (dup) encontrada na cobrança")

    installments: list[ParsedInstallment] = []
    for dup in dups:
        n_dup = _text(dup, "nDup", required=False) or "001"
        d_venc = _text(dup, "dVenc")
        v_dup = _decimal(dup, "vDup")

        if v_dup <= Decimal("0"):
            raise XMLParseError(f"Duplicata {n_dup} com valor inválido: {v_dup}")

        installments.append(
            ParsedInstallment(
                invoice_key=invoice_key,
                invoice_number=invoice_number,
                series=series,
                issued_at=issued_at,
                installment_number=n_dup,
                due_date=date.fromisoformat(d_venc),
                face_value=v_dup,
                products_value=products_value if len(dups) == 1 else Decimal("0"),
                discount_value=discount_value if len(dups) == 1 else Decimal("0"),
                freight_value=freight_value if len(dups) == 1 else Decimal("0"),
                other_value=other_value if len(dups) == 1 else Decimal("0"),
                assignor_cnpj=assignor_cnpj,
                assignor_social_reason=assignor_social_reason,
                assignor_fantasy_name=assignor_fantasy_name,
                drawee_cnpj=drawee_cnpj,
                drawee_social_reason=drawee_social_reason,
            )
        )

    return installments
