# Motor Cuantitativo Python (`trading_engine`)

Este directorio contiene el motor cuantitativo autónomo de **Bot de Finanzas** escrito en Python. Opera de manera independiente al dashboard web y cumple estrictamente las reglas de seguridad financiera:

- **Modo por defecto**: `paper` (operaciones virtuales persistidas en SQLite).
- **Operaciones reales (`live`)**: Deshabilitadas por código y configuración a menos que se superen las 12 comprobaciones de seguridad obligatorias.
- **Sin apalancamiento ni retiros**: Solo mercado spot (`BTC/USDT`, `ETH/USDT`), máximo 1 posición simultánea, riesgo previsto de `0,5%` por operación, pérdida diaria máxima de `1,0%` y drawdown máximo de `5,0%`.

## Instalación en entorno virtual (Linux / macOS / Windows)

```bash
cd trading_engine
python3 -m venv .venv
source .venv/bin/activate  # En Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip install -e .
```

## Ejecución de pruebas automatizadas

El motor incluye soporte híbrido: utiliza `pytest`/`pydantic`/`pandas`/`fastapi` cuando están instalados en el entorno virtual y cuenta con adaptadores deterministas de biblioteca estándar (`sqlite3`, `unittest`, `http.server`) para poder verificarse incluso en contenedores restringidos sin acceso a PyPI:

```bash
# Con pytest (en entorno virtual completo):
PYTHONPATH=src pytest

# Con unittest estándar (sin dependencias externas):
PYTHONPATH=src python3 -m unittest discover -s tests -p "test_*.py" -v
```

## Comandos del CLI (`trading_bot.cli`)

```bash
# Verificar estado de salud y configuración
PYTHONPATH=src python3 -m trading_bot.cli status

# Ejecutar backtest comparativo de las 3 estrategias (división 60/20/20)
PYTHONPATH=src python3 -m trading_bot.cli backtest --symbol BTC/USDT --strategy all

# Ejecutar un ciclo de evaluación de Paper Trading
PYTHONPATH=src python3 -m trading_bot.cli paper-step --symbol BTC/USDT

# Iniciar el servidor API HTTP/FastAPI en el puerto 8000
PYTHONPATH=src python3 -m trading_bot.cli serve --host 127.0.0.1 --port 8000
```
