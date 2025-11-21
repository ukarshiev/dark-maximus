import { NextFunction, Request, Response } from 'express';
import jwt from 'jsonwebtoken';
import appConfig from '../../utils/appConfig.js';


/**
 * Middleware for checking jwt token
 *
 * @param req - request object
 * @param res - response object
 * @param next - next function
 */
export default async function verifyToken(req: Request, res: Response, next: NextFunction): Promise<void> {
  const token = req.cookies.authToken;
  const clientIp = req.ip || req.connection.remoteAddress || 'unknown';
  const path = req.path;
  const method = req.method;

  try {
    if (!appConfig.auth.password) {
      res.locals.isAuthorized = false;
      next();

      return;
    }

    if (!token) {
      if (method !== 'GET' || path !== '/auth') {
        console.warn(
          `[AUTH] [codex-docs] Unauthorized access attempt: ` +
          `path=${path}, method=${method}, ip=${clientIp}, reason=no_token`
        );
      }
      res.locals.isAuthorized = false;
      next();
      return;
    }

    const decodedToken = jwt.verify(token, appConfig.auth.password + appConfig.auth.secret) as { iat?: number };

    res.locals.isAuthorized = !!decodedToken;

    // Логируем только для важных операций
    if (method !== 'GET' || path.startsWith('/api/')) {
      const tokenAge = decodedToken.iat ? Math.floor((Date.now() - decodedToken.iat * 1000) / 1000) : 'unknown';
      console.info(
        `[AUTH] [codex-docs] Token validated: ` +
        `path=${path}, method=${method}, ip=${clientIp}, token_age=${tokenAge}s`
      );
    }

    next();
  } catch (err) {
    console.warn(
      `[AUTH] [codex-docs] Token validation failed: ` +
      `path=${path}, method=${method}, ip=${clientIp}, error=${err instanceof Error ? err.message : String(err)}`
    );
    res.locals.isAuthorized = false;
    next();
  }
}
