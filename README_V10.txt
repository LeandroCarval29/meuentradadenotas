HNT FOODSERVICE BI V10 ESTÁVEL

Esta versão consolida as anteriores e prioriza estabilidade.

FLUXOS REVISADOS:
- XML NF-e
- Associação fornecedor SKU -> produto
- Unidade comercial / unidade de estoque
- Fator multiplicação / fator conversão
- Formação de custo unitário
- Confirmação de entrada transacional
- Estoque + custo + status ENTRADA + compras
- Reabertura segura de NF
- Exclusão segura de item e nota
- Inventário e estoque inicial editáveis
- Vendas consolidadas
- XLSX formatado / PDF / impressão
- Autodiagnóstico

ANTES DE ABRIR:
1. Faça backup do seu hnt_foodservice_v3.db atual.
2. Copie esse banco para esta pasta.
3. Execute INSTALAR_E_ABRIR.bat na primeira vez; depois ABRIR.bat.
4. Execute VALIDAR_V10.bat para conferir a estrutura.

REGRA DE COMPRAS:
Somente NF com status ENTRADA entra no Dashboard.
Compras = soma do xml_total dos itens das NF confirmadas.
