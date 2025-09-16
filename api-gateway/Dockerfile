FROM node:18
WORKDIR /app
COPY package.json .
RUN npm install --only=prod
COPY src/ .
EXPOSE 8000
CMD ["node", "index.js"]
