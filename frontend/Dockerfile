FROM node:20-alpine

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

EXPOSE 5173

# Dev server, not a production nginx build - this project is still under
# active iteration (see the many `npm run dev` smoke tests throughout
# development), so the container mirrors the same workflow contributors
# already use locally rather than adding a separate production build path.
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
