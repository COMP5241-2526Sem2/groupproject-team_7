#!/bin/sh
# Fix proxy configuration for Docker environment
sed -i 's|"proxy": "http://localhost:5000"|"proxy": "http://app:5000"|g' /app/package.json
npm start
