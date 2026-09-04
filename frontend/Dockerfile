FROM node:24-alpine AS deps

WORKDIR /app

COPY package.json package-lock.json ./

RUN npm ci


FROM node:24-alpine AS builder

WORKDIR /app

ARG NEXT_PUBLIC_GOOGLE_CLIENT_ID=""

ENV NEXT_TELEMETRY_DISABLED=1
ENV BACKEND_API_URL=http://backend:8000/api/v1
ENV NEXT_PUBLIC_GOOGLE_CLIENT_ID=$NEXT_PUBLIC_GOOGLE_CLIENT_ID

COPY --from=deps /app/node_modules ./node_modules
COPY . .

RUN mkdir -p public
RUN npm run build


FROM node:24-alpine AS runner

WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ENV HOSTNAME=0.0.0.0
ENV PORT=3000
ENV BACKEND_API_URL=http://backend:8000/api/v1

RUN addgroup --system --gid 1001 nodejs \
    && adduser --system --uid 1001 nextjs

COPY --from=builder --chown=nextjs:nodejs /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs

EXPOSE 3000

CMD ["node", "server.js"]
