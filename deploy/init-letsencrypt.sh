#!/bin/sh
# FinancialOS — Let's Encrypt ilk-sertifika bootstrap (MA2, Wave-8). Blok B'de canlı sunucuda BİR KEZ koşulur.
# Chicken-egg: nginx TLS cert olmadan başlamaz, certbot cert için nginx'e ihtiyaç duyar → önce dummy cert.
#
# Kullanım (canlı sunucu): DOMAIN + EMAIL export et → ./deploy/init-letsencrypt.sh
set -e

: "${DOMAIN:?DOMAIN gerekli (ör. financialos.example.com veya IP değil-gerçek-domain)}"
: "${EMAIL:?EMAIL gerekli (Let's Encrypt bildirim + kurtarma)}"
COMPOSE="docker compose -f docker-compose.prod.yml"
CERT_PATH="/etc/letsencrypt/live/${DOMAIN}"

echo "[le] 1) Dummy sertifika (nginx'in başlaması için)…"
$COMPOSE run --rm --entrypoint "sh -c '\
  mkdir -p ${CERT_PATH} && \
  openssl req -x509 -nodes -newkey rsa:2048 -days 1 \
    -keyout ${CERT_PATH}/privkey.pem -out ${CERT_PATH}/fullchain.pem \
    -subj \"/CN=${DOMAIN}\"'" certbot

echo "[le] 2) nginx başlat (dummy cert ile :443 ayağa kalkar)…"
$COMPOSE up -d web

echo "[le] 3) Dummy'yi sil + GERÇEK Let's Encrypt sertifikası al (webroot doğrulama)…"
$COMPOSE run --rm --entrypoint "sh -c '\
  rm -rf ${CERT_PATH} && \
  certbot certonly --webroot -w /var/www/certbot \
    -d ${DOMAIN} --email ${EMAIL} --agree-tos --no-eff-email --non-interactive'" certbot

echo "[le] 4) nginx reload (gerçek sertifikayı yükle)…"
$COMPOSE exec web nginx -s reload

echo "[le] TAMAM — https://${DOMAIN} gerçek TLS ile canlı. certbot servisi 12 saatte bir yeniler."
