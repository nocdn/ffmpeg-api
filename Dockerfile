# syntax=docker/dockerfile:1

FROM oven/bun:1-alpine AS deps
WORKDIR /usr/src/app

COPY package.json bun.lock ./
RUN bun install --frozen-lockfile --production

FROM oven/bun:1-alpine AS release
WORKDIR /usr/src/app

# Install ffmpeg
RUN apk add --no-cache ffmpeg

ENV NODE_ENV=production

COPY --from=deps /usr/src/app/node_modules ./node_modules
COPY package.json bun.lock tsconfig.json ./
COPY src ./src

# Create upload directory and give bun user ownership
RUN mkdir -p /tmp/ffmpeg-api && chown bun:bun /tmp/ffmpeg-api

USER bun
EXPOSE 8040

CMD ["bun", "run", "src/index.ts"]
