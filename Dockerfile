# Shared image for the Node services. Python and Java join the worker on Day 5.
FROM node:22-bookworm-slim
RUN npm install -g pnpm@12.23.0
WORKDIR /repo
COPY package.json pnpm-workspace.yaml pnpm-lock.yaml ./
COPY apps/web/package.json apps/web/
COPY apps/api/package.json apps/api/
COPY apps/worker/package.json apps/worker/
COPY packages/shared/package.json packages/shared/
COPY services/mock-sources/package.json services/mock-sources/
RUN pnpm install --frozen-lockfile
COPY . .
ARG APP_DIR
WORKDIR /repo/${APP_DIR}
CMD ["npm", "run", "start"]
