# Use the official Node-RED base image
FROM nodered/node-red:latest
#FROM nodered/node-red:minimal

# Switch to root to handle system packages and directory creation
# (Required for node-red-node-serialport to build native C++ bindings)
USER root
#RUN apk add --no-cache python3 make g++

# Create the sqlite directory inside /data and set the correct ownership
RUN mkdir -p /data/sqlite && chown -R node-red:node-red /data/sqlite

# Switch back to the default node-red user (UID 1000)
USER node-red

# Set working directory to the data folder
WORKDIR /usr/src/node-red
	
# Install additional Node-RED nodes
RUN npm install --unsafe-perm --no-update-notifier --no-fund \
    node-red-node-sqlite \
	@flowfuse/node-red-dashboard \
	node-red-contrib-bcrypt \
	node-red-contrib-finite-statemachine \
	@flowfuse/node-red-dashboard-2-ui-led \
	node-red-node-serialport \
	node-red-node-ui-table \
	node-red-contrib-modbus \
	node-red-contrib-s7 \
    node-red-contrib-opcua \
	&& npm cache clean --force
	
# Alternative STM32-related nodes (optional, uncomment if needed)
#RUN npm install --unsafe-perm --no-update-notifier --no-fund \
#    @stm32/node-red-contrib-stm32cubemonitor

# Copy custom settings file (optional)
COPY settings.js /data/settings.js

# Copy custom flows (optional)
COPY flows.json /data/flows.json

# Expose Node-RED port
EXPOSE 1880

# Use the default entrypoint and command from the base image
# CMD ["npm", "start", "--", "--userDir", "/data"]
