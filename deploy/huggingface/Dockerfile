# DoomForge Lab on Hugging Face Spaces: the chain (Ganache), the collector and the Streamlit app in one container.
FROM node:22-slim AS node

FROM python:3.14-slim

# Node.js (for Ganache, the local Ethereum chain) copied from the official Node image.
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && npm install -g ganache@7.9.2 \
    && npm cache clean --force

# Hugging Face runs the container as user 1000.
RUN useradd -m -u 1000 user
WORKDIR /home/user/app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=user:user . .
RUN sed -i 's/\r$//' start.sh && chmod +x start.sh

USER user
ENV HOME=/home/user PYTHONUNBUFFERED=1 TZ=Asia/Colombo
EXPOSE 8501
CMD ["./start.sh"]
