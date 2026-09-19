FROM node:20-alpine

WORKDIR /app

COPY package.json ./
RUN npm install || npm install --legacy-peer-deps || true

COPY . .

ENV VITE_API_BASE_URL=http://localhost:8000

EXPOSE 5173

CMD ["npm", "run", "dev"]
