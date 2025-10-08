# Install dependencies
FROM node:18-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm install

# Build the app
FROM node:18-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# Set build-time arguments
ARG FLASK_API_URL
ARG NEXT_PUBLIC_FLASK_API_URL
ARG NEXT_PUBLIC_GOOGLE_MAPS_API_KEY
ARG OPENAI_API_KEY

# Set environment variables for the build process
ENV FLASK_API_URL=${FLASK_API_URL}
ENV NEXT_PUBLIC_FLASK_API_URL=${NEXT_PUBLIC_FLASK_API_URL}
ENV NEXT_PUBLIC_GOOGLE_MAPS_API_KEY=${NEXT_PUBLIC_GOOGLE_MAPS_API_KEY}

RUN npm run build

# Production image
FROM node:18-alpine AS runner
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