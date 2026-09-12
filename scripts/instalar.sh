#!/usr/bin/env bash
# Instala as skills do KIT de Sobrevivência Hospitalar MV para o Claude Code e/ou Codex.
#
#   bash scripts/instalar.sh
#   bash scripts/instalar.sh --agente claude
#   bash scripts/instalar.sh --link      # link simbólico: 'git pull' já atualiza
#   bash scripts/instalar.sh --force     # sobrescreve sem perguntar
set -euo pipefail

AGENTE="ambos"
LINK=0
FORCE=0

while [ $# -gt 0 ]; do
  case "$1" in
    --agente) AGENTE="${2:-ambos}"; shift 2 ;;
    --link)   LINK=1; shift ;;
    --force)  FORCE=1; shift ;;
    -h|--help) sed -n '2,9p' "$0"; exit 0 ;;
    *) echo "opção desconhecida: $1" >&2; exit 1 ;;
  esac
done

case "$AGENTE" in
  claude|codex|ambos) ;;
  *) echo "--agente aceita: claude, codex ou ambos" >&2; exit 1 ;;
esac

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ORIGEM="$RAIZ/skills"
[ -d "$ORIGEM" ] || { echo "pasta 'skills' não encontrada em $RAIZ" >&2; exit 1; }

DESTINOS=()
[ "$AGENTE" = "claude" ] || [ "$AGENTE" = "ambos" ] && DESTINOS+=("$HOME/.claude/skills")
[ "$AGENTE" = "codex" ]  || [ "$AGENTE" = "ambos" ] && DESTINOS+=("$HOME/.codex/skills")

TOTAL=$(find "$ORIGEM" -mindepth 1 -maxdepth 1 -type d | wc -l | tr -d ' ')
echo "KIT de Sobrevivência Hospitalar MV"
echo "$TOTAL skills - modo: $([ "$LINK" -eq 1 ] && echo 'link simbólico' || echo 'cópia')"
echo

for destino in "${DESTINOS[@]}"; do
  mkdir -p "$destino"
  echo "-> $destino"
  for skill in "$ORIGEM"/*/; do
    nome="$(basename "$skill")"
    alvo="$destino/$nome"

    if [ -e "$alvo" ] || [ -L "$alvo" ]; then
      if [ "$FORCE" -eq 0 ]; then
        # Preserva ajustes locais: sem --force, nada é sobrescrito em silêncio.
        read -r -p "   '$nome' já existe. Sobrescrever? (s/N) " resposta </dev/tty || resposta=""
        case "$resposta" in
          s|S) ;;
          *) echo "   [pulado ] $nome"; continue ;;
        esac
      fi
      rm -rf "$alvo"
    fi

    if [ "$LINK" -eq 1 ]; then
      ln -s "${skill%/}" "$alvo"
      echo "   [linkado] $nome"
    else
      cp -r "${skill%/}" "$alvo"
      find "$alvo" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
      echo "   [copiado] $nome"
    fi
  done
  echo
done

echo "Pronto. Abra o Claude Code ou o Codex e descreva o problema em português."
echo "As skills ativam sozinhas pela descrição; para forçar: /mv-sobrevivencia"
[ "$LINK" -eq 1 ] && echo && echo "Como instalou com link, um 'git pull' neste repositório já atualiza as skills."
exit 0
