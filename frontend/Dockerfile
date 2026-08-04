# Stage 1: Install dependencies
FROM --platform=linux/amd64 node:20-slim AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

# Stage 2: Build the app
FROM --platform=linux/amd64 node:20-slim AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ENV BACKEND_URL=http://backend:8000
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

# Stage 3: Runner stage
FROM --platform=linux/amd64 node:20-slim AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
COPY --from=builder /app/package.json ./
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/public ./public

EXPOSE 3000
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

CMD ["npm", "start"]
