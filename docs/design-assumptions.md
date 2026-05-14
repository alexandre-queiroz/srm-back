# Premissas e Decisões de Design

Este documento registra decisões tomadas pelo autor onde a proposta original era ambígua ou silente. Cada item descreve o que foi assumido, por quê, e qual seria o caminho de evolução caso o requisito mude.

---

## 1. Multi-fundos

**Decisão:** o sistema opera com um único fundo, sem limite de capital e sem regras bloqueantes por fundo.

**Raciocínio:** a proposta não especificava múltiplos fundos nem regras de alocação entre eles. Introduzir a entidade `Fund` sem requisito claro seria over-engineering — adicionaria uma dimensão de isolamento (por fundo) em todas as queries sem benefício verificável no escopo atual.

**Evolução:** adicionar tabela `funds`, associar `batches` e `receivables` a um fundo, e aplicar limites de capital e regras de concentração por fundo.

---

## 2. Multi-tenant — Operador de Mesa, não Autoatendimento

**Decisão:** o usuário do sistema é um **operador interno da mesa de operações** da SRM Asset, não o próprio cedente ou sacado acessando um portal externo.

**Raciocínio:** a proposta descrevia um sistema de antecipação operado internamente. Não há requisito de portal do cedente, aprovação do sacado ou qualquer fluxo de autoatendimento. Por isso, não há segregação de tenant por empresa — um operador autenticado enxerga e opera sobre todos os cedentes e sacados sem restrição.

**Evolução:** introduzir `tenant_id` nas tabelas de operação, criar perfis de acesso por empresa e um portal externo para que cedentes acompanhem suas próprias operações.

---

## 3. Níveis de Acesso

**Decisão:** existe um único perfil de usuário com acesso total ao sistema — incluindo alteração de spread por tipo de recebível, taxa Selic nos parâmetros e confirmação de lotes de qualquer valor.

**Raciocínio:** a proposta não distinguia perfis (ex: operador, gerente, auditor). Criar roles sem requisito explícito adicionaria complexidade de autorização sem uso real.

**Evolução:** adicionar RBAC com pelo menos três perfis: `operator` (cria e consulta lotes), `manager` (aprova lotes acima de determinado valor, altera parâmetros), `auditor` (somente leitura).

---

## 4. Princípio dos 4 Olhos

**Decisão:** não há exigência de segundo operador para confirmar lotes — qualquer operador autenticado confirma qualquer lote independentemente do valor.

**Raciocínio:** o princípio dos 4 olhos (dual approval) não foi mencionado na proposta. Em FIDCs reais, lotes acima de determinado montante normalmente exigem aprovação de um segundo operador ou gerente. Isso foi omitido intencionalmente para não aumentar a complexidade do fluxo sem requisito explícito.

**Evolução:** adicionar campo `approved_by` no lote, criar status intermediário `pending_approval` e exigir aprovação de segundo operador com perfil `manager` para lotes acima de um limite configurável.

---

## 5. Bureau de Crédito

**Decisão:** nenhum cedente ou sacado passa por análise de crédito. Não há limite de exposição por empresa, score de risco ou restrição baseada em histórico de inadimplência.

**Raciocínio:** a proposta não mencionava integração com Serasa, Boa Vista, SPC ou qualquer bureau. O spread é orientado exclusivamente pelo **tipo de ativo** (produto), não pelo perfil de crédito da contraparte.

**Evolução:** integrar com bureau de crédito para scoring de sacados, criar tabela de limites por cedente/sacado e bloquear antecipações quando o limite de exposição for atingido.

---

## 6. Consulta ao BACEN / Duplicidade entre FIDCs

**Decisão:** o sistema não consulta nenhum registro externo antes de antecipar um recebível. É tecnicamente possível antecipar uma nota que já foi antecipada por outro FIDC.

**Raciocínio:** a integração com o sistema de registro de recebíveis do BACEN (ex: CERC, CIP) não foi especificada. O controle de duplicidade é interno ao sistema — uma nota já antecipada neste FIDC não pode ser antecipada novamente, mas o sistema não tem visibilidade sobre operações em outros fundos.

**Evolução:** integrar com a CERC ou CIP para registrar e consultar gravames antes de aprovar um lote, impedindo a dupla antecipação cross-FIDC.

---

## 7. Validação de XML de NF-e

**Decisão:** a única validação aplicada ao XML é de **idempotência por chave de acesso + número de parcela** — se a combinação já existe no banco, o registro é ignorado sem erro. O sistema aceita notas vencidas e permite antecipar recebíveis com vencimento no passado, tratados como `d+1`.

**Raciocínio:** a validação completa de NF-e exigiria consulta à SEFAZ/SERPRO para verificar autenticidade, cancelamento e situação fiscal da nota. Essa integração está fora do escopo do desafio. O fluxo ideal seria: upload → worker valida na SEFAZ → libera para antecipação.

**Evolução:** enviar o XML para um worker assíncrono que consulta a SEFAZ, valida a autenticidade e situação da nota, e só então altera o status do recebível para `available`.

---

## 8. Lastro Físico

**Decisão:** todo XML de NF-e enviado é armazenado no **Cloudflare R2** e o caminho do arquivo é vinculado ao recebível no banco. O arquivo original está disponível para auditoria a qualquer momento.

**Raciocínio:** em um FIDC real, o lastro físico das notas é requisito regulatório. Mesmo sem integração com SEFAZ, o arquivo original foi preservado para permitir auditoria manual caso necessário.

---

## 9. Auditoria por Usuário nas Tabelas

**Decisão:** todas as tabelas registram o usuário que realizou a última ação (`created_by`, `updated_by` ou equivalente), embora a interface não exiba essas colunas atualmente.

**Raciocínio:** rastreabilidade de operações financeiras é requisito implícito em qualquer sistema de FIDC. As colunas existem no banco e podem ser exibidas em uma tela de auditoria sem necessidade de migração.

---

## 10. Taxa de Câmbio D-1

**Decisão:** a taxa USD/BRL utilizada nas operações é sempre a taxa do **dia anterior (D-1)**, coletada pelo job diário. Não há taxa intraday — todas as operações realizadas no mesmo dia utilizam a mesma taxa.

**Raciocínio:** a PTAX do Banco Central é divulgada ao final do dia útil e é a referência padrão do mercado brasileiro para operações de câmbio em FIDCs. O uso da taxa do dia corrente (intraday) exigiria uma fonte de dados diferente e aumentaria a complexidade sem benefício claro para o modelo de precificação adotado.

**Evolução:** se o volume de operações justificar, adotar taxa intraday via B3 ou provedor de dados de mercado, com janelas de validade por horário.
