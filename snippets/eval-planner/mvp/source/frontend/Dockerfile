# Build Stage
FROM node:18-alpine as build
WORKDIR /app
COPY package.json .
# Skip installing extensive dependencies for MVP speed in this demo, 
# but in real life we would run 'npm install'.
# Since we can't easily auto-run npm install without internet or time, 
# we will rely on the user running the proper build or assume node_modules exists? 
# NO, for a "Deployable" MVP, we must install.
RUN npm install

COPY . .
RUN npm run build

# Production Stage
FROM nginx:alpine
COPY --from=build /app/build /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
