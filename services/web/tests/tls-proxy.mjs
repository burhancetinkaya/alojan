// Test-only HTTPS ingress for real Secure/HttpOnly browser-cookie validation.
import https from "node:https";
import http from "node:http";
import { readFileSync } from "node:fs";
https
  .createServer(
    {
      key: readFileSync("/evidence/key.pem"),
      cert: readFileSync("/evidence/cert.pem"),
    },
    (request, response) => {
      const upstream = http.request(
        {
          hostname: "127.0.0.1",
          port: 13001,
          path: request.url,
          method: request.method,
          headers: request.headers,
        },
        (incoming) => {
          response.writeHead(incoming.statusCode, incoming.headers);
          incoming.pipe(response);
        },
      );
      upstream.on("error", () => {
        response.writeHead(502);
        response.end();
      });
      request.pipe(upstream);
    },
  )
  .listen(18443, "127.0.0.1");
