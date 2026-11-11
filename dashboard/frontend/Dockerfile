# Install dependencies
FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

# Build the app
FROM node:22-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# Set build-time arguments. NEXT_PUBLIC_* values are inlined into the bundle
# during the build, and env files are kept out of the build (.dockerignore), so
# they must be passed here as build args.
ARG FLASK_API_URL
ARG NEXT_PUBLIC_FLASK_API_URL
ARG NEXT_PUBLIC_GOOGLE_MAPS_API_KEY
# WordPress site the header links to (read in src/components/Header.tsx)
ARG NEXT_PUBLIC_WP_HOME=https://well.mcmaster.ca
# Sentry project the dashboard reports errors to (src/lib/sentry.ts). A browser DSN is public by design (it
# can only send events); build with --build-arg NEXT_PUBLIC_SENTRY_DSN= to turn reporting off.
ARG NEXT_PUBLIC_SENTRY_DSN=https://dee04106f585f2535a092c4693fddb4a@o4512410353991680.ingest.us.sentry.io/4512410368409600

# Set environment variables for the build process
ENV FLASK_API_URL=${FLASK_API_URL}
ENV NEXT_PUBLIC_FLASK_API_URL=${NEXT_PUBLIC_FLASK_API_URL}
ENV NEXT_PUBLIC_GOOGLE_MAPS_API_KEY=${NEXT_PUBLIC_GOOGLE_MAPS_API_KEY}
ENV NEXT_PUBLIC_WP_HOME=${NEXT_PUBLIC_WP_HOME}
ENV NEXT_PUBLIC_SENTRY_DSN=${NEXT_PUBLIC_SENTRY_DSN}

RUN npm run build

# Production image
FROM node:22-alpine AS runner
WORKDIR /app

ENV NODE_ENV=production

# Add a non-root user and group
RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs

COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs

# Switch application port to 8081
EXPOSE 8081
ENV PORT=8081

CMD ["node", "server.js"]