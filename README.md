# 📺 IPTV Stream Checker - By MultiHub

Verifica automaticamente o estado dos seus canais IPTV e salva os resultados no `results.json`, exibindo tudo em uma interface web moderna. O sistema é executado a cada 6 horas usando o GitHub Actions (totalmente grátis).

## ✨ Funcionalidades

- ✅ Detecta canais **ativos**, **negados (403)**, **offline** e com **tempo esgotado (timeout)**
- 📥 **Download de M3U:** Botão flutuante na interface para baixar apenas os canais que estão ativos no momento.
- 🕐 Detecta **data de expiração** diretamente dos cabeçalhos HTTP (`Expires`, `X-Expires`)
- 🔔 **Notificações** via Discord ou Slack quando um canal cai
- 💾 Resultados salvos no `results.json` com histórico versionado no Git
- ⚡ Verificação em paralelo (até 15 workers simultâneos para maior velocidade)
- 🤖 Execução 100% automática a cada 6 horas com o GitHub Actions

---

## 🚀 Configuração Rápida

### 1. Criar o repositório no GitHub

```bash
git init iptv-checker
cd iptv-checker
# Copie todos os arquivos para esta pasta (incluindo o script e o index.html atualizados)
git add .
git commit -m "commit inicial"
gh repo create iptv-checker --public --push
