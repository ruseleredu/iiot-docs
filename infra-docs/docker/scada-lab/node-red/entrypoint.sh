#!/bin/sh
set -eu

if [ ! -f /data/package.json ]; then
  cp /opt/scada-node-red/package.json /data/package.json
fi
if [ ! -d /data/node_modules ]; then
  cp -a /opt/scada-node-red/node_modules /data/node_modules
fi
if [ ! -f /data/flows.json ]; then
  cp /opt/scada-node-red/flows.json /data/flows.json
fi
exec "$@"
