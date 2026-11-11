# Protótipo descartável do painel da UG

Responde a uma pergunta: **que história os dados do Doc List e do Aconex contam, e em
que gráficos?** Não é código de produção (sem testes, sem tratamento de erro) e sai
daqui quando o painel de verdade existir. Spec: `../spec.md`.

Da raiz do repositório:

```
python .scratch/painel-ug-html/prototipo/gerar_prototipo.py "Doc List Mapping.xlsx" Aconex_Historico.xlsx painel_ug.html --hoje 2026-11-10
```

`--chartjs <chart.umd.js>` embute o Chart.js 4.4.4 no arquivo, para abrir sem internet;
sem ele, o HTML carrega a biblioteca do jsdelivr.

O HTML gerado tem dados do cliente: **nunca** versionar neste repositório (é público).
