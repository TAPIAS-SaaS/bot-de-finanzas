# Seguridad, Secretos y Permisos (`SECURITY.md`)

## 1. Gestión de Claves y Secretos

- **Prohibición de secretos en el código y el frontend**: Ninguna clave privada (`GEMINI_API_KEY`, `EXCHANGE_API_KEY`, `EXCHANGE_API_SECRET`, `ADMIN_API_TOKEN`) se incluye en el código fuente, en los paquetes enviados al navegador ni en el repositorio de GitHub.
- **Redacción automática en SQLite y logs**: `SQLiteAuditStore` y `NodeSQLiteAuditRepository` inspeccionan los mensajes de auditoría antes de escribir en disco y redactan cualquier patrón `API_KEY=...`, `SECRET=...`, `TOKEN=...` o `PASSWORD=...`.
- **Protección de `.gitignore`**: Se excluyen todos los archivos `.env*` (salvo `.env.example`), bases de datos `*.sqlite*`, certificados `*.pem`/`*.key` y pesos locales de modelos.

## 2. Permisos Mínimos de la API del Exchange (Cuando se considere pasar a Live)

Si en el futuro el titular de la cuenta decide conectar un exchange compatible con CCXT:
1. Crear una clave API dedicada exclusivamente a **Lectura y Trading Spot**.
2. **Deshabilitar obligatoriamente el permiso de Retiros (*Enable Withdrawals = OFF*)**. El método `SpotExchangeAdapter.withdraw()` lanza `PermissionError` a nivel de código.
3. **Deshabilitar permisos de Margen, Préstamos y Futuros**.
4. Activar restricción de acceso por **dirección IP fija** (lista blanca de IPs del servidor donde corra el motor Python).

## 3. Procedimiento de Rotación y Revocación de Claves API

1. **Ante sospecha de exposición o rotación periódica (cada 90 días)**:
   - Activar inmediatamente el **Interruptor de Emergencia (Kill Switch)** en el Dashboard (`POST /api/engine/pause`).
   - Ingresar al panel de seguridad del exchange y **revocar/eliminar** la clave API anterior.
   - Si aplica a Gemini, revocar la clave en Google AI Studio / Google Cloud Console y actualizar el secreto en el panel **Settings > Secrets**.
   - Verificar en SQLite (`audit_events` y `orders_log`) que no existan órdenes abiertas o pendientes de reconciliación antes de configurar la nueva clave en `.env`.
