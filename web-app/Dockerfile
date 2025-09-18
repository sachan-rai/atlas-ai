FROM node:20-alpine
WORKDIR /app

# copy everything first so layer cache busts when package.json changes
COPY . .

# clean install + rebuild esbuild binary for alpine
RUN npm install && npm rebuild esbuild

EXPOSE 3000
CMD ["npm", "run", "dev"]
