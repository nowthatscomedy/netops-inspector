# NetOps Inspector (Español)

Language: [English](../README.md) | [한국어](README.ko.md) | [日本語](README.ja.md) | [Español](README.es.md) | [Português (Brasil)](README.pt-BR.md) | [简体中文](README.zh-CN.md)

NetOps Inspector es una herramienta CLI para inspección de dispositivos de red multi-vendor y respaldo de configuración.
Lee inventarios de dispositivos desde archivos Excel/CSV/JSON, se conecta por SSH/Telnet, ejecuta comandos de inspección, analiza salidas y genera libros de resultados.

## Funciones principales

- Arquitectura multi-vendor (módulos en `vendors/`)
- Modos de ejecución: Inspección / Respaldo / Inspección+Respaldo
- Ejecución por lotes de comandos personalizados desde TXT o Excel
- Validación de inventario (campos obligatorios, IP duplicada, compatibilidad vendor/OS)
- Control de reintentos y timeout para I/O de red
- Dashboard de terminal en tiempo real durante la ejecución
- Archivos de log de sesión por dispositivo
- Generación de libro de resultados con alias/orden de columnas configurable
- Extensiones de parsing y comandos definidas por el usuario vía `custom_rules.yaml`
- UI/mensajes con i18n (`en`, `ko`, `ja`, `es`, `pt-BR`, `zh-CN`)

## Vendors soportados (módulos actuales)

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

Los valores de OS soportados dependen de cada módulo de vendor y de los mapas de comandos en `vendors/__init__.py`.

## Requisitos

- Python 3.10+
- Conectividad de red hacia los dispositivos objetivo
- Dependencias en `requirements.txt`

Instalación:

```bash
pip install -r requirements.txt
```

## Inicio rápido

Ejecutar:

```bash
python main.py
```

Menú principal:

1. Iniciar inspección/respaldo
2. Ejecutar archivo de comandos personalizados
3. Cambiar configuración
4. Mostrar lista de `device_type` de Netmiko
5. Salir

## Esquema de entrada de inventario

Formatos de inventario soportados:

- Excel: `.xlsx`, `.xls`, `.xlsm`
- CSV: `.csv`
- JSON: `.json`
  - Forma lista: `[{"ip":"...","vendor":"..."}]`
  - Forma envoltura: `{"devices":[{"ip":"...","vendor":"..."}]}`

Archivos de ejemplo:

- `examples/inventory/devices.csv`
- `examples/inventory/devices.json`
- `examples/inventory/devices_wrapped.json`

Columnas obligatorias:

- `ip`
- `vendor`
- `os`
- `connection_type` (`ssh` o `telnet`)
- `port`
- `password`

Columnas opcionales:

- `username`
- `enable_password`

Ejemplo:

| ip | vendor | os | connection_type | port | username | password | enable_password |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 192.168.1.10 | cisco | ios | ssh | 22 | admin | ****** | ****** |
| 192.168.1.20 | ruckus | icx | ssh | 22 | super | ****** | |

## Configuración (`settings.yaml`)

El archivo se crea automáticamente en el directorio de la app si no existe.

Claves comunes:

- `console_log_level`: `CRITICAL`/`ERROR`/`WARNING`/`INFO`/`DEBUG`
- `max_retries`: máximo de reintentos de conexión
- `timeout`: timeout de conexión (segundos)
- `max_workers`: cantidad de workers en paralelo
- `inspection_excludes`: mapa de exclusión de parsing por vendor/OS

Claves de salida de inspección:

- `column_aliases`: normalizar nombres de columnas de inspección
- `inspection_column_order_global`
- `inspection_column_order_by_profile`

Claves i18n:

- `language`
- `fallback_language`
- `input_column_aliases`

Ejemplo:

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
```

## i18n

Códigos de idioma aceptados actualmente:

- `en`
- `ko`
- `ja`
- `es`
- `pt-BR`
- `zh-CN`

Archivos de traducción incluidos:

- `locales/en.yaml`
- `locales/ko.yaml`
- `locales/ja.yaml`
- `locales/es.yaml`
- `locales/pt-BR.yaml`
- `locales/zh-CN.yaml`

Los códigos de idioma no soportados se normalizan a `en`.
Si falta el archivo de locale o una clave de traducción, los mensajes usan `fallback_language` y luego inglés.

## README multilingüe

- Korean: `docs/README.ko.md`
- Japanese: `docs/README.ja.md`
- Spanish: `docs/README.es.md`
- Portuguese (Brazil): `docs/README.pt-BR.md`
- Simplified Chinese: `docs/README.zh-CN.md`

## Reglas personalizadas (`custom_rules.yaml`)

Puedes extender comandos/parsers sin modificar código Python.

Secciones de nivel superior:

- `inspection_commands`
- `backup_commands`
- `parsing_rules`
- `connection_overrides`
- `handler_overrides`

Archivo plantilla:

- `custom_rules.example.yaml`

## Salidas

Rutas generadas (con timestamp):

- Resultados de inspección: `results/inspection_results_YYYYMMDD_HHMMSS.xlsx`
- Resultados de comandos personalizados: `results/command_results_YYYYMMDD_HHMMSS.xlsx`
- Archivos de respaldo: `backup/YYYYMMDD_HHMMSS/[IP]_[vendor]_[os].txt`
- Logs de ejecución: `logs/netops_inspector_YYYYMMDD_HHMMSS.log`
- Logs de sesión: `session_logs/YYYYMMDD_HHMMSS/[IP]_[vendor]_[os].log`

## Pruebas

```bash
python -m pytest
```

## Build (Windows)

Uso:

```bat
build.bat
```

El script espera `NetOpsInspector.spec` en la raíz del repositorio.

## Notas de seguridad

- No hardcodees credenciales en archivos fuente.
- Se recomiendan variables de entorno o entrega segura de secretos en runtime.
- Trata logs y archivos de resultados exportados como datos operativos sensibles.

## Licencia

MIT License
