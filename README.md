<div align="center">

# B3 Portfolio Dashboard

**Interactive self-hosted dashboard for tracking a B3 stock portfolio.**

![Status](https://img.shields.io/badge/Status-Active-16A34A?style=flat-square)
![License](https://img.shields.io/badge/License-MIT-2563EB?style=flat-square)
![Casco Digital](https://img.shields.io/badge/Casco-Digital-111827?style=flat-square)
![Python](https://img.shields.io/badge/Python-3.9+-3776AB?style=flat-square&logo=python&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?style=flat-square&logo=docker&logoColor=white)
![Plotly](https://img.shields.io/badge/Plotly-Dash-3F4F75?style=flat-square&logo=plotly&logoColor=white)

</div>

---

Dashboard interativo para acompanhar carteira de acoes da B3 em treemaps dinamicos. Projeto pessoal, self-hosted, 100% gratuito.

![Dashboard](exemplo.jpg)

## Funcionalidades

- **Treemap com 3 visualizacoes:** variacao do dia, 7 dias e ganho/perda total
- **Rotacao automatica** entre telas com tempos configuraveis
- **Graficos historicos** de 30 dias ao clicar em qualquer acao
- **Alertas** para mudancas bruscas, oportunidades e realizacao de lucro
- **Gerenciamento** de acoes via interface web
- **Atualizacao** automatica a cada 5 minutos via Yahoo Finance

## Quick Start

```bash
git clone https://github.com/cascodigital/b3-portfolio-dashboard.git
cd b3-portfolio-dashboard
docker compose up -d
# Acesse http://localhost:8050
```

## Configuracao

Adicione acoes pela interface (botao de configuracoes) ou edite `acoes.csv`:

```csv
ticker,shares,avg_price
PETR4.SA,100,25.50
VALE3.SA,200,70.30
```

Tickers da B3 usam sufixo `.SA` (preenchido automaticamente pela GUI).

## Stack

- [Plotly Dash](https://dash.plotly.com/) + [Dash Bootstrap](https://dash-bootstrap-components.opensource.faculty.ai/)
- [yfinance](https://github.com/ranaroussi/yfinance) (dados com ~15min de atraso)
- Docker com volume persistente e restart automatico

## Avisos

Projeto pessoal para uso privado. Sem autenticacao ou protecao para exposicao publica. Use com tunnel (Cloudflare, Tailscale) ou em rede local.

---

Desenvolvido com 🐢 (e cafe) por **Casco Digital**.
