HNT FOODSERVICE BI V10.1 CORE ESTÁVEL

FOCO DESTA REVISÃO
- Corrigir o núcleo de Nota -> Produto -> Estoque -> Custo -> Compras.
- Extratos consultam diretamente os relacionamentos SQL.
- Estoque usa uma visão SQL única (v_stock_position), reduzindo consultas e aumentando velocidade.
- Custo médio é atualizado quando a NF entra.
- Inventário fechado atualiza saldo e custo numa única transação.
- Pesquisa de produto nos extratos é direta no banco.
- Mensagens de confirmação são padronizadas.
- Indicador/animation de execução do Streamlit é ocultado.
- Diagnóstico de integridade verifica entidades órfãs e divergências.

FONTE DE VERDADE
Saldo de estoque = soma da tabela movements.
Compras = itens de NF cujo status da nota = ENTRADA.
Custo vigente = cost_master; se ausente, última entrada válida.
Associação NF -> Produto = invoice_items.product_id.

ANTES DE USAR
1. Faça backup do hnt_foodservice_v3.db.
2. Copie o banco para a pasta V10.1.
3. Execute VALIDAR_V10_1.bat.
4. Abra o sistema.
5. Em Configurações, execute Autodiagnóstico e Integridade de Entidades.
