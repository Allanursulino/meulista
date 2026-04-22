#!/usr/bin/env python3
"""
IPTV Stream Checker - By MultiHub
Verifica estado e expiração de canais em playlists M3U, remove duplicados e organiza em categorias.
"""

import re
import json
import time
import datetime
import urllib.request
import urllib.error
import urllib.parse
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

# ─── Configuração ────────────────────────────────────────────────────────────
PLAYLIST_URLS = os.environ.get("PLAYLIST_URLS", "").split(",")
TIMEOUT = int(os.environ.get("CHECK_TIMEOUT", "10"))
MAX_WORKERS = int(os.environ.get("MAX_WORKERS", "15"))
OUTPUT_FILE = "results.json"
NOTIFY_WEBHOOK = os.environ.get("NOTIFY_WEBHOOK", "")  # Discord/Slack webhook
# ──────────────────────────────────────────────────────────────────────────────

def categorize_channel(name: str, original_group: str) -> str:
    """Categoriza o canal baseado em palavras-chave no nome ou no grupo original."""
    text = f"{name} {original_group}".upper()
    
    if any(kw in text for kw in ["SÉRIE", "SERIE", "EPISÓDIO", "TEMPORADA"]):
        return "Séries"
    elif any(kw in text for kw in ["FILME", "VOD", "CINEMA", "4K", "LANCAMENTO", "LANÇAMENTO", "TELECINE", "HBO", "MAX", "PRIME"]):
        return "Filmes"
    elif any(kw in text for kw in ["ESPORTE", "SPORT", "ESPN", "PREMIERE", "COMBATE", "FUTEBOL", "DAZN", "F1", "UFC", "GOL", "BANDSPORTS", "ARENA"]):
        return "Esportes"
    elif any(kw in text for kw in ["INFANTIL", "KIDS", "DISNEY", "CARTOON", "NICKELODEON", "GLOOB", "BOOMERANG"]):
        return "Infantil e Desenhos"
    elif any(kw in text for kw in ["NOTÍCIA", "NOTICIA", "NEWS", "JORNAL", "CNN", "BANDNEWS"]):
        return "Notícias"
    elif any(kw in text for kw in ["DOCUMENTÁRIO", "DOCUMENTARIO", "DISCOVERY", "HISTORY", "NAT GEO", "ANIMAL"]):
        return "Documentários"
    elif any(kw in text for kw in ["GLOBO", "SBT", "RECORD", "BAND", "REDE", "CULTURA", "GAZETA", "ABERTO"]):
        return "Canais Abertos"
    
    # Se não encontrar palavra-chave, usa o grupo original ou define como "Outros"
    if not original_group or original_group.strip() == "":
        return "Outros"
    return original_group.strip()

def fetch_playlist(url: str) -> str | None:
    """Baixa o conteúdo de uma playlist M3U."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "IPTV-Checker/1.0"})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return resp.read().decode("utf-8", errors="ignore")
    except Exception as e:
        print(f"[ERRO] Não foi possível baixar a playlist {url}: {e}")
        return None

def parse_m3u(content: str, source_url: str = "") -> list[dict]:
    """Lê uma playlist M3U e extrai os canais."""
    channels = []
    lines = content.strip().splitlines()
    current_info = {}

    try:
        parsed = urllib.parse.urlparse(source_url)
        source_label = parsed.netloc or source_url
    except Exception:
        source_label = source_url

    for line in lines:
        line = line.strip()
        if line.startswith("#EXTINF"):
            name_match = re.search(r',(.+)$', line)
            tvg_id = re.search(r'tvg-id="([^"]*)"', line)
            group_match = re.search(r'group-title="([^"]*)"', line)
            logo = re.search(r'tvg-logo="([^"]*)"', line)
            
            raw_name = name_match.group(1).strip() if name_match else "Desconhecido"
            raw_group = group_match.group(1).strip() if group_match else ""
            
            # Aplica a categoria inteligente
            clean_group = categorize_channel(raw_name, raw_group)
            
            current_info = {
                "name": raw_name,
                "tvg_id": tvg_id.group(1) if tvg_id else "",
                "group": clean_group,
                "logo": logo.group(1) if logo else "",
                "source": source_label,
            }
        elif line and not line.startswith("#") and current_info:
            current_info["url"] = line
            channels.append(current_info.copy())
            current_info = {}

    return channels

def check_stream(channel: dict) -> dict:
    """Verifica o estado de um stream individual."""
    url = channel.get("url", "")
    result = {
        "name": channel.get("name", "Desconhecido"),
        "url": url,
        "group": channel.get("group", ""),
        "tvg_id": channel.get("tvg_id", ""),
        "logo": channel.get("logo", ""),
        "source": channel.get("source", ""),
        "status": "unknown",
        "http_code": None,
        "response_time_ms": None,
        "expires_at": None,
        "checked_at": datetime.datetime.utcnow().isoformat() + "Z",
        "error": None,
    }

    if not url:
        result["status"] = "error"
        result["error"] = "URL vazia"
        return result

    try:
        start = time.time()
        req = urllib.request.Request(
            url,
            method="HEAD",
            headers={"User-Agent": "IPTV-Checker/1.0"},
        )
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            elapsed = int((time.time() - start) * 1000)
            result["http_code"] = resp.status
            result["response_time_ms"] = elapsed

            headers = dict(resp.headers)
            expires = (
                headers.get("Expires")
                or headers.get("expires")
                or headers.get("X-Expires")
                or headers.get("x-expires")
            )
            if expires:
                result["expires_at"] = expires

            if resp.status == 200:
                result["status"] = "active"
            elif resp.status == 403:
                result["status"] = "denied"
                result["error"] = "HTTP 403 - Acesso Negado"
            elif resp.status == 404:
                result["status"] = "not_found"
                result["error"] = "HTTP 404 - Não Encontrado"
            else:
                result["status"] = "error"
                result["error"] = f"HTTP {resp.status}"

    except urllib.error.HTTPError as e:
        result["http_code"] = e.code
        result["status"] = "denied" if e.code == 403 else "error"
        result["error"] = f"HTTP {e.code}"
    except urllib.error.URLError as e:
        result["status"] = "offline"
        result["error"] = str(e.reason)
    except TimeoutError:
        result["status"] = "timeout"
        result["error"] = f"Tempo esgotado após {TIMEOUT}s"
    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)

    return result

def main():
    if not any(PLAYLIST_URLS):
        print("[ERRO] Defina PLAYLIST_URLS como variável de ambiente.")
        sys.exit(1)

    all_channels = []
    for url in PLAYLIST_URLS:
        url = url.strip()
        if not url:
            continue
        print(f"📥 Baixando playlist: {url}")
        content = fetch_playlist(url)
        if content:
            channels = parse_m3u(content, url)
            all_channels.extend(channels)

    if not all_channels:
        print("[ERRO] Nenhum canal foi encontrado nas playlists.")
        sys.exit(1)

    # ─── Filtro Anti-Duplicação por URL ───────────────────────────────────────
    unique_urls = set()
    unique_channels = []
    for ch in all_channels:
        stream_url = ch.get("url", "")
        if stream_url and stream_url not in unique_urls:
            unique_urls.add(stream_url)
            unique_channels.append(ch)
            
    print(f"   → {len(all_channels)} canais totais encontrados.")
    print(f"   → {len(unique_channels)} canais únicos após remover duplicados.")
    
    all_channels = unique_channels
    # ──────────────────────────────────────────────────────────────────────────

    print(f"\n🔍 Verificando {len(all_channels)} canais com {MAX_WORKERS} workers...\n")
    results = []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(check_stream, ch): ch for ch in all_channels}
        for i, future in enumerate(as_completed(futures), 1):
            res = future.result()
            icon = {"active": "✅", "denied": "🔐", "offline": "❌", "timeout": "⏱️"}.get(
                res["status"], "⚠️"
            )
            print(f"[{i:>4}/{len(all_channels)}] {icon} {res['name'][:40]:<40} {res['status']}")
            results.append(res)

    results.sort(key=lambda x: x["name"].lower())

    stats = {
        "total": len(results),
        "active": sum(1 for r in results if r["status"] == "active"),
        "denied": sum(1 for r in results if r["status"] == "denied"),
        "offline": sum(1 for r in results if r["status"] == "offline"),
        "timeout": sum(1 for r in results if r["status"] == "timeout"),
        "error": sum(1 for r in results if r["status"] == "error"),
        "last_check": datetime.datetime.utcnow().isoformat() + "Z",
    }

    output = {"stats": stats, "channels": results}

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n📊 Resultados Finais:")
    print(f"   ✅ Ativos   : {stats['active']}")
    print(f"   🔐 Negados  : {stats['denied']}")
    print(f"   ❌ Offline  : {stats['offline']}")
    print(f"   ⏱️  Esgotado : {stats['timeout']}")
    print(f"\n💾 Salvo em {OUTPUT_FILE}")

    if stats["active"] == 0:
        sys.exit(1)

if __name__ == "__main__":
    main()
