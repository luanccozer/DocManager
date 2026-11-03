# Upload de documentos → Para aprovação (RPA)

Status: ready-for-agent (Fase 1) · needs-info (Fase 2: precisa de sessão na máquina do usuário)

Pedido do Jonathan (2026-11-03). Desenho combinado na conversa, com capturas do Aconex, do
arquivo de envio e do Controle de Documentos. Nenhum dado real neste arquivo: os códigos abaixo
são da forma, não do projeto.

## 1. O que o usuário quer

Um módulo novo, **Upload de documentos**, com três opções: **Documento novo**, **Para revisão** e
**Para aprovação**. Agora só **Para aprovação**: um robot que faz sozinho o envio de um documento
que já está em `0C` para aprovação (revisão `0`), do Box ao Aconex e de volta ao Box.

## 2. Decisões (do usuário)

- **D1 – Enfoque misto:** Aconex pela API quando a API permitir (buscar, ler o workflow; subir a
  revisão e iniciar o workflow se a API permitir) e navegador só para o que não tem API.
- **D2 – Navegador:** o **Google Chrome instalado** na máquina (Playwright, `channel="chrome"`),
  sem empacotar navegador no instalador. Sem Chrome: mensagem clara, nada é feito.
- **D3 – Box só pela web:** não há Box Drive. O robot abre o link no Chrome (login do usuário),
  baixa os arquivos e, no fim, sobe o PDF do workflow na mesma pasta.
- **D4 – Arquivos:** a pasta do Box tem **PDF + editável**; os dois sobem no documento.
- **D5 – Revisão:** sempre **`0`** neste módulo; status **"Para Aprovação"**.
- **D6 – Prazo:** **número de dias**, perguntado na tela antes de começar.
- **D7 – Código CMI:** o usuário **cola o código** numa janelinha (como faz hoje).
- **D8 – PDF final:** "imprimir estilo de tela / sem tópicos" da tela do workflow, salvo como
  `<nº do correio> - <nº do workflow> - <data>.pdf` e **subido na pasta do Box**, substituindo o
  de mesmo nome. O nº do correio e o do workflow aparecem na tela final do workflow.
- **D9 – Confirmação:** antes de qualquer gravação no Aconex, uma janela resume o que vai ser
  feito e só segue com **"Enviar"**.

## 3. Os arquivos de entrada (medidos nas capturas)

**Arquivo de envio** (Word ou Excel; o usuário não sabe qual - o app aceita os dois):
- frase "Seguem documentos para envio via ACONEX análise de ITAIPU:" e uma tabela;
- colunas: `IDENTIFICAÇÃO DOCUMENTO CMI`, `IDENTIFICAÇÃO DOCUMENTO ITAIPU`, `ESPECIFICAÇÃO TÉCNICA`,
  `CAPÍTULO ESPECIFICAÇÃO TÉCNICA`, `DESCRIÇÃO`, `TIPO DE DOCUMENTO`, `SUBTIPO DE DOCUMENTO`,
  `EMITIR REV. ITAIPÚ`, `LINK`;
- `LINK` é um **hiperlink** (texto tipo "R0 | Pov…") para a pasta do Box.
- O app acha a tabela pelo cabeçalho (`normalizar_cabecalho`), a linha pelo código CMI e lê o
  **destino do hiperlink** (no .docx, a relação `r:id` do `<w:hyperlink>`; no .xlsx,
  `cell.hyperlink.target`).

**ITAIPU CONTROLE DE DOCUMENTOS** (o Controle que o app já lê):
- cabeçalho na linha 4; código CMI na coluna `NÚMERO INTERNO`; a revisão em
  `ÚLTIMA REVISÃO EMITIDA` (fórmula `PROCV` sobre `BD_ACONEX1`: ler o valor salvo, `data_only`).
- Diferente de `0C` (ou código não encontrado): perguntar "continuar?".

## 4. O fluxo

1. **Verificar** (sem rede): arquivo de envio + Controle escolhidos, prazo > 0, código colado.
   Achar o código no arquivo de envio (link do Box) e no Controle (`0C`?).
2. **Box (Chrome):** abrir o link e deixar a aba aberta; baixar o PDF e o editável para uma pasta
   de trabalho em `pasta_dados()/upload/<código>/`.
3. **Aconex (API, só leitura):** documento pelo `Controle do Emissor` (busca do register); o
   **modelo** do último workflow desse documento pela Workflows API (`WorkflowTemplate`; se vier
   vazio, o `WorkflowName`, que é o "Nome" que o usuário copia hoje).
4. **Confirmação** (D9).
5. **Aconex (gravação):** nova revisão `0`, status "Para Aprovação", com os dois arquivos; iniciar
   o workflow com o modelo e o prazo. API se ela permitir; senão, a tela (`Atualizar` →
   arraste e solte → Revisão/Status → `Atualizar` → `Iniciar workflow` → `Próximo` → desmarcar
   "mostrar apenas modelos da minha organização" → nome do modelo → `Próximo` → prazo).
6. **Imprimir (Chrome):** a tela do workflow em "estilo de tela / sem tópicos", como PDF (D8).
7. **Box (Chrome):** subir o PDF na pasta, substituindo o de mesmo nome.

## 5. Segurança

- Da etapa 5 em diante há gravação em produção: **nenhuma retentativa automática** depois de subir
  a revisão (repetir criaria revisão ou workflow duplicado). Falha = parar, dizer em que etapa e o
  que já foi feito, para terminar à mão.
- Cada etapa no log, com o que foi lido/gravado.
- O perfil do Chrome do robot fica em `pasta_dados()/navegador` (o login fica guardado, como no
  Chrome do usuário); nenhuma senha passa pelo app.

## 6. Fases

**Fase 1 (dá para fazer e testar aqui):** o módulo e as três abas (duas "em breve"); a tela de
aprovação; a janelinha do código; leitura do arquivo de envio (.docx e .xlsx) e do Controle;
o aviso de "não está em 0C"; a busca no Aconex pela API (documento e modelo do workflow); a janela
de confirmação. Nenhuma gravação no Aconex nem no Box. Testes com arquivos sintéticos e sessão
simulada; a busca real o usuário confere na máquina dele.

**Fase 2 (precisa da máquina do usuário, com o Chrome, a VPN e um documento de teste):** Box
(baixar e subir), gravação no Aconex (API ou tela), impressão. Mapear cada tela ao vivo, numa
sessão ligada ao computador dele (Remote Control). Antes disso, verificar na documentação da API
do Aconex se ela sobe revisão com dois arquivos e se inicia workflow.

## 7. Não verificado

- Se a API do Aconex sobe nova revisão com PDF + editável no mesmo documento e se inicia workflow.
- Os seletores do Box e da tela do Aconex (nada disso é visível daqui).
- Onde exatamente aparecem o nº do correio e o do workflow na tela final.
