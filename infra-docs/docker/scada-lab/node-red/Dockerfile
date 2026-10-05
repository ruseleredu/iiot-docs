FROM nodered/node-red:latest

USER root
WORKDIR /opt/scada-node-red
COPY build/package.json ./
RUN npm install --omit=dev --no-audit --no-fund
COPY build/flows.json ./flows.json
COPY entrypoint.sh /entrypoint-scada.sh
RUN chmod +x /entrypoint-scada.sh && chown -R node-red:node-red /opt/scada-node-red /entrypoint-scada.sh
USER node-red
ENTRYPOINT ["/entrypoint-scada.sh"]
CMD ["npm", "start", "--", "--userDir", "/data"]
