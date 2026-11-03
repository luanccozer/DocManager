# 01: Ler o arquivo de envio (.docx ou .xlsx)

Status: done

`services/upload_envio.py`: achar a tabela pelo cabeçalho `IDENTIFICAÇÃO DOCUMENTO CMI`, e para o
código colado devolver o código Itaipu, a descrição, `EMITIR REV. ITAIPÚ` e o **destino do
hiperlink** de `LINK`. .docx pelo XML (`w:hyperlink` + rels, e campo `HYPERLINK`); .xlsx pelo
openpyxl (`cell.hyperlink.target`). .doc/.xls antigos: recusa com "salve como .docx/.xlsx".
Spec §3.
