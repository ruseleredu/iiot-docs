FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY camara_model.py camara_sim.py proto_*.py testar_clientes.py ./

ENV PYTHONUNBUFFERED=1
# Modbus TCP, Modbus RTU sobre TCP, S7, OPC-UA
EXPOSE 502 5021 102 4840

# Configuração por variáveis de ambiente (ver docker-compose.yml / .env)
CMD ["python", "camara_sim.py"]
