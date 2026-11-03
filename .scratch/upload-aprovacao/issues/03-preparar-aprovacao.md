# 03: Preparar o envio para aprovação (ensaio)

Status: done

`services/upload_aprovacao.py::preparar_aprovacao`: código no arquivo de envio e no Controle,
pergunta se não está em 0C, documento no Aconex pela API (`consultar_codigos`), e devolve o resumo
do que seria feito. Nada é gravado. Spec §4 passos 1, 3 e 4.
