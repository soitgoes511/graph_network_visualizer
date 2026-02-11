FROM node:22-alpine

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm install

COPY . .

# Expose port
EXPOSE 5173

# Start app
CMD ["npm", "run", "dev", "--", "--host"]
