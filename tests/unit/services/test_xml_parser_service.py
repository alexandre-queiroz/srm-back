from datetime import date
from decimal import Decimal

import pytest

from app.services.xml_parser_service import XMLParseError, parse

NFE_TEMPLATE = """<?xml version="1.0" encoding="utf-8"?>
<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe" versao="4.00">
  <NFe>
    <infNFe Id="NFe{chave}" versao="4.00">
      <ide>
        <cUF>35</cUF><cNF>12345678</cNF><natOp>VENDA</natOp><mod>55</mod>
        <serie>1</serie><nNF>100001</nNF>
        <dhEmi>2026-01-15T09:00:00-03:00</dhEmi>
        <dhSaiEnt>2026-01-15T10:00:00-03:00</dhSaiEnt>
        <tpNF>1</tpNF><idDest>1</idDest><cMunFG>3550308</cMunFG>
        <tpImp>1</tpImp><tpEmis>1</tpEmis><cDV>0</cDV><tpAmb>2</tpAmb>
        <finNFe>1</finNFe><indFinal>0</indFinal><indPres>0</indPres>
        <procEmi>0</procEmi><verProc>SRM-GEN 1.0</verProc>
      </ide>
      <emit>
        <CNPJ>{emit_cnpj}</CNPJ>
        <xNome>CEDENTE TESTE LTDA</xNome>
        <enderEmit><xLgr>RUA A</xLgr><nro>1</nro><xBairro>CENTRO</xBairro>
          <cMun>3550308</cMun><xMun>SAO PAULO</xMun><UF>SP</UF><CEP>01000000</CEP></enderEmit>
        <IE>111111111111</IE><CRT>3</CRT>
      </emit>
      <dest>
        <CNPJ>{dest_cnpj}</CNPJ>
        <xNome>SACADO TESTE S/A</xNome>
        <enderDest><xLgr>AV B</xLgr><nro>2</nro><xBairro>CENTRO</xBairro>
          <cMun>3304557</cMun><xMun>RIO DE JANEIRO</xMun><UF>RJ</UF><CEP>20000000</CEP></enderDest>
        <IE>222222222222</IE><indIEDest>1</indIEDest>
      </dest>
      <det nItem="1">
        <prod>
          <cProd>001</cProd><cEAN>SEM GTIN</cEAN><xProd>PRODUTO X</xProd>
          <NCM>84099190</NCM><CFOP>6102</CFOP><uCom>UN</uCom><qCom>10.0000</qCom>
          <vUnCom>1000.00</vUnCom><vProd>{vprod}</vProd>
          <cEANTrib>SEM GTIN</cEANTrib><uTrib>UN</uTrib><qTrib>10.0000</qTrib>
          <vUnTrib>1000.00</vUnTrib><indTot>1</indTot>
        </prod>
        <imposto>
          <ICMS><ICMSSN400><orig>0</orig><CSOSN>400</CSOSN></ICMSSN400></ICMS>
          <PIS><PISNT><CST>07</CST></PISNT></PIS>
          <COFINS><COFINSNT><CST>07</CST></COFINSNT></COFINS>
        </imposto>
      </det>
      <total>
        <ICMSTot>
          <vBC>0.00</vBC><vICMS>0.00</vICMS><vICMSDeson>0.00</vICMSDeson>
          <vFCP>0.00</vFCP><vBCST>0.00</vBCST><vST>0.00</vST>
          <vFCPST>0.00</vFCPST><vFCPSTRet>0.00</vFCPSTRet>
          <vProd>{vprod}</vProd><vFrete>0.00</vFrete><vSeg>0.00</vSeg>
          <vDesc>{vdesc}</vDesc><vII>0.00</vII><vIPI>0.00</vIPI>
          <vIPIDevol>0.00</vIPIDevol><vPIS>0.00</vPIS><vCOFINS>0.00</vCOFINS>
          <vOutro>0.00</vOutro><vNF>{vprod}</vNF>
        </ICMSTot>
      </total>
      <transp><modFrete>9</modFrete></transp>
      <cobr>
        <fat><nFat>100001</nFat><vOrig>{vprod}</vOrig><vDesc>0.00</vDesc><vLiq>{vprod}</vLiq></fat>
        {dups}
      </cobr>
      <pag><detPag><indPag>1</indPag><tPag>01</tPag><vPag>{vprod}</vPag></detPag></pag>
    </infNFe>
  </NFe>
</nfeProc>"""

VALID_CHAVE = "35260111222333000181550010001000011123456780"
SAME_CNPJ = "11222333000181"
EMIT_CNPJ = "11222333000181"
DEST_CNPJ = "44555666000115"


def _make_xml(
    chave: str = VALID_CHAVE,
    emit_cnpj: str = EMIT_CNPJ,
    dest_cnpj: str = DEST_CNPJ,
    vprod: str = "10000.00",
    vdesc: str = "0.00",
    dups: str = '<dup><nDup>001</nDup><dVenc>2026-03-15</dVenc><vDup>10000.00</vDup></dup>',
) -> bytes:
    return NFE_TEMPLATE.format(
        chave=chave, emit_cnpj=emit_cnpj, dest_cnpj=dest_cnpj,
        vprod=vprod, vdesc=vdesc, dups=dups,
    ).encode("utf-8")


class TestParseHappyPath:
    def test_single_installment_returns_one_item(self):
        result = parse(_make_xml())
        assert len(result) == 1

    def test_fields_extracted_correctly(self):
        result = parse(_make_xml())
        inst = result[0]
        assert inst.invoice_key == VALID_CHAVE
        assert inst.invoice_number == "100001"
        assert inst.series == "1"
        assert inst.issued_at == date(2026, 1, 15)
        assert inst.installment_number == "001"
        assert inst.due_date == date(2026, 3, 15)
        assert inst.face_value == Decimal("10000.00")
        assert inst.assignor_cnpj == EMIT_CNPJ
        assert inst.drawee_cnpj == DEST_CNPJ

    def test_multiple_installments_returns_multiple_items(self):
        dups = """
        <dup><nDup>001</nDup><dVenc>2026-03-15</dVenc><vDup>5000.00</vDup></dup>
        <dup><nDup>002</nDup><dVenc>2026-04-15</dVenc><vDup>5000.00</vDup></dup>
        """
        result = parse(_make_xml(dups=dups))
        assert len(result) == 2
        assert result[0].installment_number == "001"
        assert result[1].installment_number == "002"
        assert result[0].face_value == Decimal("5000.00")

    def test_single_installment_carries_totals(self):
        result = parse(_make_xml(vprod="10000.00"))
        inst = result[0]
        assert inst.products_value == Decimal("10000.00")

    def test_multiple_installments_have_zero_totals(self):
        dups = """
        <dup><nDup>001</nDup><dVenc>2026-03-15</dVenc><vDup>5000.00</vDup></dup>
        <dup><nDup>002</nDup><dVenc>2026-04-15</dVenc><vDup>5000.00</vDup></dup>
        """
        result = parse(_make_xml(dups=dups))
        assert result[0].products_value == Decimal("0")
        assert result[1].products_value == Decimal("0")


class TestParseErrors:
    def test_invalid_xml_raises(self):
        with pytest.raises(XMLParseError, match="XML inválido"):
            parse(b"<not valid xml")

    def test_missing_inf_nfe_raises(self):
        with pytest.raises(XMLParseError, match="infNFe"):
            parse(b'<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe"><NFe></NFe></nfeProc>')

    def test_invalid_chave_length_raises(self):
        with pytest.raises(XMLParseError, match="Chave de acesso inválida"):
            parse(_make_xml(chave="123"))

    def test_same_cnpj_assignor_drawee_raises(self):
        with pytest.raises(XMLParseError, match="mesmo CNPJ"):
            parse(_make_xml(emit_cnpj=SAME_CNPJ, dest_cnpj=SAME_CNPJ))

    def test_missing_cobr_raises(self):
        xml = _make_xml().decode().replace("<cobr>", "").replace("</cobr>", "")
        # Remove all dup and fat content between cobr tags
        import re
        xml = re.sub(r"<cobr>.*?</cobr>", "", xml, flags=re.DOTALL)
        with pytest.raises(XMLParseError, match="cobr"):
            parse(xml.encode())

    def test_no_dup_raises(self):
        xml = _make_xml(dups="").decode()
        with pytest.raises(XMLParseError, match="duplicata"):
            parse(xml.encode())

    def test_zero_value_dup_raises(self):
        dups = '<dup><nDup>001</nDup><dVenc>2026-03-15</dVenc><vDup>0.00</vDup></dup>'
        with pytest.raises(XMLParseError, match="valor inválido"):
            parse(_make_xml(dups=dups))
