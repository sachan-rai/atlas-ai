FROM node:20-alpine
WORKDIR /app

# copy only package.json
COPY package.json ./
# install prod deps (no lockfile needed)
RUN npm install --omit=dev

# now copy source
COPY src/ ./src/

EXPOSE 8000
CMD ["node", "src/index.js"]
