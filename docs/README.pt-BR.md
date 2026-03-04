# NetOps Inspector (Português - Brasil)

Language: [English](../README.md) | [한국어](README.ko.md) | [日本語](README.ja.md) | [Español](README.es.md) | [Português (Brasil)](README.pt-BR.md) | [简体中文](README.zh-CN.md)

NetOps Inspector é uma ferramenta CLI para inspeção de dispositivos de rede multi-vendor e backup de configuração.
Ela lê inventários de dispositivos em Excel/CSV/JSON, conecta via SSH/Telnet, executa comandos de inspeção, faz parsing das saídas e gera arquivos de resultado (Excel/JSON/CSV).

## Principais recursos

- Arquitetura multi-vendor (módulos em `vendors/`)
- Modos de execução: Inspeção / Backup / Inspeção+Backup
- Modo preflight (checagem de inventário/referências de credenciais/TCP)
- Execução em lote de comandos personalizados a partir de TXT ou Excel
- Validação de inventário (campos obrigatórios, IP duplicado, compatibilidade vendor/OS)
- Controle de retry e timeout para I/O de rede
- Dashboard de terminal em tempo real durante a execução
- Arquivos de log de sessão por dispositivo
- Geração de arquivos de resultado (Excel/JSON/CSV) com alias/ordem de colunas configurável
- Extensões de parsing e comandos definidas pelo usuário via `custom_rules.yaml`
- UI/mensagens com i18n (`en`, `ko`, `ja`, `es`, `pt-BR`, `zh-CN`)

## Vendors suportados (módulos atuais)

- `alcatel-lucent`
- `aruba`
- `axgate`
- `cisco`
- `dayou`
- `handreamnet`
- `juniper`
- `nexg`
- `piolink`
- `ruckus`
- `ubiquoss`

Os valores de OS suportados dependem de cada módulo de vendor e dos mapas de comando em `vendors/__init__.py`.

## Requisitos

- Python 3.10+
- Conectividade de rede com os dispositivos alvo
- Dependências em `requirements.txt`

Instalação:

```bash
pip install -r requirements.txt
```

## Início rápido

Execute:

```bash
python main.py
```

Menu principal:

1. Iniciar inspeção/backup
2. Executar arquivo de comandos personalizados
3. Alterar configurações
4. Mostrar lista de `device_type` do Netmiko
5. Executar preflight
6. Sair

## Esquema de entrada de inventário

Formatos de inventário suportados:

- Excel: `.xlsx`, `.xls`, `.xlsm`
- CSV: `.csv`
- JSON: `.json`
  - Formato lista: `[{"ip":"...","vendor":"..."}]`
  - Formato encapsulado: `{"devices":[{"ip":"...","vendor":"..."}]}`

Arquivos de exemplo:

- `examples/inventory/devices.csv`
- `examples/inventory/devices.json`
- `examples/inventory/devices_wrapped.json`

Colunas obrigatórias:

- `ip`
- `vendor`
- `os`
- `connection_type` (`ssh` ou `telnet`)
- `port`
- `password`

Colunas opcionais:

- `username`
- `enable_password`

Sintaxe de referência de credenciais (opcional):

- `username`, `password`, `enable_password` aceitam `env:NOME_VARIAVEL`
- Exemplo: `password: env:NETOPS_DEVICE_PASSWORD`
- Se a variável de ambiente estiver vazia/ausente, o dispositivo falha com segurança

Exemplo:

| ip | vendor | os | connection_type | port | username | password | enable_password |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 192.168.1.10 | cisco | ios | ssh | 22 | admin | ****** | ****** |
| 192.168.1.20 | ruckus | icx | ssh | 22 | super | ****** | |

## Configurações (`settings.yaml`)

O arquivo é criado automaticamente no diretório da aplicação quando não existe.

Chaves comuns:

- `console_log_level`: `CRITICAL`/`ERROR`/`WARNING`/`INFO`/`DEBUG`
- `max_retries`: máximo de tentativas de conexão
- `timeout`: timeout de conexão (segundos)
- `max_workers`: número de workers em paralelo
- `inspection_excludes`: mapa de exclusão de parsing por vendor/OS
- `output_plugin`: `excel_results` | `json_results` | `csv_results`

Chaves de saída de inspeção:

- `column_aliases`: normaliza nomes de colunas de inspeção
- `inspection_column_order_global`
- `inspection_column_order_by_profile`

Chaves de i18n:

- `language`
- `fallback_language`
- `input_column_aliases`

Exemplo:

```yaml
language: en
fallback_language: en
console_log_level: WARNING
max_retries: 3
timeout: 10
max_workers: 10

input_column_aliases:
  "ip address": ip
  "vendor name": vendor
  "connection type": connection_type

column_aliases:
  "host name": Hostname
  "cpu usage": CPU Usage

output_plugin: excel_results
```

## i18n

Códigos de idioma aceitos atualmente:

- `en`
- `ko`
- `ja`
- `es`
- `pt-BR`
- `zh-CN`

Arquivos de tradução incluídos:

- `locales/en.yaml`
- `locales/ko.yaml`
- `locales/ja.yaml`
- `locales/es.yaml`
- `locales/pt-BR.yaml`
- `locales/zh-CN.yaml`

Códigos de idioma não suportados são normalizados para `en`.
Se faltar o arquivo de locale ou uma chave de tradução, as mensagens caem para `fallback_language` e depois para inglês.

## README multilíngue

- Korean: `docs/README.ko.md`
- Japanese: `docs/README.ja.md`
- Spanish: `docs/README.es.md`
- Portuguese (Brazil): `docs/README.pt-BR.md`
- Simplified Chinese: `docs/README.zh-CN.md`

## Rascunho de arquitetura

- Rascunho da plataforma de plugins: `docs/plugin-platform-draft.md`

## Regras customizadas (`custom_rules.yaml`)

Você pode estender comandos/parsers sem alterar código Python.

Seções de nível superior:

- `inspection_commands`
- `backup_commands`
- `parsing_rules`
- `connection_overrides`
- `handler_overrides`

Arquivo template:

- `custom_rules.example.yaml`

## Saídas

Caminhos gerados (com timestamp):

- Resultados de inspeção: `results/inspection_results_YYYYMMDD_HHMMSS.xlsx`
- Resultados de comandos personalizados: `results/command_results_YYYYMMDD_HHMMSS.xlsx`
- Resultados de preflight: `results/preflight_results_YYYYMMDD_HHMMSS.xlsx`
- Saídas JSON/CSV quando `output_plugin` estiver selecionado:
  - `results/*_YYYYMMDD_HHMMSS.json`
  - `results/*_YYYYMMDD_HHMMSS.csv`
- Arquivos de backup: `backup/YYYYMMDD_HHMMSS/[IP]_[vendor]_[os].txt`
- Logs de execução: `logs/netops_inspector_YYYYMMDD_HHMMSS.log`
- Logs de sessão: `session_logs/YYYYMMDD_HHMMSS/[IP]_[vendor]_[os].log`

## Testes

```bash
python -m pytest
```

## Build (Windows)

Uso:

```bat
build.bat
```

## Notas de segurança

- Não faça hardcode de credenciais nos arquivos-fonte.
- Prefira variáveis de ambiente ou entrega segura de segredos em runtime.
- Trate logs exportados e arquivos de resultados como dados operacionais sensíveis.

## Licença

MIT License
