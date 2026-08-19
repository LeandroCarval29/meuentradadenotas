# HNT FoodService BI V3

Sistema local, sem licença e sem expiração.

Cadastro inicial: 649 itens amplos de food service, com cadastro ilimitado por Excel ou tela.

Módulos: DF-e/SEFAZ, XML NF-e, produtos, múltiplos barcodes, fornecedores, vendas, estoque, custo médio 3 meses, inventário import/export, contagem de compra por dia, cotações, retiradas, perdas, CMV semanal/quinzenal/mensal, Pareto, representatividade e assistente BI.

## Rodar
1. Instale Python 3.12+
2. Extraia a pasta.
3. Execute INICIAR.bat.
4. Abra http://localhost:8501

## SEFAZ
Configure CNPJ, código UF e PFX. A senha do PFX não é gravada. A consulta usa NFeDistribuicaoDFe e controle de ultNSU. Homologue antes de usar em produção.

## CMV
- CMV Compras % = Compras / Vendas
- Perdas % = Perdas / Vendas
- Compras + Perdas % = (Compras + Perdas) / Vendas
- CMV Contábil = Estoque Inicial + Compras - Estoque Final, quando houver inventários comparáveis.


## Melhorias V3.1

### Inventário por categoria
- Inventário manual pode ser filtrado por uma ou várias categorias.
- Exportação da planilha de contagem pode ser GERAL ou conter somente categorias selecionadas.
- Modelo padrão de inventário contém Categoria e Subcategoria.
- Histórico de inventário também pode ser filtrado por categoria.
- Importação continua usando o Código Produto como chave principal e preserva categoria para conferência.

### Retiradas por categoria
- Filtro por uma ou várias categorias antes de selecionar o produto.
- Histórico de retiradas filtrável pelas mesmas categorias.
- Exibe categoria, subcategoria, quantidade, custo e valor da retirada.

### Crítica de custo na entrada de NF-e
Ao associar um item fiscal a um produto interno, o sistema compara automaticamente:
1. custo unitário convertido da NF-e;
2. custo médio dos últimos 3 meses;
3. último custo histórico não-zero.

Quando o preço atual estiver acima das referências, a tela apresenta alerta com a variação percentual.

### Fornecedores mais em conta
O módulo Cotações agora possui:
- cotações atuais;
- melhor proposta atual;
- variação entre fornecedor mais barato e mais caro;
- histórico real das NF-e lançadas;
- custo médio ponderado convertido por produto e fornecedor;
- fornecedor historicamente mais barato por produto;
- economia potencial percentual;
- exportação para Excel do relatório de fornecedores mais em conta.


## V3.2 — Correção de Vendas e Ampliação de Bebidas

### Importação de vendas
- Detecta automaticamente colunas com nomes equivalentes (Data/Data Venda/Dia, Loja/Unidade/Filial, Venda Líquida/Faturamento Líquido, etc.).
- Aceita moeda em formato brasileiro, inclusive `R$ 12.345,67`.
- Aceita datas `dd/mm/aaaa`, datas nativas do Excel e outros formatos reconhecíveis.
- Mostra prévia, período e totais antes de gravar.
- Evita duplicidade por `Data + Loja`.
- Permite atualizar um registro existente ou ignorar duplicados.
- Permite filtrar vendas por loja e período e exportar o resultado.
- Gera relatório de erros quando alguma linha não puder ser importada.

### Catálogo de bebidas
- Cadastro ampliado de refrigerantes, águas, sucos, chás, isotônicos, energéticos, xaropes, bases e drinks sem álcool.
- Famílias não alcoólicas de Coca-Cola, Sprite, Fanta, Del Valle, Powerade, Pepsi, Guaraná Antarctica, H2OH!, Gatorade e Heineken 0.0.
- Categoria administrativa para bebidas alcoólicas permanece disponível para cadastro/importação pelo estabelecimento.
- O catálogo é migratório: ao abrir a V3.2 sobre um banco existente, novos itens do catálogo são adicionados sem apagar os produtos já cadastrados.

### Modelo Excel de vendas
O `MODELO_VENDAS.xlsx` foi atualizado com exemplos numéricos e exemplos em moeda brasileira.

## V4 - Gestão de estoque e inventário

- Importação de vendas simplificada: o usuário escolhe a coluna de Data, Venda Líquida e, opcionalmente, Loja/Venda Bruta.
- Inventário exporta todos os itens no modo GERAL ou todos os itens das categorias selecionadas, com quantidade em branco para contagem.
- Central de Custos Médios: custo ajustado passa a ser o custo vigente em estoque, inventário, retiradas e perdas. NF-e histórica permanece auditável.
- CMV de inventário: Estoque Inicial + Compras - Estoque Final, com filtro opcional por categoria.
- Dias de estoque, estoque de segurança, mínimo, padrão e máximo calculados pelas movimentações de retirada/perda.
- Contagem & Compras possui modelo padrão de Excel para exportação/importação.
- Impressão de etiquetas em PDF: tamanho em mm, número de colunas, margem, espaçamento, cópias e escolha do barcode interno/adicional.
- Catálogo não alcoólico ampliado: Ice Tea, Monster, Red Bull, Del Valle, guaranás naturais, isotônicos, Coca-Cola e Pepsi/Ambev.
- Categoria administrativa de bebidas alcoólicas disponível para cadastro/importação fiscal pelo estabelecimento.

### Observação de auditoria de custos
O sistema não reescreve os valores fiscais históricos de notas já lançadas. O ajuste na Central de Custos altera o custo vigente usado para avaliação operacional atual. Isso preserva rastreabilidade das NF-e.

## V4.2 – Vendas, CMV, dispositivos, backup e logs

- Importação de vendas simplificada para 3 colunas obrigatórias: DATA, PRESENCIAL e DELIVERY. LOJA é opcional.
- Data exibida em formato abreviado dd/mm/aa.
- Classificação automática de cada venda em 1ª, 2ª, 3ª ou 4ª semana do mês.
- Venda Total = Presencial + Delivery.
- CMV semanal usa a Venda Total e mostra Presencial, Delivery, Compras e Perdas por semana.
- CMV geral mantém Estoque Inicial + Compras - Estoque Final e usa a Venda Total para os percentuais.
- Valores principais exibidos no padrão brasileiro R$ 1.234,56; custos unitários podem exibir até 6 casas decimais com vírgula.
- Nova aba Logs com usuário, dispositivo, data/hora, módulo, ação e detalhes.
- Configuração de aparelho: Computador, Notebook, Tablet, Celular ou Terminal de Estoque.
- Backup: exportação do arquivo .db e restauração/importação de um backup, com cópia automática antes da substituição.
- O modo de rede local e a documentação para implantação externa/Supabase continuam incluídos.

### Observação sobre bebidas alcoólicas
O cadastro mantém uma categoria administrativa para bebidas alcoólicas, mas esta distribuição não inclui um catálogo pré-carregado detalhado de marcas de cerveja, vinho ou destilados. SKUs administrativos existentes do estabelecimento podem ser mantidos por importação/cadastro autorizado.


## V4.4 — Correção SQLite / Cotações / Entrada Manual

### Cotações
- Corrigido `sqlite3.OperationalError: database is locked`.
- SQLite usa WAL, `busy_timeout` e timeout de 30 segundos.
- Cadastro automático do fornecedor durante a cotação usa a mesma conexão/transação.
- Importação de cotações trata erros linha a linha e não trava o banco inteiro.

### Entrada manual de notas
A aba Notas / XML agora aceita:
1. Importação XML NF-e.
2. Criação de Nota Manual.

Na entrada manual é possível:
- selecionar fornecedor já cadastrado;
- cadastrar fornecedor no ato;
- informar número, série, data e observações;
- adicionar vários itens manualmente;
- informar código do fornecedor, descrição, unidade, quantidade, valor unitário, barcode, NCM e CFOP;
- associar ao produto interno;
- cadastrar o produto interno durante a associação se ele ainda não existir;
- usar fatores de multiplicação e conversão;
- receber crítica automática de custo;
- confirmar a entrada no estoque usando o mesmo motor das NF-e XML.


## V4.3 STREAMLIT STABLE

Esta edição mantém a interface Streamlit aprovada e corrige os pontos de estabilidade.

### Correções
- SQLite com WAL, timeout de 30s e busy_timeout.
- Cotações usam uma única conexão/transação ao cadastrar fornecedor.
- DF-e não mantém o SQLite travado durante importação de NF-e.
- Vendas: importação oficial DATA | PRESENCIAL | DELIVERY | LOJA.
- Data abreviada e semana do mês automáticas.
- Entrada manual de notas no mesmo módulo do XML.
- Fornecedor pode ser cadastrado na criação da nota manual.
- Itens manuais passam pelo mesmo fluxo de associação/conversão/crítica de custo.
- Cadastro de produto durante associação da NF-e continua disponível.
- Mantidos inventário por categoria, custos médios, CMV, estoque de segurança,
  relatórios, etiquetas, logs, backup e DF-e/SEFAZ.

### Instalação
Primeira vez: execute INSTALAR_E_ABRIR.bat.
Depois: execute ABRIR.bat.
Para celular/tablet na mesma rede: ABRIR_REDE.bat.

Se houver problema: execute DIAGNOSTICO.bat.


## Stable 2
- CMV: participação de cada categoria sobre vendas e compras.
- CMV de inventário por categoria quando há inventários no período.
- Produto de maior impacto em cada categoria.
- Linha do tempo / extrato de itens.
- Etiquetas em lote com impressora configurável, impressão direta e botão IMPRIMIR.


## V4.3 Cloud Simples 3 — Controle de Notas e Inventários

### Notas
- Seleção individual ou em grupo.
- COLOCAR EM ABERTO: se a nota já tiver dado entrada, o sistema desfaz os movimentos da nota e volta para PENDENTE.
- Dados de cabeçalho e itens podem ser alterados quando a nota está aberta.
- FECHAR ALTERAÇÃO bloqueia novas edições.
- EXCLUIR / LIBERAR REIMPORTAÇÃO remove nota/itens, desfaz estoque e libera o XML/DF-e novamente.
- Novas entradas registram invoice_id no movimento para reversão exata.
- Auditoria de reabertura/fechamento.

### DF-e / SEFAZ
- Lista operacional mostra somente documentos ainda pendentes para o CNPJ da loja configurada.
- Quando a entrada da nota é concluída, ela deixa a caixa de pendências.

### Inventários
- Novo ciclo: ABERTO / FECHADO.
- Criar, abrir para alterar, fechar, reabrir ou excluir.
- Inventário aberto não altera estoque nem CMV.
- Ao fechar, são criados os ajustes de estoque.
- Ao reabrir/excluir, os ajustes do inventário são revertidos.
- Planilha geral ou por categoria pode ser exportada e reimportada durante o inventário aberto.
- Inventários antigos sem sessão continuam tratados como fechados para compatibilidade.


## V4.3 CLOUD SIMPLES 4

Novidades:
- Tabelas de fornecedores: upload XLS/XLSX, cadastro manual de itens, associação a produto existente ou criação do produto no ato.
- A associação vira mapping e é reutilizada na NF-e.
- Produto pode ser criado durante inventário.
- Custo do inventário é editável; quando alterado vira custo vigente e entra no Extrato de Custos.
- Novo Extrato de Custos por produto.
- Central de Correções/Exclusões para vendas, retiradas, perdas, cotações, contagens e itens de fornecedor.
- Assistente IA opcional usando Gemini API free tier via GEMINI_API_KEY.
- Etiquetas: código de barras REAL (EAN13/Code128), com regra automática:
  * pesáveis (hortifruti, proteínas, peixes, frangos e laticínios) -> código interno;
  * demais -> código de barras do fornecedor.
  A grade permite corrigir/informar o barcode antes de imprimir.
- DF-e/SEFAZ: auto-sync quando o app abre, no máximo uma vez por hora; diagnóstico cStat/xMotivo/ultNSU/maxNSU.
- PFX/senha podem ser configurados por Streamlit Secrets.

IMPORTANTE:
O Streamlit Community Cloud NÃO garante persistência do SQLite local. Para manter dados gravados em produção,
use banco/armazenamento externo persistente. Esta versão mantém migrações aditivas e não apaga os dados de um
banco SQLite existente quando ele é reutilizado.


## LOCAL STABLE 6 — Vendas Diárias e BI

Novo módulo de Vendas:
- Importação múltipla de Excel.
- Reconhecimento de Venda_3s, Geral_99 e conciliação iFood.
- 3S: venda sem gorjeta.
- 99: Fica Loja = Receita total.
- iFood: Fica Loja = soma dos lançamentos financeiros associados aos pedidos de cada dia.
- Digitação manual.
- Alteração e exclusão de vendas.
- Ticket médio e clientes/tickets diários.
- Venda/Fica Loja dia a dia.
- Dia da semana e participação percentual.
- Participação por origem e marca.
- Comparação automática com período anterior de mesma duração.
- Dashboards de Venda x Fica Loja, clientes e ticket médio.
- Reimportação é idempotente por Data + Origem + Marca + Loja, substituindo a apuração daquela chave sem duplicar.


## LOCAL STABLE 7 — REGRA CORRETA DE VENDAS

Consolidado operacional:
- BALCÃO 3S = Total Bruto - Total Gorjeta.
- DELIVERY = tudo que não é 3S.
- 99 = coluna Receita total (líquido loja).
- iFood = soma da coluna valor somente das linhas impacto_no_repasse = SIM.
- Total Consolidado = Balcão 3S sem gorjeta + Delivery líquido.

O sistema mantém separadamente a venda bruta/base dos deliveries para análise,
mas NÃO soma essa venda bruta ao consolidado operacional.

iFood:
- Venda Bruta = valor_cesta_final uma vez por pedido.
- Entradas/Créditos, Taxas/Comissões e Serviços/Promoções/Ajustes.
- Líquido Loja reconciliado pelo impacto_no_repasse = SIM.


## LOCAL STABLE 8 FAST

### Excel / PDF / Impressão
- Exportações operacionais agora usam XLSX formatado, PDF e botão de impressão.
- CSV/XML não são mais oferecidos pelo botão padrão de exportação.
- Valores monetários são exportados como NÚMEROS Excel, com formato R$ #.##0,00.
- Datas são datas Excel e percentuais são percentuais reais.
- XLSX possui cabeçalho formatado, autofiltro, tabela, congelamento da primeira linha e aba Resumo.
- Planilhas padrão XLSX disponíveis nos módulos de entrada principais.

### Estoque Inicial
- Novo módulo Contagem Inicial de Estoque.
- Criar contagem inicial aberta.
- Cadastrar produto durante a contagem.
- Quantidade e custo informados no ato.
- Custo passa a compor custo vigente e Extrato de Custos.
- Ao fechar, cria movimento OPENING no Extrato de Itens.
- Reabrir/excluir desfaz os movimentos do estoque inicial.
- Importação/exportação XLSX e PDF/impressão.

### Vendas
- Importar arquivo não sobrescreve Data+Origem+Marca+Loja já existentes.
- Somente dias/registros inexistentes são acrescentados.
- Para substituir um lançamento existente, use a alteração manual.

### Performance
- Novos índices SQLite para NF, itens, movimentos, inventário, perdas, vendas e DF-e.
- PRAGMA synchronous NORMAL, cache em memória e mmap.
- Cadastro de produtos em cache curto.
- Itens de notas paginados em 10 por página, reduzindo a carga de widgets e consultas.


## LOCAL STABLE 9 — CONTAGENS EM TABELA

Melhorias de operação:
- Estoque Inicial: grade editável com vários produtos de uma vez.
- Inventário: grade editável com quantidade e custo na mesma linha.
- Contagem & Compras: contagem rápida em tabela.
- Entrada de Notas: itens da NF em tabela, reduzindo expanders e cliques.
- Associação de item de fornecedor a produto feita por seleção simples.
- Cadastro de produto no ato mantido em Estoque Inicial, Inventário e Notas.
- Custos continuam alimentando custo médio e Extrato de Custos.
- Exportação XLSX/PDF/impressão mantida.


## LOCAL STABLE 9.1 — FIX XLSX / NOTAS

Correção:
- Removido autofiltro duplicado do XlsxWriter.
- A tabela XLSX já possui autofiltro nativo.
- Exportações XLSX/PDF agora são isoladas em tratamento de erro.
- Uma falha de exportação não derruba mais o módulo operacional.
- Entrada de Notas volta a carregar normalmente.


## LOCAL STABLE 9.2 — IMPORTAÇÃO XML NF-e

- Removida planilha padrão XLSX para importação de NF.
- NF-e entra pelo XML fiscal.
- Permite importar vários XMLs de uma vez.
- Preview: NF, série, emissão, fornecedor, CNPJ, quantidade de itens e valor.
- Cria/atualiza fornecedor automaticamente.
- Importa todos os itens do XML.
- Reutiliza associações fornecedor SKU -> produto existentes.
- Nota importada fica PENDENTE e ABERTA para revisão/associação.
- XML já existente é mantido sem duplicar a nota.
- XLSX permanece somente como exportação de listagens/relatórios.


## LOCAL STABLE 9.3 — CUSTO UNITÁRIO NA ENTRADA DE NOTAS

Mantida a configuração da Entrada de Notas e acrescentados:
- Unidade Comercial.
- Unidade de Estoque.
- Fator Multiplicação.
- Fator Conversão.
- Quantidade Convertida.
- Custo Unitário calculado.

Fórmulas:
Qtd Convertida = Qtd Fiscal × Fator Multiplicação × Fator Conversão
Custo Unitário = Valor do Item ÷ Qtd Convertida

A regra é salva por Fornecedor + SKU e reutilizada em novas NF-e.


## LOCAL STABLE 9.4 — EDIÇÃO TOTAL

Regra geral do sistema:
- Dados digitados ou importados devem poder ser corrigidos ou excluídos.
- NF-e: reabrir, editar descrição, barcode, quantidade, valor do item, unidade comercial,
  unidade de estoque, fator de multiplicação, fator de conversão, custo e associação.
- NF-e: excluir item individual.
- NF-e: excluir a nota completa e liberar o XML para reimportação.
- NF-e já lançada: a reabertura estorna a entrada no estoque antes da edição.
- Inventário: reabrir, alterar quantidade/custo e excluir item individual.
- Inventário fechado: a reabertura remove os ajustes antes da alteração.
- Estoque Inicial: reabrir, alterar quantidade/custo e excluir item individual.
- Central de Correções continua disponível para os demais lançamentos.


## LOCAL STABLE 9.5 — FIX ENTRADAS / COMPRAS

Correção crítica:
- Confirmação de NF agora usa uma única transação SQLite.
- Movimento de estoque, histórico de custo, custo vigente, status ENTRADA e DF-e são atualizados juntos.
- Eliminado o conflito de segunda conexão que podia impedir a gravação da entrada.
- Em erro, tudo é revertido; não há entrada parcial.
- Compras do Dashboard usam exatamente as NF com Status ENTRADA.
- Dashboard ganhou Diagnóstico de Compras para conferência.


## LOCAL STABLE 9.6 — FIX EXCLUSÃO DE ITEM DA NF

- Exclusão de item feita em uma única transação SQLite.
- Se a NF já estava em ENTRADA, todos os movimentos da NF são estornados antes da exclusão.
- Histórico de custo gerado pela NF é removido no estorno.
- Custo vigente dos produtos afetados é recalculado pelo último histórico restante.
- Somente o item selecionado é excluído.
- NF fica PENDENTE/ABERTA para revisão.
- DF-e volta para XML COMPLETO.
- Auditoria registra item excluído e se houve estorno.
- Interface captura erro sem derrubar a página.
