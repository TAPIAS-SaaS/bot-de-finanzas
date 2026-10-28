/**
 * Punto de entrada full-stack (`server.ts`) en el puerto 3000.
 * En desarrollo monta `vite.middlewares`; en producción sirve los estáticos de `dist/`.
 */

import 'dotenv/config';
import path from 'node:path';
import express from 'express';
import { createServer as createViteServer } from 'vite';
import { createExpressApp } from './server/index';

async function startServer() {
  const { app } = createExpressApp();
  const port = Number(process.env.PORT || 3000);

  if (process.env.NODE_ENV !== 'production') {
    const vite = await createViteServer({
      server: { middlewareMode: true },
      appType: 'spa',
    });
    app.use(vite.middlewares);
  } else {
    const distPath = path.resolve(process.cwd(), 'dist');
    app.use(express.static(distPath));
    app.get('*', (_req, res) => {
      res.sendFile(path.join(distPath, 'index.html'));
    });
  }

  app.listen(port, '0.0.0.0', () => {
    console.log(`Bot de Finanzas — Servidor activo en http://0.0.0.0:${port}`);
  });
}

startServer().catch((err) => {
  console.error('Error fatal al iniciar el servidor:', err);
  process.exit(1);
});
