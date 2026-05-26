# Guia de Testes - RAC Price Monitor v2.0

## 📋 Pré-requisitos

### 1. Instalar Dependências

```bash
# Instalar todas as dependências
pip install -r requirements.txt

# Instalar browsers do Playwright (Chrome, Firefox)
playwright install chromium
playwright install firefox
```

### 2. Configurar Variáveis de Ambiente

```bash
# Copiar template de configuração
cp .env.example .env

# Editar com suas credenciais (opcional para testes básicos)
nano .env
```

**Configuração mínima para testes:**
```env
# Pode deixar em branco para testes locais sem Supabase
SUPABASE_URL=
SUPABASE_KEY=

# Settings de scraper
MAX_BROWSERS=2
HEADLESS=true
MIN_DELAY=0.5
MAX_DELAY=1.0
MAX_PAGES=2
ENABLE_SCREENSHOTS=false
```

---

## 🧪 Tipos de Testes

### 1. Teste de Sintaxe e Imports

Verifica se todos os módulos importam corretamente:

```bash
python -m pytest src/tests/test_imports.py -v
```

### 2. Teste de Configuração

Valida se as configs YAML são carregadas corretamente:

```bash
python -m pytest src/tests/test_config.py -v
```

### 3. Teste Unitário (Mock)

Testa lógica de negócio sem navegar em sites reais:

```bash
python -m pytest src/tests/test_unit.py -v
```

### 4. Teste de Integração (Real)

Executa scraping real em sites (mais lento):

```bash
# Teste rápido (apenas 1 keyword, 2 páginas)
python -m src.main --platforms mercado_livre --keywords ar-condicionado-split --output test_output.csv

# Teste completo
python -m src.main --all --output full_collection.csv
```

### 5. Teste de Status

Mostra configurações ativas sem coletar:

```bash
python -m src.main --status
```

---

## 🚀 Comandos de Teste Rápidos

### Teste 1: Verificar Status do Sistema
```bash
cd /workspace
python -m src.main --status
```

**Resultado esperado:** Tabela mostrando:
- Total de keywords
- Keywords habilitadas
- Plataformas disponíveis
- Configurações ativas

### Teste 2: Coleta Rápida (Mercado Livre)
```bash
python -m src.main \
  --platforms mercado_livre \
  --priority alta \
  --output teste_ml.csv \
  --keywords ar-condicionado-split-12000-btus
```

**Resultado esperado:**
- CSV com ~16-22 produtos
- Logs em `logs/rac_scraper_YYYY-MM-DD.log`
- Mensagem: "✓ Collection complete: X records"

### Teste 3: Coleta Múltiplas Keywords
```bash
python -m src.main \
  --platforms mercado_livre \
  --priority alta \
  --output teste_priority.csv
```

**Resultado esperado:**
- Coleta todas keywords de prioridade "alta"
- CSV consolidado

### Teste 4: Executar Testes Unitários
```bash
python -m pytest src/tests/ -v --tb=short
```

---

## 📁 Estrutura de Testes

```
src/tests/
├── __init__.py
├── conftest.py              # Fixtures compartilhados
├── test_imports.py          # Testa imports
├── test_config.py           # Testa carregamento de configs
├── test_models.py           # Testa ProductRecord
├── test_scraper_base.py     # Testa BaseScraper
├── test_mercado_livre.py    # Testa scraper ML (mock)
├── test_dealers.py          # Testa scraper dealers (mock)
└── test_integration.py      # Teste end-to-end
```

---

## 🔍 Debug de Problemas Comuns

### Erro: "Browser not found"
```bash
# Reinstalar browsers
playwright install chromium --force
```

### Erro: "ModuleNotFoundError"
```bash
# Reinstalar dependências
pip install -r requirements.txt --upgrade
```

### Erro: "CAPTCHA detected"
- Aumente os delays no `.env`
- Use `HEADLESS=false` para debug
- Reduza `MAX_PAGES`

### Erro: "0 produtos coletados"
- Verifique selectors em `configs/selectors/`
- Execute com `--status` para validar config
- Check logs em `logs/` para detalhes

---

## 📊 Validação de Resultados

### Verificar CSV gerado:
```bash
# Contar linhas (exclui header)
wc -l teste_ml.csv

# Visualizar primeiras linhas
head -n 10 teste_ml.csv

# Validar colunas
head -n 1 teste_ml.csv | tr ',' '\n'
```

### Colunas esperadas (19 total):
```
collection_id, timestamp, platform, keyword, product_name, brand, 
price_original, price_current, discount, seller, seller_rating, 
fulfillment, shipping_info, product_url, image_url, availability, 
category, scraped_at, metadata_json
```

---

## 🎯 Checklist de Validação

- [ ] Dependencies instaladas (`pip list | grep playwright`)
- [ ] Browsers instalados (`playwright install chromium`)
- [ ] `.env` configurado
- [ ] `python -m src.main --status` funciona
- [ ] Coleta rápida retorna >0 produtos
- [ ] CSV gerado tem colunas corretas
- [ ] Logs estão sendo gravados em `logs/`
- [ ] Tests unitários passam (`pytest src/tests/ -v`)

---

## 📈 Próximos Passos Após Testes

1. **Configurar Supabase** (opcional):
   ```bash
   # Adicionar credenciais no .env
   SUPABASE_URL=https://xxx.supabase.co
   SUPABASE_KEY=xxx
   ```

2. **Agendar coletas automáticas**:
   ```bash
   # Exemplo cron (Linux)
   0 */6 * * * cd /workspace && python -m src.main --all --output /data/$(date +\%Y\%m\%d).csv
   ```

3. **Iniciar Dashboard**:
   ```bash
   streamlit run src/dashboard/app.py
   ```

4. **Habilitar notificações Telegram**:
   ```env
   TELEGRAM_BOT_TOKEN=xxx
   TELEGRAM_CHAT_ID=xxx
   ENABLE_NOTIFICATIONS=true
   ```

---

## 🆘 Suporte

Para issues específicos:
1. Check logs em `logs/rac_scraper_YYYY-MM-DD.log`
2. Execute com `--status` para validar config
3. Rode testes unitários para isolar problema
4. Consulte `docs/ARQUITETURA.md` para detalhes técnicos
